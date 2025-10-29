import os
from fastapi import Request, Query, BackgroundTasks, HTTPException, FastAPI
from pydantic import BaseModel
from typing import Dict, Any, List, Optional
from rmr_agent.workflow import *
from rmr_agent.utils import (
    get_next_run_id, load_step_output, save_step_output
    )

app = FastAPI()

CHECKPOINT_BASE_PATH = os.environ.get("CHECKPOINT_BASE_PATH", "rmr_agent/checkpoints")

# In-memory storage for workflow states
# In a production environment, we'll want to use Redis or a database instead
if 'workflow_states' not in globals():
    workflow_states: Dict[str, Dict[str, Any]] = {}

# Request models
class WorkflowRequest(BaseModel):
    github_url: str
    input_files: List[str]
    run_id: Optional[str] = None
    start_from: Optional[str] = None
    existing_config_path: Optional[str] = None

class ComponentsResponse(BaseModel):
    verified_components: List[Dict[str, Dict[str, Any]]]

class DagResponse(BaseModel):
    verified_dag: str 

def save_human_feedback(request: ComponentsResponse | DagResponse, repo_name: str, run_id: str, background_tasks: BackgroundTasks = None):
    # Save the human verification response
    if not run_id:
        raise HTTPException(400, "run_id required for continuing")
    
    # Check which human verification result this is
    if isinstance(request, ComponentsResponse):
        step_name = "human_verification_of_components"
        update_name = "verified_components"
        update = {update_name: request.verified_components}
    elif isinstance(request, DagResponse):
        step_name = "human_verification_of_dag"
        update_name = "verified_dag"
        update = {update_name: request.verified_dag}
    else:
        raise HTTPException(400, "Invalid request type for saving human feedback")

    start_idx = STEPS.index((step_name, None))
    # add update to our global state
    workflow_states[repo_name][run_id].update(update)
    # Save to checkpoints folder
    save_step_output(checkpoint_base_path=CHECKPOINT_BASE_PATH, repo_name=repo_name, run_id=run_id, step=step_name, output=update)
    start_idx += 1 # that is it for this step, just saving. Increment to move on to next step
    step_name = STEPS[start_idx][0]
    background_tasks.add_task(run_workflow_background, WorkflowRequest(github_url="", input_files=[]), repo_name, run_id, start_idx)
    return {"repo_name": repo_name, "run_id": run_id, "step": step_name, "status": "running"}


def run_workflow_background(request: WorkflowRequest, repo_name: str, run_id: str, start_idx: int):
    # Get the global state
    state = workflow_states[repo_name][run_id]
    state["step"] = STEPS[start_idx][0]
    try:
        # Update state to show we're starting
        state["status"] = "running"
        
        # Load from checkpoints folder all previous steps output
        for step_name, _ in STEPS[:start_idx]:
            if state.get("status") == "cancelled":
                print("Cancelling workflow while loading checkpoints")
                return
            state.update(load_step_output(checkpoint_base_path=CHECKPOINT_BASE_PATH, repo_name=repo_name, run_id=run_id, step=step_name))
        
        # Continue running the workflow starting from the provided start index
        for step_name, step_func in STEPS[start_idx:]:
            if state.get("status") == "cancelled":
                print("Cancelling workflow at step", step_name)
                return
            state["step"] = step_name
            print("Running step", step_name)
            if step_name in HUMAN_STEPS:
                break
            step_output = step_func(state)
            # Update global state
            state.update(step_output)
            # Save to checkpoints folder
            save_step_output(checkpoint_base_path=CHECKPOINT_BASE_PATH, repo_name=repo_name, run_id=run_id, step=step_name, output=step_output)
            # await asyncio.sleep(1)
        else:
            # Loop completed without break - mark that we have successfully completed the entire workflow
            if state.get("status") != "cancelled":
                state["step"] = "complete"

    except Exception as e:
        # Handle any errors
        state["status"] = "failed"
        state["error"] = str(e)

@app.get("/")
def read_root():
    return {"Hello": "World"}

@app.get("/workflow-status/{repo_name}")
def get_workflow_status(
    repo_name: str,
    run_id: str = Query(..., description="Run ID for continuing workflow")
):
    # Check if the workflow exists
    if repo_name not in workflow_states:
        raise HTTPException(status_code=404, detail=f"Workflow with repo_name {repo_name} not found")
    
    # Check if the run_id exists for this repository
    if run_id not in workflow_states[repo_name]:
        raise HTTPException(status_code=404, detail=f"Run ID {run_id} not found in repository {repo_name}")
    
    # Return the current state for this specific run
    print("returning status update with current step being: ", workflow_states[repo_name][run_id]["step"])
    return workflow_states[repo_name][run_id]

@app.post("/cancel-workflow/{repo_name}")
def cancel_workflow(
    repo_name: str,
    run_id: str = Query(..., description="Run ID for continuing workflow")
):
    """Cancel a running workflow"""
    if repo_name not in workflow_states:
        raise HTTPException(status_code=404, detail=f"Workflow not found for repo_name {repo_name} with run_id {run_id}")

    # Check if the run_id exists for this repository
    if run_id not in workflow_states[repo_name]:
        raise HTTPException(status_code=404, detail=f"Run ID {run_id} not found in repository {repo_name}")
    
    # Set cancellation flag in the state
    workflow_states[repo_name][run_id]["status"] = "cancelled"
    
    return {"status": "cancelled", "message": f"Workflow has been cancelled for run_id {run_id} for repo_name {repo_name}"}

# Main workflow endpoint
@app.post("/run-workflow")
async def run_workflow_endpoint(
    raw_request: Request,
    repo_name: str = Query(..., description="Repository name (required)"),
    run_id: Optional[str] = Query(None, description="Run ID for continuing workflow"),
    background_tasks: BackgroundTasks = None
):
    payload = await raw_request.json()
    print("📥 Received payload:", payload)

    # === DAG Feedback ===
    if "verified_dag" in payload:
        print("🧩 Detected: DagResponse")
        parsed = DagResponse(**payload)
        workflow_states[repo_name][run_id]["step"] = "human_verification_of_dag"
        workflow_states[repo_name][run_id]["status"] = "saving_feedback"
        return save_human_feedback(parsed, repo_name, run_id, background_tasks)

    # === Component Feedback ===
    elif "verified_components" in payload:
        print("🧩 Detected: ComponentsResponse")
        parsed = ComponentsResponse(**payload)
        workflow_states[repo_name][run_id]["step"] = "human_verification_of_components"
        workflow_states[repo_name][run_id]["status"] = "saving_feedback"
        return save_human_feedback(parsed, repo_name, run_id, background_tasks)

    # === Workflow Init / Start ===
    elif "github_url" in payload and "input_files" in payload:
        print("🚀 Detected: WorkflowRequest")
        parsed = WorkflowRequest(**payload)

        # Start or continue workflow
        run_id = parsed.run_id or get_next_run_id(checkpoint_base_path=CHECKPOINT_BASE_PATH, repo_name=repo_name)
        start_idx = 0 if not parsed.start_from else next(i for i, (s, _) in enumerate(STEPS) if s == parsed.start_from)
        step_name = STEPS[start_idx][0]
        status = "initializing"

        # Initialize the workflow state
        if repo_name not in workflow_states:
            workflow_states[repo_name] = {}
        workflow_states[repo_name][run_id] = INITIAL_STATE.copy()
        state = workflow_states[repo_name][run_id]
        state["step"] = step_name
        state["status"] = status
        state["github_url"] = parsed.github_url
        state["input_files"] = parsed.input_files
        state["repo_name"] = repo_name
        state["run_id"] = run_id
        if parsed.existing_config_path:
            state["existing_config_path"] = parsed.existing_config_path
            print(f"Setting config file path: {parsed.existing_config_path}")

        # Add background task to run
        background_tasks.add_task(run_workflow_background, parsed, repo_name, run_id, start_idx)
        return {"repo_name": repo_name, "run_id": run_id, "step": step_name, "status": status}

    else:
        raise HTTPException(400, "Invalid or unrecognized request type")

# Uvicorn entry point
if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000, log_level="debug")
