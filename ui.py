import streamlit as st
import requests
import json
import sys
from rmr_agent.utils import parse_github_url 

API_URL = "http://localhost:8000/run-workflow"

sys.stdout.flush()

# Maximize layout width
st.set_page_config(layout="wide")

# UI title
st.title("RMR Agent")

# Initialize session state
if "result" not in st.session_state:
    st.session_state["result"] = None

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

# Load available ML components with their descriptions
with open("rmr_agent/ml_components/component_definitions.json", 'r') as file:
    ml_components = json.load(file)

REPOS_BASE_DIR = "rmr_agent/repos/"


# Start workflow
if not st.session_state["result"]:
    left_col, right_col = st.columns([3, 1])  # Match layout for consistency
    with left_col:
        github_url = st.text_input("GitHub URL", "https://github.paypal.com/GADS-Consumer-ML/ql-store-recommendation-prod.git")
        input_files = st.text_area("Input Files with core ML logic (one per line, relative to repo root directory)", "research/pipeline/00_driver.ipynb\nresearch/pipeline/01_bq_feat.ipynb\nresearch/pipeline/01_varmart_feat.ipynb\nresearch/pipeline/02_combine.ipynb\nresearch/pipeline/03_prepare_training_data.ipynb\nresearch/pipeline/04_training.ipynb\nresearch/pipeline/05_scoring_oot.ipynb\nresearch/pipeline/06_evaluation.ipynb").splitlines()
        run_id = st.text_input("Run ID (optional)", "3", help="Enter an existing run ID (e.g. 1, 2, 3) to resume, or leave blank for a new run")
        start_from = st.selectbox(
            "Start From (optional)",
            [""] + [step for step in STEPS],  # Empty option + all step names
            help="Choose a step to start from, or leave blank to start from the beginning"
        )
        if st.button("Start Workflow"):
            _, repo_name = parse_github_url(github_url)
            print('Repo name:', repo_name)
            payload = {
                "github_url": github_url,
                "input_files": input_files
            }
            # Add optional fields if provided
            if run_id:
                payload["run_id"] = run_id
            if start_from:
                payload["start_from"] = start_from
            
            # Construct url with repo_name and run_id (if specified)
            url = f"{API_URL}?repo_name={repo_name}"
            if run_id:
                url += f"&run_id={run_id}"

            with st.spinner("Starting workflow..."):
                response = requests.post(url, json=payload)
            if response.status_code == 200:
                st.session_state["result"] = response.json()
                st.session_state["current_file_index"] = 0
                st.session_state["edited_components_list"] = []
            else:
                st.error(f"Error: {response.text}")

# Handle Workflow Steps
if st.session_state["result"]:
    result = st.session_state["result"]
    repo_name = result.get("repo_name")
    run_id = result.get("run_id")
    current_step = result["step"]
    cleaned_step_name = current_step.replace('_', ' ').title()

    # Calculate progress based on current step position
    total_steps = len(STEPS)
    current_step_idx = STEPS.index(current_step)
    if current_step == "complete":
        completed_steps = total_steps
    else:
        completed_steps = current_step_idx + 1 if current_step_idx >= 0 else 0
    
    # Split layout into two columns
    left_col, right_col = st.columns([3, 1])  # 3:1 ratio for main content vs. steps

    with left_col:
        # Main content (current step, progress, verification UI)
        # Display current step and progress
        st.write(f"**Current Step**: {cleaned_step_name}")
        st.progress(completed_steps / total_steps)
        st.write(f"Progress: {completed_steps}/{total_steps} steps completed")

        if current_step == "human_verification_of_components":
            st.subheader("Please verify/edit the components identified in each file")

            # Display all ML component descriptions as a reference
            st.sidebar.subheader("Available ML Components Reference")
            for component_name, description in ml_components.items():
                with st.sidebar.expander(component_name):
                    st.write(description)

            components = result["components"]
            repo_name = result.get("repo_name")
            run_id = result.get("run_id")
            if not repo_name or not run_id:
                print(f"Missing repo_name or run_id: {result}")
                st.error(f"Missing repo_name or run_id: {result}")

            if not isinstance(components, list) or not components:
                st.error("Components should be a non-empty list of dictionaries")
            
            total_files = len(components)
            current_index = st.session_state["current_file_index"]

            if current_index >= total_files:
                st.success("All files verified! Submitting...")
            else:
                # Current file’s components dictionary
                current_components_dict = components[current_index]
                file_name = next(iter(current_components_dict.values()))["file_name"]  # Get from first component
                st.write(f"Verifying components for: **{file_name}** ({current_index + 1}/{total_files})")

                # Existing component names
                existing_component_names = list(current_components_dict.keys())

                # Multiselect to keep/delete/add component names
                selected_components = st.multiselect(
                    "Component Names (select to keep, deselect to remove, add new below)",
                    options=list(ml_components.keys()),
                    default=existing_component_names,
                    key=f"components_{current_index}"
                )

                # Display details for identified components (read-only)
                for component_name in selected_components:
                    if component_name in current_components_dict:
                        with st.expander(f"Reasoning for identifying {component_name}"):
                            details = current_components_dict[component_name]
                            st.write(f"**Line Range**: {details['line_range']}")
                            st.write("**Evidence**:")
                            for evidence in details["evidence"]:
                                st.write(f"- {evidence}")
                            st.write(f"**Why Separate**: {details['why_separate']}")


                # Build edited components dict
                edited_components_dict = {}
                for name in selected_components:
                    if name in current_components_dict:
                        # Keep existing details
                        edited_components_dict[name] = current_components_dict[name]
                    else:
                        # New component from available_ml_components
                        edited_components_dict[name] = {
                            "line_range": "TBD",
                            "evidence": ["Added manually during verification"],
                            "why_separate": "Added manually during verification",
                            "file_name": file_name
                        }

                # Navigation
                col1, col2 = st.columns(2)
                with col1:
                    if st.button("Previous", disabled=(current_index == 0)):
                        st.session_state["edited_components_list"][current_index] = edited_components_dict
                        st.session_state["current_file_index"] -= 1
                        st.rerun()
                with col2:
                    if st.button("Next", disabled=(current_index >= total_files - 1)):
                        st.session_state["edited_components_list"].append(edited_components_dict)
                        st.session_state["current_file_index"] += 1
                        st.rerun()
            
                # Submit all when done
                if current_index == total_files - 1 and st.button("Submit All Components"):
                    st.session_state["edited_components_list"].append(edited_components_dict)
                    payload = {"verified_components": st.session_state["edited_components_list"]}
                    url = f"{API_URL}?repo_name={repo_name}&run_id={run_id}"
                    print(f"Submitting: {url}, Payload: {payload}")
                    response = requests.post(url, json=payload)
                    print(f"Submit Status: {response.status_code}, Response: '{response.text}'")
                    if response.status_code == 200:
                        st.session_state["result"] = response.json()
                        st.session_state["edited_components_list"] = []
                    else:
                        st.error(f"Submit Error: {response.text}")

        elif current_step == "human_verification_of_dag":
            st.subheader("Please verify/edit the identified DAG")
            dag_yaml = result["dag_yaml"]
            edited_dag = st.text_area("DAG YAML", dag_yaml, height=300)
            if st.button("Submit DAG"):
                payload = {"verified_dag": edited_dag}  # Adjust if dag_yaml is a dict
                response = requests.post(
                    f"{API_URL}?repo_name={result['repo_name']}&run_id={result['run_id']}",
                    json=payload
                )
                if response.status_code == 200:
                    st.session_state["result"] = response.json()
                else:
                    st.error(f"Error: {response.text}")

        elif current_step == "complete":
            st.success("Workflow Complete!")
            st.json(result["result"])

    with right_col:
        # Workflow steps on the right
        # Display step status
        st.subheader("Workflow Steps")
        for i, step_name in enumerate(STEPS):
            if i < current_step_idx:
                status = "✅ Completed"
            elif i == current_step_idx:
                status = "⏳ Running"
            else:
                status = "⏸️ Pending"
            st.write(f"{i + 1}. {step_name.replace('_', ' ').title()}: {status}")

# Run: streamlit run ui.py