import litellm
import json
from llms import LLMClient
from utils import convert_to_dict, preprocess_python_file


def retry_component_identification(python_file_path, full_file_list, code_summary, model="gpt-4o", temperature=0, max_tokens=2048, 
                 frequency_penalty=0, presence_penalty=0):
    pass

def parse_component_identification(response_text, file):
    """
    Parse component identification response, extracting components with their line ranges,
    evidence, and why_separate sections.
    
    Args:
        response_text (str): The raw LLM response text
        
    Returns:
        dict: A dictionary where:
            - keys are component names
            - values are dictionaries with:
                - 'line_range' (str): The full line range text
                - 'evidence' (list): List of evidence items
                - 'why_separate' (str or None): Explanation of why this component is separate
        
    Raises:
        ValueError: If no components are identified or if the response format is invalid
    """

    parse_prompt = f"""Parse the following component identification response and return a JSON object with the following structure:
{{
    "Component Name": {{
        "line_range": "A single range from the minimum to maximum line number across all ranges (e.g., 'Lines 258-311' for 'Lines 258-287, 300-311')",
        "evidence": [
            "Full evidence item text including the quoted part and description",
            "Another evidence item text"
        ],
        "why_separate": "The explanation of why this component is separate (or null if not present)"
    }}
}}

Make sure to:
1. Merge all line ranges into a single range using the minimum start value and maximum end value (e.g., 'Lines 258-311' for 'Lines 258-287, 300-311'), even if there are gaps.
2. Extract all evidence items with their descriptions
3. Include the "why_separate" section if present, otherwise set to null
4. Ignore any additional text that appears after the last component

Here's the content to parse:

{response_text}
"""
    llm_client = LLMClient(model_name="gpt-4o")
    response: litellm.types.utils.ModelResponse = llm_client.call_llm(
        prompt=parse_prompt,
        max_tokens=2048,
        temperature=0.0,
        repetition_penalty=1.0,
        top_p=0.3,
    )
    choices: litellm.types.utils.Choices = response.choices
    parsed_text = choices[0].message.content or ""

    with open('rmr_agent/ml_components/component_definitions.json', 'r') as f:
        component_definitions = json.load(f)
    allowed_components = list(component_definitions.keys())

    # Create dictionary with parsed data
    parsed_dict = convert_to_dict(parsed_text)
    # Add the file name to each identified component
    for component, metadata in parsed_dict.items():
        if component not in allowed_components:
            print(f'Found identified component outside of allowed set of components for {file}: "{component}"')
            
        metadata['file_name'] = file

        if len(parsed_dict) == 1:
            # when only one component identified in the file, just take all of the lines in the file for that component. 
            cleaned_code = preprocess_python_file(file)
            num_lines = len(cleaned_code.splitlines())
            metadata['line_range'] = f"Lines 1-{num_lines}"

    

    return parsed_text, parsed_dict



