import os
import json
import tempfile
import requests
import argparse
import subprocess
from typing import Dict, Any, List
from concurrent.futures import ThreadPoolExecutor
from rmr_agent.utils import (
    clone_repo, parse_github_url, convert_notebooks,
    get_next_run_id, load_step_output, save_step_output
)
from langgraph.graph import StateGraph, END

# State
WorkflowState = Dict[str, Any]

CHECKPOINT_BASE_PATH = "rmr_agent/checkpoints"

def is_cancelled(state: WorkflowState) -> bool:
    """Check if the workflow has been cancelled."""
    return state.get("status") == "cancelled"

def clone_and_prepare_repo(state: WorkflowState) -> Dict[str, Any]:
    if "files" in state and state["files"]:
        print("Skipping clone_and_prepare_repo: 'files' already in state")
        return {}
    local_repo_path = clone_repo(state["github_url"])
    files = convert_notebooks(state["input_files"], local_repo_path)
    return {
        "github_url": state['github_url'],
        "local_repo_path": local_repo_path,
        "files": files
    }

def summarize(state: WorkflowState) -> Dict[str, Any]:
    if "summaries" in state and state["summaries"]:
        print("Skipping summarize: 'summaries' already in state")
        return {}
    from rmr_agent.agents.summarization import summarize_code
    full_file_list = state["files"]
    summaries = {}
    cleaned_code = {}
    
    with ThreadPoolExecutor() as executor:
        # Map processing across threads using a lambda
        results = executor.map(
            lambda file: (file, *summarize_code(file, full_file_list)),
            full_file_list
        )
        
        for file, clean_code, summary_text in results:
            if is_cancelled(state):
                print("Workflow cancelled during code summarization")
                return {}
            summaries[file] = summary_text
            cleaned_code[file] = clean_code
            print(f"Generated summary for {file}")

    return {
        "summaries": summaries,
        "cleaned_code": cleaned_code
    }

def run_component_identification(state: WorkflowState) -> Dict[str, Any]:
    if "component_identification" in state and state["component_identification"]:
        print("Skipping run_component_identification: 'component_identification' already in state")
        return {}
    from rmr_agent.agents.component_identification import component_identification_agent
    full_file_list = state["files"]
    summaries = state["summaries"]
    component_identification = []
    
    with ThreadPoolExecutor() as executor:
        # Map processing across threads using a lambda
        results = executor.map(
            lambda file: (file, component_identification_agent(file, full_file_list, code_summary=summaries[file])),
            full_file_list
        )
        
        for file, component_id_str in results:
            if is_cancelled(state):
                print("Workflow cancelled during component identification")
                return {}
            component_identification.append(component_id_str)
            print(f"Identified components for {file}")

    return {"component_identification": component_identification}

def run_component_parsing(state: WorkflowState) -> Dict[str, Any]:
    if "component_parsing" in state and state["component_parsing"]:
        print("Skipping run_component_parsing: 'component_parsing' already in state")
        return {}
    from rmr_agent.agents.component_parsing import parse_component_identification
    full_file_list = state["files"]
    component_identification = state["component_identification"]
    component_parsing = []
    
    with ThreadPoolExecutor() as executor:
        # Map processing across threads using a lambda
        results = executor.map(
            lambda pair: (pair[0], *parse_component_identification(pair[1], pair[0])),
            zip(full_file_list, component_identification)
        )
        
        for file, parsed_component_id_text, parsed_component_id_dict in results:
            if is_cancelled(state):
                print("Workflow cancelled during component parsing")
                return {}
            component_parsing.append(parsed_component_id_dict)
            print(f"Parsed the component identification response for {file}")

    return {"component_parsing": component_parsing}

def human_verification_of_components(state: WorkflowState) -> Dict[str, Any]:
    # temporarily just edit in vim -> later move to user interface front end to verify the list of components identified for each python file
    if "verified_components" in state and state["verified_components"]:
        print("Skipping human_verification_of_components: 'verified_components' already in state")
        return {}
    components = state.get("component_parsing", [])
    if not components:
        raise ValueError("No components to verify")

    editor = os.environ.get('EDITOR', 'vim')  # Default to vim if EDITOR not set
    
    while True:  # Keep trying until we get valid JSON
        with tempfile.NamedTemporaryFile(suffix='.json', mode='w', delete=False) as temp_file:
            json_path = temp_file.name
            # Add a "verified" field to each component 
            editable_components = []
            for component in components:
                editable_component = component.copy()
                editable_components.append(editable_component)

            # Write to the temp file
            json.dump(editable_components, temp_file, indent=2)
        
        # Instructions for the user
        print(f"\nTemporary file created at: {json_path}")
        print("\nPlease review and edit the components in the editor that will open:")
        print("- You can modify component details as needed")
        print("- To delete a component, delete its entire JSON object (including the comma)")
        print("- Save and close the editor when done\n")
        
        # Open the editor for the user to make changes
        input("Press Enter to open the editor...")
        subprocess.call([editor, json_path])

        # Read the edited file
        try:
            with open(json_path, 'r') as file:
                verified_components = json.load(file)
                print("\nVerification complete! JSON is valid.")
                # Clean up the temp file
                os.unlink(json_path)
                return {"verified_components": verified_components}
        except json.JSONDecodeError as e:
            print(f"\nError: The file contains invalid JSON: {str(e)}")
            print("The error is usually caused by missing/extra commas or brackets.")
            
            retry = input("Would you like to try editing again? (y/n): ")
            if retry.lower() != 'y':
                print("Verification cancelled.")
                os.unlink(json_path)
                raise
            # If retry, the loop continues and opens the editor again
        except Exception as e:
            print(f"\nUnexpected error: {str(e)}")
            os.unlink(json_path)
            raise


def run_attribute_identification(state: WorkflowState) -> Dict[str, Any]:
    # print(f"run_attribute_identification state: {state}")
    if 'attribute_identification' in state and state['attribute_identification']:
        print("Skipping run_attribute_identification: 'attribute_identification' already in state")
        return {}
    from rmr_agent.agents.attribute_identification import attribute_identification_agent
    full_file_list = state["files"]
    verified_components = state['verified_components']
    cleaned_code = state['cleaned_code']
    attribute_identification = []
    
    with ThreadPoolExecutor() as executor:
        # Map processing across threads using a lambda
        results = executor.map(
            lambda pair: (pair[0], attribute_identification_agent(pair[0], pair[1], cleaned_code[pair[0]])),
            zip(full_file_list, verified_components)
        )
        
        for file, attribution_text in results:
            if is_cancelled(state):
                print("Workflow cancelled during attribute identification")
                return {}
            attribute_identification.append(attribution_text)
            print(f"Identified attributes for components in {file}")

    return {"attribute_identification": attribute_identification}

def run_attribute_parsing(state: WorkflowState) -> Dict[str, Any]:
    # to do - add config values from existing config if applicable. Add conditional logic to check if that is the case, use LLM call to fill the values (easiest way) 
    if 'attribute_parsing' in state and state['attribute_parsing']:
        print("Skipping run_attribute_parsing: 'attribute_parsing' already in state")
        return {}
    from rmr_agent.agents.attribute_parsing import parse_attribute_identification
    verified_components = state['verified_components']
    attribute_identification = state['attribute_identification']
    attribute_parsing = []
    
    with ThreadPoolExecutor() as executor:
        # Map processing across threads using a lambda
        results = executor.map(
            lambda x: (x[0], *parse_attribute_identification(x[0], x[1])),
            zip(verified_components, attribute_identification)
        )
        
        for component_dict, parsed_attributes_text, parsed_attributes_dict in results:
            if is_cancelled(state):
                print("Workflow cancelled during attribute parsing")
                return {}
            attribute_parsing.append(parsed_attributes_dict)

    return {"attribute_parsing": attribute_parsing}

def run_node_aggregator(state: WorkflowState) -> Dict[str, Any]:
    if "node_aggregator" in state and state["node_aggregator"]:
        print("Skipping run_node_aggregator: 'node_aggregator' already in state")
        return {}
    from rmr_agent.agents.node_aggregator import node_aggregator_agent
    nodes_yaml = node_aggregator_agent(state["attribute_parsing"])
    nodes_yaml_path = f"{CHECKPOINT_BASE_PATH}/{state['repo_name']}/{state['run_id']}/nodes.yaml"
    try:
        with open(nodes_yaml_path, 'w') as yaml_file:
            yaml_file.write(nodes_yaml)
        print(f"YAML successfully exported to {nodes_yaml_path}")
    except Exception as e:
        print(f"Error exporting YAML to {nodes_yaml_path}: {type(e).__name__}: {str(e)}")

    return {"node_aggregator": nodes_yaml}

def run_edge_identification(state: WorkflowState) -> Dict[str, Any]:
    if "edges" in state and state["edges"]:
        print("Skipping run_edge_identification: 'edges' already in state")
        return {}
    from rmr_agent.agents.edge_identification import edge_identification_agent
    edges = edge_identification_agent(state["node_aggregator"])
    return {"edges": edges}

def generate_dag_yaml(state: WorkflowState) -> Dict[str, Any]:
    if "dag_yaml" in state and state["dag_yaml"]:
        print("Skipping generate_dag_yaml: 'dag_yaml' already in state")
        return {}
    from rmr_agent.agents.dag import generage_dag_yaml
    dag_yaml_str = generage_dag_yaml(aggregated_nodes=state["node_aggregator"], edges=state["edges"])
    dag_yaml_path = f"{CHECKPOINT_BASE_PATH}/{state['repo_name']}/{state['run_id']}/dag.yaml"
    try:
        with open(dag_yaml_path, 'w') as yaml_file:
            yaml_file.write(dag_yaml_str)
        print(f"DAG YAML successfully exported to {dag_yaml_path}")
    except Exception as e:
        print(f"Error exporting YAML to {dag_yaml_path}: {type(e).__name__}: {str(e)}")
    return {"dag_yaml": dag_yaml_str}

def human_verification_of_dag(state: WorkflowState) -> Dict[str, Any]:
    if "verified_dag" in state and state["verified_dag"]:
        print("Skipping human_verification: 'verified_dag' already in state")
        return {}
    response = requests.post("http://localhost:8000/verify_dag", json={"dag_yaml": state["dag_yaml"]})
    if response.status_code != 200:
        raise Exception("Failed to send DAG for verification")
    while True:
        verification_response = requests.get("http://localhost:8000/get_verified_dag")
        if verification_response.status_code == 200 and verification_response.json().get("dag"):
            return {"verified_dag": verification_response.json()["dag"]}
        time.sleep(2)

def run_config_agent(state: WorkflowState) -> Dict[str, Any]:
    if "config" in state and state["config"]:
        print("Skipping run_config_agent: 'config' already in state")
        return {}
    from rmr_agent.agents.ini_config import config_agent
    config = config_agent(state["verified_dag"])
    return {"config": config}

def run_notebook_agent(state: WorkflowState) -> Dict[str, Any]:
    if "notebooks" in state and state["notebooks"]:
        print("Skipping run_notebook_agent: 'notebooks' already in state")
        return {}
    from rmr_agent.agents.notebook import notebook_agent
    notebooks = notebook_agent(state["verified_dag"])
    return {"notebooks": notebooks}


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

INITIAL_STATE = {
    # status related
    "step": "",
    "status": "",
    "error": None,
    
    # workflow related
    "github_url": "",
    "input_files": "",
    "repo_name": "",
    "run_id": "",
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

def build_workflow():
    workflow = StateGraph(WorkflowState)
    
    # Add all nodes using a for loop
    for step_name, step_function in STEPS:
        workflow.add_node(step_name, step_function)
    
    # Add edges using a for loop - just a sequential workflow
    for i in range(len(STEPS) - 1):
        current_step = STEPS[i][0]
        next_step = STEPS[i + 1][0]
        workflow.add_edge(current_step, next_step)
    
    # Add final edge to END
    workflow.add_edge(STEPS[-1][0], END)
    
    # Set entry point
    workflow.set_entry_point(STEPS[0][0])
    
    return workflow.compile()

# For testing locally
def run_workflow(github_url: str, input_files: List[str], run_id: str | None = None, start_from: str | None = None, existing_config_path: str | None = None):
    _, repo_name = parse_github_url(github_url)
    if not run_id:
        run_id = get_next_run_id(checkpoint_base_path=CHECKPOINT_BASE_PATH, repo_name=repo_name)
    start_idx = 0 if not start_from else next(i for i, (s, _) in enumerate(STEPS) if s == start_from)
    step_name = STEPS[start_idx][0]
    status = "initializing"
    
    state = INITIAL_STATE.copy()
    state["step"] = step_name
    state["status"] = status
    state["github_url"] = github_url
    state["input_files"] = input_files
    state["repo_name"] = repo_name
    state["run_id"] = run_id

    # Load state up to the start_from step
    start_idx = 0 if not start_from else next(i for i, (step, _) in enumerate(STEPS) if step == start_from)
    for step_name, _ in STEPS[:start_idx]:
        step_output = load_step_output(checkpoint_base_path=CHECKPOINT_BASE_PATH, repo_name=repo_name, run_id=run_id, step=step_name)
        state.update(step_output)

    # Run from start_from onward
    for step_name, step_func in STEPS[start_idx:]:
        update = step_func(state)
        state.update(update)
        save_step_output(checkpoint_base_path=CHECKPOINT_BASE_PATH, repo_name=repo_name, run_id=run_id, step=step_name, output=update)

    return state



if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Run the workflow with a GitHub URL and input files.")
    parser.add_argument("--github-url", type=str, required=True, help="GitHub repository URL")
    parser.add_argument("--input-files", type=str, nargs="+", required=True, help="List of input file paths (e.g., 'notebooks/notebook1.ipynb') from the root directory of repo")
    parser.add_argument("--run-id", type=str, default=None, help="Set if want to use 'start-from' tag, we will load checkpoints from this run_id (e.g. 1, 2, 3, etc.)")
    parser.add_argument("--start-from", type=str, default=None, help="Step to start from (e.g., 'summarize', 'component_identification')")
    parser.add_argument("--existing-config-path", type=str, default=None, help="If you already have a config in research code, specify its path from root directory of repo")

    args = parser.parse_args()

    result = run_workflow(
        github_url=args.github_url,
        input_files=args.input_files,
        run_id=args.run_id,
        start_from=args.start_from,
        existing_config_path=args.existing_config_path
    )
    print("Final Config:", result["config"])
    print("Final Notebooks:", result["notebooks"])
