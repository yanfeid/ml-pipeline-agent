
from rmr_agent.llms import LLMClient
import os
import ast

def code_editor_agent(python_file_path: str, llm_model: str = "gpt-4o"):
    llm_client = LLMClient(model_name=llm_model)

    # ==================    Params Replacement Part ======================
    with open(python_file_path, "r", encoding="utf-8") as f:
        python_code = f.read()

    prompt_editor = f"""
    You are an AI agent tasked with refactoring research scripts to ensure that configuration values are used consistently.

    Your instructions:
    1. Inside the === Research Code === section, only remove pure parameter assignment lines (e.g., x = ..., y = ...) where the variable is already defined earlier using config.get.
    2. DO NOT remove, modify, or touch any other lines, even if they are non-Python, invalid syntax, BigQuery magics (%%bigquery), SQL code, or unknown formats.
    3. Ensure the research code uses only the variables loaded from config, with no hard-coded values.
    4. Return the complete modified script with no markdown or explanations. Do **not** include any Markdown formatting such as ```python or ``` — return only the raw Python code.

    Remember: even if the code is not standard Python, you must preserve it unchanged.

    Here is the script:
    {python_code}
    """
 
    # print('prompt DEBUG',prompt_editor)
 
    # Call the LLM to process the code
    response = llm_client.call_llm(
        prompt=prompt_editor,
        max_tokens=16384,
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
    You are an AI agent responsible for formatting messy code into readable, well-organized scripts. 

    Your instructions:
    1. Your task is to fix only indentation and spacing according to PEP 8. 
    2. Do not delete any original code lines or comments, even if you do not understand them.
    e.g,. ## gsutil authentication
           %ppauth
    or any other magic commands
    3. Group code into logical blocks separated by two blank lines. Avoid overly short blocks. Each block should be a complete and meaningful unit and should contain at least 4 lines of code.
    4. Output only the updated code — do not include any explanations or Markdown formatting (e.g., ```python or ``` ).

    Here is the Python script:
    {modified_code}
    """

    # Call the LLM to process the code
    response = llm_client.call_llm(
        prompt=prompt_editor,
        max_tokens=16384,
        temperature=0,
        repetition_penalty=1.0,
        top_p=1
    )

    final_code = response.choices[0].message.content
    # Write the modified code back to the file
    with open(python_file_path, "w", encoding="utf-8") as file:
        file.write(final_code)

    print(f"Updated {python_file_path}: Code has been cleaned.")