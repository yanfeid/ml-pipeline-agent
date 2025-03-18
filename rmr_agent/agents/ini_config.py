import yaml
import configparser
from typing import Dict, Any
from llms import LLMClient 
import os
import re
import configparser
from io import StringIO
from utils.save_file import save_state, save_ini_file


# ========== **Extract .ini Content from AI Response** ==========
def extract_ini_content(response):
    """Extracts the `.ini` formatted content from an AI-generated response."""

    if response is None:
        raise ValueError("AI response is None, unable to extract `.ini` content.")

    # Ensure the response contains valid choices with a message
    if hasattr(response, "choices") and response.choices:
        response_text = response.choices[0].message.content  # Extract the `.ini` formatted string
    else:
        raise ValueError("Invalid AI response format, unable to extract `.ini` content.")

    if not response_text:
        raise ValueError("AI returned an empty `.ini` content.")

    # Remove potential Markdown-style code block formatting (```ini ... ```)
    if response_text.startswith("```ini"):
        response_text = response_text[6:].strip()
    if response_text.endswith("```"):
        response_text = response_text[:-3].strip()

    return response_text


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
    yaml_data = verified_dag
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
    - Your response MUST be valid JSON. No explanations. No extra text.

    ### Fixed Structure of `environment.ini`:
    The file should always contain the following fields:
    ```
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
    ```

    ### Guidelines to Follow

    1. **Date & Default Values**
    - **Insert Today's Date:** Automatically fill in `refresh_date` with the current date.
    - **Default Values:**
        - Set `mo_name` as blank by default.
        - Set `environment` as `dev` by default.
        - `Queue Name` set to `default` if not provided.
        - `Namespace` set to `gds-packman` if not provided.

    2. **User & Owner Identification**
    - **Check for User Name:** Review the directory structure to identify if a user name (or owner) is present.
    - If detected, treat that directory segment as the username.

    3. **Dataproc Project & Storage Bucket**
    - **Dataproc Project Name:** Identify keywords such as `gcp_project_id`, `project_name`, etc., to determine the project name.
    - **Dataproc Storage Bucket:** Identify keywords such as `gcs_bucket_name`, `bucket_name`, `bucket_id`, etc., to determine the storage bucket name.

    4. **Path Analysis**
    - **Local Output Base Path:**
        - Identify paths containing keywords like “local” (typically starting with `/projects`).
        - Extract the longest common directory path.
    - **GCS Base Path:**
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
    {yaml.dump(yaml_data, default_flow_style=False)}
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
        top_p=1
    )

    environment_ini_str = extract_ini_content(response_environment)


    # ========== **Step 2: AI agent generates solution.ini content** ==========
    llm_client = LLMClient(model_name=llm_model)

    prompt_solution = f"""
    You are an AI agent that processes machine learning pipeline configurations in YAML format. 
    Your task is to analyze the provided YAML structure and the environment.ini, and generate a corresponding solution.ini content.

    <Task Overview>
    This task involves converting a YAML file into an INI format while maintaining structural integrity and ensuring configurability. 

    <Steps to Follow>
    1.First section should always be general section. All parameters in this section is fixed. Populate it with values extracted from the YAML file; leave it blank if no corresponding information is found.
    2.Ignore edges part in yaml. For each node in the YAML structure, create a separate section (e.g., [driver_creation], [feature_engineering], [data_pulling]) in the order they appear in the YAML file.
    3.Extract relevant key-value pairs for each section, replacing hardcoded values with configurable parameters from environment.ini where applicable.
    4.Avoid duplicate entries: if a path appears in one section, it should not be repeated in any other section. Ideally, you should classify these info into the first section.
    5.Preserve the original YAML file order for all sections (except that the [general] section must always be placed at the top and appear only once).
    6.Confirm and verify that no information is missed and the order of sections matches the YAML file.
   
    ###
    EXAMPLE INPUTS
    [Given the YAML content]
    - Model Packaging:
        file_name: repos/ql-store-recommendation-prod/research/pipeline/04_packaging.ipynb
        line_range: Lines 15-24
    - Model Scoring:
        file_name: repos/ql-store-recommendation-prod/research/pipeline/05_scoring_oot.ipynb
        line_range: Lines 25-94
        inputs:
        working_path: /projects/gds/ql-store-recommendation-prod/research
        params_path: /projects/gds/ql-store-recommendation-prod/research/config
        outputs:
        eval_result_path: gs://pypl-pacman/user/chenzhao/prod/ql-store-rmr/data/ql_store_rmr_oot_transformed_scored
        log_file: "/projects/gds/ql-store-recommendation-prod/research/logs/{{job_id}}.log"
    -  Model Evaluation:
        file_name: repos/ql-store-recommendation-prod/research/pipeline/06_evaluation.ipynb
        line_range: Lines 95-125
        inputs:
        model_version_path: ../_current_model_version
        outputs:
        exported_eval_readout_base: "../artifacts/18/exported_eval_readouts"

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

        [Model Packaging]
        file_name: repos/ql-store-recommendation-prod/research/pipeline/04_packaging.ipynb
        line_range: Lines 15-24

        [model_scoring]
        file_name: repos/ql-store-recommendation-prod/research/pipeline/05_scoring_oot.ipynb
        line_range: Lines 25-94
        working_path: ${{general:local_output_base_path}}
        params_path: ${{general:local_output_base_path}}/config
        eval_result_path: ${{general:gcs_base_path}}/ql_store_rmr_oot_transformed_scored
        log_file: "${{general:local_output_base_path}}/logs/{{job_id}}.log"

        [Model Evaluation]
        file_name: repos/ql-store-recommendation-prod/research/pipeline/06_evaluation.ipynb
        line_range: Lines 95-125
        model_version_path: ../_current_model_version
        exported_eval_readout_base: "../artifacts/18/exported_eval_readouts"
    ###
        

    ### Below is the YAML content and the environment.ini content:
    ```yaml
    {yaml.dump(yaml_data, default_flow_style=False)}
    ```environment.ini
    {environment_ini_str}

    ### Now, generate a properly formatted `solution.ini` configuration file as a string.
    The format should follow standard `.ini` conventions, with sections enclosed in square brackets (`[section]`),
    and key-value pairs using the `key = value` syntax. Avoid using JSON format.
    """

    print("DEBUG: Prompt I used in the second call==================================================================================================================:", prompt_solution)

    response_solution = llm_client.call_llm(
        prompt=prompt_solution,
        max_tokens=3500,  #need to change to a approprate value
        temperature=0,
        repetition_penalty=1.0,
        top_p=1
    )

    try:
        solution_ini_str = extract_ini_content(response_solution)

        result = {
            "environment_ini": environment_ini_str,
            "solution_ini": solution_ini_str
        }

    except ValueError as e:
        print(f"⚠️ Error extracting .ini content: {e}")


    return result

    
 # ========== **Step 3: Simple Unit Test Code** ==========

if __name__ == "__main__":
    with open("dag.yaml", "r") as file:
        test_verified_dag = yaml.safe_load(file)

    # get .ini data
    state = config_agent(test_verified_dag)

    CHECKPOINT_SUBDIR = os.path.abspath("../checkpoints/ql-store-recommendation-prod")
    STATE_FILE = os.path.join(CHECKPOINT_SUBDIR, "ini_config.json") 

    print(f"Checkpoints will be stored in: {CHECKPOINT_SUBDIR}")
    print(f"State file path: {STATE_FILE}")

    save_state(state, STATE_FILE )
    save_ini_file("environment.ini", state["environment_ini"], CHECKPOINT_SUBDIR)
    save_ini_file("solution.ini", state["solution_ini"], CHECKPOINT_SUBDIR)