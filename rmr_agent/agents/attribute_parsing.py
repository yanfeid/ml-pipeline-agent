from pathlib import Path
import litellm
from llms import LLMClient
from utils import convert_to_dict


def update_attributes_with_existing_config(attribute_yaml, config_path):
    path_obj = Path(config_path)
    config_text = path_obj.read_text()
    #print(config_text)

    fill_config_attributes_prompt = f"""Replace all configuration references in this YAML with their actual values from the provided configuration data. Maintain the same format (with the dash prefix) but replace any expressions with the actual string values from the config.
    YAML: 
    {attribute_yaml}

    Config: 
    {config_text}"""

    llm_client = LLMClient(model_name="gpt-4o")
    response: litellm.types.utils.ModelResponse = llm_client.call_llm(
        prompt=fill_config_attributes_prompt,
        max_tokens=2048,
        temperature=0.0,
        repetition_penalty=1.0,
        top_p=0.3,
    )
    choices: litellm.types.utils.Choices = response.choices
    updated_attributes = choices[0].message.content or ""
    return updated_attributes


def get_component_location(component_identification_dict):
    output_str = "" 
    for component in component_identification_dict.keys():
        output_str += f"{component}:\n"
        output_str += f"  - File name: {component_identification_dict[component].get('file_name', 'None')}\n"
        output_str += f"  - Line range: {component_identification_dict[component].get('line_range', 'None')}\n"
    return output_str



def parse_attribute_identification(component_identification_dict, attribute_text):
    location_str = get_component_location(component_identification_dict)
    parse_prompt = f"""Parse the following ML component line range and attribute identification response and return a JSON object with the following structure:
{{
    "Component Name": {{
        "file_name": "The exact file_name as specified (e.g., 'research/driver_creation.ipynb')",
        "line_range": "The exact line range as specified (e.g., 'Lines 258-311')",
        "inputs": [
            "Full input item line including its variable name and value",
            "Another input item text"
        ],
        "outputs": [
            "Full output item line including its variable name and value",
            "Another output item text"
        ]
    }}
}}

### Make Sure To:
1. Exclude any extra components which are not present in the "Components Locations" section with a file name and line range identified
2. Keep the line range exactly as specified in the text.
3. Extract all input and output items with their variable names and descriptions. If no name is present, make a descriptive name for the attribute. 
4. Exclude input/output attributes that contain function/method calls or list comprehension expressions. 
5. Ignore any additional text that appears after the last component.

### Component Locations:
{location_str}

### Component Input and Output Attributes:
{attribute_text}
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
    parsed_attributes_text = choices[0].message.content or ""
    parsed_attributes_dict = convert_to_dict(parsed_attributes_text)
    return parsed_attributes_text, parsed_attributes_dict
