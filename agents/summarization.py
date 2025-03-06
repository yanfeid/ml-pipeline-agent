import os
from utils import preprocess_python_file
from llms import LLMClient
import litellm

def summarize_code(python_file_path, full_file_list):
    base_name = os.path.basename(python_file_path)  
    file_name = base_name.replace('.py', '.ipynb')

    cleaned_code = preprocess_python_file(python_file_path)
    line_count = len(cleaned_code.splitlines())  
    print(f"Summarizing code for file {file_name} which has ~{line_count} lines of code")
    summarization_prompt = f"""Analyze the following machine learning Python code and provide a practical summary of each major code block. Do not include an overall summary or draw conclusions beyond what each block explicitly does. Include only MAJOR code blocks or logical sections. Ignore code which is commented out. Do not include any code in the output — provide only concise, descriptive summaries in plain English.

Full File List:
{full_file_list}

Current File's Name:
{file_name}

Current File's Content:
{cleaned_code}

Output Format (for each major code block):
**[Brief few-word summary of what this block does] (Lines [start_line]-[end_line]):**
- [Brief, practical bullet points going into slightly more detail]

"""
    llm_client = LLMClient(model_name="gpt-4o")
    response: litellm.types.utils.ModelResponse = llm_client.call_llm(
        prompt=summarization_prompt,
        max_tokens=2048,
        temperature=0.0,
        repetition_penalty=1.0,
        top_p=0.3,
    )
    choices: litellm.types.utils.Choices = response.choices
    summary = choices[0].message.content or ""
    if not summary:
        raise ValueError(f"Summary for {file_name} is empty")
    return summary

    