from langgraph.graph import StateGraph, END
#from langgraph.types import interrupt
from typing import Dict, Any, List
import yaml
import json
import os
import requests
import time
import subprocess
import tempfile
from utils.git_utils import clone_repo, parse_github_url
from utils.convert_ipynb_to_py import convert_notebooks
from utils.save_file import save_state, save_ini_file
import argparse

WorkflowState = Dict[str, Any]

def load_step_state(repo_name: str, step: str) -> Dict[str, Any]:
    checkpoint_path = f"checkpoints/{repo_name}/{step}.json"
    if os.path.exists(checkpoint_path):
        with open(checkpoint_path, "r") as f:
            state = json.load(f)
        print(f"Loaded {step} state from {checkpoint_path}")
        return state
    return {}

def save_step_state(repo_name: str, step: str, state: Dict[str, Any]):
    os.makedirs(f"checkpoints/{repo_name}", exist_ok=True)
    checkpoint_path = f"checkpoints/{repo_name}/{step}.json"
    with open(checkpoint_path, "w") as f:
        json.dump(state, f, indent=2)
    print(f"Saved {step} state to {checkpoint_path}")

def clone_and_prepare_repo(state: WorkflowState) -> Dict[str, Any]:
    # print(f"clone_and_prepare_repo state: {state}")
    if "files" in state and state["files"]:
        print("Skipping clone_and_prepare_repo: 'files' already in state")
        return {}
    local_repo_path = clone_repo(state["github_url"])
    files = convert_notebooks(state["input_files"], local_repo_path)
    return {
        "local_repo_path": local_repo_path,
        "files": files
    }

def summarize(state: WorkflowState) -> Dict[str, Any]:
    # print(f"Summarize state: {state}")
    if "summaries" in state and state["summaries"]:
        print("Skipping summarize: 'summaries' already in state")
        return {}
    from agents.summarization import summarize_code
    full_file_list = state["files"]
    summaries = []
    for file in full_file_list:
        summary_text = summarize_code(file, full_file_list)
        summaries.append({"summary": summary_text})
        print(f"Generated summary for {file}")
    return {"summaries": summaries}

def run_component_identification(state: WorkflowState) -> Dict[str, Any]:
    # print(f"run_component_identification state: {state}")
    if "component_identification" in state and state["component_identification"]:
        print("Skipping run_component_identification: 'component_identification' already in state")
        return {}
    from agents.component_identification import component_identification_agent
    full_file_list = state["files"]
    summaries = state["summaries"]
    component_identification = []
    for file, summary_data in zip(full_file_list, summaries):
        nodes = component_identification_agent(file, full_file_list, code_summary=summary_data["summary"])
        component_identification.append(nodes)
        print(f"Identified components for {file}")
    return {"component_identification": component_identification}

def run_component_parsing(state: WorkflowState) -> Dict[str, Any]:
    # print(f"run_component_parsing state: {state}")
    if "component_parsing" in state and state["component_parsing"]:
        print("Skipping run_component_parsing: 'component_parsing' already in state")
        return {}
    from agents.component_parsing import parse_component_identification
    full_file_list = state["files"]
    component_identification = state["component_identification"]
    component_parsing = []
    for file, component_identification_text in zip(full_file_list, component_identification):
        parsed_component_identification_text, parsed_component_identification_dict = parse_component_identification(component_identification_text, file)
        component_parsing.append(parsed_component_identification_dict)
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

    with tempfile.NamedTemporaryFile(suffix='.json', mode='w', delete=False) as temp_file:
        json_path = temp_file.name
        # Add a "verified" field to each component 
        editable_components = []
        for component in components:
            editable_component = component.copy()
            editable_components.append(editable_component)

        # Write to the temp file
        json.dump(editable_components, temp_file, indent=2)
    
    # Determine which editor to use
    editor = os.environ.get('EDITOR', 'vim')  # Default to vim if EDITOR not set

    # Instructions for the user
    print(f"\nTemporary file created at: {json_path}")
    print("\nPlease review and edit the components in the editor that will open:")
    print("- You can modify component details as needed")
    print("- Save and close the editor when done\n")
    
    # Open the editor for the user to make changes
    input("Press Enter to open the editor...")
    subprocess.call([editor, json_path])

    # Read the edited file
    with open(json_path, 'r') as file:
        try:
            verified_components = json.load(file)
            print("\nVerification complete!")
        except json.JSONDecodeError:
            print("\nError: The file was not saved as valid JSON.")
            raise
    
    # Clean up the temp file
    os.unlink(json_path)
    
    return {"verified_components": verified_components}


def run_attribute_identification(state: WorkflowState) -> Dict[str, Any]:
    # print(f"run_attribute_identification state: {state}")
    if 'attribute_identification' in state and state['attribute_identification']:
        print("Skipping run_attribute_identification: 'attribute_identification' already in state")
        return {}
    from agents.attribute_identification import attribute_identification_agent
    full_file_list = state["files"]
    verified_components = state['verified_components']
    attribute_identification = []
    for file, component_dict in zip(full_file_list, verified_components):
        attribution_text = attribute_identification_agent(file, component_dict)
        attribute_identification.append(attribution_text)
        print(f"Identified attributes for components in {file}")
    return {"attribute_identification": attribute_identification}

def run_attribute_parsing(state: WorkflowState) -> Dict[str, Any]:
    # to do - add config values from existing config if applicable. Add conditional logic to check if that is the case, use LLM call to fill the values (easiest way) 
    if 'attribute_parsing' in state and state['attribute_parsing']:
        print("Skipping run_attribute_parsing: 'attribute_parsing' already in state")
        return {}
    from agents.attribute_parsing import parse_attribute_identification
    verified_components = state['verified_components']
    attribute_identification = state['attribute_identification']
    attribute_parsing = []
    for component_identification_dict, attributes_text in zip(verified_components, attribute_identification):
        parsed_attributes_text, parsed_attributes_dict = parse_attribute_identification(component_identification_dict, attributes_text)
        attribute_parsing.append(parsed_attributes_dict)
    return {"attribute_parsing": attribute_parsing}

def run_node_aggregator(state: WorkflowState) -> Dict[str, Any]:
    if "node_aggregator" in state and state["node_aggregator"]:
        print("Skipping run_node_aggregator: 'node_aggregator' already in state")
        return {}
    from agents.node_aggregator import node_aggregator_agent
    node_aggregator = node_aggregator_agent(state["attribute_parsing"])
    return {"node_aggregator": node_aggregator}
    
def run_edge_identification(state: WorkflowState) -> Dict[str, Any]:
    if "edges" in state and state["edges"]:
        print("Skipping run_edge_identification: 'edges' already in state")
        return {}
    from agents.edge_identification import edge_identification_agent
    edges = edge_identification_agent(state["node_aggregator"])
    return {"edges": edges}

def generate_dag_yaml(state: WorkflowState) -> Dict[str, Any]:
    if "dag_yaml" in state and state["dag_yaml"]:
        print("Skipping generate_dag_yaml: 'dag_yaml' already in state")
        return {}
    dag = {"nodes": state["consolidated_nodes"], "edges": state["edges"]}
    dag_yaml = yaml.dump(dag, default_flow_style=False)
    return {"dag_yaml": dag_yaml}

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
    from agents.ini_config import config_agent
    config = config_agent(state["verified_dag"])

    BASE_DIR = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))  
    CHECKPOINT_SUBDIR = os.path.join(BASE_DIR, "checkpoints", "ql-store-recommendation-prod")
    STATE_FILE = os.path.join(CHECKPOINT_SUBDIR, "ini_config.json")

 
    os.makedirs(CHECKPOINT_SUBDIR, exist_ok=True)

    print(f" Checkpoints will be stored in: {CHECKPOINT_SUBDIR}")
    print(f" State file path: {STATE_FILE}")


    save_state(config, STATE_FILE)
    save_ini_file("environment.ini", config["environment_ini"], CHECKPOINT_SUBDIR)
    save_ini_file("solution.ini", config["solution_ini"], CHECKPOINT_SUBDIR)

    return {"config": config}  


def run_notebook_agent(state: WorkflowState) -> Dict[str, Any]:
    if "notebooks" in state and state["notebooks"]:
        print("Skipping run_notebook_agent: 'notebooks' already in state")
        return {}
    from agents.notebook import notebook_agent
    notebooks = notebook_agent(state["verified_dag"])
    return {"notebooks": notebooks}

def build_workflow():
    workflow = StateGraph(WorkflowState)
    workflow.add_node("clone_and_prepare_repo", clone_and_prepare_repo)
    workflow.add_node("summarize", summarize)
    workflow.add_node("component_identification", run_component_identification)
    workflow.add_node("component_parsing", run_component_parsing)
    workflow.add_node("human_verification_of_components", human_verification_of_components)
    workflow.add_node("attribute_identification", run_attribute_identification)
    workflow.add_node("attribute_parsing", run_attribute_parsing)
    workflow.add_node("node_aggregator", run_node_aggregator)
    workflow.add_node("edge_identification", run_edge_identification)
    workflow.add_node("generate_dag_yaml", generate_dag_yaml)
    workflow.add_node("human_verification_of_dag", human_verification_of_dag)
    workflow.add_node("config_agent", run_config_agent)
    workflow.add_node("notebook_agent", run_notebook_agent)

    workflow.add_edge("clone_and_prepare_repo", "summarize")
    workflow.add_edge("summarize", "component_identification")
    workflow.add_edge("component_identification", "component_parsing")
    workflow.add_edge("component_parsing", "human_verification_of_components")
    workflow.add_edge("human_verification_of_components", "attribute_identification")
    workflow.add_edge("attribute_identification", "node_aggregator")
    workflow.add_edge("node_aggregator", "edge_identification")
    workflow.add_edge("edge_identification", "generate_dag_yaml")
    workflow.add_edge("generate_dag_yaml", "human_verification")
    workflow.add_edge("human_verification_of_dag", "config_agent")
    workflow.add_edge("config_agent", "notebook_agent")
    workflow.add_edge("notebook_agent", END)

    workflow.set_entry_point("clone_and_prepare_repo")
    return workflow.compile()

def run_workflow(github_url: str, input_files: List[str], start_from: str | None = None, existing_config_path: str | None = None):
    _, repo_name = parse_github_url(github_url)
    
    initial_state = {
        "github_url": github_url,
        "input_files": input_files,
        "repo_name": repo_name,
        "local_repo_path": "",
        "existing_config_path": existing_config_path,
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
        "notebooks": []
    }

    # Define all steps with their functions
    steps = [
        ("clone_and_prepare_repo", clone_and_prepare_repo),
        ("summarize", summarize),
        ("component_identification", run_component_identification),
        ("component_parsing", run_component_parsing),
        ("human_verification_of_components", human_verification_of_components),
        ("attribute_identification", run_attribute_identification),
        ("attribute_parsing", run_attribute_parsing),
        ("node_aggregator", run_node_aggregator),
        ("edge_identification", run_edge_identification),
        ("generate_dag_yaml", generate_dag_yaml),
        ("human_verification_of_dag", human_verification_of_dag),
        ("config_agent", run_config_agent),
        ("notebook_agent", run_notebook_agent)
    ]

    # Load state up to the start_from step
    current_state = initial_state.copy()
    start_idx = 0 if not start_from else next(i for i, (step, _) in enumerate(steps) if step == start_from)
    for step_name, _ in steps[:start_idx]:
        step_state = load_step_state(repo_name, step_name)
        current_state.update(step_state)

    # Run from start_from onward
    for step_name, step_func in steps[start_idx:]:
        #step_state = load_step_state(repo_name, step_name) # could remove?
        #current_state.update(step_state) # could remove?
        update = step_func(current_state)
        if update:
            current_state.update(update)
            save_step_state(repo_name, step_name, current_state)
        else:
            print(f"Step '{step_name}' skipped, using loaded state")

    return current_state

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Run the workflow with a GitHub URL and input files.")
    parser.add_argument("--github-url", type=str, required=True, help="GitHub repository URL")
    parser.add_argument("--input-files", type=str, nargs="+", required=True, help="List of input file paths (e.g., 'notebooks/notebook1.ipynb') from the root directory of repo")
    parser.add_argument("--start-from", type=str, default=None, help="Step to start from (e.g., 'summarize', 'component_identification')")
    parser.add_argument("--existing-config-path", type=str, default=None, help="If you already have a config in research code, specify its path from root directory of repo")

    args = parser.parse_args()

    result = run_workflow(
        github_url=args.github_url,
        input_files=args.input_files,
        start_from=args.start_from,
        existing_config_path=args.existing_config_path
    )
    print("Final Config:", result["config"])
    print("Final Notebooks:", result["notebooks"])