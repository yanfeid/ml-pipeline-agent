
from rmr_agent.llms import LLMClient
from rmr_agent.utils import py_to_notebook

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
    4. Return the complete modified script only, with no markdown formatting, no explanations, and no code fences like ```python.

    Remember: even if the code is not standard Python, you must preserve it unchanged.

    Here is the script:
    {python_code}
    """
 
    # print('prompt DEBUG',prompt_editor)
    response = llm_client.call_llm(
        prompt=prompt_editor,
        max_tokens=16384,
        temperature=0,
        repetition_penalty=1.0,
        top_p=0.1
    )

    # print("raw response:", response)
    modified_code = response.choices[0].message.content
    # Write the modified code back to the file
    with open(python_file_path, "w", encoding="utf-8") as file:
        file.write(modified_code)

    print(f"Updated {python_file_path}: Hardcoded values replaced with configuration variables.")
    py_to_notebook(python_file_path)

