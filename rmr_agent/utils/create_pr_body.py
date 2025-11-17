import json
import yaml
import os
import logging
from pathlib import Path
import re
# Import locally to avoid circular imports
from .correction_logging import format_component_corrections_for_pr, format_dag_corrections_for_pr
from .logging_config import setup_logger

# Set up module logger
logger = setup_logger(__name__)

# Helper function to load JSON files
def load_json_file(filepath):
    """Loads a JSON file and returns its content."""
    try:
        with open(filepath, 'r') as f:
            return json.load(f)
    except FileNotFoundError:
        logger.warning("File not found - %s", filepath)
        return None
    except json.JSONDecodeError:
        logger.warning("Could not decode JSON from - %s", filepath)
        return None

# Helper function to load YAML files or YAML strings
def load_yaml_data(data_source):
    """Loads YAML from a file path or a string."""
    if isinstance(data_source, (str, Path)) and os.path.exists(data_source): # If it's a path to a YAML file
        try:
            with open(data_source, 'r') as f:
                return yaml.safe_load(f)
        except FileNotFoundError:
            logger.warning("File not found - %s", data_source)
            return None
        except yaml.YAMLError:
            logger.warning("Could not parse YAML from file - %s", data_source)
            return None
    elif isinstance(data_source, str): # If it's a YAML string
        try:
            return yaml.safe_load(data_source)
        except yaml.YAMLError:
            logger.warning("Could not parse YAML from string: '%s...'", data_source[:100]) # Log part of string
            return None
    else:
        logger.warning("Invalid YAML data source type: %s", type(data_source))
        return None

def sanitize_mermaid_id(name):
    """Sanitizes a string to be used as a Mermaid node ID."""
    if not isinstance(name, str):
        name = str(name)
    # Remove characters not suitable for Mermaid IDs
    name = re.sub(r'[^a-zA-Z0-9_]', '_', name)
    return name

def format_introduction():
    """Generates the introductory part of the PR body."""
    return (
        "Hello!\n\n"
        "We've automatically refactored your exploratory ML code into a more robust and configurable ML pipeline. "
        "This Pull Request contains the refactored code, including new modular notebooks and configuration files."
    )

def format_pipeline_summary_from_dag(dag_data):
    """
    Formats the summary of the refactored pipeline based on the final DAG.
    Includes a list of components and a Mermaid diagram.
    """
    if not dag_data or 'nodes' not in dag_data:
        return "Could not retrieve final pipeline structure information. 'nodes' key missing in parsed DAG data."

    md_parts = []
    md_parts.append("## Summary of Your Refactored Pipeline")
    md_parts.append(
        "Based on your final verification, your code has been organized into the following components and pipeline structure. "
        "These components, derived from your original files, have been used to generate the new set of modular notebooks you see in this Pull Request."
    )
    md_parts.append("\n### Pipeline Components:")

    nodes_list_from_yaml = dag_data.get('nodes', [])
    processed_nodes_for_mermaid = [] # To store name and id for mermaid diagram

    if not nodes_list_from_yaml:
        md_parts.append("*No components (nodes) were found in the verified DAG data.*")
    else:
        for node_item in nodes_list_from_yaml:
            if not (isinstance(node_item, dict) and len(node_item) == 1):
                md_parts.append(f"- *Skipping malformed node item: {str(node_item)[:100]}...*")
                continue
            
            node_name = list(node_item.keys())[0]
            #logger.debug("Processing node: %s", node_name)
            node_details = node_item[node_name]

            if not isinstance(node_details, dict):
                md_parts.append(f"- *Skipping node '{node_name}': details are not a dictionary.*")
                continue

            file_name = node_details.get('file_name', 'N/A').replace(".py", ".ipynb") # Assuming all input files were .ipynb
            
            """
            line_range_raw = node_details.get('line_range', 'N/A')
            line_range_str = "N/A"
            if isinstance(line_range_raw, str):
                line_range_str = line_range_raw # Directly use if it's a string like '1-100'
            elif isinstance(line_range_raw, list) and len(line_range_raw) == 2:
                line_range_str = f"{line_range_raw[0]}-{line_range_raw[1]}"
            """
            
            md_parts.append(f"- **{node_name}**")
            md_parts.append(f"  - *Original Source:* `{file_name}`")
            sanitized_node_id = sanitize_mermaid_id(node_name)
            #logger.debug("Sanitized node ID: %s", sanitized_node_id)
            processed_nodes_for_mermaid.append({"name": node_name, "id": sanitized_node_id})


    md_parts.append("\n### Pipeline Visualization (DAG):")
    md_parts.append("```mermaid")
    md_parts.append("graph TD;")

    # Add nodes to Mermaid diagram
    if not processed_nodes_for_mermaid:
         md_parts.append("    %% No valid nodes to display %%")
    else:
        for node_info in processed_nodes_for_mermaid:
            md_parts.append(f'    {node_info["id"]}["{node_info["name"]}"]')

    # Add edges to Mermaid diagram
    edges = dag_data.get('edges', [])
    if edges:
        for edge in edges:
            source_name = edge.get('from')
            target_name = edge.get('to')

            if source_name and target_name:
                source_id = sanitize_mermaid_id(source_name) # Source/Target names in edges should match node names
                target_id = sanitize_mermaid_id(target_name)
                md_parts.append(f'    {source_id} --> {target_id}')
            else:
                md_parts.append(f"    %% Skipping malformed edge: {str(edge)[:100]}... %%")
    elif processed_nodes_for_mermaid: # Only add this comment if there were nodes but no edges
        md_parts.append("    %% No edges defined in the DAG %%")
            
    md_parts.append("```")
    md_parts.append("*(This diagram shows the flow of data and dependencies between the components in your new pipeline.)*")

    return "\n".join(md_parts)

def format_key_changes():
    """Explains the key refactoring changes made."""
    return (
        "## Key Changes Made\n"
        "- Your original code has been refactored into a series of **modular notebooks**, one for each component in the pipeline.\n"
        "- **Configuration** (e.g., parameters, file paths) has been extracted from your code and placed into central `config/` files.\n"
        "- Each refactored notebook now **loads its configuration dynamically**. This replaces hardcoded values, making your entire pipeline more flexible, configurable, and reproducible."
    )

def format_next_steps():
    """Suggests next steps for the user."""
    return (
        "## Next Steps for You\n"
        "1.  **Review the Code:** Carefully examine the generated notebooks and configuration files in this Pull Request.\n"
        "2.  **Test the Code Locally:** Follow these steps to fetch and test the PR branch locally:\n\n"
        "    ```bash\n"
        "    # Step 1: Add the fork as a remote (only needed once)\n"
        "    git remote add rmr-fork [FORK_URL]\n\n"
        "    # Step 2: Fetch the PR branch\n"
        "    git fetch rmr-fork [BRANCH_NAME]\n\n"
        "    # Step 3: Check out the branch locally\n"
        "    git checkout rmr-fork/[BRANCH_NAME]\n\n"
        "    # OR create a new local branch based on the PR\n"
        "    git checkout -b test-rmr-changes rmr-fork/[BRANCH_NAME]\n"
        "    ```\n\n"
        "    *Note: Replace [FORK_URL] with the URL of the fork repository and [BRANCH_NAME] with the name of the PR branch.*\n\n"
        "3.  **Verify Functionality:** Run the refactored pipeline from start to finish. Ensure it executes correctly and produces the expected results. Pay close attention to variable definitions and data flow, as minor adjustments might be needed.\n"
        "4.  **Consult [RMR Templates](https://github.paypal.com/FOCUS-ML/Automation/tree/master/examples/rmr_pipelines):** For best practices and recommended libraries for each component in the MDLC (e.g., driver creation, feature selection, model training), please consult our RMR Template documentation and code.\n"
        "5.  **Consider Deployment:** If your goal is to deploy this model, you may need to add a deployment-specific notebook or scripts.\n"
        "6.  **Provide Feedback:** We value your input! Please reach out to matjacobs@paypal.com and yanfdai@paypal.com if you encounter any issues, have questions, or have suggestions for improvement."
    )

def format_appendix_component_changes(initial_parsed_components_data, human_verified_components_data):
    """
    (Optional Appendix Section)
    Shows the user the components initially identified versus what they verified.
    """
    md_parts = ["## Appendix: Component Verification Summary"]
    md_parts.append(
        "For your reference, this section outlines the components initially identified by our automated parsing "
        "and the final set of components after your verification. This can help you recall any changes "
        "(renaming, merging, splitting, adding, or removing components) you made during the interactive verification process."
    )

    # Process initial components from component_parsing.json
    md_parts.append("\n### Initially Identified Components (from `component_parsing.json`):")
    if initial_parsed_components_data:
        found_initial = False
        # component_parsing.json is a list of dictionaries, where each dict has file_name as key
        for file_entry in initial_parsed_components_data: 
            for file_name, components in file_entry.items():
                md_parts.append(f"- **File: `{file_name.replace('.py', '.ipynb')}`**")
                if components: # components is a dict of component_name: details
                    for comp_name, comp_details in components.items():
                        #line_range = comp_details.get('line_range', ['N/A', 'N/A'])
                        #line_range_str = f"{line_range[0]}-{line_range[1]}" if isinstance(line_range, list) and len(line_range) == 2 else "N/A"
                        md_parts.append(f"  - {comp_name}")
                        found_initial = True
                else:
                    md_parts.append(f"  - *No components identified in this file.*")
        if not found_initial and not initial_parsed_components_data: # Check if list was empty
             md_parts.append("*No initial components were recorded or data is missing (component_parsing.json might be empty or unparsable).*")
        elif not found_initial: # List was not empty, but no components found within
             md_parts.append("*No components were found across the parsed files.*")

    else:
        md_parts.append("*Could not load initial component parsing data (component_parsing.json not found or invalid).*")

    # Process human-verified components from human_verification_of_components.json
    md_parts.append("\n### Verified Components (from `human_verification_of_components.json`):")
    if human_verified_components_data and 'verified_components' in human_verified_components_data:
        verified_components = human_verified_components_data['verified_components']
        if verified_components: # This is a list of component dicts
            for comp in verified_components:
                name = comp.get('name', 'Unnamed Component')
                file_name = comp.get('file_name', 'N/A').replace(".py", ".ipynb") # Assuming all input files were .ipynb
                #line_range = comp.get('line_range', ['N/A', 'N/A'])
                #line_range_str = f"{line_range[0]}-{line_range[1]}" if isinstance(line_range, list) and len(line_range) == 2 else "N/A"
                md_parts.append(f"- {name} (Source: `{file_name}`")
        else:
            md_parts.append("*No components were marked as verified in human_verification_of_components.json.*")
    else:
        md_parts.append("*Could not load human-verified component data (human_verification_of_components.json not found, invalid, or 'verified_components' key missing).*")

    return "\n".join(md_parts)


def generate_pr_body(checkpoints_dir_path: str, include_appendix: bool = False):
    """
    Generates the full Markdown string for the PR body.
    """
    if include_appendix:
        raise ValueError("The 'include_appendix' parameter is not supported at this time")
    checkpoints_dir = Path(checkpoints_dir_path)
    md_sections = []

    # 1. Introduction
    md_sections.append(format_introduction())

    # 2. Pipeline Summary from verified DAG
    final_dag_json_path = os.path.join(checkpoints_dir, "human_verification_of_dag.json")
    final_dag_json_content = load_json_file(final_dag_json_path) # This is the outer JSON

    dag_data = None
    if final_dag_json_content:
        # The "verified_dag" key points to a YAML STRING.
        dag_yaml_string = final_dag_json_content.get("verified_dag")
        if dag_yaml_string and isinstance(dag_yaml_string, str):
            dag_data = load_yaml_data(dag_yaml_string) # Parse the YAML string
            if not dag_data:
                logger.warning("Successfully extracted YAML string from 'verified_dag' in %s, but failed to parse it as YAML.", final_dag_json_path)
        elif not dag_yaml_string:
            logger.warning("'verified_dag' key not found in %s or its value is empty.", final_dag_json_path)
        else: # dag_yaml_string is not a string
            logger.warning("Value of 'verified_dag' in %s is not a string (found type: %s). Expected a YAML string.", final_dag_json_path, type(dag_yaml_string))
    else:
        logger.warning("Could not load %s.", final_dag_json_path)


    if dag_data and 'nodes' in dag_data: # Ensure 'nodes' key exists in the parsed YAML data
        md_sections.append(format_pipeline_summary_from_dag(dag_data))
    else:
        # Provide a more specific message based on why dag_data might be None or malformed
        error_message_base = "## Refactoring Summary\n*Note: Could not display pipeline structure. "
        if not final_dag_json_content:
            error_message = f"{error_message_base}The file `human_verification_of_dag.json` was not found or is invalid.*"
        elif "verified_dag" not in final_dag_json_content:
            error_message = f"{error_message_base}The `human_verification_of_dag.json` file does not contain the expected 'verified_dag' key.*"
        elif not isinstance(final_dag_json_content.get("verified_dag"), str):
            error_message = f"{error_message_base}The 'verified_dag' key in `human_verification_of_dag.json` does not point to a YAML string.*"
        elif final_dag_json_content.get("verified_dag") and dag_data is None: # YAML string was present but parsing failed
            error_message = f"{error_message_base}The YAML string under 'verified_dag' in `human_verification_of_dag.json` could not be parsed.*"
        elif dag_data and 'nodes' not in dag_data: # Parsed YAML, but 'nodes' is missing
            error_message = f"{error_message_base}The parsed DAG from `human_verification_of_dag.json` does not contain a 'nodes' list.*"
        else: # Generic fallback
            error_message = f"{error_message_base}There was an issue processing the DAG information from `human_verification_of_dag.json`.*"
        md_sections.append(error_message + " Please check the file and its format directly.*")

    # 3. Key Changes
    md_sections.append(format_key_changes())

    # 4. Add Human Corrections Summary
    md_sections.append("## Human Corrections Summary")
    md_sections.append(
        "This section outlines the changes you made during the verification process. "
        "These corrections help improve the quality of the refactored code and enhance the system's ability to "
        "accurately identify ML components and their relationships in the future."
    )

    # Component corrections
    component_corrections_path = os.path.join(checkpoints_dir, "human_verification_of_components.json")
    component_corrections_content = load_json_file(component_corrections_path)
    if component_corrections_content and "component_corrections" in component_corrections_content:
        corrections = component_corrections_content["component_corrections"]
        md_sections.append(format_component_corrections_for_pr(corrections))
    else:
        md_sections.append(
            "### ML Component Corrections\n"
            "*No component correction data was found or the components were accepted without changes.*"
        )

    # DAG corrections
    dag_corrections = None
    if final_dag_json_content and "dag_corrections" in final_dag_json_content:
        dag_corrections = final_dag_json_content["dag_corrections"]

    if dag_corrections:
        md_sections.append(format_dag_corrections_for_pr(dag_corrections))
    else:
        md_sections.append(
            "### DAG Structure Corrections\n"
            "*No DAG correction data was found or the DAG was accepted without changes.*"
        )

    # 5. Next Steps
    md_sections.append(format_next_steps())

    # 6. Appendix (Optional)
    if include_appendix:
        initial_components_path = os.path.join(checkpoints_dir, "component_parsing.json")
        human_verified_components_path = os.path.join(checkpoints_dir, "human_verification_of_components.json")

        initial_data = load_json_file(initial_components_path)
        verified_data = load_json_file(human_verified_components_path)

        md_sections.append(format_appendix_component_changes(initial_data, verified_data))

    return "\n\n".join(md_sections)

