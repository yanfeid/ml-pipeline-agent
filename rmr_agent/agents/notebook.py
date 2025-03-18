# section_name = "section name here"

# # General params
# project_id = config.get('general', 'dataproc_project_name')
# storage_bucket = config.get('general', 'dataproc_storage_bucket')

# # section specific params
# model_name = config.get(section_name, 'model_name')

# # dependencies from other sections
# param = config.get('some previous section', 'param_name')

# ### research code below...

import os
import configparser
from typing import Dict, Any
import yaml

def notebook_agent(verified_dag: Dict[str, Any]) -> Dict[str, str]:
    """
    Generates Python files in the 'notebooks/' directory based on solution.ini sections.
    
    Args:
        verified_dag (Dict[str, Any]): The parsed DAG structure (only needed for dependencies).
    
    Returns:
        Dict[str, str]: A dictionary mapping section names to generated file paths.
    """



    # === Step 1: Calculate BASE_DIR，ensure code could run in any env ===
    BASE_DIR = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))  # rmr_agent directory
    NOTEBOOKS_DIR = os.path.join(BASE_DIR, "notebooks")
    CHECKPOINTS_DIR = os.path.join(BASE_DIR, "checkpoints", "ql-store-recommendation-prod","1")
    ENV_FILE = os.path.join(CHECKPOINTS_DIR, "environment.ini")
    SOL_FILE = os.path.join(CHECKPOINTS_DIR, "solution.ini")

    os.makedirs(NOTEBOOKS_DIR, exist_ok=True)
    print(f"✅ Created notebooks directory: {NOTEBOOKS_DIR}")

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

    print("\n🔍 Debugging edges processing:")
    for edge in edges:
        from_section = edge.get("from").strip().lower().replace(" ", "_")
        to_section = edge.get("to").strip().lower().replace(" ", "_")

        print(f"  Processing edge: from {from_section} → to {to_section}")

        if from_section and to_section:
            dependencies[to_section] = from_section
            if "attributes" in edge:
                edge_attributes.setdefault(to_section, {}).update(edge["attributes"])

    print(f"\n Final dependencies mapping: {dependencies}")
    print(f" Final edge attributes mapping: {edge_attributes}\n")

    # === Step 4: generate Python file（based on solution.ini）===
    generated_files = {}

    for section_name in config.sections():
        if section_name.lower() == "general":  # ✅ skip general
            print(f"🚀 Skipping general section: {section_name}")
            continue

        node_name = section_name.strip().lower().replace(" ", "_")  # standardized file name
        file_path = os.path.join(NOTEBOOKS_DIR, f"{node_name}.py")
        generated_files[section_name] = file_path  # record file's path

        print(f"\n Generating file for: {section_name} (node_name: {node_name})")
        print(f"  Checking dependencies for {node_name}: {dependencies.get(node_name, 'None')}")
        print(f"  Checking edge attributes for {node_name}: {edge_attributes.get(node_name, 'None')}")

        with open(file_path, "w", encoding="utf-8") as f:
            # === Section Name ===
            f.write(f"# Section Name\n")
            f.write(f"section_name = \"{section_name}\"\n\n")

            # === General Parameters from environment.ini ===
            f.write("# General Parameters (from environment.ini)\n")
            if "general" in config:
                for key in config.options("general"):
                    f.write(f"{key} = \"{config.get('general', key)}\"\n")

            f.write("\n")

            # === Section-Specific Parameters from solution.ini ===
            f.write("# Section-Specific Parameters (from solution.ini)\n")
            for key in config.options(section_name):
                f.write(f"{key} = \"{config.get(section_name, key)}\"\n")

            f.write("\n")

            # === Dependencies from DAG ===
            f.write("# Dependencies from Other Sections\n")

            prev_section = dependencies.get(node_name, None)

            if prev_section:
                f.write(f"# Previous section: {prev_section}\n")

                # Debug: ensure edge_attributes[node_name] exist
                if node_name in edge_attributes:
                    f.write("# Edge Attributes from DAG\n")
                    for key, value in edge_attributes[node_name].items():
                        f.write(f"{key} = \"{value}\"\n")
                        print(f"  Writing edge attribute: {key} = {value}")

                # get params from `solution.ini`
                if prev_section in config:
                    for key in config.options(prev_section):
                        f.write(f"{key} = \"{config.get(prev_section, key)}\"\n")
            else:
                f.write("# No dependencies (first section)\n")

            # === Research Code Placeholder ===
            f.write("\n# Research code goes here\n")
            f.write("def research_function():\n")
            f.write("    print('Running research code for', section_name)\n")

        print(f" Created: {file_path}")

    print("🎉 All sections processed. Python files are ready in notebooks/")
    
    return  generated_files
  # return notebooks




if __name__ == "__main__":
    # set up path
    BASE_DIR = "/Users/yanfdai/Desktop/codespace/DAG_FULLSTACK/rmr_agent/rmr_agent"
    NOTEBOOKS_DIR = os.path.join(BASE_DIR, "notebooks")

    with open("dag.yaml", "r") as file:
        test_dag = yaml.safe_load(file)

    # run notebook_agent to generate notebooks
    generated_files = notebook_agent(test_dag)

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