import os
import json
import glob
import logging
from typing import Dict, Any, List
from .logging_config import setup_logger

# Set up module logger
logger = setup_logger(__name__)

def get_next_run_id(checkpoint_base_path: str, repo_name: str) -> int:
    run_pattern = f"{checkpoint_base_path}/{repo_name}/run_*"
    existing_runs = glob.glob(run_pattern)
    
    if not existing_runs:
        return 1
        
    # Extract run numbers from directory names
    run_numbers = []
    for run_dir in existing_runs:
        try:
            run_num = int(run_dir.split("run_")[1])
            run_numbers.append(run_num)
        except (IndexError, ValueError):
            continue
            
    # If no valid run numbers found, start with 1
    if not run_numbers:
        return 1
        
    return max(run_numbers) + 1

def get_run_identifier(repo_name: str) -> str:
    run_num = get_next_run_id(repo_name)
    return f"run_{run_num}"

def load_step_output(checkpoint_base_path: str, repo_name: str, step: str, run_id: str) -> Dict[str, Any]:
    checkpoint_path = f"{checkpoint_base_path}/{repo_name}/{run_id}/{step}.json"
    logger.debug("Attempting to load checkpoint JSON from: %s", checkpoint_path)

    if os.path.exists(checkpoint_path):
        with open(checkpoint_path, "r") as f:
            output = json.load(f)
        logger.info("Loaded %s output from %s", step, checkpoint_path)
        return output
    raise FileNotFoundError(f"Checkpoint not found for step {step}")

def save_step_output(checkpoint_base_path: str, repo_name: str, step: str, run_id: str, output: Dict[str, Any]):
    os.makedirs(f"{checkpoint_base_path}/{repo_name}/{run_id}", exist_ok=True)
    checkpoint_path = f"{checkpoint_base_path}/{repo_name}/{run_id}/{step}.json"

    # Check if the file exists, if it does, read and compare the content first
    if os.path.exists(checkpoint_path):
        try:
            with open(checkpoint_path, "r") as f:
                existing_content = json.load(f)

            # Special handling: If this is the human_verification_of_dag step and there are no user modifications, we should keep the original file unchanged
            if step == "human_verification_of_dag" and "verified_dag" in existing_content and "verified_dag" in output:
                # Check if the verified DAG YAML is the same, ignoring whitespace and format differences
                try:
                    import yaml
                    existing_dag = yaml.safe_load(existing_content["verified_dag"])
                    new_dag = yaml.safe_load(output["verified_dag"])

                    # If the parsed structures are the same, keep the original file unchanged
                    if existing_dag == new_dag:
                        logger.debug("DAG content unchanged for %s, skipping write", step)
                        return
                except Exception as e:
                    logger.warning("Error comparing DAG YAML: %s", e)
                    # If YAML comparison fails, fall back to regular JSON comparison

            # Compare if existing content and new content are the same
            if existing_content == output:
                logger.debug("Content unchanged for %s, skipping write", step)
                return
        except Exception as e:
            logger.warning("Error reading existing file %s: %s", checkpoint_path, e)
            # If reading fails, continue writing the new file

    # If the file doesn't exist or content is different, write the file
    with open(checkpoint_path, "w") as f:
        # Use a consistent JSON serialization format
        json.dump(output, f, indent=2, sort_keys=True, ensure_ascii=False)
    logger.info("Saved %s output to %s", step, checkpoint_path)