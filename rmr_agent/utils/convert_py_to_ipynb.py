import os
import nbformat
from nbformat.v4 import new_notebook, new_code_cell
from typing import List

def convert_py_scripts(
    input_files: List[str],
    local_repo_path: str,
    overwrite: bool = False
) -> List[str]:
    """
    Convert specified .py files to .ipynb files in-place using nbformat.

    Args:
        input_files: List of file paths relative to local_repo_path (e.g., 'scripts/myscript.py').
        local_repo_path: Root directory of the repo.
        overwrite: If True, delete the original .py file after conversion.

    Returns:
        List of converted .ipynb file paths.
    """
    converted_files = []

    for file_path in input_files:
        if not file_path.endswith(".py"):
            raise ValueError(f"File {file_path} is not a Python script (.py)")
        
        full_path = os.path.join(local_repo_path, file_path)
        if not os.path.exists(full_path):
            raise FileNotFoundError(f"File {full_path} not found in repo")

        output_ipynb_path = full_path.replace('.py', '.ipynb')

        try:
            with open(full_path, "r", encoding="utf-8") as f:
                lines = f.readlines()

            # Group lines into cells (split by empty lines)
            cells = []
            buffer = []
            for line in lines:
                if line.strip() == "" and buffer:
                    cells.append(new_code_cell("".join(buffer)))
                    buffer = []
                else:
                    buffer.append(line)
            if buffer:
                cells.append(new_code_cell("".join(buffer)))

            nb = new_notebook(cells=cells, metadata={"language": "python"})

            with open(output_ipynb_path, "w", encoding="utf-8") as f:
                nbformat.write(nb, f)

            # Delete original .py file if overwrite is True
            if overwrite:
                os.remove(full_path)
                print(f"🗑 Deleted original: {file_path}")

            converted_files.append(output_ipynb_path)
            print(f"✔ Converted: {file_path} → {os.path.relpath(output_ipynb_path, local_repo_path)}")

        except Exception as e:
            print(f" Error converting {file_path}: {e}")
            raise

    return converted_files


# convert_py_scripts(
#     input_files=["notebooks/clean_data.py", "scripts/train.py"],
#     local_repo_path="/Users/you/myrepo",
#     overwrite=True  
# )
