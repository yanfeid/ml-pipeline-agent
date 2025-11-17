"""
api.py - Add ML file detection endpoint to existing API
"""

import os
from fastapi import Request, Query, BackgroundTasks, HTTPException, FastAPI
from pydantic import BaseModel
from typing import Dict, Any, List, Optional
from rmr_agent.workflow import *
from rmr_agent.utils import (
    get_next_run_id, load_step_output, save_step_output,
    log_component_corrections, log_dag_corrections,
    fork_and_clone_repo, parse_github_url  # Add these imports
)
from rmr_agent.utils.logging_config import setup_logger

# Import file detection agent
from rmr_agent.agents.file_identification import LLMFileIdentificationAgent

# Set up module logger
logger = setup_logger(__name__)

app = FastAPI()

CHECKPOINT_BASE_PATH = os.environ.get("CHECKPOINT_BASE_PATH", "rmr_agent/checkpoints")

# In-memory storage for workflow states
if 'workflow_states' not in globals():
    workflow_states: Dict[str, Dict[str, Any]] = {}

# Add file detection cache
if 'file_detection_cache' not in globals():
    file_detection_cache: Dict[str, Dict] = {}

# ============ New Request/Response models ============
class FileDetectionRequest(BaseModel):
    github_url: str

class FileDetectionResponse(BaseModel):
    ml_files: List[str]
    confidence: float
    reasoning: str
    repo_name: str
    local_repo_path: str
    status: str = "success"
    error: Optional[str] = None

# ============ Existing Request models unchanged ============
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

# ============ New file detection endpoint ============
@app.post("/detect-ml-files", response_model=FileDetectionResponse)
async def detect_ml_files(request: FileDetectionRequest):
    """
    Detect core ML files in a GitHub repo
    Reuses existing fork_and_clone_repo function
    """
    try:
        # Parse repo name
        _, repo_name = parse_github_url(request.github_url)
        
        # Check cache
        cache_key = request.github_url
        if cache_key in file_detection_cache:
            logger.info(f"Using cached detection results for {repo_name}")
            cached_result = file_detection_cache[cache_key]
            # Ensure correct response format
            return FileDetectionResponse(**cached_result)
        
        # Use temporary run_id for cloning
        temp_run_id = "detection"
        
        # Reuse existing clone function
        logger.info(f"Cloning repository for ML file detection: {request.github_url}")
        local_repo_path, fork_clone_url = fork_and_clone_repo(
            request.github_url, 
            temp_run_id
        )
        
        # Use LLM Agent to detect ML files
        logger.info(f"Detecting ML files in {local_repo_path}")
        agent = LLMFileIdentificationAgent(local_repo_path)
        result = agent.identify_ml_files()
        
        # Build response
        response_data = {
            "ml_files": result['ml_files'],
            "confidence": result['confidence'],
            "reasoning": result['reasoning'],
            "repo_name": repo_name,
            "local_repo_path": local_repo_path,
            "status": "success",
            "error": None
        }
        
        # Cache results (avoid repeated cloning)
        file_detection_cache[cache_key] = response_data
        
        return FileDetectionResponse(**response_data)
        
    except Exception as e:
        logger.error(f"Error detecting ML files: {str(e)}")
        return FileDetectionResponse(
            ml_files=[],
            confidence=0.0,
            reasoning=f"Error occurred during detection: {str(e)}",
            repo_name=repo_name if 'repo_name' in locals() else "",
            local_repo_path="",
            status="error",
            error=str(e)
        )

# ============ Clear cache endpoint (optional) ============
@app.post("/clear-detection-cache")
async def clear_detection_cache():
    """Clear the file detection cache"""
    global file_detection_cache
    file_detection_cache.clear()
    return {"message": "Detection cache cleared"}

# ============ The following are your existing endpoints, kept unchanged ============

def save_human_feedback(request: ComponentsResponse | DagResponse, repo_name: str, run_id: str, background_tasks: BackgroundTasks = None):
    # Save the human verification response
    if not run_id:
        raise HTTPException(400, "run_id required for continuing")

    # Check which human verification result this is
    if isinstance(request, ComponentsResponse):
        step_name = "human_verification_of_components"
        update_name = "verified_components"

        # Get original components for comparison
        try:
            original_output = load_step_output(
                checkpoint_base_path=CHECKPOINT_BASE_PATH,
                repo_name=repo_name,
                run_id=run_id,
                step="component_parsing"
            )
            original_components = original_output.get("component_parsing", [])

            # Log the differences between original and verified components
            component_corrections = log_component_corrections(original_components, request.verified_components)
            logger.info(f"Logged component corrections: {len(component_corrections.get('modified', []))} modified, "
                  f"{component_corrections.get('summary', {}).get('added_count', 0)} added, "
                  f"{component_corrections.get('summary', {}).get('deleted_count', 0)} deleted")

            # Include corrections in the update
            update = {
                update_name: request.verified_components,
                "component_corrections": component_corrections
            }
        except Exception as e:
            logger.error(f"Error logging component corrections: {e}")
            update = {update_name: request.verified_components}

    elif isinstance(request, DagResponse):
        step_name = "human_verification_of_dag"
        update_name = "verified_dag"

        # Get original DAG for comparison
        try:
            original_output = load_step_output(
                checkpoint_base_path=CHECKPOINT_BASE_PATH,
                repo_name=repo_name,
                run_id=run_id,
                step="generate_dag_yaml"
            )
            original_dag = original_output.get("dag_yaml", "")

            # Log the differences between original and verified DAG
            dag_corrections = log_dag_corrections(original_dag, request.verified_dag)
            logger.info(f"Logged DAG corrections: {len(dag_corrections.get('modified_edges', []))} modified edges, "
                  f"{dag_corrections.get('summary', {}).get('added_edge_count', 0)} added, "
                  f"{dag_corrections.get('summary', {}).get('deleted_edge_count', 0)} deleted")

            # Include corrections in the update
            update = {
                update_name: request.verified_dag,
                "dag_corrections": dag_corrections
            }
            
            # IMPORTANT: Also save the verified DAG to dag.yaml file
            dag_yaml_path = os.path.join(CHECKPOINT_BASE_PATH, repo_name, run_id, "dag.yaml")
            try:
                with open(dag_yaml_path, 'w') as yaml_file:
                    yaml_file.write(request.verified_dag)
                logger.info(f"Updated dag.yaml file with verified DAG at {dag_yaml_path}")
            except Exception as e:
                logger.error(f"Error updating dag.yaml file: {e}")

            # NEW: Update verified_components if there are renamed nodes
            if dag_corrections.get("renamed_nodes"):
                try:
                    # Load existing verified_components
                    components_path = os.path.join(CHECKPOINT_BASE_PATH, repo_name, run_id, 'human_verification_of_components.json')
                    if os.path.exists(components_path):
                        with open(components_path, 'r') as file:
                            components_data = json.load(file)
                            verified_components = components_data.get('verified_components', [])
                        
                        # Update component names based on renames
                        updated_components = []
                        for file_components in verified_components:
                            updated_file_components = {}
                            for comp_name, comp_data in file_components.items():
                                # Check if this component was renamed
                                new_name = dag_corrections["renamed_nodes"].get(comp_name, comp_name)
                                updated_file_components[new_name] = comp_data
                            updated_components.append(updated_file_components)
                        
                        # Save updated components back
                        components_data['verified_components'] = updated_components
                        with open(components_path, 'w') as file:
                            json.dump(components_data, file, indent=2)
                        logger.info(f"Updated verified_components with renamed nodes")
                        
                except Exception as e:
                    logger.error(f"Error updating verified_components: {e}")
                    
        except Exception as e:
            logger.error(f"Error logging DAG corrections: {e}")
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
                logger.warning("Cancelling workflow while loading checkpoints")
                return
            state.update(load_step_output(checkpoint_base_path=CHECKPOINT_BASE_PATH, repo_name=repo_name, run_id=run_id, step=step_name))
        
        # Continue running the workflow starting from the provided start index
        for step_name, step_func in STEPS[start_idx:]:
            if state.get("status") == "cancelled":
                logger.warning(f"Cancelling workflow at step {step_name}")
                return
            state["step"] = step_name
            logger.info(f"Running step {step_name}")
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
    logger.info(f"Returning status update with current step: {workflow_states[repo_name][run_id]['step']}")
    return workflow_states[repo_name][run_id]

@app.get("/correction-logs/{repo_name}")
def get_correction_logs(
    repo_name: str,
    run_id: str = Query(..., description="Run ID for the workflow")
):
    """Get logs of human corrections for a specific workflow run"""
    # Check if the workflow exists
    if repo_name not in workflow_states:
        raise HTTPException(status_code=404, detail=f"Workflow with repo_name {repo_name} not found")

    # Check if the run_id exists for this repository
    if run_id not in workflow_states[repo_name]:
        raise HTTPException(status_code=404, detail=f"Run ID {run_id} not found in repository {repo_name}")

    # Get correction logs
    state = workflow_states[repo_name][run_id]
    logs = {
        "component_corrections": state.get("component_corrections", {}),
        "dag_corrections": state.get("dag_corrections", {})
    }

    return logs

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
    logger.info("📥 Received payload")
    logger.debug(f"Payload content: {payload}")

    # === DAG Feedback ===
    if "verified_dag" in payload:
        logger.info("🧩 Detected: DagResponse")
        parsed = DagResponse(**payload)
        workflow_states[repo_name][run_id]["step"] = "human_verification_of_dag"
        workflow_states[repo_name][run_id]["status"] = "saving_feedback"
        return save_human_feedback(parsed, repo_name, run_id, background_tasks)

    # === Component Feedback ===
    elif "verified_components" in payload:
        logger.info("🧩 Detected: ComponentsResponse")
        parsed = ComponentsResponse(**payload)
        workflow_states[repo_name][run_id]["step"] = "human_verification_of_components"
        workflow_states[repo_name][run_id]["status"] = "saving_feedback"
        return save_human_feedback(parsed, repo_name, run_id, background_tasks)

    # === Workflow Init / Start ===
    elif "github_url" in payload and "input_files" in payload:
        logger.info("🚀 Detected: WorkflowRequest")
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
            logger.info(f"Setting config file path: {parsed.existing_config_path}")

        # Add background task to run
        background_tasks.add_task(run_workflow_background, parsed, repo_name, run_id, start_idx)
        return {"repo_name": repo_name, "run_id": run_id, "step": step_name, "status": status}

    else:
        raise HTTPException(400, "Invalid or unrecognized request type")

# Uvicorn entry point
if __name__ == "__main__":
    import uvicorn
    import logging

    # Configure the root logger for the FastAPI application
    logging.basicConfig(level=logging.INFO)
    logger.info("Starting RMR Agent API server with ML file detection support")

    # Run the server
    uvicorn.run(app, host="0.0.0.0", port=8000, log_level="info")