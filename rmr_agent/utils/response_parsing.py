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
    
    
def yaml_to_dict(yaml_str: str):
    """
    Extracts YAML content from a string, prioritizing content within
    a ```yaml ... ``` or ``` ... ``` code block if present.
    If no block is found, it attempts to parse the entire string.

    Args:
        yaml_str (str): The string potentially containing YAML data,
                        possibly within a Markdown code block and with
                        other surrounding text.

    Returns:
        dict or list: The parsed YAML data, or None if parsing fails
                      or input is not a string.
    """
    if not isinstance(yaml_str, str):
        print("Error: Input must be a string.")
        return None

    # Regex to find content within ```yaml ... ``` or ``` ... ```
    # - ```(?:yaml\s*)? : Matches "```" followed optionally by "yaml" and spaces.
    #   (?:...) is a non-capturing group. \s* matches zero or more whitespace chars.
    # - (.*?) : Captures the content in between. It's non-greedy (?),
    #   and re.DOTALL makes . match newlines.
    # - ``` : Matches the closing triple backticks.
    pattern = re.compile(r"```(?:yaml\s*)?(.*?)```", re.DOTALL)
    match = pattern.search(yaml_str)

    content_to_parse = None
    source_of_content = "" # For debugging messages

    if match:
        # A fenced block was found, extract its content
        extracted_content = match.group(1).strip() # .strip() to remove leading/trailing newlines/spaces from the captured group
        if extracted_content: # Ensure extracted content is not empty
            content_to_parse = extracted_content
            source_of_content = "extracted YAML block"
        else:
            # Block found but was empty, try parsing the whole string as a fallback
            # print("DEBUG: Found an empty YAML block. Attempting to parse the whole string.")
            content_to_parse = yaml_str.strip()
            source_of_content = "entire string (after finding empty block)"
    else:
        # No ```...``` block found. Assume the entire string might be YAML.
        # print("DEBUG: No explicit YAML block found. Attempting to parse the whole string.")
        content_to_parse = yaml_str.strip()
        source_of_content = "entire string (no block detected)"

    if content_to_parse:
        try:
            return yaml.safe_load(content_to_parse)
        except yaml.YAMLError as e:
            print(f"Error parsing YAML from {source_of_content}: {e}")
            print(f"--- Content that failed to parse ---\n{content_to_parse}\n------------------------------------")
            return None
    else:
        # This case should ideally not be hit if yaml_str was not empty,
        # as content_to_parse would be yaml_str.strip().
        # But if yaml_str itself was empty or only whitespace.
        print("Error: No content to parse after processing.")
        return None

    
def dict_to_yaml(data):
    """Convert dictionary back to YAML string."""
    return yaml.dump(data, default_flow_style=False, sort_keys=False)