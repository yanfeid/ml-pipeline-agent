import sys
import streamlit as st
import requests
import json
import time
from datetime import datetime
from streamlit import rerun
from rmr_agent.utils import parse_github_url 
from rmr_agent.workflow import STEPS, HUMAN_STEPS
from rmr_agent.frontend.ui_utils import (
    clean_file_path, remove_line_numbers, clean_line_range,
    get_components, get_cleaned_code, get_dag_yaml,
    get_default_line_range, get_steps_could_start_from,
    dag_edge_editor
)

BASE_URL = "http://localhost:8000"
#BASE_URL = "http://rmr-agent-api:8000"

sys.stdout.flush()

# Maximize layout width
st.set_page_config(layout="wide")

# Define all step names
STEPS = [step_name for step_name, _ in STEPS]

# Initialization of session state
if 'github_url' not in st.session_state:
    st.session_state["github_url"] = None
if 'repo_name' not in st.session_state:
    st.session_state["repo_name"] = None
if 'run_id' not in st.session_state:
    st.session_state["run_id"] = None
if 'input_files' not in st.session_state:
    st.session_state["input_files"] = None
if 'start_from' not in st.session_state:
    st.session_state["start_from"] = None
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
if 'last_status' not in st.session_state:
    st.session_state["last_status"] = None



def display_welcome_page():
    if st.session_state.workflow_running == True:
        return
    # st.title("RMR Agent")
    st.image("assets/rmr_agent_image.jpg", width=500)
    st.subheader("Welcome to RMR Agent!")
    st.write("Convert your ML research code into a robust, modular, and configurable RMR pipeline.")
    # Take in github url
    default_url = st.session_state["github_url"] if st.session_state["github_url"] else "https://github.paypal.com/dnaomi/bt-retry-v2"
    st.session_state["github_url"] = st.text_input("Specify the GitHub URL for your ML code", default_url)
    _, st.session_state["repo_name"] = parse_github_url(st.session_state["github_url"])
    # Take in input ML files
    default_input_files = "\n".join(st.session_state["input_files"]) if st.session_state["input_files"] else "etl/01_etl.ipynb\netl/02_bq_to_dataproc.ipynb\nmodel-dev/train.ipynb\nmodel-dev/evaluate.ipynb\ndeployment/01_export_to_ume.ipynb\ndeployment/02_pyscoring_validation.ipynb"
    input_files = st.text_area("List the notebooks in your repo which contain the core ML logic (one per line, relative to repo root directory)", default_input_files).splitlines()
    st.session_state["input_files"] = [file for file in input_files if file]
    # Take in run id
    default_run_id = st.session_state["run_id"] if st.session_state["run_id"] else "1"
    st.session_state["run_id"] = st.text_input("Run ID (optional)", default_run_id, help="Enter an existing run ID (e.g. 1, 2, 3) to resume, or leave blank for a new run")
    # Allow starting from specific step
    start_from = st.selectbox(
        "Start From (optional)",
        [""] + get_steps_could_start_from(st.session_state["repo_name"], st.session_state["run_id"], STEPS),  # Empty option + all step names
        help="Choose a step to start from, or leave blank to start from the beginning"
    )
    st.session_state["start_from"] = start_from.split('.')[-1].strip().lower().replace(" ", "_")
    print(st.session_state["start_from"])
    # allow specifying existing config file if their code leverages one
    # TO DO: let user set config file path in their repo if they are using a configuration file already during research




def start_workflow():
    """Function to start the workflow after the user presses Start Workflow button"""
    if not st.session_state["repo_name"]:
        _, st.session_state["repo_name"] = parse_github_url(st.session_state["github_url"])
    print('Repo name:', st.session_state["repo_name"])
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
    url = f"{BASE_URL}/run-workflow/?repo_name={st.session_state["repo_name"]}"
    if st.session_state["run_id"]:
        url += f"&run_id={st.session_state["run_id"]}"

    with st.spinner("Starting workflow..."):
        response = requests.post(url, json=payload)
    if response.status_code == 200:
        data = response.json()
        st.session_state["result"] = data
        st.session_state["run_id"] = data["run_id"]
        st.session_state["last_status"] = "running"
        st.session_state['current_step'] = st.session_state["start_from"] if st.session_state["start_from"] else "starting"
        st.session_state.workflow_running = True if st.session_state['current_step'] not in HUMAN_STEPS else False
        st.session_state["display_welcome_page"] = False # remove welcome page now that workflow has started
        st.success(f"Starting workflow for run_id={data["run_id"]}")
        time.sleep(0.5)  # Brief pause to show the success message
        st.rerun() # update UI
    else:
        st.error(f"Error: {response.text}")


def check_workflow_status():
    """Function to poll for the current workflow status"""
    try:
        response = requests.get(
            f"{BASE_URL}/workflow-status/{st.session_state["repo_name"]}?run_id={st.session_state.run_id}"
        )
        
        print(response.status_code)

        if response.status_code == 200:
            data = response.json()
            status = data.get("status")
            current_step = data.get("step")
            print(f"{datetime.now().strftime("%H:%M:%S")} Poll API returned - Status: {status}, Step: {current_step}")

            step_changed = False
            prev_step = st.session_state.get("current_step", "")
            if prev_step != current_step:
                step_changed = True
                print(f"Step changed from '{prev_step}' to '{current_step}'")
            
            # Update the session state with latest info
            st.session_state["result"] = data
            st.session_state["last_status"] = status
            st.session_state["current_step"] = current_step
            
            if st.session_state["current_step"] in HUMAN_STEPS:
                # Found a human verification step - stop auto-polling
                print(f"Human verification step detected: {current_step}")
                st.session_state.workflow_running = False
            elif st.session_state["current_step"] == "complete":
                print("✅ backend returned complete status")
                st.session_state.workflow_running = False
                st.session_state["workflow_complete"] = True
                st.rerun()
                st.success("Workflow completed successfully!")
            elif status == "failed":
                st.session_state.workflow_running = False
                st.error(f"Workflow failed: {data.get('error', 'Unknown error')}")
                
            return step_changed
                
    except Exception as e:
        st.warning(f"Error checking workflow status: {e}")

def submit_human_feedback(payload, repo_name, run_id):
    url = f"{BASE_URL}/run-workflow/?repo_name={repo_name}&run_id={run_id}"
    print(f"Submitting human feedback to: {url}, Payload: {payload}")
    response = requests.post(url, json=payload)
    print(f"Submit Status: {response.status_code}, Response: '{response.text}'")
    if response.status_code == 200:
        data = response.json()
        st.session_state["result"] = data
        st.session_state.workflow_running = True
        st.session_state["current_step"] = data["step"]
        st.session_state["last_status"] = data["status"]
        st.success("Feedback submitted successfully!")
        time.sleep(1)  # Brief pause to show the success message
        st.rerun()
    else:
        st.error(f"Submit Error: {response.text}")

def display_progress_bar(current_step, write_cur_step=True):
    if current_step not in STEPS:
        return 
    # Calculate progress based on current step position
    total_steps = len(STEPS)
    current_step_idx = STEPS.index(current_step)
    if current_step == "complete":
        completed_steps = total_steps
    else:
        completed_steps = current_step_idx if current_step_idx >= 0 else 0
    
    # Display progress
    st.progress(completed_steps / total_steps)
    st.write(f"Progress: {completed_steps}/{total_steps} steps completed")
    if write_cur_step:
        st.write(f"Running step {st.session_state["current_step"].replace("_", " ").title()} ...")

def display_detailed_progress(current_step):
    if current_step not in STEPS:
        return
    # Sidebar: Detailed step list
    if "sidebar_placeholder" not in st.session_state:
        st.session_state["sidebar_placeholder"] = st.sidebar.empty()
    markdown_content = "### Workflow Steps\n\n"  # Plain text header
    current_step_idx = STEPS.index(current_step)
    for idx, step in enumerate(STEPS):
        if idx < current_step_idx:
            status_icon = "✅"
        elif idx == current_step_idx:
            status_icon = "⏳"
        else:
            status_icon = "⬜"
        
        # Human-readable step name
        step_name = step.replace("_", " ").title()

        # Append step to the markdown string
        markdown_content += f"{status_icon} **{idx + 1}. {step_name}**\n\n"
        
    # Display step in sidebar with icon and status
    st.session_state["sidebar_placeholder"].markdown(markdown_content)


def cancel_workflow_button():
    # Cancel button
    if st.button("Cancel Workflow", type="primary", key="cancel_workflow"):
        st.write("Cancelling workflow...")
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

    # Load available ML components with their descriptions
    with open("rmr_agent/ml_components/component_definitions.json", 'r') as file:
        ml_components = json.load(file)

    # Display all ML component descriptions as a reference
    st.sidebar.subheader("Descriptions for Available ML Components")
    for component_name, description in ml_components.items():
        with st.sidebar.expander(component_name):
            st.write(description)

    # Load identified components
    components = get_components(repo_name, run_id) # result["components"] # loading from checkpoint instead of from API result
    if not isinstance(components, list):
        st.error("Components should be a non-empty list of dictionaries")
    if not components:
        st.error("Retrieved components is empty")

    # Get index for current file we are validating components for
    total_files = len(components)
    current_index = st.session_state["current_file_index"]

    # Initialize edited_components_list with empty dicts for all files
    if not st.session_state["edited_components_list"]:
        st.session_state["edited_components_list"] = [{} for _ in range(total_files)]
    
    if current_index >= total_files:
        st.success("All files verified! Submitting...")
    else:
        # Current file’s components dictionary
        if (
            "edited_components_list" in st.session_state and
            current_index < len(st.session_state["edited_components_list"]) and
            st.session_state["edited_components_list"][current_index]
        ):
            # Load from the edited version in session state
            current_components_dict = st.session_state["edited_components_list"][current_index]
        else:
            # Load from the original components list
            current_components_dict = components[current_index]
        file_name = next(iter(current_components_dict.values()))["file_name"]  # Get from first component
        cleaned_file_name = clean_file_path(file_name, repo_name)

        # Get the cleaned code for the current file
        cleaned_code = get_cleaned_code(repo_name, run_id) # result.get("cleaned_code", {}) # loading from checkpoint instead of from API result
        if not cleaned_code:
            st.error(f"Could not recover cleaned code for file {file_name}")

        if file_name in cleaned_code:
            code_lines = cleaned_code[file_name].splitlines()
        else:
            st.error(f"file_name = {file_name} not found in cleaned_code dict, keys = {list(cleaned_code.keys())}")

        # Code that will be displayed
        code_display = code_lines if file_name in cleaned_code else []
        code_display = remove_line_numbers(code_display) # line numbers will already be shown by streamlit

        # Existing component names for this file
        existing_component_names = list(current_components_dict.keys())

        # Split into two columns so we can always show cleaned code on the right for reference -> easier to identify line numbers this way
        col_1, col_2 = st.columns([0.4, 0.6])

        with col_1:
            st.subheader("ML Component Verification")
            st.write("Current file:")
            st.write(f"     - **{cleaned_file_name}** ({current_index + 1}/{total_files})")

            # Multiselect to keep/delete/add component names
            multiselect_options = list(ml_components.keys()) + ["Other"]
            # Ensure all existing_component_names (which are the defaults) are in multiselect_options.
            # This is crucial for when custom components were added and are now part of the defaults.
            for comp_name in existing_component_names:
                if comp_name not in multiselect_options:
                    multiselect_options.append(comp_name)
            if not existing_component_names:
                st.warning("None of the available ML components could identified in this file. Please select the appropriate component(s).")
            selected_components = st.multiselect(
                "Components identified in this file (please verify):",
                options=multiselect_options,
                default=existing_component_names,
                key=f"components_{current_index}"
            )

            # Allow user to enter their own ML component names if they feel the available list is insufficient
            if "Other" in selected_components:
                st.write("You selected 'Other' as the component type. Please ensure this is a component you want in your final RMR pipeline. Otherwise, remove it.")
                other_components = st.text_area(
                    "Please specify other component(s) (one per line):",
                    key=f"other_components_{current_index}"
                )
                # Process the other components
                if other_components:
                    # Split by newline to get individual components
                    custom_components = [comp.strip().replace('_', ' ').title() for comp in other_components.split('\n') if comp.strip()]
                    
                    # Remove "Other" and add the custom components
                    selected_components.remove("Other")
                    selected_components.extend(custom_components)

            # Store edited components and verify line ranges
            edited_components_dict = {}

            for component_name in selected_components:
                # Base details (existing or new)
                if component_name in current_components_dict:
                    details = current_components_dict[component_name].copy()
                    # If user deleted some components and resulted in a single component, we can update the line range to be the entire file
                    if len(selected_components) == 1:
                        details['line_range'] = get_default_line_range(selected_components, code_display)
                else:
                    details = {
                        "evidence": ["Added manually during verification"],
                        "why_this_is_separate": "Added manually during verification",
                        "file_name": file_name,
                        "line_range": get_default_line_range(selected_components, code_display)
                    }
                
                with st.expander(f"Details for **{component_name}** - needs verification!"):
                    # Always allow line_range editing
                    line_range_identified = clean_line_range(details["line_range"])
                    line_range = st.text_input(
                        "**Line Range**:",
                        value=line_range_identified,
                        key=f"{current_index}_{component_name}_line_range"
                    )
                    st.write(f"**Please delete this identified ML component if**:")
                    st.write(f"     - It is not actually what your code is doing")
                    st.write(f"     - It is not actually a separate ML component that should run independently")
                    st.write(f"     - It's line range overlaps with other identified components in this file")
                    st.write(f"Otherwise, please **correct the line range above** for this component by viewing the cleaned code to the right")
                    st.write(f"     - Ensure the line range is **not overlapping** with other components")
                    st.write(f"     - Don't worry about import statements")
                    
                    # Show evidence and why_separate for existing components
                    if component_name in current_components_dict:
                        show_evidence = st.checkbox("Show Evidence for this ML component classification", key=f"{component_name}_{current_index}")
                        if show_evidence:
                            with st.container():
                                st.write("**Classification Evidence**:")
                                for evidence_dict in details["evidence"]:
                                    st.write(f'- "{evidence_dict.get("quote_or_paraphrase", "Could not get evidence quote")}": {evidence_dict.get("support_reason", "Could not get support reasoning")}')
                                if len(current_components_dict) > 1:
                                    # Only show separation reasoning if we performed a separation in this file (idenfitied more than one component)
                                    st.write("**Why this was identified as a separate component**:")
                                    st.write(f"    - {details['why_this_is_separate']}")
                
                # Update line_range and store
                details["line_range"] = clean_line_range(line_range).replace(':', '-')
                edited_components_dict[component_name] = details

            # Navigation
            col_1a, col_1b = st.columns(2)
            with col_1a:
                if st.button("Previous", disabled=(current_index == 0)):
                    st.session_state["edited_components_list"][current_index] = edited_components_dict
                    st.session_state["current_file_index"] -= 1
                    st.rerun()
            with col_1b:
                if st.button("Next", disabled=(current_index >= total_files - 1)):
                    st.session_state["edited_components_list"][current_index] = edited_components_dict
                    st.session_state["current_file_index"] += 1
                    st.rerun()
        
            # Submit all when done
            if current_index == total_files - 1 and st.button("Submit All Components"):
                st.session_state["edited_components_list"][current_index] = edited_components_dict
                payload = {"verified_components": st.session_state["edited_components_list"]}
                st.session_state.workflow_running = True # before submit back to API, set workflow running again to continue polling
                submit_human_feedback(payload=payload, repo_name=repo_name, run_id=run_id)
                st.session_state["edited_components_list"] = []

            st.write("**Tips**:")
            st.write("  - Please review the Descriptions for Available ML Components on the left for further details how we define each component")
            st.write("  - Select 'Other' if you feel none of the available ML components match what your code in this file is doing.")

        with col_2:
            st.subheader("") # filler space for better alignment
            # Display the code in right column so it can always be viewed alongside the identified components
            if code_display:
                st.write(f"**Cleaned Code For This File** ({len(code_display)} lines):")
                # Create a fixed-height container that will automatically scroll
                container = st.container(height=600)
                # Display the code inside the container with line numbers and syntax highlighting
                with container:
                    numbered_code = "\n".join(f"{i+1}: {line}" for i, line in enumerate(code_display))
                    st.code(numbered_code, language="python")
            else:
                st.error("Could not display code for this file")

def human_verification_of_dag_ui(repo_name, run_id):
    print("\n=== 🚧 ENTER DAG UI ===")
    print("📍 current_step =", st.session_state.get("result", {}).get("step"))

    if st.session_state.get("result", {}).get("step") != "human_verification_of_dag":
        print("🔁 Step changed – not rendering DAG editor UI")
        return

    dag_yaml = get_dag_yaml(repo_name, run_id)
    updated_dag_yaml = dag_edge_editor(dag_yaml)

    if updated_dag_yaml:
        payload = {
            "verified_dag": updated_dag_yaml,
            "github_url": st.session_state["github_url"],
            "input_files": st.session_state["input_files"]
        }
        print("📤 Submitting human feedback from DAG UI...")
        submit_human_feedback(payload=payload, repo_name=repo_name, run_id=run_id)


def main():
    if st.session_state.get("workflow_complete"):
        st.success("🎉 Workflow is complete!")

        if st.button("Back to Home"):
            st.session_state.clear()
            st.rerun()
        return

    # UI welcome page before starting workflow
    if st.session_state["display_welcome_page"] == True:
        display_welcome_page()

        # Start workflow
        if st.button("Start Workflow"):
            start_workflow()

    # Status display while workflow is running in backend 
    elif st.session_state.workflow_running:
        cancel_workflow_button()
        st.write(f"Run ID: **{st.session_state["run_id"]}**")
        with st.status(f"**Running {st.session_state["current_step"].replace("_", " ").title()}** ...", expanded=True, state="running") as status:
            display_detailed_progress(st.session_state["current_step"])
            while st.session_state.workflow_running:
                step_changed = False
                while not step_changed:
                    # Poll every 2 seconds
                    step_changed = check_workflow_status()
                    time.sleep(2)
                # update the status with the new step
                status.update(label=f"Running {st.session_state["current_step"].replace("_", " ").title()} ...", state="running")
                display_progress_bar(st.session_state["current_step"], write_cur_step=False)
                display_detailed_progress(st.session_state["current_step"])
                current_time = datetime.now().strftime("%H:%M:%S")
                print(f"Displayed - Last updated: {current_time}, Running step: {st.session_state["current_step"]}")
        
        st.rerun()


    # Handle human verification steps and workflow completion
    else: 
        back_to_home_button()

        if st.session_state["last_status"] == "failed":
            # Reset session state and return to home screen
            st.session_state.workflow_running = False
            st.session_state["display_welcome_page"] = True
            st.error(f"Workflow failed: {st.session_state["result"].get('error', 'Unknown error')}")
            time.sleep(10)  # Brief delay for user feedback
            st.rerun()
            

        result = st.session_state["result"]
        repo_name = result.get("repo_name")
        run_id = result.get("run_id")
        current_step = result["step"]
        print('handling a human step: ', current_step)

        # Calculate and display progress bar
        display_progress_bar(current_step, write_cur_step=False)
        
        if current_step == "human_verification_of_components":
            human_verification_of_components_ui(repo_name, run_id)
        elif current_step == "human_verification_of_dag":
            human_verification_of_dag_ui(repo_name, run_id)

if __name__ == "__main__":
    main()


# Run: streamlit run rmr_agent/frontend/ui.py