import os
import subprocess

def convert_notebooks(input_files: list[str], local_repo_path: str) -> list[str]:
    """Convert specified .ipynb files to .py files using jupytext.
    
    Args:
        input_files: List of file paths relative to local_repo_path (e.g., 'notebooks/notebook1.ipynb').
        local_repo_path: Root directory of the cloned repo.
    
    Returns:
        List of converted .py file paths.
    """
    converted_files = []
    for file_path in input_files:
        full_path = os.path.join(local_repo_path, file_path)
        if not file_path.endswith(".ipynb"):
            raise ValueError(f"File {file_path} is not a Jupyter notebook (.ipynb)")
        if not os.path.exists(full_path):
            raise FileNotFoundError(f"File {full_path} not found in cloned repo")
        
        output_py_path = full_path.replace(".ipynb", ".py")
        command = (
            f"jupytext --to py '{full_path}' "
            "--opt cell_metadata_filter='-all' "
            "--opt notebook_metadata_filter='-all'"
        )
        try:
            subprocess.check_call(command, shell=True)
            converted_files.append(output_py_path)
        except subprocess.CalledProcessError as e:
            print(f"Error converting {full_path}: {e}")
            raise
    
    return converted_files