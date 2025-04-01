import os
import json
import glob
from typing import Dict, Any, List

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
    print(f"Attempting to load checkpoint JSON from: {checkpoint_path}")

    if os.path.exists(checkpoint_path):
        with open(checkpoint_path, "r") as f:
            output = json.load(f)
        print(f"Loaded {step} output from {checkpoint_path}")
        return output
    raise FileNotFoundError(f"Checkpoint not found for step {step}")

def save_step_output(checkpoint_base_path: str, repo_name: str, step: str, run_id: str, output: Dict[str, Any]):
    os.makedirs(f"{checkpoint_base_path}/{repo_name}/{run_id}", exist_ok=True)
    checkpoint_path = f"{checkpoint_base_path}/{repo_name}/{run_id}/{step}.json"
    with open(checkpoint_path, "w") as f:
        json.dump(output, f, indent=2)
    print(f"Saved {step} output to {checkpoint_path}")