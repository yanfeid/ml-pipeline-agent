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


def update_attributes_with_existing_config(attribute_dict, config_path):
    """
    Replace all configuration references in the attribute dictionary with actual values from the config file.

    Args:
        attribute_dict (dict): The parsed attribute dictionary with config references
        config_path (str): Path to the configuration file

    Returns:
        dict: Updated attribute dictionary with actual values
    """
    if not config_path or not attribute_dict:
        return attribute_dict

    # Read the configuration file and parse it into a dictionary
    try:
        with open(config_path, 'r', encoding='utf-8') as f:
            if config_path.endswith('.json'):
                config = json.load(f)
            elif config_path.endswith(('.yaml', '.yml')):
                config = yaml.safe_load(f)
            elif config_path.endswith('.ini'):
                parser = configparser.ConfigParser()
                parser.read_file(f)
                # Convert to dictionary
                config = {}
                for section in parser.sections():
                    for key, value in parser.items(section):
                        config[key] = value
                # Add DEFAULT section
                for key, value in parser.defaults().items():
                    config[key] = value
            else:
                print(f"Unsupported configuration file format: {config_path}")
                return attribute_dict
    except Exception as e:
        print(f"Error reading configuration file: {e}")
        return attribute_dict

    # Regular expression patterns for matching configuration references
    # 1. Match config.get('key') and config.get('section', 'key')
    config_get_pattern = re.compile(r"config\.get\(['\"]([^'\"]+)['\"](?:,\s*['\"]([^'\"]+)['\"])?(?:,\s*([^)]+))?\)")
    # 2. Match config['key']
    config_bracket_pattern = re.compile(r"config\[['\"]([^'\"]+)['\"]\]")
    # 3. Match config['section']['key'] nested references
    config_nested_pattern = re.compile(r"config\[['\"]([^'\"]+)['\"]\]\[['\"]([^'\"]+)['\"]\]")

    # Process all components and their attributes recursively
    for component_name, component_data in attribute_dict.items():
        component_updated = False

        # Process input attributes
        if "inputs" in component_data:
            for input_item in component_data["inputs"]:
                value = input_item.get("value")
                if not value:
                    continue

                # Check if value is a string type
                if not isinstance(value, str):
                    continue

                # 1. Match config['section']['key'] nested patterns - process nested patterns first
                match = config_nested_pattern.search(value)
                if match:
                    section, key = match.group(1), match.group(2)
                    # Check if the configuration dictionary has the section part
                    if section in config and isinstance(config[section], dict) and key in config[section]:
                        # Format value according to type
                        input_item["value"] = format_value_for_yaml(config[section][key])
                        component_updated = True
                    continue

                # 2. Match config.get('key') or config.get('section', 'key') patterns
                match = config_get_pattern.search(value)
                if match:
                    section_or_key = match.group(1)
                    option = match.group(2)  # May be None

                    if option:  # Has second parameter, indicating section.option format
                        if (section_or_key in config and
                            isinstance(config[section_or_key], dict) and
                            option in config[section_or_key]):
                            # Get option value from section
                            input_item["value"] = format_value_for_yaml(config[section_or_key][option])
                            component_updated = True
                    else:  # Only one parameter, directly as key
                        if section_or_key in config:
                            # Format value according to type
                            input_item["value"] = format_value_for_yaml(config[section_or_key])
                            component_updated = True
                    continue

                # 3. Match config['key'] pattern
                match = config_bracket_pattern.search(value)
                if match:
                    key = match.group(1)
                    if key in config:
                        # Format value according to type
                        input_item["value"] = format_value_for_yaml(config[key])
                        component_updated = True
                    continue

                # Check more complex expressions like os.path.join(config['path'], 'subdir')
                if "config" in value and ("os.path.join" in value or "os.path.abspath" in value):
                    for key, conf_value in config.items():
                        # Only process string type configuration values for path joining
                        if isinstance(conf_value, str) and f"config['{key}']" in value:
                            # Simple path joining processing
                            if "os.path.join" in value:
                                parts = value.split("os.path.join(")[1].rstrip(")").split(",")
                                if len(parts) > 1 and f"config['{key}']" in parts[0]:
                                    # Extract second path part
                                    second_part = parts[1].strip().strip("'\"")
                                    input_item["value"] = os.path.join(conf_value, second_part)
                                    component_updated = True
                                    break
                            # Replace config references in other path expressions
                            input_item["value"] = value.replace(f"config['{key}']", conf_value).replace(f"config[\"{key}\"]", conf_value)
                            component_updated = True
                            break

        # Process output attributes
        if "outputs" in component_data:
            for output_item in component_data["outputs"]:
                value = output_item.get("value")
                if not value:
                    continue

                # Check if value is a string type
                if not isinstance(value, str):
                    continue

                # 1. Match config['section']['key'] nested patterns - process nested patterns first
                match = config_nested_pattern.search(value)
                if match:
                    section, key = match.group(1), match.group(2)
                    # Check if the configuration dictionary has the section part
                    if section in config and isinstance(config[section], dict) and key in config[section]:
                        # Format value according to type
                        output_item["value"] = format_value_for_yaml(config[section][key])
                        component_updated = True
                    continue

                # 2. Match config.get('key') or config.get('section', 'key') patterns
                match = config_get_pattern.search(value)
                if match:
                    section_or_key = match.group(1)
                    option = match.group(2)  # May be None

                    if option:  # Has second parameter, indicating section.option format
                        if (section_or_key in config and
                            isinstance(config[section_or_key], dict) and
                            option in config[section_or_key]):
                            # Get option value from section
                            output_item["value"] = format_value_for_yaml(config[section_or_key][option])
                            component_updated = True
                    else:  # Only one parameter, directly as key
                        if section_or_key in config:
                            # Format value according to type
                            output_item["value"] = format_value_for_yaml(config[section_or_key])
                            component_updated = True
                    continue

                # 3. Match config['key'] pattern
                match = config_bracket_pattern.search(value)
                if match:
                    key = match.group(1)
                    if key in config:
                        # Format value according to type
                        output_item["value"] = format_value_for_yaml(config[key])
                        component_updated = True
                    continue

                # Check more complex expressions like os.path.join(config['path'], 'subdir')
                if "config" in value and ("os.path.join" in value or "os.path.abspath" in value):
                    for key, conf_value in config.items():
                        # Only process string type configuration values for path joining
                        if isinstance(conf_value, str) and (f"config['{key}']" in value or f'config["{key}"]' in value):
                            # Simple path joining processing
                            if "os.path.join" in value:
                                parts = value.split("os.path.join(")[1].rstrip(")").split(",")
                                if len(parts) > 1 and (f"config['{key}']" in parts[0] or f'config["{key}"]' in parts[0]):
                                    # Extract second path part
                                    second_part = parts[1].strip().strip("'\"")
                                    output_item["value"] = os.path.join(conf_value, second_part)
                                    component_updated = True
                                    break
                            # Replace config references in other path expressions
                            output_item["value"] = value.replace(f"config['{key}']", conf_value).replace(f"config[\"{key}\"]", conf_value)
                            component_updated = True
                            break

        # If any component has been updated, set needs_config_fill to False
        if component_updated and "needs_config_fill" in component_data:
            component_data["needs_config_fill"] = False

    return attribute_dict

def format_value_for_yaml(value):
    """
    Format a value according to its type for YAML compatibility.

    Args:
        value: The value to be formatted

    Returns:
        Value formatted appropriately for YAML
    """
    if isinstance(value, (int, float, bool)):
        # Numbers and boolean values don't need quotes
        return value
    elif isinstance(value, str):
        # String values don't need quotes
        return value
    elif isinstance(value, list):
        # Format lists as string representation with single quotes
        list_str = str(value)
        # Replace double quotes with single quotes to match YAML format
        list_str = list_str.replace('"', "'")
        return list_str
    elif isinstance(value, dict):
        # Format dictionaries as string representation with single quotes
        dict_str = str(value)
        # Replace double quotes with single quotes to match YAML format
        dict_str = dict_str.replace('"', "'")
        return dict_str
    else:
        # Convert other types to string
        return str(value)


def read_config_file(file_path):
    """
    Open a configuration file (e.g., .yaml, .json, .ini) and return its content as a string.

    Args:
        file_path (str): The path to the configuration file.

    Returns:
        str: The content of the file as a string.
    """
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

        if not attribute_identification_dict:
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
    """
    Parse attribute identification text and optionally fill in values from existing config file.

    Args:
        component_identification_dict (dict): Dictionary of identified components
        attribute_text (str): Raw attribute identification text from LLM
        existing_config_file_path (str, optional): Path to existing config file. Defaults to "".

    Returns:
        tuple: (parsed_attributes_text, parsed_attributes_dict)
    """
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
        config_content = read_config_file(existing_config_file_path)
        if config_content:
            config_fill_prompt = f"""\n### Config values to use to fill in the variable values:\n{config_content}"""
            parse_prompt += config_fill_prompt
            print(f"Added config content from {existing_config_file_path} to the prompt")
        else:
            print(f"Warning: Could not read config file at {existing_config_file_path}")
    
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
        print("No valid JSON object found in the LLM attribute identification response")
        return parsed_attributes_text, {}
    
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

    # Fill in attribute values from existing config file if provided
    if existing_config_file_path and parsed_attributes_dict:
        # Check if any component needs config values filled
        needs_filling = False
        for component_data in parsed_attributes_dict.values():
            if component_data.get("needs_config_fill", False):
                needs_filling = True
                break

        if needs_filling:
            print(f"Filling attribute values from config file: {existing_config_file_path}")
            try:
                # Update attributes with values from the config file
                filled_attributes_dict = update_attributes_with_existing_config(
                    parsed_attributes_dict,
                    existing_config_file_path
                )
                # Use the filled attributes if successful
                if filled_attributes_dict:
                    parsed_attributes_dict = filled_attributes_dict
                    # Also update the text representation for consistency
                    parsed_attributes_text = json.dumps(filled_attributes_dict, indent=2)
            except Exception as e:
                print(f"Error filling attribute values from config: {str(e)}")

    return parsed_attributes_text, parsed_attributes_dict


