import os
    
# ========== **Save .ini file to checkpoints** ==========
def save_ini_file(file_name, content, checkpoint_dir):
    """Save the .ini content as an actual file in the user-specified checkpoints directory."""
    os.makedirs(checkpoint_dir, exist_ok=True)  # Ensure the directory exists

    file_path = os.path.join(checkpoint_dir, file_name)
    with open(file_path, "w", encoding="utf-8") as file:
        file.write(content)  # Save the .ini string as a file

    print(f"Saved {file_name} to {checkpoint_dir}")