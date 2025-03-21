import json
import yaml
import re


def convert_to_dict(json_str):
    """
    Convert the LLM-generated JSON string to a Python dictionary.
    
    Args:
        json_str (str): The raw text response from the LLM
        
    Returns:
        dict or None: The parsed dictionary with component information, or None if parsing fails.
    """
    try:
        # Strip unnecessary whitespace
        json_str = json_str.strip()

        # Use regex to find the first JSON object in the text
        match = re.search(r'\{.*\}', json_str, re.DOTALL)
        if not match:
            raise ValueError("No JSON object found in the LLM response")
        
        json_content = match.group(0)  # Extract matched JSON content
        
        # Parse JSON into a Python dictionary
        return json.loads(json_content)

    except json.JSONDecodeError as e:
        print(f"Error parsing JSON: {e}")
        print(f"JSON content attempted to parse: {json_content[:300]}...")
        return None  # Returning None instead of an error dictionary
    
    except Exception as e:
        print(f"Unexpected error: {e}")
        return None  # Returning None to signal failure
    


def list_to_yaml_string(data_list):
    """
    Convert a list of dictionaries to a YAML-formatted string while preserving order.
    
    Args:
        data_list (list): List of dictionaries to convert
        
    Returns:
        str: YAML-formatted string representation of the list of dictionaries
    """
    try:
        # Use yaml.safe_dump to convert Python objects to YAML string
        # Set sort_keys=False to preserve the order of dictionary keys
        yaml_string = yaml.safe_dump(data_list, sort_keys=False)
        return yaml_string
    except Exception as e:
        print(f"Error converting to YAML string: {e}")
        return ""
    

def yaml_to_dict(yaml_str):
    # Remove Markdown code block markers and clean whitespace
    cleaned_yaml = re.sub(r'```(?:yaml)?\n|```', '', yaml_str).strip()
    try:
        return yaml.safe_load(cleaned_yaml)
    except yaml.YAMLError as e:
        print(f"Error parsing YAML: {e}")
        return None
    
def dict_to_yaml(data):
    """Convert dictionary back to YAML string."""
    return yaml.dump(data, default_flow_style=False, sort_keys=False)