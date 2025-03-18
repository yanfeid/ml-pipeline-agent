import os
import time
import json


# ========== **Save state file to checkpoints** ==========
def save_state(state, state_file):
    """Save the state to a JSON file."""
    os.makedirs(os.path.dirname(state_file), exist_ok=True)

    if os.path.exists(state_file):
        with open(state_file, "r", encoding="utf-8") as f:
            old_state = json.load(f)
    else:
        old_state = {}

    timestamp = time.strftime("%Y-%m-%d_%H-%M-%S")
    old_state[timestamp] = state

    with open(state_file, "w", encoding="utf-8") as f:
        json.dump(old_state, f, indent=4)

    print(f"State saved to {state_file}")

    
# ========== **Save .ini file to checkpoints** ==========
def save_ini_file(file_name, content, checkpoint_dir):
    """Save the .ini content as an actual file in the user-specified checkpoints directory."""
    os.makedirs(checkpoint_dir, exist_ok=True)  # Ensure the directory exists

    file_path = os.path.join(checkpoint_dir, file_name)
    with open(file_path, "w", encoding="utf-8") as file:
        file.write(content)  # Save the .ini string as a file

    print(f"Saved {file_name} to {checkpoint_dir}")