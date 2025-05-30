import os
import json
import yaml
import re
import ast
import configparser
from pathlib import Path
import litellm
from rmr_agent.llms import LLMClient
from rmr_agent.utils import convert_to_dict


def update_attributes_with_existing_config(attribute_text, config_path):
    raise NotImplementedError("This function is not implemented yet.")
    path_obj = Path(config_path)
    config_text = path_obj.read_text()
    #print(config_text)

    fill_config_attributes_prompt = f"""Replace all configuration references in this YAML with their actual values from the provided configuration data. Maintain the same format (with the dash prefix) but replace any expressions with the actual string values from the config.
    YAML: 
    {attribute_text}

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


def read_config_file(file_path):
    """
    Open a configuration file (e.g., .yaml, .json, .ini) and return its content as a string.
    
    Args:
        file_path (str): The path to the configuration file.
        
    Returns:
        str: The content of the file as a string.
    """
    raise NotImplementedError("This function is not implemented yet.")
    file_extension = os.path.splitext(file_path)[1].lower()
    
    try:
        with open(file_path, 'r', encoding='utf-8') as f:
            if file_extension == '.json':
                # For JSON files
                config_content = json.dumps(json.load(f), indent=2)
            elif file_extension in ['.yaml', '.yml']:
                # For YAML files
                config_content = yaml.dump(yaml.safe_load(f), default_flow_style=False)
            elif file_extension == '.ini':
                # For INI files
                config = configparser.ConfigParser()
                config.read_file(f)
                config_content = '\n'.join([f'[{section}]\n' + '\n'.join(f'{key}={value}' for key, value in config.items(section)) for section in config.sections()])
            else:
                # If file is not recognized, just return its content as plain text
                config_content = f.read()

        return config_content
    
    except Exception as e:
        print(f"Error reading {file_path}: {e}")
        return None


def check_if_need_config_fill(attribute_text):
    try:
        # Convert the JSON response into a Python dictionary
        attribute_identification_dict = convert_to_dict(attribute_text)

        if attribute_identification_dict == None:
            raise ValueError("No JSON object found in the LLM attribute identification response")
        
        # Check if any component in the dictionary has 'needs_config_fill' set to True
        for component_name, component_data in attribute_identification_dict.items():
            # If 'needs_config_fill' is present and True, return True
            if component_data.get('needs_config_fill', False):
                return True
        
        # If no component requires config fill, return False
        return False
    except Exception as e:
        print(f"Error in check_if_need_config_fill: {e}")
        return False



# Agent function
def parse_attribute_identification(component_identification_dict, attribute_text, existing_config_file_path=""):
    components_list = list(component_identification_dict.keys())
    needs_config_fill = check_if_need_config_fill(attribute_text)
    parse_prompt = f"""You are parsing a JSON string to correct its content and produce a valid JSON.

### Instructions:
    - Include all components from the provided "Components List" and exclude any additional components not listed.
    - Extract only input and output variables that are static and configurable, excluding any variables with values that are function calls, method calls, list comprehensions, or other dynamic expressions.
    - Exclude long column lists, such as categorical, numerical, meta, or candidate columns, from being treated as variables. The target (or label) column list, weight column list, are okay to included as variables however. Also, lists used directly in data operations (e.g., join keys, filter keys, grouping keys, indexing or sort keys) are fine to include if necessary.
    - For the extracted valid input and output variables, maintain the "already_exists" and "renamed" values (true or false) as they are in the provided JSON. 
    - Detect whether or not there are any variables loaded from a configuration file - identify whether any of the variables have a value which is missing in the code and instead being loaded dynamically from a configuration file (e.g. the value is left as config['variable_name'] or config.get('variable_name', 'default_value')). If so, set the "needs_config_fill" flag to True for that component.
    - Produce only valid JSON in your response

### Output format (JSON):
{{
    "<ML_COMPONENT_NAME_HERE>": {{
        "inputs": [
            {{
                "name": "<INPUT_VARIABLE_1_NAME>", 
                "value": "<INPUT_VARIABLE_1_VALUE>",
                "already_exists": <BOOL_HERE>,
                "renamed": <BOOL_HERE>
            }},
            {{
                "name": "<INPUT_VARIABLE_2_NAME>", 
                "value": "<INPUT_VARIABLE_2_VALUE>",
                "already_exists": <BOOL_HERE>,
                "renamed": <BOOL_HERE>
            }}
        ],
        "outputs": [
            {{
                "name": "<OUTPUT_VARIABLE_1_NAME>", 
                "value": "<OUTPUT_VARIABLE_1_VALUE>",
                "already_exists": <BOOL_HERE>,
                "renamed": <BOOL_HERE>
            }},
            {{
                "name": "<OUTPUT_VARIABLE_2_NAME>", 
                "value": "<OUTPUT_VARIABLE_2_VALUE>",
                "already_exists": <BOOL_HERE>,
                "renamed": <BOOL_HERE>
            }}
        ],
        "needs_config_fill": <BOOL_HERE>
    }}
}}

### Components List:
{components_list}

### Components With Their Identified Input and Output Variables:
{attribute_text}
"""
    if needs_config_fill and existing_config_file_path:
        # to do - use config file path
        config_content = read_config_file(existing_config_file_path)
        config_fill_prompt = f"""\n### Config values to use to fill in the variable values:\n{config_content}"""
        parse_prompt += config_fill_prompt
    
    # Call the LLM to parse the attribute identification
    llm_client = LLMClient()
    response: litellm.types.utils.ModelResponse = llm_client.call_llm(
        prompt=parse_prompt,
        max_tokens=2048,
        temperature=0.0,
        repetition_penalty=1.0,
        top_p=0.3,
    )
    choices: litellm.types.utils.Choices = response.choices
    parsed_attributes_text = choices[0].message.content or ""
    if not parsed_attributes_text:
        raise ValueError("No content returned from the LLM for attribute identification parsing")

    # Convert the LLM response into a dictionary
    parsed_attributes_dict = convert_to_dict(parsed_attributes_text)
    if not parsed_attributes_dict:
        raise ValueError("No valid JSON object found in the LLM attribute identification response")
    
    # Add file name and line range to the result to bring all the node information together. Delete any extra components hallucinated by LLM. 
    components_to_delete = []
    for component in parsed_attributes_dict.keys():
        if component not in component_identification_dict:
            print(f"Found an extra component {component} added by LLM during attribute identification parsing. Deleting it")
            components_to_delete.append(component) # delete later so we do not edit dictionary we are iterating over
            continue
        parsed_attributes_dict[component]["file_name"] = component_identification_dict[component].get('file_name', 'None')
        parsed_attributes_dict[component]["line_range"] = component_identification_dict[component].get('line_range', 'None')

    # Delete the invalid components
    for component in components_to_delete:
        del parsed_attributes_dict[component]

    return parsed_attributes_text, parsed_attributes_dict


