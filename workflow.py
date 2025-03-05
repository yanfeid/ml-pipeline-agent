from langgraph.graph import StateGraph, END
from typing import List, Dict, Any
import yaml
import json
import os
import requests
import time
from utils.git_utils import clone_repo, parse_github_url
from utils.convert_ipynb_to_py import convert_notebooks
import argparse

CHECKPOINT_BASE_DIR = "checkpoints"
os.makedirs(CHECKPOINT_BASE_DIR, exist_ok=True)

WorkflowState = dict[str, Any]

def clone_and_prepare_repo(state: WorkflowState) -> dict:
    if "files" in state and state["files"]:
        print("Skipping clone_and_prepare_repo: 'files' already in state")
        return {}
    repo_name, local_repo_path = clone_repo(state["github_url"])
    files = convert_notebooks(state["input_files"], local_repo_path)
    return {
        "repo_name": repo_name,
        "local_repo_path": local_repo_path,
        "files": files
    }

def summarize(state: WorkflowState) -> dict:
    if "summaries" in state and state["summaries"]:
        print("Skipping summarize: 'summaries' already in state")
        return {}
    from agents.summarization import summarize_code
    print('state for Summarize:', state)
    full_file_list = state["files"]
    summaries = []
    
    checkpoint_dir = os.path.join(CHECKPOINT_BASE_DIR, state["repo_name"], "summarize")
    os.makedirs(checkpoint_dir, exist_ok=True)

    for file in full_file_list:
        safe_filename = os.path.basename(file).replace("/", "_").replace("\\", "_")
        checkpoint_path = os.path.join(checkpoint_dir, f"summarize_{safe_filename}.json")
        
        if os.path.exists(checkpoint_path):
            with open(checkpoint_path, "r") as f:
                summary = json.load(f)
            print(f"Loaded cached summary for {file} from {checkpoint_path}")
        else:
            summary_text = summarize_code(file, full_file_list)  # Returns a string
            summary_data = {"summary": summary_text}
            with open(checkpoint_path, "w") as f:
                json.dump(summary_data, f, indent=2)
            print(f"Saved summary for {file} to {checkpoint_path}")
        
        summaries.append(summary_data)
    
    return {"summaries": summaries}

def run_cia(state: WorkflowState) -> dict:
    if "all_nodes" in state and state["all_nodes"]:
        print("Skipping run_cia: 'all_nodes' already in state")
        return {}
    from agents.cia import component_identification_agent
    full_file_list = state["files"]
    summaries = state["summaries"]
    all_nodes = []
    
    checkpoint_dir = os.path.join(CHECKPOINT_BASE_DIR, state["repo_name"], "cia")
    os.makedirs(checkpoint_dir, exist_ok=True)

    for file, summary in zip(full_file_list, summaries):
        safe_filename = os.path.basename(file).replace("/", "_").replace("\\", "_")
        checkpoint_path = os.path.join(checkpoint_dir, f"cia_{safe_filename}.json")
        
        if os.path.exists(checkpoint_path):
            with open(checkpoint_path, "r") as f:
                nodes = json.load(f)
            print(f"Loaded cached nodes for {file} from {checkpoint_path}")
        else:
            nodes = component_identification_agent(file, full_file_list, summary)  # Pass summary to CIA
            with open(checkpoint_path, "w") as f:
                json.dump(nodes, f, indent=2)
            print(f"Saved nodes for {file} to {checkpoint_path}")
        
        all_nodes.append(nodes)
    
    return {"all_nodes": all_nodes}

def run_node_aggregator(state: WorkflowState) -> dict:
    if "consolidated_nodes" in state and state["consolidated_nodes"]:
        print("Skipping run_node_aggregator: 'consolidated_nodes' already in state")
        return {}
    from agents.node_aggregator import node_aggregator_agent
    consolidated_nodes = node_aggregator_agent(state["all_nodes"])
    return {"consolidated_nodes": consolidated_nodes}

def run_edge(state: WorkflowState) -> dict:
    if "edges" in state and state["edges"]:
        print("Skipping run_edge: 'edges' already in state")
        return {}
    from agents.edge import edge_identification_agent
    edges = edge_identification_agent(state["consolidated_nodes"])
    return {"edges": edges}

def generate_dag_yaml(state: WorkflowState) -> dict:
    if "dag_yaml" in state and state["dag_yaml"]:
        print("Skipping generate_dag_yaml: 'dag_yaml' already in state")
        return {}
    dag = {"nodes": state["consolidated_nodes"], "edges": state["edges"]}
    dag_yaml = yaml.dump(dag, default_flow_style=False)
    return {"dag_yaml": dag_yaml}

def human_verification(state: WorkflowState) -> dict:
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

def run_config_agent(state: WorkflowState) -> dict:
    if "config" in state and state["config"]:
        print("Skipping run_config_agent: 'config' already in state")
        return {}
    from agents.ini_config import config_agent
    config = config_agent(state["verified_dag"])
    return {"config": config}

def run_notebook_agent(state: WorkflowState) -> dict:
    if "notebooks" in state and state["notebooks"]:
        print("Skipping run_notebook_agent: 'notebooks' already in state")
        return {}
    from agents.notebook import notebook_agent
    notebooks = notebook_agent(state["verified_dag"])
    return {"notebooks": notebooks}

def save_checkpoint(state: WorkflowState, repo_name: str, node_name: str):
    checkpoint_dir = os.path.join(CHECKPOINT_BASE_DIR, repo_name)
    os.makedirs(checkpoint_dir, exist_ok=True)
    checkpoint_path = os.path.join(checkpoint_dir, f"state_{node_name}.json")
    with open(checkpoint_path, "w") as f:
        json.dump(state, f, indent=2)
    print(f"Saved checkpoint for node '{node_name}' in repo {repo_name}")

def load_checkpoint(repo_name: str, node_name: str) -> dict | None:
    checkpoint_path = os.path.join(CHECKPOINT_BASE_DIR, repo_name, f"state_{node_name}.json")
    if os.path.exists(checkpoint_path):
        with open(checkpoint_path, "r") as f:
            loaded_state = json.load(f)
        print(f"Loaded checkpoint for node '{node_name}' in repo {repo_name}")
        return loaded_state
    return None

def build_workflow():
    workflow = StateGraph(WorkflowState)
    workflow.add_node("clone_and_prepare_repo", clone_and_prepare_repo)
    workflow.add_node("summarize", summarize)
    workflow.add_node("cia", run_cia)
    workflow.add_node("node_aggregator", run_node_aggregator)
    workflow.add_node("edge", run_edge)
    workflow.add_node("generate_dag_yaml", generate_dag_yaml)
    workflow.add_node("human_verification", human_verification)
    workflow.add_node("config_agent", run_config_agent)
    workflow.add_node("notebook_agent", run_notebook_agent)

    workflow.add_edge("clone_and_prepare_repo", "summarize")
    workflow.add_edge("summarize", "cia")
    workflow.add_edge("cia", "node_aggregator")
    workflow.add_edge("node_aggregator", "edge")
    workflow.add_edge("edge", "generate_dag_yaml")
    workflow.add_edge("generate_dag_yaml", "human_verification")
    workflow.add_edge("human_verification", "config_agent")
    workflow.add_edge("config_agent", "notebook_agent")
    workflow.add_edge("notebook_agent", END)

    workflow.set_entry_point("clone_and_prepare_repo")
    return workflow.compile()

def run_workflow(github_url: str, input_files: List[str], start_from: str | None = None):
    workflow = build_workflow()
    
    _, repo_name = parse_github_url(github_url)
    
    # Define initial state
    state = {
        "github_url": github_url,
        "input_files": input_files,
        "repo_name": repo_name,
        "local_repo_path": "",
        "files": [],
        "all_nodes": [],
        "consolidated_nodes": [],
        "edges": [],
        "dag_yaml": "",
        "verified_dag": {},
        "config": {},
        "notebooks": []
    }

    # Load state from specified node if provided
    if start_from:
        loaded_state = load_checkpoint(repo_name, start_from)
        if loaded_state:
            initial_state = loaded_state
        else:
            raise FileNotFoundError(f"No checkpoint found for node '{start_from}' in repo {repo_name}")
        
    print("Initial state:", initial_state)

    nodes = [
        ("clone_and_prepare_repo", clone_and_prepare_repo),
        ("summarize", summarize),
        ("cia", run_cia),
        ("node_aggregator", run_node_aggregator),
        ("edge", run_edge),
        ("generate_dag_yaml", generate_dag_yaml),
        ("human_verification", human_verification),
        ("config_agent", run_config_agent),
        ("notebook_agent", run_notebook_agent)
    ]

    start_idx = 0 if not start_from else next(i for i, (name, _) in enumerate(nodes) if name == start_from)
    for node_name, node_func in nodes[start_idx:]:
        update = node_func(state)
        state.update(update)
        save_checkpoint(state, repo_name, node_name)
        print(f"Completed node: {node_name}")

    return state

    # Run the workflow and save state after each node
    for output in workflow.stream(initial_state, config={"recursion_limit": 1000}):
        print('Output', output)
        for node_name, state_update in output.items():
            initial_state.update(state_update)
            print('initial state in loop:', initial_state)
            save_checkpoint(initial_state, repo_name, node_name)
            print(f"Completed node: {node_name}")

    return initial_state

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Run the workflow with a GitHub URL and input files.")
    parser.add_argument("--github-url", type=str, required=True, help="GitHub repository URL")
    parser.add_argument("--input-files", type=str, nargs="+", required=True, help="List of input file paths (e.g., 'notebooks/notebook1.ipynb')")
    parser.add_argument("--start-from", type=str, default=None, help="Node name to start from (e.g., 'cia', 'generate_dag_yaml')")
    args = parser.parse_args()

    result = run_workflow(
        github_url=args.github_url,
        input_files=args.input_files,
        start_from=args.start_from
    )
    print("Config:", result["config"])
    print("Notebooks:", result["notebooks"])