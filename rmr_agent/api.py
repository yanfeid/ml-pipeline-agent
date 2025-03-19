from fastapi import FastAPI, HTTPException, Query, BackgroundTasks
from pydantic import BaseModel
from typing import Dict, Any, List, Optional
from workflow import *
from utils import (
    get_next_run_id, load_step_output, save_step_output
    )
import asyncio


app = FastAPI()

CHECKPOINT_BASE_PATH = "rmr_agent/checkpoints"

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
    verified_dag: Dict[str, Any]


# Define steps requiring human input
HUMAN_STEPS = {"human_verification_of_components", "human_verification_of_dag"}

# Define all steps (without human verification functions, as they'll be API-driven)
STEPS = [
    ("clone_and_prepare_repo", clone_and_prepare_repo),
    ("summarize", summarize),
    ("component_identification", run_component_identification),
    ("component_parsing", run_component_parsing),
    ("human_verification_of_components", None),  # Placeholder
    ("attribute_identification", run_attribute_identification),
    ("attribute_parsing", run_attribute_parsing),
    ("node_aggregator", run_node_aggregator),
    ("edge_identification", run_edge_identification),
    ("generate_dag_yaml", generate_dag_yaml),
    ("human_verification_of_dag", None),  # Placeholder
    ("config_agent", run_config_agent),
    ("notebook_agent", run_notebook_agent)
]


def save_human_feedback(request: ComponentsResponse | DagResponse, repo_name: str, run_id: str, background_tasks: BackgroundTasks = None):
    # Save the human verification response
    if not run_id:
        raise HTTPException(400, "run_id required for continuing")
    
    # Check which human verification result this is
    if isinstance(request, ComponentsResponse):
        step_name = "human_verification_of_components"
        update_name = "verified_components"
    elif isinstance(request, DagResponse):
        step_name = "human_verification_of_dag"
        update_name = "verified_dag"
    else:
        raise HTTPException(400, "Invalid request type for saving human feedback")

    start_idx = STEPS.index((step_name, None))
    update = {update_name: request.verified_components}
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
def run_workflow_endpoint(
    request: WorkflowRequest | ComponentsResponse | DagResponse,
    repo_name: str = Query(..., description="Repository name (required)"),
    run_id: Optional[str] = Query(None, description="Run ID for continuing workflow"),
    background_tasks: BackgroundTasks = None
):

    if isinstance(request, WorkflowRequest):
        # Start or continue workflow
        run_id = request.run_id or get_next_run_id(checkpoint_base_path=CHECKPOINT_BASE_PATH, repo_name=repo_name)
        start_idx = 0 if not request.start_from else next(i for i, (s, _) in enumerate(STEPS) if s == request.start_from)
        step_name = STEPS[start_idx][0]
        status = "initializing"

        # Initialize the workflow state
        if repo_name not in workflow_states:
            workflow_states[repo_name] = {}

        workflow_states[repo_name][run_id] = {
            # status related
            "step": step_name,
            "status": status,
            "error": None,
            
            # workflow related
            "github_url": request.github_url,
            "input_files": request.input_files,
            "repo_name": repo_name,
            "run_id": run_id,
            "local_repo_path": "",
            "existing_config_path": "",
            "files": [],
            "summaries": {},
            "cleaned_code": {},
            "component_identification": [],
            "component_parsing": [],
            "verified_components": [],
            "attribute_identification": [],
            "attribute_parsing": [],
            "node_aggregator": [],
            "edges": [],
            "dag_yaml": "",
            "verified_dag": {},
            "config": {},
            "notebooks": [],
            "pr_url": ""
        }
        
        # Add workflow task to run in background, return immediately so we can poll the results in UI
        background_tasks.add_task(run_workflow_background, request, repo_name, run_id, start_idx)
        return {"repo_name": repo_name, "run_id": run_id, "step": step_name, "status": status}
    elif isinstance(request, ComponentsResponse):
        # Save the verified components and move on to next step
        workflow_states[repo_name]["step"] = "human_verification_of_components"
        workflow_states[repo_name]["status"] = "saving_feedback"
        result = save_human_feedback(request=request, repo_name=repo_name, run_id=run_id, background_tasks=background_tasks)
        return result
    elif isinstance(request, DagResponse):
        # Save the verified DAG and move on to next step
        workflow_states[repo_name]["step"] = "human_verification_of_dag"
        workflow_states[repo_name]["status"] = "saving_feedback"
        result = save_human_feedback(request=request, repo_name=repo_name, run_id=run_id, background_tasks=background_tasks)
        return result
    else:
        raise HTTPException(400, "Invalid request type")


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000, log_level="debug")
