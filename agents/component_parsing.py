import litellm
from llms import LLMClient
from utils import convert_to_dict

    

def parse_component_identification(response_text):
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
        "line_range": "The exact line range as specified (e.g., 'Lines 258-287, 300-311')",
        "evidence": [
            "Full evidence item text including the quoted part and description",
            "Another evidence item text"
        ],
        "why_separate": "The explanation of why this component is separate (or null if not present)"
    }}
}}

Make sure to:
1. Keep the line range exactly as specified in the text
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
    parsed_dict = convert_to_dict(parsed_text)
    return parsed_text, parsed_dict



