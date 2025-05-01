import os
import re
import configparser
from typing import Dict, Any
import yaml
import json


def clean_prefix(path: str) -> str:
    return os.path.splitext(os.path.basename(path))[0].strip().lower()


def normalize_node_name(name):
    return re.sub(r'\s+', '_', name.strip().lower())

 # === EXTRACT CODE FROM CLEAN_CODE ===
def extract_code_from_json(cleaned_code, verified_dag):
    """
    Read JSON file,
    Extract code based on DAG YAML file
    Args:
        json_file: Json file, a dict, typically summarize.json
        verified_dag: A dictionary after yaml.safe_load(f)
    Returns:
        Dict[str, str]: A dictionary mapping section names to generated file paths.
    """
    
    # cleaned_code = json_file.get("cleaned_code", {})
    extracted_code = {}

    for node in verified_dag["nodes"]:
        # Get node's name（
        node_name, node_info = list(node.items())[0]
      
        full_file_path = node_info["file_name"]  # full path
        file_prefix = os.path.splitext(os.path.basename(full_file_path))[0]  # extract the path without Filename Extension
        line_range_str = node_info["line_range"]

        match = re.search(r"(\d+)-(\d+)", line_range_str)

        if not match:
            print(f"Warning: Invalid line range format for {node_name}: {line_range_str}")
            continue
        start_line, end_line = int(match.group(1)), int(match.group(2))

        # search for the matching files in JSON
        matched_file = None
        dag_prefix = clean_prefix(file_prefix)

        # print(f"\n🔍 Searching match for DAG prefix: '{dag_prefix}'")
        # print("📂 Available cleaned_code prefixes:")

        for json_file_path in cleaned_code.keys():
            json_file_prefix = clean_prefix(json_file_path)
            # print(f"  - {json_file_prefix}")
            
            if json_file_prefix == dag_prefix:
                matched_file = json_file_path
                print(f"✅ Match found: {json_file_path}")
                break

        if matched_file:
            code_content = cleaned_code[matched_file]
            lines = code_content.split("\n")
            selected_lines = lines[start_line-1:end_line]

            extracted_code[node_name] = {
                "code": "\n".join(selected_lines),
            }
        else:
            print(f"⚠️ Warning: No match found for '{dag_prefix}' in cleaned_code.")

    return extracted_code

# BASE_DIR = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))  # rmr_agent directory
# CHECKPOINTS_DIR = os.path.join(BASE_DIR, "checkpoints", "ql-store-recommendation-prod","1")
# dag_yaml = os.path.join(CHECKPOINTS_DIR, "dag_copy.yaml")
# JSON_FILE = os.path.join(CHECKPOINTS_DIR, "summarize.json")
# extracted_code = extract_code_from_json(JSON_FILE, dag_yaml)

# for node, data in extracted_code.items():
#     print(f"\n# Extracted code for {node}:\n{data['code']}")

 # === NOTEBOOK AGENT CODE ===
def notebook_agent(verified_dag, cleaned_code, local_repo_path):
    """
    Generates Python files in the 'notebooks/' directory based on solution.ini sections.
    Args:
        verified_dag: A dictionary after yaml.safe_load(f)
    Returns:
        Dict[str, str]: A dictionary mapping section names to generated file paths.
    """

    # === Step 1: Calculate BASE_DIR，ensure code could run in any env ===
    NOTEBOOKS_DIR = os.path.join(local_repo_path, "notebooks")
    CONFIG_DIR = os.path.join(local_repo_path, "config")
    ENV_FILE = os.path.join(CONFIG_DIR, "environment.ini")
    SOL_FILE = os.path.join(CONFIG_DIR, "solution.ini")

    os.makedirs(NOTEBOOKS_DIR, exist_ok=True)
    print(f"Created notebooks directory: {NOTEBOOKS_DIR}")

    # === Step 2: read environment.ini 和 solution.ini ===
    config = configparser.ConfigParser()

    if not os.path.exists(ENV_FILE):
        raise FileNotFoundError(f" Environment file not found: {ENV_FILE}")
    config.read(ENV_FILE)

    if not os.path.exists(SOL_FILE):
        raise FileNotFoundError(f" Solution file not found: {SOL_FILE}")
    config.read(SOL_FILE)

    # === Step 3: read DAG to get dependencies and attributes ===
    edges = verified_dag.get("edges", [])
    
    # read dependencies and attributes
    dependencies = {}
    edge_attributes = {}

    for edge in edges:
        from_section = edge.get("from").strip().lower().replace(" ", "_")
        to_section = edge.get("to").strip().lower().replace(" ", "_")

        if from_section and to_section:
            dependencies.setdefault(to_section, []).append(from_section)
            if "attributes" in edge:
                edge_attributes.setdefault(to_section, {}).setdefault(from_section, {}).update(edge["attributes"])


    print(f"\n Final dependencies mapping: {dependencies}")
    print(f" Final edge attributes mapping: {edge_attributes}\n")

    # === Step 4: generate Python file（based on solution.ini）===
    # generated_files = {}

    # for section_name in config.sections():
    #     if section_name.lower() == "general":  # ✅ skip general
    #         print(f"🚀 Skipping general section: {section_name}")
    #         continue

    #     node_name = section_name.strip().lower().replace(" ", "_")  # standardized file name
    #     file_path = os.path.join(NOTEBOOKS_DIR, f"{node_name}.py")
    #     generated_files[section_name] = file_path  # record file's path

    #     print(f"\n Generating file for: {section_name} (node_name: {node_name})")
    #     print(f"  Checking dependencies for {node_name}: {dependencies.get(node_name, 'None')}")
    #     print(f"  Checking edge attributes for {node_name}: {edge_attributes.get(node_name, 'None')}")

    #     with open(file_path, "w", encoding="utf-8") as f:
    
    generated_files = {}
    sections = [s for s in config.sections() if s.lower() != "general"]

    for index, section_name in enumerate(sections):
        node_name = section_name.strip().lower().replace(" ", "_")  # standardized file name
        filename = f"{index}_{node_name}.py" 
        file_path = os.path.join(NOTEBOOKS_DIR, filename)
        generated_files[section_name] = file_path  # record file's path
        print(f"\n Generating file for: {section_name} (node_name: {node_name})")
        print(f"  Checking dependencies for {node_name}: {dependencies.get(node_name, 'None')}")
        print(f"  Checking edge attributes for {node_name}: {edge_attributes.get(node_name, 'None')}")

         # === Standard Code for RMR ===       
        with open(file_path, "w", encoding="utf-8") as f:
            f.write("""## gsutil authentication
%ppauth
                    
from rmr_config.simple_config import Config
from rmr_config.state_manager import StateManager
import os, sys, ast, json
from datetime import datetime

if "working_path" not in globals():
    from pathlib import Path
    path = Path(os.getcwd())
    working_path = path.parent.absolute()

folder = os.getcwd()
username = os.environ['NB_USER']
params_path = os.path.join(working_path, 'config')
config = Config(params_path)
local_base_path = config.get("general","local_output_base_path")
os.makedirs(local_base_path, exist_ok=True)

# set working directory
os.chdir(working_path)
if not config:
    raise ValueError('config is not correctly setup')
                
print(f'username={username}, working_path={working_path}')
                    
""")


            # === Section Name ===
            formatted_section_name = section_name.replace(" ", "_").lower()
            f.write(f"# Section Name\n")
            f.write(f"section_name = \"{formatted_section_name}\"\n\n")

            # === General Parameters from environment.ini === 
            # mo_name driver_dataset dataproc_project_name dataproc_storage_bucket gcs_base_path queue_name check_point state_file 
            f.write("# General Parameters \n")

            required_keys = [
                "mo_name",
                "driver_dataset",
                "dataproc_project_name",
                "dataproc_storage_bucket",
                "gcs_base_path",
                "queue_name",
                "check_point",
                "state_file"
            ]

            if "general" in config:
                for key in required_keys:
                    f.write(f"{key} = config.get('general', '{key}')\n")

            f.write("\n")


            # === Section-Specific Parameters from solution.ini ===
            f.write("# Section-Specific Parameters (from solution.ini)\n")
            for key in config.options(section_name):
                f.write(f"{key} = config.get(section_name, '{key}')\n")

            f.write("\n")

            # === Dependencies from DAG ===
            node_dict = {}
            for item in verified_dag.get("nodes", []):
                if isinstance(item, dict):
                    for raw_name, data in item.items():
                        norm_name = normalize_node_name(raw_name)
                        node_dict[norm_name] = data
            
            norm_node_name = normalize_node_name(node_name)
            current_node_params = node_dict.get(norm_node_name, {}).get("inputs", {})
            # print("🎯 Current normalized node:", norm_node_name)
            # print("🧩 Current params:", current_node_params)

            f.write("# Dependencies from Previous Sections=====\n")
            for from_node in dependencies.get(node_name, []):
                f.write(f"# Previous section: {from_node}\n")

                dep_attributes = edge_attributes.get(node_name, {}).get(from_node, {})
                if dep_attributes:
                    f.write("# Edge Attributes from DAG\n")
                    for dep_key, dep_val in dep_attributes.items():
                        matched_key = None
                        for curr_key, curr_val in current_node_params.items():
                            if curr_val == dep_val:
                                matched_key = curr_key
                                break

                        final_key = matched_key if matched_key else dep_key
                        f.write(f"{final_key} = config.get('{from_node}', '{dep_key}')\n")
                        print(f"Writing edge attribute: {final_key} = config.get('{from_node}', '{dep_key}')")

            f.write("\n")

            # === Research Code === 
            extracted_code = extract_code_from_json(cleaned_code,verified_dag)
    
            if section_name.lower() == "general": 
                print(f"🚀 Skipping general section: {section_name}")
                continue

            match_key = next(
                (k for k in extracted_code if k.lower().replace(" ", "_") == section_name),
                None
            )
            if match_key:
                print(f"MATCH FOUND: {match_key}")

                research_code_lines = extracted_code[match_key]["code"].split("\n")  
                cleaned_code_list = []
                for line in research_code_lines:
                    cleaned_line = line.split("|", 1)[-1].strip()
                    cleaned_code_list.append(cleaned_line)

                research_code = "\n".join(cleaned_code_list)
                f.write("\n" + "# === Research Code ===\n")
                f.write(research_code + "\n")
                f.write("\nprint('Script initialized')\n")
                print(f"Research code inserted into {file_path}")
            else:
                print(f"⚠️ WARNING: No research code found for {section_name}")

            print("All notebooks generated successfully!")
        print(f" Created: {file_path}")
    print("All sections processed. Python files are ready in notebooks/")
    
    return  generated_files
  # might return a dict


# #==========================simple test====================================

if __name__ == "__main__":
    # set up path
    BASE_DIR = "/Users/yanfdai/Desktop/codespace/DAG_FULLSTACK/rmr_agent/rmr_agent"
    NOTEBOOKS_DIR = os.path.join(BASE_DIR, "notebooks")

    local_repo_path = "/Users/yanfdai/Desktop/codespace/DAG_FULLSTACK/rmr_agent/rmr_agent/repos/ql-store-recommendation-prod"

    CHECKPOINTS_DIR = os.path.join(BASE_DIR, "checkpoints", "ql-store-recommendation-prod","4")
    dag_yaml = os.path.join(CHECKPOINTS_DIR, "dag.yaml")
    json_path= os.path.join(CHECKPOINTS_DIR,"summarize.json" )
    
    with open(json_path, "r", encoding="utf-8") as f:
        json_file = json.load(f)

    json = json_file.get('cleaned_code')
    
    with open(dag_yaml, "r", encoding="utf-8") as f:
        verified_dag = yaml.safe_load(f)

    # with open(dag_state, "r", encoding="utf-8") as f:
    #     dag_file = json.load(f)

    generated_files = notebook_agent(verified_dag, json, local_repo_path)

    # check notebooks
    if os.path.exists(NOTEBOOKS_DIR):
        print(f" Notebooks directory exists: {NOTEBOOKS_DIR}")
    else:
        print(f" Notebooks directory missing: {NOTEBOOKS_DIR}")

    # check py file
    for section, file_path in generated_files.items():
        if os.path.exists(file_path):
            print(f" File exists: {file_path}")
        else:
            print(f" File missing: {file_path}")

    print(" Notebook generation test completed!")