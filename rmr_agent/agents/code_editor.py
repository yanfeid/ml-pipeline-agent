from llms import LLMClient  # Importing the LLM client 1

def process_file(file_path, llm_model: str = "gpt-4o"):
    """
    Reads a Python file, calls LLM to replace hardcoded values with configuration variables, 
    and writes back the modified version.

    :param file_path: Path to the Python file to modify.
    :param llm_model: The name of the LLM model to use.
    """
    # Initialize the LLM client
    llm_client = LLMClient(model_name=llm_model)

    # Read the original Python code
    with open(file_path, "r", encoding="utf-8") as file:
        original_code = file.read()

    # Construct the LLM prompt
    prompt_editor = f"""
    You are an AI agent that processes Python scripts containing configuration parameters.
    Your task is to analyze the provided Python code, detect any hardcoded values (such as 
    strings, numbers, or paths), and replace them with the corresponding predefined 
    configuration variables when applicable.

    - Identify all configuration variables already defined in the script.
    - Only modify the research code part(below the research code comments), do not modify other code
    - Find occurrences of hardcoded values that match or should be mapped to these variables.
    - Replace hardcoded values with their corresponding configuration variables.
    - Avoid duplicated code and make sure the research code is clean
    - Ensure the modified script remains functionally equivalent and syntactically correct.

    Below is the Python script that requires modification:

    ```python
    {original_code}
    ```

    Please return the modified Python script without any additional explanations.
    """

    # Call the LLM to process the code
    modified_code = llm_client.call_llm(
        prompt=prompt_editor,
        max_tokens=500,
        temperature=0,
        repetition_penalty=1.0,
        top_p=1
    )

    # Write the modified code back to the file
    with open(file_path, "w", encoding="utf-8") as file:
        file.write(modified_code)

    print(f"Updated {file_path}: Hardcoded values replaced with configuration variables.")

# Example usage
if __name__ == "__main__":
    llm_model = "gpt-4o"  # Define your LLM model name

# might need to use forloop
    process_file("research_code.py", llm_model)
