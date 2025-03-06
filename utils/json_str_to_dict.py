import json

def convert_to_dict(json_str):
    """
    Convert the LLM-generated JSON string to a Python dictionary.
    
    Args:
        json_str (str): The raw text response from the LLM
        
    Returns:
        dict: The parsed dictionary with component information
    """
    try:
        # First, try to find JSON content by looking for opening and closing braces
        json_start = json_str.find('{')
        json_end = json_str.rfind('}') + 1
        
        if json_start == -1 or json_end == 0:
            raise ValueError("No JSON object found in the LLM response")
        
        # Extract the JSON part
        json_content = json_str[json_start:json_end]
        
        # Parse the JSON into a Python dictionary
        result = json.loads(json_content)
        
        return result
    
    except json.JSONDecodeError as e:
        # Handle malformed JSON
        print(f"Error parsing JSON: {e}")
        print(f"JSON content attempted to parse: {json_content[:100]}...")
        return {"error": f"Failed to parse JSON: {str(e)}"}
    
    except Exception as e:
        # Handle other errors
        return {"error": f"Unexpected error: {str(e)}"}