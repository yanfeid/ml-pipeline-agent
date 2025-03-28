import os
import json
import yaml
import re
from typing import List, Dict
import litellm
from rmr_agent.llms import LLMClient


def clean_string_value(value):
    """Clean string values by removing outer quotes and unescaping inner quotes."""
    if value is None:
        return "undefined"
    if not isinstance(value, str):
        return str(value)
    if (value.startswith('"') and value.endswith('"')) or (value.startswith("'") and value.endswith("'")):
        value = value[1:-1]
    return value.replace('\\"', '"').replace("\\'", "'")

def dict_list_to_yaml(components_list):
    """
    Convert a list of component dictionaries to a YAML string.

    Args:
        components_list (list): List of dictionaries, each containing components as keys
                               and their data (file_name, line_range, inputs, outputs) as values.

    Returns:
        str: YAML-formatted string of the components.
    """
    # Track component occurrences and processed counts in one pass
    component_counts = {}
    yaml_data = []

    for component_dict in components_list:
        for component_name, component_data in component_dict.items():
            # Increment occurrence count
            component_counts[component_name] = component_counts.get(component_name, 0) + 1

            # Generate unique component name with underscore (Pythonic)
            count = component_counts[component_name]
            final_name = f"{component_name} {count}" if count > 1 else component_name

            # Initialize component structure
            component_entry = {
                final_name: {
                    'file_name': component_data.get('file_name', 'unknown_file'),
                    'line_range': component_data.get('line_range', ''),
                    'inputs': {},
                    'outputs': {}
                }
            }

            # Process inputs
            for input_item in component_data.get('inputs', []):
                key = input_item.get("name", "unnamed_variable")
                val = clean_string_value(input_item.get("value", "undefined"))
                component_entry[final_name]['inputs'][key] = val

            # Process outputs
            for output_item in component_data.get('outputs', []):
                key = output_item.get("name", "unnamed_variable")
                val = clean_string_value(output_item.get("value", "undefined"))
                component_entry[final_name]['outputs'][key] = val

            # Add to the list
            yaml_data.append(component_entry)

    # Custom YAML string representer for cleaner output
    def represent_str(dumper, data):
        if '\n' in data:
            return dumper.represent_scalar('tag:yaml.org,2002:str', data, style='|')
        return dumper.represent_scalar('tag:yaml.org,2002:str', data, style='')

    yaml.add_representer(str, represent_str)

    # Convert to YAML and return
    return yaml.dump(yaml_data, default_flow_style=False, sort_keys=False)


def node_aggregator_agent(all_final_components: List[Dict]):
    yaml_string = dict_list_to_yaml(all_final_components)
    # For now just bringing to properly formatted YAML. Not renaming any attributes (not sure if that is the right approach / necessary)
    '''
    node_aggregation_prompt = f"""You are analyzing variable names in a YAML file. Your task is to ensure all variables which have identical values also use identical variable names.
### Instructions:

"""
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
    '''

    agreggated_nodes_yaml = yaml_string
    return agreggated_nodes_yaml
