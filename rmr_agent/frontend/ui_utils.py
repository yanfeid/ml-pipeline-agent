import os
import json
import yaml
from rmr_agent.workflow import CHECKPOINT_BASE_PATH


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
        file_path = os.path.join(CHECKPOINT_BASE_PATH, repo_name, run_id, 'component_parsing.json')
        with open(file_path, 'r') as file:
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
        file_path = os.path.join(CHECKPOINT_BASE_PATH, repo_name, run_id, 'summarize.json')
        with open(file_path, 'r') as file:
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
        file_path = os.path.join(CHECKPOINT_BASE_PATH, repo_name, run_id, 'dag.yaml')
        with open(file_path, 'r') as file:
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

def get_steps_could_start_from(repo_name, run_id, all_steps):
    directory_path = os.path.join(CHECKPOINT_BASE_PATH, repo_name, run_id)
    if not os.path.isdir(directory_path):
        print(f"Directory does not exist: {directory_path}, so no start_from options will be shown")
        return []
    
    # Get list of JSON files in the directory
    json_files = set()
    for filename in os.listdir(directory_path):
        if filename.endswith(".json"):
            # Remove the .json extension
            step_name = os.path.splitext(filename)[0]
            json_files.add(step_name)

    # Accumulate steps until we find the first missing one
    available_steps = []
    for step in all_steps:
        available_steps.append(step)
        if step not in json_files:
            # Found first missing step, add it because it could be started from, then break
            break
    
    # Clean up step names
    display_available_steps = []
    for i, step in enumerate(available_steps):
        display_step = f"{i + 1}. {step.replace("_", " ").title()}"
        display_available_steps.append(display_step)

    
    return display_available_steps