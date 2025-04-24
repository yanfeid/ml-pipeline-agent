
from llms import LLMClient  
import os
import ast

def code_editor_agent(python_file_path: str, llm_model: str = "gpt-4o"):
    llm_client = LLMClient(model_name=llm_model)

    # ==================    Params Replacement Part ======================
    with open(python_file_path, "r", encoding="utf-8") as f:
        python_code = f.read()

    prompt_editor = f"""
    You are an AI agent tasked with refactoring Python research scripts to ensure that configuration values are used consistently.

    Your instructions:
    1. In the **=== Research Code ===** section, remove any parameter declarations that are already defined earlier in the script. These predefined parameters have values starting with config.get.
    2. Ensure the research code just uses the correct variable name loaded from config in previous sections, avoid hard-coded.
    3. Ensure all parameters are declared properly and the code remains fully configurable.
    4. Return the complete modified Python script without any explanations or additional comments. 
    5. Do **not** include any Markdown formatting such as ```python or ``` — return only the raw Python code.

    Here is the Python script:
    {python_code}
    """
 
    print('prompt DEBUG',prompt_editor)
 
    # Call the LLM to process the code
    response = llm_client.call_llm(
        prompt=prompt_editor,
        max_tokens=4096,
        temperature=0,
        repetition_penalty=1.0,
        top_p=1
    )

    # print("👉 raw response:", response)

    modified_code = response.choices[0].message.content
    # Write the modified code back to the file
    with open(python_file_path, "w", encoding="utf-8") as file:
        file.write(modified_code)

    print(f"Updated {python_file_path}: Hardcoded values replaced with configuration variables.")

    # ==================    Code Cleanning Part ======================

    prompt_editor = f"""
    You are an AI agent responsible for cleaning and formatting messy Python code into readable, well-organized scripts or Jupyter Notebooks. 

    Your instructions:
    1. Do not delete any of the original code (unless there is clearly duplicated code). 
    Especially following code:
    ## gsutil authentication
    %ppauth
    2. Fix indentation and spacing to comply with PEP 8 and ensure the code runs smoothly in a Jupyter Notebook environment.
    3. Format the code into logical blocks, separated by two blank lines, avoid splitting the script into overly short chunks. Each block should reflect a meaningful code unit for conversion to Jupyter Notebook cells.
    4. Output only the raw Python code — do not include any explanations, comments, or Markdown formatting (e.g., ```python or ``` ).

    Here is the Python script:
    {modified_code}
    """

    # Call the LLM to process the code
    response = llm_client.call_llm(
        prompt=prompt_editor,
        max_tokens=4096,
        temperature=0,
        repetition_penalty=1.0,
        top_p=1
    )

    final_code = response.choices[0].message.content
    # Write the modified code back to the file
    with open(python_file_path, "w", encoding="utf-8") as file:
        file.write(final_code)

    print(f"Updated {python_file_path}: Code has been cleaned.")


    # ================== Assets Extraction Part ======================

    # Construct the LLM prompt
    prompt_editor = f"""
    You are given some research code that contains hardcoded column lists used for data processing.
    Your task is to refactor this code by extracting all column lists and organizing them into a Python dictionary, where each key corresponds to a specific column category, and the value is a list of column names.

    The target categories are fixed and must be:
    - candidate
    - categorical
    - feature
    - meta
    - var_analysis
    - vc_candidate

    If a column list does not clearly fit into one of the above categories, place it under the "other" category.

    Your response must meet **all** of the following rules:
    1. Return only a **valid Python dictionary** (not wrapped in markdown or code blocks).
    2. Do **not include any explanation**, comment, formatting, or extra text.
    3. The dictionary keys must match the categories exactly as written above.
    4. If a category has no columns, use an empty list as its value.
    5. All column names must be strings inside the lists.

    Example format (your output mightlook like this):

    {{
        "candidate": ["col1", "col2"],
        "categorical": [],
        "feature": ["f1", "f2"],
        "meta": ["id", "timestamp"],
        "var_analysis": [],
        "vc_candidate": [],
        "other": ["unexpected_col1"]
    }}

    Return only the dictionary.

    Here is the research code:
    {final_code}
    """
 
    # print('prompt DEBUG',prompt_editor)
 
    # Call the LLM to process the code
    response = llm_client.call_llm(
        prompt=prompt_editor,
        max_tokens=2048,
        temperature=0,
        repetition_penalty=1.0,
        top_p=1
    )

    llm_output = response.choices[0].message.content

    try:
        column_lists = ast.literal_eval(llm_output)
    except Exception as e:
        raise ValueError(f"Failed to parse LLM response. Error: {e}\nContent:\n{llm_output}")

    known_categories = [
        'candidate',
        'categorical',
        'feature',
        'meta',
        'var_analysis',
        'vc_candidate'
    ]

    final_columns = {key: [] for key in known_categories}
    final_columns['other'] = []

    for key, columns in column_lists.items():
        if key in known_categories:
            final_columns[key] = columns
        else:
            final_columns['other'].extend(columns)


    os.makedirs('../assets', exist_ok=True)

    for category, columns in final_columns.items():
        file_path = os.path.join('../assets', f'{category}.txt')
        with open(file_path, 'w', encoding='utf-8') as f:
            for col in columns:
                f.write(f"{col}\n")

    return  column_lists


# if __name__ == "__main__":
#     BASE_DIR = "/Users/yanfdai/Desktop/codespace/DAG_FULLSTACK/rmr_agent/rmr_agent"
#     notebooks_dir = os.path.join(BASE_DIR, "notebooks")
#     for filename in os.listdir(notebooks_dir):
#         if filename.endswith(".py"):
#             python_file_path = os.path.join(notebooks_dir, filename)
#             print(f"\n🛠️ Processing: {filename}")

#             try:
#                 modified_code = code_editor_agent(python_file_path)
#                 print("✅ Modified script:")
#                 print(modified_code)
#             except Exception as e:
#                 print(f"❌ Error processing {filename}: {e}")

#     print("\n✅ All scripts in notebooks/ processed.")