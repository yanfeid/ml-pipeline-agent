import autoflake


def remove_unused_imports(code: str) -> str:
    """Removes unused imports using autoflake."""
    return autoflake.fix_code(code, remove_all_unused_imports=True)

def remove_empty_lines(code: str) -> str:
    """Removes empty lines from the code."""
    clean_lines = []
    for line in code.split('\n'):
        # Skip lines that are empty or contain only whitespace
        if line.strip() == '':
            continue
        clean_lines.append(line)
    return '\n'.join(clean_lines)

def remove_print_statements(code: str) -> str:
    """Removes print and logger statements."""
    clean_lines = []
    for line in code.split('\n'):
        stripped = line.strip()
        # Skip print statements
        if stripped.startswith('print('):
            continue
        # Skip logger statements
        if any(stripped.startswith(f'logger.{level}(') 
               for level in ['debug', 'info', 'warning', 'error']):
            continue
        clean_lines.append(line)
    return '\n'.join(clean_lines)

def remove_exploratory_code(code: str) -> str:
    """Removes common exploratory statements."""
    clean_lines = []
    for line in code.split('\n'):
        stripped = line.strip()
        # Skip .head(), .info(), .describe() calls
        if any(stripped.endswith(f'.{method}()') 
               for method in ['head', 'info', 'describe', 'count']):
            continue
        # Also catch cases with parameters like .head(5)
        if any(f'.{method}(' in stripped 
               for method in ['head', 'info', 'describe']):
            continue
        clean_lines.append(line)
    return '\n'.join(clean_lines)

def remove_plusminus_markers(code: str) -> str:
    """Removes Jupyter notebook cell markers."""
    clean_lines = []
    for line in code.split('\n'):
        stripped = line.strip()
        # Skip # + and # - lines
        if stripped in ['# +', '# -']:
            continue
        clean_lines.append(line)
    return '\n'.join(clean_lines)


def add_line_numbers(code: str) -> str:
    lines = code.split('\n')
    numbered_lines = [f"{i+1:4d} | {line}" for i, line in enumerate(lines)]
    return '\n'.join(numbered_lines)

def preprocess_python_file(filepath: str) -> str:
    """Loads a Python file, removes noisy code, and returns cleaned code."""
    with open(filepath, 'r', encoding='utf-8') as f:
        code = f.read()
    
    code = remove_unused_imports(code)
    #code = remove_unused_functions(code) # cannot get this to work
    code = remove_print_statements(code)
    code = remove_empty_lines(code)
    # code = remove_visualization_code(code) # visualization code may indicate like evaluation or EDA or something, which we still want to be able to classify
    # code = remove_notebook_specific_code(code) # some magic stuff could be useful info - saving bq to parquet on GCS for example
    code = remove_exploratory_code(code)
    code = remove_plusminus_markers(code)
    code = add_line_numbers(code)
    
    return code
