import streamlit as st
import requests
import json
import sys
import time
import yaml
from rmr_agent.utils import parse_github_url 

BASE_URL = "http://localhost:8000"
CHECKPOINT_BASE_PATH = "rmr_agent/checkpoints"


sys.stdout.flush()

# Maximize layout width
st.set_page_config(layout="wide")

# Define steps requiring human input
HUMAN_STEPS = {"human_verification_of_components", "human_verification_of_dag"}

# Define all steps (without human verification functions, as they'll be API-driven)
STEPS = [
    "clone_and_prepare_repo", 
    "summarize",
    "component_identification", 
    "component_parsing", 
    "human_verification_of_components", 
    "attribute_identification", 
    "attribute_parsing", 
    "node_aggregator", 
    "edge_identification", 
    "generate_dag_yaml", 
    "human_verification_of_dag",
    "config_agent", 
    "notebook_agent"
]


def clean_file_path(file_path, repo_name, repos_base_dir="rmr_agent/repos/"):
    prefix = repos_base_dir + repo_name + "/"
    cleaned_file_path = file_path.replace('.py', '.ipynb')
    if file_path.startswith(prefix):
        return cleaned_file_path[len(prefix):]
    return cleaned_file_path

def remove_line_numbers(code_lines):
    cleaned_lines = []
    for line in code_lines:
        cleaned_lines.append(line.split('|')[-1])
    return cleaned_lines

def clean_line_range(line_range: str):
    return line_range.lower().split('lines')[-1].strip()

def get_components(repo_name, run_id):
    try:
        with open(f"{CHECKPOINT_BASE_PATH}/{repo_name}/{run_id}/component_parsing.json", 'r') as file:
            components = json.load(file)
        return components['component_parsing']
    except FileNotFoundError:
        raise FileNotFoundError(f"Component parsing file not found for repo: {repo_name}, run_id: {run_id}")
    except json.JSONDecodeError as e:
        raise json.JSONDecodeError(f"Invalid JSON in component parsing file: {e.msg}", e.doc, e.pos)
    except IOError as e:
        raise IOError(f"Error reading component parsing file: {str(e)}")


def get_cleaned_code(repo_name, run_id):
    try:
        with open(f"{CHECKPOINT_BASE_PATH}/{repo_name}/{run_id}/summarize.json", 'r') as file:
            content = json.load(file)
        return content['cleaned_code']
    except FileNotFoundError:
        raise FileNotFoundError(f"Summarize file not found for repo: {repo_name}, run_id: {run_id}")
    except json.JSONDecodeError as e:
        raise json.JSONDecodeError(f"Invalid JSON in summarize file: {e.msg}", e.doc, e.pos)
    except KeyError:
        raise KeyError(f"Missing 'cleaned_code' key in summarize file for repo: {repo_name}, run_id: {run_id}")
    except IOError as e:
        raise IOError(f"Error reading summarize file: {str(e)}")


def get_dag_yaml(repo_name, run_id):
    try:
        with open(f"{CHECKPOINT_BASE_PATH}/{repo_name}/{run_id}/dag.yaml", 'r') as file:
            # dag_yaml = yaml.safe_load(file)
            dag_yaml_str = file.read()
            print("Successfully loaded dag.yaml")
        return dag_yaml_str
    except FileNotFoundError:
        raise FileNotFoundError(f"DAG YAML file not found for repo: {repo_name}, run_id: {run_id}")
    except yaml.YAMLError as e:
        raise yaml.YAMLError(f"Invalid YAML in DAG file: {str(e)}")
    except IOError as e:
        raise IOError(f"Error reading DAG YAML file: {str(e)}")

def get_default_line_range(selected_components, cleaned_code):
    if len(selected_components) == 1:
        return f"1-{len(cleaned_code)}"
    return "Specify line range here (e.g. 1-40)"



# Initialization of session state
if "display_welcome_page" not in st.session_state:
    st.session_state["display_welcome_page"] = True
if "workflow_running" not in st.session_state:
    st.session_state.workflow_running = False
if "current_step" not in st.session_state:
    st.session_state["current_step"]= None
if "result" not in st.session_state:
    st.session_state["result"] = None
if "current_file_index" not in st.session_state:
    st.session_state["current_file_index"] = 0
if "edited_components_list" not in st.session_state:
    st.session_state["edited_components_list"] = []
if 'github_url' not in st.session_state:
    st.session_state["github_url"] = None
if 'repo_name' not in st.session_state:
    st.session_state["repo_name"] = None
if 'run_id' not in st.session_state:
    st.session_state["run_id"] = None
if 'start_from' not in st.session_state:
    st.session_state["start_from"] = None
if 'last_status' not in st.session_state:
    st.session_state["last_status"] = None



def display_welcome_page():
    if st.session_state.workflow_running == True:
        return
    st.title("RMR Agent")
    st.subheader("Welcome to RMR Agent!")
    st.write("Convert your ML research code into a robust, modular, and configurable RMR pipeline.")
    st.session_state["github_url"] = st.text_input("Specify the GitHub URL for your ML code", "https://github.paypal.com/GADS-Consumer-ML/ql-store-recommendation-prod.git")
    st.session_state["input_files"] = st.text_area("List the notebooks in your repo which contain the core ML logic (one per line, relative to repo root directory)", "research/pipeline/00_driver.ipynb\nresearch/pipeline/01_bq_feat.ipynb\nresearch/pipeline/01_varmart_feat.ipynb\nresearch/pipeline/02_combine.ipynb\nresearch/pipeline/03_prepare_training_data.ipynb\nresearch/pipeline/04_training.ipynb\nresearch/pipeline/05_scoring_oot.ipynb\nresearch/pipeline/06_evaluation.ipynb").splitlines()
    st.session_state["run_id"] = st.text_input("Run ID (optional)", "1", help="Enter an existing run ID (e.g. 1, 2, 3) to resume, or leave blank for a new run")
    st.session_state["start_from"] = st.selectbox(
        "Start From (optional)",
        [""] + [step for step in STEPS],  # Empty option + all step names
        help="Choose a step to start from, or leave blank to start from the beginning"
    )



def start_workflow():
    """Function to start the workflow after the user presses Start Workflow button"""
    _, repo_name = parse_github_url(st.session_state["github_url"])
    print('Repo name:', repo_name)
    st.session_state["repo_name"] = repo_name
    payload = {
        "github_url": st.session_state["github_url"],
        "input_files": st.session_state["input_files"]
    }
    # Add optional fields if provided
    if st.session_state["run_id"]:
        payload["run_id"] = st.session_state["run_id"]
    if st.session_state["start_from"]:
        payload["start_from"] = st.session_state["start_from"]
    
    # Construct url with repo_name and run_id (if specified)
    url = f"{BASE_URL}/run-workflow/?repo_name={repo_name}"
    if st.session_state["run_id"]:
        url += f"&run_id={st.session_state["run_id"]}"

    with st.spinner("Starting workflow..."):
        response = requests.post(url, json=payload)
    if response.status_code == 200:
        data = response.json()
        st.session_state["result"] = data
        st.session_state["run_id"] = data["run_id"]
        st.session_state.workflow_running = True
        st.session_state["last_status"] = "running"
        st.session_state['current_step'] = st.session_state["start_from"] if st.session_state["start_from"] else STEPS[0]
        st.session_state["display_welcome_page"] = False # remove welcome page now that workflow has started
        st.success(f"Starting workflow for run_id={data["run_id"]}")
        time.sleep(1)  # Brief pause to show the success message
        st.rerun() # update UI
    else:
        st.error(f"Error: {response.text}")


def check_workflow_status():
    """Function to poll for the current workflow status"""
    if not st.session_state.workflow_running or not st.session_state["run_id"]:
        return
    
    try:
        response = requests.get(
            f"{BASE_URL}/workflow-status/{st.session_state["repo_name"]}?run_id={st.session_state.run_id}"
        )
        
        print(response.status_code)

        if response.status_code == 200:
            data = response.json()
            status = data.get("status")
            current_step = data.get("step")
            #print(data)
            
            # Update the session state with latest info
            st.session_state["result"] = data
            st.session_state["last_status"] = status
            st.session_state["current_step"] = current_step
            
            if st.session_state["current_step"] in HUMAN_STEPS:
                # Found a human verification step - stop auto-polling
                print(f"Human verification step detected: {current_step}")
                st.session_state.workflow_running = False
                st.rerun()
            elif status == "completed":
                st.session_state.workflow_running = False
                st.success("Workflow completed successfully!")
            elif status == "failed":
                st.session_state.workflow_running = False
                st.error(f"Workflow failed: {data.get('error', 'Unknown error')}")
                
            # If still running, we'll check again on next rerun
                
    except Exception as e:
        st.warning(f"Error checking workflow status: {e}")

def submit_human_feedback(payload, repo_name, run_id):
    url = f"{BASE_URL}/run-workflow/?repo_name={repo_name}&run_id={run_id}"
    print(f"Submitting human feedback to: {url}, Payload: {payload}")
    response = requests.post(url, json=payload)
    print(f"Submit Status: {response.status_code}, Response: '{response.text}'")
    if response.status_code == 200:
        st.session_state["result"] = response.json()
        st.session_state.workflow_running = True
        st.success("Feedback submitted successfully!")
        time.sleep(1)  # Brief pause to show the success message
        st.rerun()
    else:
        st.error(f"Submit Error: {response.text}")

def display_progress(current_step):
    # Calculate progress based on current step position
    total_steps = len(STEPS)
    current_step_idx = STEPS.index(current_step)
    if current_step == "complete":
        completed_steps = total_steps
    else:
        completed_steps = current_step_idx + 1 if current_step_idx >= 0 else 0
    
    # Display progress
    st.progress(completed_steps / total_steps)
    st.write(f"Progress: {completed_steps}/{total_steps} steps completed")

    print(f"Current Steps List: {STEPS}")
    print(f"Current Step Received: {current_step}")


def cancel_workflow_button():
    # Cancel button
    if st.button("Cancel Workflow", type="primary", key="cancel_workflow"):
        # Make API call to cancel the workflow
        cancel_url = f"{BASE_URL}/cancel-workflow/{st.session_state["repo_name"]}?run_id={st.session_state["run_id"]}"
        try:
            cancel_response = requests.post(cancel_url)
            
            if cancel_response.status_code == 200:
                st.session_state.workflow_running = False
                st.session_state["display_welcome_page"] = True
                st.success("Workflow cancelled successfully")
                time.sleep(1)  # Give user time to see the success message
                st.rerun()
            else:
                st.error(f"Failed to cancel: {cancel_response.text}")
        except Exception as e:
            st.error(f"Error sending cancellation request: {str(e)}")

def back_to_home_button():
    if st.button("Back to Home", key="back_to_home"):
        # Reset session state and return to home screen
        st.session_state.workflow_running = False
        st.session_state["display_welcome_page"] = True
        st.session_state.pop("result", None)  # Clear result if needed
        st.success("Returning to home screen...")
        # time.sleep(1)  # Brief delay for user feedback
        st.rerun()

def human_verification_of_components_ui(repo_name, run_id):
    st.subheader("ML Component Verification")

    # Load available ML components with their descriptions
    with open("rmr_agent/ml_components/component_definitions.json", 'r') as file:
        ml_components = json.load(file)

    # Display all ML component descriptions as a reference
    st.sidebar.subheader("Descriptions for Available ML Components")
    for component_name, description in ml_components.items():
        with st.sidebar.expander(component_name):
            st.write(description)

    components = get_components(repo_name, run_id) # result["components"] # loading from checkpoint instead of from API result
    if not isinstance(components, list):
        st.error("Components should be a non-empty list of dictionaries")
    if not components:
        st.error("Retrieved components is empty")
    
    total_files = len(components)
    current_index = st.session_state["current_file_index"]

    # Initialize edited_components_list with empty dicts for all files
    if not st.session_state["edited_components_list"]:
        st.session_state["edited_components_list"] = [{} for _ in range(total_files)]

    if current_index >= total_files:
        st.success("All files verified! Submitting...")
    else:
        # Current file’s components dictionary
        current_components_dict = components[current_index]
        file_name = next(iter(current_components_dict.values()))["file_name"]  # Get from first component
        cleaned_file_name = clean_file_path(file_name, repo_name)
        st.write("Current file:")
        st.write(f"     - **{cleaned_file_name}** ({current_index + 1}/{total_files})")

        # Existing component names (identified by agent)
        existing_component_names = list(current_components_dict.keys())

        # Multiselect to keep/delete/add component names
        selected_components = st.multiselect(
            "Components identified in this file (please verify):",
            options=list(ml_components.keys()),
            default=existing_component_names,
            key=f"components_{current_index}"
        )

        # Get the cleaned code for the current file
        cleaned_code = get_cleaned_code(repo_name, run_id) # result.get("cleaned_code", {}) # loading from checkpoint instead of from API result
        if not cleaned_code:
            st.error(f"Could not recover cleaned code for file {file_name}")

        if file_name in cleaned_code:
            code_lines = cleaned_code[file_name].splitlines()
        else:
            st.error(f"file_name = {file_name} not found in cleaned_code dict, keys = {list(cleaned_code.keys())}")

        # Store edited components and verify line ranges
        edited_components_dict = {}
        code_display = code_lines if file_name in cleaned_code else []
        code_display = remove_line_numbers(code_display) # line numbers will already be shown by streamlit
        for component_name in selected_components:
            # Base details (existing or new)
            if component_name in current_components_dict:
                details = current_components_dict[component_name].copy()
            else:
                details = {
                    "evidence": ["Added manually during verification"],
                    "why_separate": "Added manually during verification",
                    "file_name": file_name,
                    "line_range": get_default_line_range(selected_components, code_display)
                }
            
            with st.expander(f"Details for **{component_name}** - needs verification!"):
                st.write(f"Please correct the line range for this component by viewing the cleaned code below")
                line_range_identified = clean_line_range(details["line_range"])
                # Always allow line_range editing
                line_range = st.text_input(
                    "**Line Range**:",
                    value=line_range_identified,
                    key=f"{current_index}_{component_name}_line_range"
                )
                
                # Highlight code for this component
                if code_display:
                    st.write(f"**Cleaned Code** ({len(code_display)} lines):")
                    try:
                        start, end = map(int, line_range.split("-"))
                        highlighted_code = "\n".join(
                            f"{i+1}: {line}" if start <= i+1 <= end else f"{i+1}: {line}"
                            for i, line in enumerate(code_display)
                        )
                        st.code(highlighted_code, language="python")
                    except (ValueError, AttributeError):
                        st.code("\n".join(f"{i+1}: {line}" for i, line in enumerate(code_display)), language="python")
                        st.warning("Invalid line range format. Use 'start-end'.")
                else:
                    st.error("Could not display code for this file")
                
                # Show evidence and why_separate for existing components
                if component_name in current_components_dict:
                    st.write("**Evidence for this ML component classification**:")
                    for evidence in details["evidence"]:
                        st.write(f"- {evidence}")
                    if len(current_components_dict) > 1:
                        # Only show separation reasoning if we performed a separation in this file (idenfitied more than one component)
                        st.write(f"**Why this was identified as a separate component**:\n{details['why_separate']}")
            
            # Update line_range and store
            details["line_range"] = line_range
            edited_components_dict[component_name] = details

        # Navigation
        col1, col2 = st.columns(2)
        with col1:
            if st.button("Previous", disabled=(current_index == 0)):
                st.session_state["edited_components_list"][current_index] = edited_components_dict
                st.session_state["current_file_index"] -= 1
                st.rerun()
        with col2:
            if st.button("Next", disabled=(current_index >= total_files - 1)):
                st.session_state["edited_components_list"][current_index] = edited_components_dict
                st.session_state["current_file_index"] += 1
                st.rerun()
    
        # Submit all when done
        if current_index == total_files - 1 and st.button("Submit All Components"):
            st.session_state["edited_components_list"].append(edited_components_dict)
            payload = {"verified_components": st.session_state["edited_components_list"]}
            st.session_state.workflow_running = True # before submit back to API, set workflow running again to continue polling
            submit_human_feedback(payload=payload, repo_name=repo_name, run_id=run_id)
            st.session_state["edited_components_list"] = []

def human_verification_of_dag_ui(repo_name, run_id):
    # WIP -> improve DAG editing experience. Should focus on editing edges because nodes were already verified
    st.subheader("Please verify/edit the identified DAG")
    dag_yaml = get_dag_yaml(repo_name, run_id) # result["dag_yaml"] # loading from checkpoint instead of from API result
    edited_dag = st.text_area("DAG YAML", dag_yaml, height=300)
    if st.button("Submit DAG"):
        payload = {"verified_dag": edited_dag}
        st.session_state.workflow_running = True # before submit back to API, set workflow running again to continue polling
        submit_human_feedback(payload=payload, repo_name=repo_name, run_id=run_id)



# UI welcome page before starting workflow
if st.session_state["display_welcome_page"] == True:
    display_welcome_page()

    # Start workflow
    if st.button("Start Workflow"):
        start_workflow()

# Status display while workflow is running in backend 
elif st.session_state.workflow_running:
    cancel_workflow_button()

    if 'status_placeholder' not in st.session_state:
        st.session_state["status_placeholder"] = st.empty()
    
    # Calculate and display progress bar
    current_step = st.session_state['current_step']
    current_step_clean = current_step.replace("_", " ").title()
    display_progress(current_step)
    print(f"Running step: {current_step_clean}")
    
    # Display current status with a spinner
    with st.session_state["status_placeholder"].container():
        with st.spinner(f"Running step: {current_step_clean}"):
            # Display additional info if needed
            st.info(f"Workflow run_id = {st.session_state['run_id']}")
            st.info(f"Status = {st.session_state['last_status']}")
        
            # Check status (this happens on every rerun)
            check_workflow_status()
            
            # Auto-refresh using a timeout
            if st.session_state.workflow_running:
                time.sleep(3)  # Wait 3 seconds
                st.rerun()  # Trigger a rerun to check status again


# Handle human verification steps and workflow completion
else: 
    back_to_home_button()
    result = st.session_state["result"]
    repo_name = result.get("repo_name")
    run_id = result.get("run_id")
    current_step = result["step"]
    print('handling a human step: ', current_step)

    # Calculate and display progress bar
    display_progress(current_step)
    
    if current_step == "human_verification_of_components":
        human_verification_of_components_ui(repo_name, run_id)
    elif current_step == "human_verification_of_dag":
        human_verification_of_dag_ui(repo_name, run_id)
    elif current_step == "complete":
        st.session_state.workflow_running=False
        st.success("Workflow Complete!")
        st.json(result["result"])




# Run: streamlit run ui.py