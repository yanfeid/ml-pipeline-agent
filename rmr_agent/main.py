
import asyncio
from typing import Dict, Any, List, Optional
from utils import (
    get_next_run_id, load_step_output, save_step_output
    )
from workflow import *
from fastapi import FastAPI, HTTPException, Query
from fastapi.responses import StreamingResponse, JSONResponse
from pydantic import BaseModel


app = FastAPI()

CHECKPOINT_BASE_PATH = "rmr_agent/checkpoints"

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


async def stream_progress(messages):
    for msg in messages:
        yield f"data: {json.dumps({'message': msg})}\n\n"
        await asyncio.sleep(0.1)  # Simulate processing delay

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

# Main workflow endpoint
@app.post("/run-workflow")
async def run_workflow_endpoint(
    request: WorkflowRequest | ComponentsResponse | DagResponse,
    repo_name: str = Query(..., description="Repository name (required)"),
    run_id: Optional[str] = Query(None, description="Run ID for continuing workflow")
):
    
    messages = []  # Collect progress messages

    current_state = {
        "github_url": getattr(request, "github_url", ""),
        "input_files": getattr(request, "input_files", []),
        "repo_name": repo_name,
        "run_id": run_id,
        "local_repo_path": "",
        "existing_config_path": getattr(request, "existing_config_path", ""),
        "files": [],
        "summaries": [],
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

    if isinstance(request, WorkflowRequest):
        print("Starting workflow initialization")
        messages.append("Starting workflow initialization")
        run_id = request.run_id or get_next_run_id(checkpoint_base_path=CHECKPOINT_BASE_PATH, repo_name=repo_name)
        start_idx = 0 if not request.start_from else next(i for i, (s, _) in enumerate(STEPS) if s == request.start_from)
    else:
        if not run_id:
            raise HTTPException(status_code=400, detail="run_id required for continuing")
        print(f"Resuming workflow for run_id={run_id}")
        messages.append(f"Resuming workflow for run_id={run_id}")
        start_idx = next((i for i, (s, _) in enumerate(STEPS) if not load_step_output(checkpoint_base_path=CHECKPOINT_BASE_PATH, repo_name=repo_name, run_id=run_id, step=s)), 0)


    for step_name, _ in STEPS[:start_idx]:
        current_state.update(load_step_output(checkpoint_base_path=CHECKPOINT_BASE_PATH, repo_name=repo_name, run_id=run_id, step=step_name))

    # Run steps until human input or completion
    for step_name, step_func in STEPS[start_idx:]:
        print(f"Running step: {step_name}")
        messages.append(f"Running step: {step_name}")
        if step_name in HUMAN_STEPS:
            if step_name == "human_verification_of_components" and current_state["verified_components"] == [] and not getattr(request, "verified_components", []):
                print('Human needs to verify the identified components')
                return {
                    "run_id": run_id,
                    "repo_name": repo_name,
                    "step": step_name,
                    "message": "Please verify/edit the identified components",
                    "components": current_state["component_parsing"],
                    "progress": messages
                }
            elif step_name == "human_verification_of_dag" and current_state["verified_dag"] == {} and not getattr(request, "verified_dag", {}):
                print('Human needs to verify the identified DAG')
                return {
                    "run_id": run_id,
                    "repo_name": repo_name,
                    "step": step_name,
                    "message": "Verify/edit the identified DAG",
                    "dag_yaml": current_state["dag_yaml"],
                    "progress": messages
                }
            # Process human input
            if isinstance(request, ComponentsResponse) and step_name == "human_verification_of_components":
                print("Saving verified components")
                update = {"verified_components": request.verified_components}
            elif isinstance(request, DagResponse) and step_name == "human_verification_of_dag":
                print("Saving verified DAG")
                update = {"verified_dag": request.verified_dag}
            else:
                continue  # Skip if no input yet ?
        else:
            update = step_func(current_state)

        current_state.update(update)
        save_step_output(checkpoint_base_path=CHECKPOINT_BASE_PATH, repo_name=repo_name, run_id=run_id, step=step_name, output=update)
    
    messages.append("Workflow completed")
    return {
        "run_id": run_id,
        "state": "complete",
        "result": {"pr_url": current_state["pr_url"]}
    }


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000, log_level="debug")
