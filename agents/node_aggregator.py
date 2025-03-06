import os
import json
import yaml
import re
from typing import List, Dict
import litellm
from llms import LLMClient


def combine_dicts_to_yaml(dict_list):
    """
    Convert a list of dictionaries directly to a YAML string.
    
    Args:
        dict_list (list): List of dictionaries to convert to YAML
    
    Returns:
        str: A single YAML string containing all the node data
    """
    # Dictionary to hold all node data
    all_nodes = {}
    
    # Process each dictionary in the list
    for dictionary in dict_list:
        if isinstance(dictionary, dict):
            # Add each key-value pair to the combined dictionary
            for key, value in dictionary.items():
                all_nodes[key] = value
    
    # Convert the combined dictionary to a YAML string
    yaml_string = yaml.dump(all_nodes, sort_keys=False, default_flow_style=False)
    
    return yaml_string



def node_aggregator_agent(all_final_components: List[Dict]):
    yaml_string = combine_dicts_to_yaml(all_final_components)
    aggregation_prompt = f"""

"""
    llm_client = LLMClient(model_name="gpt-4o")
    response: litellm.types.utils.ModelResponse = llm_client.call_llm(
        prompt=aggregation_prompt,
        max_tokens=2048,
        temperature=0.0,
        repetition_penalty=1.0,
        top_p=0.3,
    )
    choices: litellm.types.utils.Choices = response.choices
    agreggated_nodes_yaml = choices[0].message.content or ""
    return agreggated_nodes_yaml
