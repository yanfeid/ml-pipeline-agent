import nbformat
import re
import os

def py_to_notebook(py_path):
    with open(py_path, 'r', encoding='utf-8') as f:
        lines = f.readlines()

    cells = []
    cell_lines = []
    cell_type = 'code'

    def add_cell(cell_lines, cell_type):
        content = ''.join(cell_lines).strip('\n')
        if content:
            if cell_type == 'markdown':
                cell = nbformat.v4.new_markdown_cell(content)
            else:
                cell = nbformat.v4.new_code_cell(content)
            cells.append(cell)

    for line in lines:
        match = re.match(r'# %%(\s*\[markdown\])?', line)
        if match:
            add_cell(cell_lines, cell_type)
            cell_lines = []
            cell_type = 'markdown' if match.group(1) else 'code'
        else:
            cell_lines.append(line)

    add_cell(cell_lines, cell_type)

    nb = nbformat.v4.new_notebook()
    nb['cells'] = cells

    ipynb_path = os.path.splitext(py_path)[0] + '.ipynb'

    with open(ipynb_path, 'w', encoding='utf-8') as f:
        nbformat.write(nb, f)

    os.remove(py_path)
    print(f"Converted to notebook: {ipynb_path}")



