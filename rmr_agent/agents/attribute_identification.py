import os
import json
import logging
from typing import Dict, Any
import litellm
from rmr_agent.llms import LLMClient
from rmr_agent.utils.logging_config import setup_logger

# 设置模块日志记录器
logger = setup_logger(__name__)


component_specific_hints = {
    "Driver Creation": [
        "For the input variables, focus on SQL query parameters. Do not include tables.",
        "Output should only be the very final driver table/dataset. It is often also saved to GCS (e.g. parquet, CSV).",
        "Intermediate table results should NEVER be included (e.g. positive, negative, base tables etc.). Focus on the major inputs and FINAL output table(s) of the entire driver creation process.",
        #"The final driver dataset contains the all of the basic rows and metadata all in one table (e.g. class labels (0, 1), class weights, split category (train, val, test/OOT)).",
        "If the different splits (train, validation, test, OOT) are saved in separate tables/datasets, include those as output variables as well."
    ],
    "Feature Engineering": [
        "Inputs include driver dataset (BigQuery table or GCS path) and SQL query parameters for transformations",
        "Output should only be the very final table/dataset with engineered features, often saved to BigQuery or GCS",
        "Intermediate table results should NEVER be included. Focus on the major inputs and FINAL output table(s) of the entire feature engineering process."
        "Look for aggregation or transformation parameters (e.g., window sizes, group-by keys)"
    ],
    "Data Pulling": [
        "Inputs include driver dataset path and feature store API parameters (e.g., for Data Fetcher, PyOFS, QPull, MadMen, PyDPU, mdlc.dataset)",
        "Data Fetcher produces its output in data_loc"
        ],
    "Feature Consolidation": [
        "Inputs are multiple dataset paths to merge",
        "Output is a unified feature set, often saved to GCS",
        "Intermediate table results should not be included. Focus on the major inputs and final output"
        "Look for join keys or merge parameters"
    ],
    "Data Preprocessing": [
        "Inputs include feature set path and transformation parameters (e.g., imputation method, scaling factors)",
        "Outputs include cleaned/transformed data path and preprocessor save paths",
        "Look for Shifu library usage or WOE/normalization parameters",
        "Shifu runs normalization through the eval() method with the '-norm' flag set. The resulting normalized dataset will be located in the `hdfsModelSetPath` if specified"
    ],
    "Feature Selection": [
        "Input is train dataset path(s), and may include other parameters and the target column list, etc.",
        "Outputs include final variable list path and optional feature importance path",
        "Look for Shifu or model_automation calls"
    ],
    "TFRecord Conversion": [
        "Input is normalized train/validation data paths",
        "Output is TFRecord file paths (typically on GCS)",
        "Look for Dataproc job submission parameters or tfrecord conversion function args"
    ],
    "Model Training": [
        "Inputs include training data path (potentially normalized data paths or tfrecord paths), hyperparameters (e.g., learning_rate, n_estimators), and training params (e.g., epochs, batch_size)",
        "Output is model artifact path using library-specific formats (e.g., .h5, .tf, .model, .pt, .txt, .json on local or GCS)",
        "If hyperparameter optimization is present, the output may include those final hyperparameter values",
        "Note that Model Packaging to formats such as UME and ONNX is considered a separate component from Model Training, so do not include them here"
    ],
    "Hyperparameter Optimization": [
        "Inputs include training data path (potentially normalized data paths or tfrecord paths), initial hyperparameters (e.g., learning_rate, n_estimators), and training params (e.g., epochs, batch_size)",
        "Output should be the final best hyperparameter results path (e.g. optuna study path)"
    ],
    "Model Ensembling": [
        "Inputs include the trained models' paths and any other ensembling parameters",
        "Output is the final ensembled model artifact path",
    ],
    "Model Packaging": [
        "Input is trained model path (e.g., 'gs://bucket/model.h5') and optional preprocessing logic (e.g., Shifu path, saved preprocessor paths)",
        "Output is deployment-ready model path (e.g., ONNX, UME)",
    ],
    "Model Scoring": [
        "Inputs include model path and test/OOT data path",
        "Output is scored data path",
        "Look for PyScoring tool usage"
    ],
    "Model Evaluation": [
        "Input is scored data path or model predictions",
        "Output is final performance metrics path",
        "Look for metric calculation parameters (e.g., threshold, metric names)"
    ],
    "Model Deployment": [
        "Input is packaged model path",
        # should specify some output hint here, not sure at the moment. Many times research code does not include the deployment code - they do it manually elsewhere or through UI for example. 
    ],
}

generic_tips = [
    "User specified a custom component name, use your best judgment of what input & output variables exist for this component that should be made configurable"
]

def get_component_hints(component, component_specific_hints):    
    # Find hints for components that are in our list
    if component in component_specific_hints:
        matching_hints = component_specific_hints[component]
    else:
       matching_hints = generic_tips
    
    # Format the hints
    result = ""
    for hint in matching_hints:
        result += f"    - {hint}\n"
    result += "\n"
    
    return result



def attribute_identification_agent(python_file_path: str, component_dict: Dict[str, Any], clean_code: str):
    base_name = os.path.basename(python_file_path)  
    file_name = base_name.replace('.py', '.ipynb')
    line_count = len(clean_code.splitlines())  
    identified_components = list(component_dict.keys())
    logger.info("Running attribute identification for %s which has ~%d lines of code, with identified components: %s ...", file_name, line_count, identified_components)

    attribute_identification_result = ""

    # Identify attributes for each of the identified components separately for improved accuracy
    for component, component_details in component_dict.items():
        line_range = component_details["line_range"]
        formatted_component_hints = get_component_hints(component, component_specific_hints)
        attribute_prompt = f"""You are analyzing Python code from a machine learning (ML) component within an ML workflow (DAG). You will be given the code along with the identified ML component. Your task is to extract the input and output variables for this component into a valid JSON. 

### Instructions:
    1. Examine the component's code carefully, leveraging the verified **line range** provided. 
    2. Identify all **input** variables (name & value) for this component.
    3. Identify all **output** variables (name & value) for this component. 
    4. For each input and output variable identified, provide:
        a. The variable **name**: 
            - If the value comes from an existing declared variable with a descriptive, unique name (e.g., train_batch_size = 32), use that exact variable name
            - If the value comes from an existing variable with a reused name (e.g., source_table_name used for multiple different tables), create a more descriptive name (e.g., train_source_table_name, validation_source_table_name)
            - If the value is hardcoded directly in the code (e.g., model.fit(epochs=100) where 100 is hardcoded), create a unique, descriptive variable name following standard Python naming: lowercase letters with underscores (e.g., training_epochs, batch_size, driver_output_path). Ensure your variables names are unique. 
        b. The current **value** in the code
        c. Whether the variable **already exists** in the code as a declared variable vs. is a hardcoded value
        d. Whether you **renamed** an existing non-unique variable to make it unique and more descriptive

### Additional Guidance:
    - Focus only on input/output variables that should be **configurable** in a rerunnable pipeline. Pay special attention to hardcoded variables that might change between pipeline runs!
        - If a variable should be configurable and is already being loaded from a config file, still include it. Your output will be used in the next step to retrieve its actual value from the config file.
    - Include only static, configurable variables. Exclude function/method calls and file name lists. Paths constructed with `os.path.join()` are okay to include.
    - Exclude long column lists, such as categorical, numerical, meta, or candidate columns, from being treated as variables. The target (or label) column list, weight column list, can be included as variables however. Also, lists used directly in data operations (e.g., join keys, filter keys, grouping keys, indexing or sort keys) are fine to include if necessary.
    - Make sure each variable in your response has both a variable name followed by its value. Use valid JSON structure for your output. 

### Variable Classification Examples:
- Existing variable with good name ("already_exists": true, "renamed": false):
    ```python
    train_batch_size = 32
    model.fit(X_train, y_train, batch_size=train_batch_size)
    ```
    → Variable name: train_batch_size, Value: 32, Already exists: true, Renamed: false
- Existing variable with reused name ("already_exists": true, "renamed": true):
    ```python
    source_table_name = "train_data_path"
    move_data(source_table_name, target_table_name)
    # Later in code...
    source_table_name = "validation_data_path"  # Same variable reused!
    move_data(source_table_name, target_table_name)
    ```
    → For first usage: Variable name: train_source_table_name (you rename it), Value: "train_data_path", Already exists: true, Renamed: true
    → For second usage: Variable name: validation_source_table_name (you rename it), Value: "validation_data_path", Already exists: true, Renamed: true 
- Hardcoded value ("already_exists": false):
    ```python
    model.fit(X_train, y_train, batch_size=32)
    ```
    → Variable name: batch_size (you create this name), Value: 32, Already exists: false
  

### Output Format (JSON):
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
        ]
    }}
}}

### The Identified ML Component:
{component}

### Line range to focus on for this ML Component:
{line_range}

### Hints for Identifying Input & Output Variables for this Component:
{formatted_component_hints}
        
### Code:
{clean_code}
    """
        # Call the LLM to identify attributes for this component
        llm_client = LLMClient()
        response: litellm.types.utils.ModelResponse = llm_client.call_llm(
            prompt=attribute_prompt,
            max_tokens=2048,
            temperature=0.0,
            repetition_penalty=1.0,
            top_p=0.3,
        )
        choices: litellm.types.utils.Choices = response.choices
        attribute_text = choices[0].message.content or ""

        # add to overall result
        attribute_identification_result += attribute_text + "\n\n"
    return attribute_identification_result



