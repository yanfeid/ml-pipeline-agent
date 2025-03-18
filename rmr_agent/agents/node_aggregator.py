import os
import json
import yaml
import re
from typing import List, Dict
import litellm
from llms import LLMClient


def clean_string_value(value):
    """
    Clean and normalize string values from the input format.
    
    Args:
        value (str): The input string value, possibly with escaped quotes
        
    Returns:
        str: The cleaned string value
    """
    # Remove outer quotes if present
    if (value.startswith('"') and value.endswith('"')) or (value.startswith("'") and value.endswith("'")):
        value = value[1:-1]
    
    # Unescape quotes
    value = value.replace('\\"', '"').replace("\\'", "'")
    
    return value


def dict_list_to_yaml(components_list):
    """
    Convert a list of dictionaries to a YAML string.
    
    Parameters:
    components_list (list): A list containing dictionaries. 
                           Each dictionary contains one or more components as keys.
                           Each component is a dictionary with 'line_range', 'inputs', and 'outputs'.
    
    Returns:
    str: A YAML-formatted string representation of the input.
    """
    # Create a list to hold the reformatted data
    yaml_list = []
    
    # Process each dictionary in the input list
    for component_dict in components_list:
        for component_name, component_data in component_dict.items():
            # Create a dictionary for this component
            yaml_component = {
                component_name: {
                    'file_name': component_data['file_name'],
                    'line_range': component_data['line_range'],
                    'inputs': {},
                    'outputs': {}
                }
            }
            
            # Process inputs
            for input_item in component_data.get('inputs', []):
                parts = input_item.split(':', 1)
                if len(parts) == 2:
                    key = parts[0].strip()
                    value = parts[1].strip()
                    
                    # Clean the value string - remove outer quotes and unescape inner quotes
                    value = clean_string_value(value)
                    
                    yaml_component[component_name]['inputs'][key] = value
            
            # Process outputs 
            for output_item in component_data['outputs']:
                parts = output_item.split(':', 1)
                if len(parts) == 2:
                    key = parts[0].strip()
                    value = parts[1].strip()
                    
                    # Clean the value string
                    value = clean_string_value(value)
                    
                    yaml_component[component_name]['outputs'][key] = value
            
            yaml_list.append(yaml_component)
    
    # Define a custom representer for strings to avoid unnecessary quoting
    def represent_str(dumper, data):
        if '\n' in data:
            return dumper.represent_scalar('tag:yaml.org,2002:str', data, style='|')
        elif re.search(r'[,\[\]{}]', data) or data.startswith('"') or data.startswith("'"):
            return dumper.represent_scalar('tag:yaml.org,2002:str', data, style='"')
        else:
            return dumper.represent_scalar('tag:yaml.org,2002:str', data, style='')
    
    # Register the custom representer
    yaml.add_representer(str, represent_str)
    
    # Convert to YAML and return
    return yaml.dump(yaml_list, default_flow_style=False, sort_keys=False)


def node_aggregator_agent(all_final_components: List[Dict]):
    yaml_string = dict_list_to_yaml(all_final_components)
    # For now just bringing to properly formatted YAML. Not renaming any attributes (not sure if that is the right approach / necessary)
    """
    aggregation_prompt = f""""""
    llm_client = LLMClient(model_name="gpt-4o")
    response: litellm.types.utils.ModelResponse = llm_client.call_llm(
        prompt=aggregation_prompt,
        max_tokens=4096,
        temperature=0.0,
        repetition_penalty=1.0,
        top_p=0.3,
    )
    choices: litellm.types.utils.Choices = response.choices
    agreggated_nodes_yaml = choices[0].message.content or ""
    """
    agreggated_nodes_yaml = yaml_string
    return agreggated_nodes_yaml
