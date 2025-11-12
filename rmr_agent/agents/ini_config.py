import os
import re
import yaml
import logging
from datetime import datetime
from rmr_agent.llms import LLMClient
from typing import Dict, Any
from rmr_agent.utils.logging_config import setup_logger

# 设置模块日志记录器
logger = setup_logger(__name__)

# ========== **Extract .ini Content from AI Response** ==========
def extract_ini_content(response):
    """Extracts and cleans `[general]` section content from LLM response. Ensures .ini format and removes markdown."""
    if response is None:
        raise ValueError("AI response is None, unable to extract `.ini` content.")
    # Ensure the response contains valid choices with a message
    if hasattr(response, "choices") and response.choices:
        response_text = response.choices[0].message.content  # Extract the `.ini` formatted string
    else:
        raise ValueError("Invalid AI response format, unable to extract `.ini` content.")
    if not response_text:
        raise ValueError("AI returned an empty `.ini` content.")

    # Remove Markdown-style code block formatting, including ```ini, ```yaml, or plain ```
    response_text = re.sub(r"^```(?:ini|yaml)?\s*|^```\s*|\s*```$", "", response_text.strip(), flags=re.IGNORECASE)

    return response_text

# ========== **Filter duplicate lines** ==========
def filter_duplicate_value_lines(ini_str, verified_dag):

    controlled_params = set()
    seen_controlled_params = set()

    for edge in verified_dag.get("edges", []):
        attributes = edge.get("attributes", {})
        for param_name in attributes.keys():
            controlled_params.add(param_name)

    filtered_lines = []
    current_section = None

    for line in ini_str.splitlines():
        stripped = line.strip()

        if stripped.startswith("[") and stripped.endswith("]"):
            current_section = stripped.strip("[]").lower()
            filtered_lines.append(line)
            continue

        if stripped == "":
            filtered_lines.append(line)
            continue

        if "=" in line:
            key, value = line.split("=", 1)
            key = key.strip()
            value = value.strip()

            if key in controlled_params:
                if key not in seen_controlled_params:
                    filtered_lines.append(line)
                    seen_controlled_params.add(key)
                else:
                    continue
            else:
                filtered_lines.append(line)
        else:
            filtered_lines.append(line)

    return "\n".join(filtered_lines)

# ========== **Replace hard-coded params with general configurable params in env.ini** ==========
def parse_env_ini(env_ini):
    """
    Parse environment_ini_str into a dictionary of key-value pairs.
    :param env_ini_str: The environment ini content as a string.
    :return: A dictionary of parameters.
    """
    env_vars = {}
    for line in env_ini.splitlines():
        match = re.match(r'(\w+)\s*=\s*(.+)', line)  # Match key=value pairs
        if match:
            key, value = match.groups()
            env_vars[key] = value.strip()
    return env_vars

def replace_with_env_vars(generated_file, env_vars):
    """
    Replace paths in the generated file with ${general:<param_name>} if they match env.ini values.
    :param generated_file_str: The content of the generated file.
    :param env_vars: Dictionary of environment variables.
    :return: The modified file content.
    """
    for param_name, param_value in sorted(env_vars.items(), key=lambda x: -len(x[1])):  # Sort by length (longest first)
        if param_value and param_value in generated_file:
            generated_file = generated_file.replace(param_value, f"${{general:{param_name}}}")

    return generated_file

# ========== **fill in today's date** ==========
def fill_in_today_date(ini_content: str) -> str:
    """
    Replaces the line starting with 'refresh_date =' with today's date in the given .ini content.
    """
    today_str = datetime.today().strftime('%Y-%m-%d')
    lines = ini_content.splitlines()

    for i, line in enumerate(lines):
        if line.strip().startswith("refresh_date"):
            lines[i] = f"refresh_date = {today_str}"
            break

    return "\n".join(lines)


# ========== **Config Agent Part** ==========
def config_agent(verified_dag: Dict[str, Any], llm_model: str = "gpt-4o") -> Dict[str, Dict[str, Dict[str, str]]]:
    """
    Parses the verified DAG (YAML structure) and generates solution.ini and environment.ini content using an AI agent.

    Parameters:
    - verified_dag: Dict[str, Any] -> The validated DAG structure (parsed YAML)
    - llm_model: str -> Name of the LLM model to use (default: "gpt-4o")

    Returns:
    - Dict[str, Dict[str, Dict[str, str]]]: 
      - "solution_ini": Parsed solution.ini content
      - "environment_ini": Parsed environment.ini content
    """

    # Load YAML structure directly from verified_dag

    llm_client = LLMClient(model_name=llm_model)

    # ========== **Step 1: AI agent generates environment.ini content** ==========
    prompt_environment = f"""
    You are an AI agent that processes machine learning pipeline configurations in YAML format. 
    Your task is to analyze the provided YAML structure and generate a corresponding environment.ini content.

    ### Task Overview:
    - The structure of `environment.ini` is **fixed and must not be changed**.
    - Your goal is to **fill in the missing values based on the given YAML data**.
    - If a value **exists in the YAML**, insert it into the corresponding field.
    - If a value **is missing in the YAML**, leave the field empty (`""`).
    - Your response MUST be No explanations, No extra text. No backticks.

    ### Fixed Structure of `environment.ini`:
 
    [general]
    refresh_date =
    user =
    environment =
    mo_name =
    driver_dataset =
    dataproc_project_name =
    dataproc_storage_bucket =
    local_output_base_path =
    gcs_base_path =
    queue_name =
    namespace =

    ### Guidelines to Follow

    1. Default Values**
    - **Default Values:** 
        - Set `refresh_date` as blank by default.
        - Set `mo_name` as blank by default.
        - Set `environment` as blank by default.
        - `Queue Name` set to `default` if not provided.
        - `Namespace` set to `gds-packman` if not provided.

    2. **User & Owner Identification**
    - **Check for User Name:** Review the directory structure to identify if a user name (or owner) is present.
    - If detected, treat that directory segment as the username.

    3. **dataproc_project_name & dataproc_storage_bucket**
    - **dataproc_project_name:** Dataproc_project_name always starts with "ccg24-hrzana-". You can search keywords such as `gcp_project_id`, `project_name`. Leave blank if you could not fina a value started with "ccg24-hrzana-". 
    - **dataproc_storage_bucket:** Dataproc_storage_bucket always starts with "pypl-bkt-rsh-row-std-". You can search keywords such as `gcs_bucket_name`, `bucket_name`, `bucket_id`, etc. Set to blank if not provided.

    4. **Path Analysis**
    - **local_output_base_path:**
        - Identify paths containing keywords like “local” (typically starting with `/projects`).
        - Extract the longest common directory path.
    - **gcs_base_path:**
        - Detect paths starting with `gs://`.
        - Extract the longest common directory path.

    5. **Dynamic Replacement of Hardcoded Paths**
    - **Configurable Parameters:**  
        - For both local_output_base_path and gcs_base_path, only replace those directory segments whose content exactly matches the actual value of a configuration parameter (e.g., user, dataproc_project_name, dataproc_storage_bucket, etc.). 
        - **Rule:** Inspect each directory segment in the path. If a segment's content exactly equals the actual value of a configuration parameter, replace it with the corresponding placeholder in the format ${{general:<parameter_name>}}.
        - **Example:**  
        Given the input path:gs://pypl-pacman/administrator/david/dev/rmr
        If the actual value of dataproc_storage_bucket is pypl-pacman and the actual value of user is david, then the transformed path should be:
        gs://${{general:dataproc_storage_bucket}}/user/${{general:user}}/dev/rmr. Any directory segment that does not match any configuration parameter should remain unchanged.
        - **Note:** Only replace segments that are clearly identified as dynamic parameters; do not alter unrelated path segments.

    6. **Validation**
    - Verify that each hardcoded directory level in both `local_output_base_path` and `gcs_base_path` is either:
        - Correctly replaced by a configurable parameter, or
        - Left unchanged if it does not correspond to a dynamic parameter.


    ### YAML Content
    The YAML content is provided below:
    ```yaml
    {yaml.dump(verified_dag, default_flow_style=False)}
    ```

    Now, generate a properly formatted `environment.ini` configuration file as a string.
    The format should follow standard `.ini` conventions, with sections enclosed in square brackets (`[section]`),
    and key-value pairs using the `key = value` syntax. Avoid using JSON format.
    """

    response_environment = llm_client.call_llm(
        prompt=prompt_environment,
        max_tokens=500,
        temperature=0,
        repetition_penalty=1.0,
        top_p=0.1
    )

    environment_ini_str = fill_in_today_date(extract_ini_content(response_environment))

    # ========== **Step 2: AI agent generates solution.ini content** ==========
    llm_client = LLMClient(model_name=llm_model)

    prompt_solution = f"""
    You are an AI agent that processes machine learning pipeline configurations in YAML format. 
    Your task is to analyze the provided YAML structure and the environment.ini, and generate a corresponding solution.ini content.

    <Task Overview>
    This task involves converting a YAML file into an INI format while maintaining structural integrity and ensuring configurability. 

    <Steps to Follow>
    1.First section should always be general section. All parameters in this section is fixed. The general section differs from general section of environment.ini. Populate it with values extracted from the YAML file; leave it blank if no corresponding information is found.
    2.For each node in the YAML structure, create a separate section (e.g., [driver_creation], [feature_engineering], [data_pulling]) in the order they appear in the YAML file.
    3.Extract relevant key-value pairs for each section, replacing hardcoded values with configurable parameters from environment.ini only in the values, not in the keys. 
    4.Do not use variables in keys or parameter names — keep them hardcoded as originally written (e.g., driver_dev_features_table = /projects/gds, !Do not change it to driver_${{general:environment}}_features_table = /projects/gds.
    5.Do not include the file_name and the line_range in the solution.ini output.
    6.Confirm and verify that no information is missed. 
   
    ###
    EXAMPLE INPUTS
    [Given the YAML content]
    - Model Scoring:
        file_name: repos/ql-store-recommendation-prod/research/pipeline/05_scoring_oot.ipynb
        line_range: Lines 25-94
        inputs:
        working_path: /projects/gds/ql-store-recommendation-prod/research
        params_path: /projects/gds/ql-store-recommendation-prod/research/config
        outputs:
        eval_result_path: gs://pypl-pacman/user/chenzhao/prod/ql-store-rmr/data/ql_store_rmr_oot_transformed_scored
        log_file: /projects/gds/ql-store-recommendation-prod/research/logs/{{job_id}}.log
    -  Model Evaluation:
        file_name: repos/ql-store-recommendation-prod/research/pipeline/06_evaluation.ipynb
        line_range: Lines 95-125
        inputs:
        driver_dev_table_list: driver_dev_features
        model_version_path: ../_current_model_version
        outputs:
        exported_eval_readout_base: ../artifacts/18/exported_eval_readouts

    [Given the environment.ini]
        [general]
        refresh_date = 2023-10-11
        user = chenzhao
        environment = dev
        mo_name = 
        driver_dataset = 
        dataproc_project_name = ccg24-hrzana-gds-pacman
        dataproc_storage_bucket = pypl-pacman
        local_output_base_path = /projects/gds/ql-store-recommendation-prod/research
        gcs_base_path = gs://${{general:dataproc_storage_bucket}}/user/${{general:user}}/prod/ql-store-rmr/data
        queue_name = default
        namespace = gds-packman

    EXAMPLE OUTPUTS
    [Expected output: solution.ini]
        [general]
        model_name = RMR_MODEL_ID
        check_point = 
        email_to = chenzhao
        state_file = 
        cosmos_project = chenzhao
        gcp_app_id = 
        
        [model_scoring]
        working_path = ${{general:local_output_base_path}}
        params_path = ${{general:local_output_base_path}}/config
        eval_result_path = ${{general:gcs_base_path}}/ql_store_rmr_oot_transformed_scored
        log_file = ${{general:local_output_base_path}}/logs/{{job_id}}.log

        [Model Evaluation]
        driver_dev_table_list = driver_${{general:environment}}_features
        model_version_path = ../_current_model_version
        exported_eval_readout_base = ../artifacts/18/exported_eval_readouts
    ###
        

    ### Below is the YAML content and the environment.ini content:
    ```yaml
    {yaml.dump(verified_dag, default_flow_style=False)}
    ```environment.ini
    {environment_ini_str}

    ### Now, generate a properly formatted `solution.ini` configuration file as a string.
    The format should follow standard `.ini` conventions, with sections enclosed in square brackets (`[section]`),
    and key-value pairs using the `key = value` syntax. Avoid using JSON format.
    """

    logger.debug("Prompt used in the solution.ini generation: %s", prompt_solution)

    response_solution = llm_client.call_llm(
        prompt=prompt_solution,
        max_tokens=4096,  # increase the max_tokens
        temperature=0,
        repetition_penalty=1.0,
        top_p=0.1
    )

    try:
        env_vars = parse_env_ini(environment_ini_str)
        logger.debug("verified_dag = %s", repr(verified_dag))

        solution_ini_str = replace_with_env_vars(filter_duplicate_value_lines(extract_ini_content(response_solution),yaml.safe_load(verified_dag)),env_vars)

        result = {
            "environment_ini": environment_ini_str,
            "solution_ini": solution_ini_str
        }
        return result

    except ValueError as e:
        logger.error("Error extracting .ini content: %s", e)
        raise  
    
 # ========== **Step 3: Simple Unit Test Code** ==========
# if __name__ == "__main__":
#     # Base paths
#     BASE_DIR = "/Users/yanfdai/Desktop/codespace/DAG_FULLSTACK/rmr_agent/rmr_agent"
#     CHECKPOINT_DIR = os.path.join(BASE_DIR, "checkpoints", "ql-store-recommendation-prod", "1")
#     CONFIG_DIR = os.path.join(BASE_DIR, "config")

#     # Load DAG config
#     dag_path = os.path.join(CHECKPOINT_DIR, "dag_copy.yaml")
#     with open(dag_path, "r") as f:
#         verified_dag = yaml.safe_load(f)

#     # Generate config
#     config = config_agent(verified_dag)

#     # Save configs
#     os.makedirs(CONFIG_DIR, exist_ok=True)
#     save_ini_file("environment.ini", config["environment_ini"], CONFIG_DIR)
#     save_ini_file("solution.ini", config["solution_ini"], CONFIG_DIR)

#     print(f"[✓] INI files saved to: {CONFIG_DIR}")
#     print(f"[✓] Checkpoint directory used: {CHECKPOINT_DIR}")

