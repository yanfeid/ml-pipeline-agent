import os
import json
import yaml
import tempfile
import requests
import argparse
import subprocess
import logging
from typing import Dict, Any, List
from concurrent.futures import ThreadPoolExecutor
from rmr_agent.utils import (
    fork_and_clone_repo, parse_github_url, convert_notebooks,
    get_next_run_id, load_step_output, save_step_output,
    save_ini_file
)
import time
from rmr_agent.utils.logging_config import setup_logger

# Set up module logger
logger = setup_logger(__name__)

# State
WorkflowState = Dict[str, Any]

CHECKPOINT_BASE_PATH = "rmr_agent/checkpoints"
BASE_DIR = os.path.abspath(os.path.dirname(__file__))


def is_cancelled(state: WorkflowState) -> bool:
    """Check if the workflow has been cancelled."""
    return state.get("status") == "cancelled"

def fork_and_clone_repository(state: WorkflowState) -> Dict[str, Any]:
    if "files" in state and state["files"]:
        logger.info("Skipping fork_and_clone_repository: 'files' already in state")
        return {}
    # Fork and clone the repository and prepare the local path
    local_repo_path, fork_clone_url = fork_and_clone_repo(state["github_url"], state['run_id'])

    # Convert notebooks to Python files
    files = convert_notebooks(state["input_files"], local_repo_path)
    return {
        "github_url": state['github_url'],
        "local_repo_path": local_repo_path,
        "fork_clone_url": fork_clone_url,
        "files": files
    }

def summarize(state: WorkflowState) -> Dict[str, Any]:
    if "summaries" in state and state["summaries"]:
        logger.info("Skipping summarize: 'summaries' already in state")
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
                logger.warning("Workflow cancelled during code summarization")
                return {}
            summaries[file] = summary_text
            cleaned_code[file] = clean_code
            logger.info(f"Generated summary for {file}")

    return {
        "summaries": summaries,
        "cleaned_code": cleaned_code
    }

def run_component_identification(state: WorkflowState) -> Dict[str, Any]:
    if "component_identification" in state and state["component_identification"]:
        logger.info("Skipping run_component_identification: 'component_identification' already in state")
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
                logger.warning("Workflow cancelled during component identification")
                return {}
            component_identification.append(component_id_str)
            logger.info(f"Identified components for {file}")

    return {"component_identification": component_identification}

def run_component_parsing(state: WorkflowState) -> Dict[str, Any]:
    if "component_parsing" in state and state["component_parsing"]:
        logger.info("Skipping run_component_parsing: 'component_parsing' already in state")
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
                logger.warning("Workflow cancelled during component parsing")
                return {}
            component_parsing.append(parsed_component_id_dict)
            logger.info(f"Parsed the component identification response for {file}")

    return {"component_parsing": component_parsing}

def human_verification_of_components(state: WorkflowState) -> Dict[str, Any]:
    """This is a mock function that simulates human verification of the identified ML Components."""
    if "verified_components" in state and state["verified_components"]:
        logger.info("Skipping human_verification_of_components: 'verified_components' already in state")
        return {}
    components = state.get("component_parsing", [])
    if not components:
        logger.error("No components to verify")
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
        # Keep print statements for direct user feedback but also log the information
        logger.info(f"Temporary file created at: {json_path}")
        print(f"\nTemporary file created at: {json_path}")
        print("\nPlease review and edit the components in the editor that will open:")
        print("- You can modify component details as needed")
        print("- To delete a component, delete its entire JSON object (including the comma)")
        print("- Save and close the editor when done\n")

        # Log the user instructions for record-keeping
        logger.info("User instructed to review and edit components in the editor")

        # Open the editor for the user to make changes
        input("Press Enter to open the editor...")
        subprocess.call([editor, json_path])

        # Read the edited file
        try:
            with open(json_path, 'r') as file:
                verified_components = json.load(file)
                # Keep print for user feedback, but make sure it's also logged
                logger.info("Verification complete! JSON is valid.")
                print("\nVerification complete! JSON is valid.")
                # Clean up the temp file
                os.unlink(json_path)
                return {"verified_components": verified_components}
        except json.JSONDecodeError as e:
            # Log the error with detail
            logger.error(f"Error: The file contains invalid JSON: {str(e)}")
            logger.error("The error is likely caused by missing/extra commas or brackets.")

            # Print for immediate user feedback
            print(f"\nError: The file contains invalid JSON: {str(e)}")
            print("The error is usually caused by missing/extra commas or brackets.")

            retry = input("Would you like to try editing again? (y/n): ")
            if retry.lower() != 'y':
                logger.warning("Verification cancelled.")
                print("Verification cancelled.")
                os.unlink(json_path)
                raise
            # If retry, the loop continues and opens the editor again
        except Exception as e:
            # Log error for debugging and monitoring
            logger.error(f"Unexpected error: {str(e)}")

            # Print for immediate user feedback
            print(f"\nUnexpected error: {str(e)}")
            os.unlink(json_path)
            raise


def run_attribute_identification(state: WorkflowState) -> Dict[str, Any]:
    if 'attribute_identification' in state and state['attribute_identification']:
        logger.info("Skipping run_attribute_identification: 'attribute_identification' already in state")
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
                logger.warning("Workflow cancelled during attribute identification")
                return {}
            attribute_identification.append(attribution_text)
            logger.info(f"Identified attributes for components in {file}")

    return {"attribute_identification": attribute_identification}

def run_attribute_parsing(state: WorkflowState) -> Dict[str, Any]:
    if 'attribute_parsing' in state and state['attribute_parsing']:
        logger.info("Skipping run_attribute_parsing: 'attribute_parsing' already in state")
        return {}
    from rmr_agent.agents.attribute_parsing import parse_attribute_identification
    verified_components = state['verified_components']
    attribute_identification = state['attribute_identification']
    attribute_parsing = []

    # Get the config file path from the state if it exists
    existing_config_path = state.get('existing_config_path', '')
    config_file_path = ''

    if existing_config_path:
        # Convert relative path to absolute path using local_repo_path
        if state.get('local_repo_path') and not os.path.isabs(existing_config_path):
            config_file_path = os.path.join(state['local_repo_path'], existing_config_path)
        else:
            config_file_path = existing_config_path

        logger.info(f"Using config file path: {config_file_path}")

    with ThreadPoolExecutor() as executor:
        # Map processing across threads using a lambda, pass the config file path
        results = executor.map(
            lambda x: (x[0], *parse_attribute_identification(x[0], x[1], config_file_path)),
            zip(verified_components, attribute_identification)
        )

        for component_dict, parsed_attributes_text, parsed_attributes_dict in results:
            if is_cancelled(state):
                logger.warning("Workflow cancelled during attribute parsing")
                return {}
            attribute_parsing.append(parsed_attributes_dict)

    return {"attribute_parsing": attribute_parsing}

def run_node_aggregator(state: WorkflowState) -> Dict[str, Any]:
    if "node_aggregator" in state and state["node_aggregator"]:
        logger.info("Skipping run_node_aggregator: 'node_aggregator' already in state")
        return {}
    from rmr_agent.agents.node_aggregator import node_aggregator_agent
    nodes_yaml = node_aggregator_agent(state["attribute_parsing"])
    nodes_yaml_path = f"{CHECKPOINT_BASE_PATH}/{state['repo_name']}/{state['run_id']}/nodes.yaml"
    try:
        with open(nodes_yaml_path, 'w') as yaml_file:
            yaml_file.write(nodes_yaml)
        logger.info(f"YAML successfully exported to {nodes_yaml_path}")
    except Exception as e:
        logger.error(f"Error exporting YAML to {nodes_yaml_path}: {type(e).__name__}: {str(e)}")

    return {"node_aggregator": nodes_yaml}

def run_edge_identification(state: WorkflowState) -> Dict[str, Any]:
    if "edges" in state and state["edges"]:
        logger.info("Skipping run_edge_identification: 'edges' already in state")
        return {}
    from rmr_agent.agents.edge_identification import edge_identification_agent
    edges, edge_identification_response = edge_identification_agent(state["node_aggregator"])
    edge_id_justification_path = os.path.join(CHECKPOINT_BASE_PATH, state['repo_name'], state['run_id'], "edge_identification_response.txt")
    try:
        with open(edge_id_justification_path, 'w') as file:
            file.write(edge_identification_response)
        logger.info(f"Edge identification response successfully exported to {edge_id_justification_path}")
    except Exception as e:
        logger.error(f"Error exporting edge identification response to {edge_id_justification_path}: {type(e).__name__}: {str(e)}")
    return {"edges": edges}

def generate_dag_yaml(state: WorkflowState) -> Dict[str, Any]:
    if "verified_dag" in state and state["verified_dag"]:
        logger.info("Using verified_dag from human verification")
        dag_yaml_str = state["verified_dag"]

        dag_yaml_path = os.path.join(CHECKPOINT_BASE_PATH, state['repo_name'], state['run_id'], "dag.yaml")
        try:
            with open(dag_yaml_path, 'w') as yaml_file:
                yaml_file.write(dag_yaml_str)
            logger.info(f"Verified DAG YAML successfully exported to {dag_yaml_path}")
        except Exception as e:
            logger.error(f"Error exporting verified YAML to {dag_yaml_path}: {type(e).__name__}: {str(e)}")

        return {"dag_yaml": dag_yaml_str}

    if "dag_yaml" in state and state["dag_yaml"]:
        logger.info("Skipping generate_dag_yaml: 'dag_yaml' already in state")
        return {}

    # Generate new DAG
    from rmr_agent.agents.dag import generage_dag_yaml
    dag_yaml_str = generage_dag_yaml(aggregated_nodes=state["node_aggregator"], edges=state["edges"])

    # Clean the DAG to remove any component_details that might have been added
    dag_data = yaml.safe_load(dag_yaml_str)
    if dag_data and "nodes" in dag_data:
        cleaned_nodes = []
        for node in dag_data["nodes"]:
            if isinstance(node, dict):
                cleaned_node = {}
                for name, attrs in node.items():
                    # Remove component_details if present
                    if attrs and isinstance(attrs, dict) and 'component_details' in attrs:
                        attrs = {k: v for k, v in attrs.items() if k != 'component_details'}
                    cleaned_node[name] = attrs
                cleaned_nodes.append(cleaned_node)
        dag_data["nodes"] = cleaned_nodes

        # Convert back to YAML
        dag_yaml_str = yaml.dump(dag_data, sort_keys=False, default_flow_style=False)

    dag_yaml_path = os.path.join(CHECKPOINT_BASE_PATH, state['repo_name'], state['run_id'], "dag.yaml")
    try:
        with open(dag_yaml_path, 'w') as yaml_file:
            yaml_file.write(dag_yaml_str)
        logger.info(f"DAG YAML successfully exported to {dag_yaml_path}")
    except Exception as e:
        logger.error(f"Error exporting YAML to {dag_yaml_path}: {type(e).__name__}: {str(e)}")

    return {"dag_yaml": dag_yaml_str}

# def human_verification_of_dag(state: WorkflowState) -> Dict[str, Any]:
#     """This is a mock function that simulates human verification of the DAG."""
#     if "verified_dag" in state and state["verified_dag"]:
#         logger.info("Skipping human_verification: 'verified_dag' already in state")
#         return {}
#     response = requests.post("http://localhost:8000/verify_dag", json={"dag_yaml": state["dag_yaml"]})
#     if response.status_code != 200:
#         logger.error("Failed to send DAG for verification")
#         raise Exception("Failed to send DAG for verification")

#     logger.info("DAG sent for human verification, waiting for response")
#     while True:
#         verification_response = requests.get("http://localhost:8000/get_verified_dag")
#         if verification_response.status_code == 200 and verification_response.json().get("dag"):
#             logger.info("Received verified DAG from human verification")
#             result = {"verified_dag": verification_response.json()["dag"]}

#             # Check if there are actual modifications
#             dag_corrections = verification_response.json().get("dag_corrections", {})
#             if dag_corrections and any([
#                 dag_corrections.get("renamed_nodes"),
#                 dag_corrections.get("added_nodes"),
#                 dag_corrections.get("deleted_nodes"),
#                 dag_corrections.get("added_edges"),
#                 dag_corrections.get("deleted_edges"),
#                 dag_corrections.get("modified_edges"),
#                 dag_corrections.get("modified_nodes")
#             ]):
#                 # If there are modifications, add a flag
#                 result["human_verification_of_dag_corrections"] = True
#                 # Also save modification information
#                 result["dag_corrections"] = dag_corrections

#             return result
#         time.sleep(2)
def human_verification_of_dag(state: WorkflowState) -> Dict[str, Any]:
    """This is a mock function that simulates human verification of the DAG."""
    if "verified_dag" in state and state["verified_dag"]:
        logger.info("Skipping human_verification: 'verified_dag' already in state")
        return {}
    
    # Save the original DAG sent for verification
    original_dag_for_verification = state["dag_yaml"]
    
    # Add debug: Save pre-verification DAG to file
    debug_path = f"rmr_agent/checkpoints/{state['repo_name']}/{state['run_id']}/debug_dag_sent.yaml"
    with open(debug_path, 'w') as f:
        f.write(original_dag_for_verification)
    logger.info(f"Saved DAG sent for verification to: {debug_path}")
    
    # Calculate pre-verification DAG hash
    import hashlib
    original_hash = hashlib.md5(original_dag_for_verification.encode()).hexdigest()
    logger.info(f"DAG sent for verification hash: {original_hash}")
    
    response = requests.post("http://localhost:8000/verify_dag", json={"dag_yaml": original_dag_for_verification})
    if response.status_code != 200:
        logger.error("Failed to send DAG for verification")
        raise Exception("Failed to send DAG for verification")

    logger.info("DAG sent for human verification, waiting for response")
    while True:
        verification_response = requests.get("http://localhost:8000/get_verified_dag")
        if verification_response.status_code == 200 and verification_response.json().get("dag"):
            logger.info("Received verified DAG from human verification")
            verified_dag = verification_response.json()["dag"]
            
            # Save the received verified DAG
            debug_path_verified = f"rmr_agent/checkpoints/{state['repo_name']}/{state['run_id']}/debug_dag_received.yaml"
            with open(debug_path_verified, 'w') as f:
                f.write(verified_dag)
            logger.info(f"Saved received verified DAG to: {debug_path_verified}")
            
            # Calculate the post-verification DAG hash
            verified_hash = hashlib.md5(verified_dag.encode()).hexdigest()
            logger.info(f"DAG received after verification hash: {verified_hash}")
            
            # Direct comparison of the two DAG strings
            if original_dag_for_verification == verified_dag:
                logger.info("✅ DAG completely unmodified (strings exactly the same)")
                return {"verified_dag": verified_dag}
            else:
                logger.warning("⚠️ DAG modification detected")
                
                # Try to compare YAML content (ignoring format differences)
                import yaml
                try:
                    original_parsed = yaml.safe_load(original_dag_for_verification)
                    verified_parsed = yaml.safe_load(verified_dag)
                    
                    if original_parsed == verified_parsed:
                        logger.info("📝 DAG content identical, only format differs (YAML parsing matches)")
                        # Content is the same, just format is different, shouldn't record as a modification
                        return {"verified_dag": verified_dag}
                    else:
                        logger.warning("❌ DAG content was actually modified")
                        
                        # Only calculate corrections when the content is actually modified
                        from rmr_agent.utils.correction_logging import log_dag_corrections
                        dag_corrections = log_dag_corrections(original_dag_for_verification, verified_dag)
                        
                        # Print modification summary
                        logger.info(f"Modification summary: {dag_corrections.get('summary', {})}")
                        
                        result = {"verified_dag": verified_dag}
                        # Only add corrections when there are actual modifications
                        if dag_corrections and dag_corrections.get('summary', {}).get('correction_ratio', 0) > 0:
                            result["dag_corrections"] = dag_corrections
                            result["human_verification_of_dag_corrections"] = True
                        
                        return result
                except Exception as e:
                    logger.error(f"YAML parsing failed: {e}")
                    # If parsing fails, conservatively assume there are modifications
                    from rmr_agent.utils.correction_logging import log_dag_corrections
                    dag_corrections = log_dag_corrections(original_dag_for_verification, verified_dag)
                    return {
                        "verified_dag": verified_dag,
                        "dag_corrections": dag_corrections,
                        "human_verification_of_dag_corrections": True
                    }
        time.sleep(2)

def run_config_agent(state: WorkflowState) -> Dict[str, Any]:
    logger.debug(f"Current state keys: {state.keys()}")
    if "config" in state and state["config"]:
        logger.info("Skipping run_config_agent: 'config' already in state")
        return {}
    from rmr_agent.agents.ini_config import config_agent

    # Use verified_dag if available, otherwise use dag_yaml
    dag_to_use = state.get("verified_dag") or state.get("dag_yaml")
    if not dag_to_use:
        logger.error("No DAG available for config generation")
        raise ValueError("No DAG available for config generation")

    config = config_agent(dag_to_use)

    config_dir = os.path.join(state["local_repo_path"], "config")
    os.makedirs(config_dir, exist_ok=True)

    save_ini_file("environment.ini", config["environment_ini"], config_dir)
    save_ini_file("solution.ini", config["solution_ini"], config_dir)
    logger.info(f"Config files saved to {config_dir}")

    return {"config": config}

def run_notebook_agent(state: WorkflowState) -> Dict[str, Any]:
    logger.debug(f"DEBUG - cleaned_code type: {type(state['cleaned_code'])}")
    if "notebooks" in state and state["notebooks"]:
        logger.info("Skipping run_notebook_agent: 'notebooks' already in state")
        return {}

    from rmr_agent.agents.notebook import notebook_agent

    # Use verified_dag if available, otherwise use dag_yaml
    dag_to_use = state.get("verified_dag") or state.get("dag_yaml")
    if not dag_to_use:
        logger.error("No DAG available for notebook generation")
        raise ValueError("No DAG available for notebook generation")

    notebooks = notebook_agent(yaml.safe_load(dag_to_use), state["cleaned_code"], state["local_repo_path"])
    logger.info(f"Generated {len(notebooks)} notebooks")
    return {"notebooks": notebooks}

def run_code_editor_agent(state: WorkflowState) -> Dict[str, Any]:
    if "edited_notebooks" in state and state["edited_notebooks"]:
        logger.info("Skipping run_code_editor_agent: 'edited_notebooks' already in state")
        return {}

    from rmr_agent.agents.code_editor import code_editor_agent
    edited_notebooks = {}

    attribute_parsing_list = state["attribute_parsing"]
    attribute_config = {"attribute_parsing": attribute_parsing_list}

    logger.info("Starting code editing for notebooks")
    with ThreadPoolExecutor() as executor:
        results = executor.map(
            lambda item: (item[0], code_editor_agent(item[1], attribute_config)),
            state["notebooks"].items()
        )
        edited_notebooks = dict(results)

    logger.info(f"Edited {len(edited_notebooks)} notebooks")
    return {"edited_notebooks": edited_notebooks}


def create_pr_body(state: WorkflowState) -> Dict[str, Any]:
    if "pr_body" in state and state["pr_body"]:
        logger.info("Skipping create_pr_body: 'pr_body' already in state")
        return {}

    from rmr_agent.utils import generate_pr_body

    checkpoint_dir = os.path.join(CHECKPOINT_BASE_PATH, state['repo_name'], state['run_id'])
    if not os.path.exists(checkpoint_dir):
        logger.error(f"Checkpoint directory {checkpoint_dir} does not exist. Please run the workflow first.")
        raise FileNotFoundError(f"Checkpoint directory {checkpoint_dir} does not exist. Please run the workflow first.")

    # Generate the PR body (markdown file) to include in the push & PR
    pr_body = generate_pr_body(checkpoints_dir_path=checkpoint_dir)
    logger.info("Generated PR body")
    logger.debug(f"PR body content:\n{pr_body}")

    # Save the PR body to a markdown file
    pr_body_save_path = os.path.join('rmr_agent', 'repos', state['repo_name'], "rmr_agent_results.md")
    try:
        with open(pr_body_save_path, 'w') as f:
            f.write(pr_body)
        logger.info(f"PR body saved to {pr_body_save_path}")
    except Exception as e:
        logger.error(f"Error saving PR body to {pr_body_save_path}: {type(e).__name__}: {str(e)}")

    return {"pr_body": pr_body}

def push_code_changes(state: WorkflowState) -> Dict[str, Any]:
    if "successfully_pushed_code" in state and state["successfully_pushed_code"]:
        logger.info("Skipping push_code_changes: 'successfully_pushed_code' already True in state")
        return {}
    from rmr_agent.utils import push_refactored_code

    checkpoint_dir = os.path.join(CHECKPOINT_BASE_PATH, state['repo_name'], state['run_id'])
    if not os.path.exists(checkpoint_dir):
        logger.error(f"Checkpoint directory {checkpoint_dir} does not exist. Please run the workflow first.")
        raise FileNotFoundError(f"Checkpoint directory {checkpoint_dir} does not exist. Please run the workflow first.")

    # Push the refactored code and pr_body markdown file to the repository
    logger.info("Pushing refactored code to repository")
    successfully_pushed_code = push_refactored_code(github_url=state['github_url'], run_id=state['run_id'])
    logger.info(f"Code push successful: {successfully_pushed_code}")
    return {"successfully_pushed_code": successfully_pushed_code}

def run_pr_creation(state: WorkflowState) -> Dict[str, Any]:
    # Check environment variable to control whether to create a real PR
    env_mode = os.environ.get("ENVIRONMENT", "").lower()
    if env_mode == "dev":
        logger.info("Running in DEV mode. Skipping actual PR creation.")
        logger.info(f"PR would have been created with title: 'RMR Agent Refactor - Run {state['run_id']}'")

        # Return mock PR URL to avoid errors in subsequent steps
        mock_pr_url = f"https://github.com/example/repo/pull/DEV-MODE-{state['run_id']}"
        logger.info(f"Mock PR URL: {mock_pr_url}")
        return {"pr_url": mock_pr_url}

    if "pr_url" in state and state["pr_url"]:
        logger.info("Skipping PR creation: 'pr_url' already in state")
        return {}
    if "successfully_pushed_code" in state and not state["successfully_pushed_code"]:
        logger.warning("Skipping PR creation: Code changes must be successfully pushed before creating a PR.")
        return {}

    from rmr_agent.utils import create_rmr_agent_pull_request

    logger.info("Creating pull request")
    pr_url = create_rmr_agent_pull_request(github_url=state["github_url"], pr_body_text=state["pr_body"], run_id=state["run_id"])
    logger.info(f"Pull request created: {pr_url}")
    return {"pr_url": pr_url}



# Define steps requiring human input
HUMAN_STEPS = {"human_verification_of_components", "human_verification_of_dag"}

# Define all steps (without human verification functions, as they'll be API-driven)
STEPS = [
    ("fork_and_clone_repository", fork_and_clone_repository),
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
    ("notebook_agent", run_notebook_agent),
    ("code_editor_agent", run_code_editor_agent),
    ("create_pr_body", create_pr_body),
    ("push_code_changes", push_code_changes),
    ("create_pull_request", run_pr_creation)
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
    "fork_clone_url": "",
    "existing_config_path": "",
    "files": [],
    "summaries": {},
    "cleaned_code": {},
    "component_identification": [],
    "component_parsing": [],
    "verified_components": [],
    "component_corrections": {},  # Added for logging human corrections to components
    "attribute_identification": [],
    "attribute_parsing": [],
    "node_aggregator": [],
    "edges": [],
    "dag_yaml": "",
    "verified_dag": {},
    "dag_corrections": {},  # Added for logging human corrections to DAG
    "config": {},
    "notebooks": [],
    "edited_notebooks": [],
    "pr_body": "",
    "successfully_pushed_code": False,
    "pr_url": ""
}

def build_workflow():
    from langgraph.graph import StateGraph, END
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

    logger.info(f"Starting workflow for {github_url}, run_id: {run_id}")
    if start_from:
        logger.info(f"Starting from step: {start_from}")

    state = INITIAL_STATE.copy()
    state["step"] = step_name
    state["status"] = status
    state["github_url"] = github_url
    state["input_files"] = input_files
    state["repo_name"] = repo_name
    state["run_id"] = run_id
    if existing_config_path:
        state["existing_config_path"] = existing_config_path
        logger.info(f"Using existing config path: {existing_config_path}")

    # Load state up to the start_from step
    start_idx = 0 if not start_from else next(i for i, (step, _) in enumerate(STEPS) if step == start_from)
    for step_name, _ in STEPS[:start_idx]:
        logger.info(f"Loading previous step output: {step_name}")
        step_output = load_step_output(checkpoint_base_path=CHECKPOINT_BASE_PATH, repo_name=repo_name, run_id=run_id, step=step_name)
        state.update(step_output)

    # Run from start_from onward
    for step_name, step_func in STEPS[start_idx:]:
        if step_name in HUMAN_STEPS:
            logger.info(f"Starting human verification step: {step_name}")
        else:
            logger.info(f"Starting step: {step_name}")

        update = step_func(state)

        if update:
            state.update(update)
            if step_name in HUMAN_STEPS and not update.get(f"{step_name}_corrections"):
                logger.debug(f"Skipping save for {step_name} as no corrections were made")
            else:
                save_step_output(checkpoint_base_path=CHECKPOINT_BASE_PATH, repo_name=repo_name, run_id=run_id, step=step_name, output=update)
        logger.info(f"Completed step: {step_name}")

    logger.info("Workflow completed successfully")
    return state



if __name__ == "__main__":
    # Configure logging for CLI usage
    logger = setup_logger(__name__, level=logging.INFO)

    parser = argparse.ArgumentParser(description="Run the workflow with a GitHub URL and input files.")
    parser.add_argument("--github-url", type=str, required=True, help="GitHub repository URL")
    parser.add_argument("--input-files", type=str, nargs="+", required=True, help="List of input file paths (e.g., 'notebooks/notebook1.ipynb') from the root directory of repo")
    parser.add_argument("--run-id", type=str, default=None, help="Set if want to use 'start-from' tag, we will load checkpoints from this run_id (e.g. 1, 2, 3, etc.)")
    parser.add_argument("--start-from", type=str, default=None, help="Step to start from (e.g., 'summarize', 'component_identification')")
    parser.add_argument("--existing-config-path", type=str, default=None, help="If you already have a config in research code, specify its path from root directory of repo")
    parser.add_argument("--debug", action="store_true", help="Enable debug logging")

    args = parser.parse_args()

    if args.debug:
        logger.setLevel(logging.DEBUG)
        logger.debug("Debug logging enabled")

    logger.info("Starting RMR Agent workflow")
    result = run_workflow(
        github_url=args.github_url,
        input_files=args.input_files,
        run_id=args.run_id,
        start_from=args.start_from,
        existing_config_path=args.existing_config_path
    )

    logger.info("Workflow completed successfully")
    logger.info(f"Config files created: {list(result.get('config', {}).keys())}")
    logger.info(f"Number of generated notebooks: {len(result.get('notebooks', []))}")





