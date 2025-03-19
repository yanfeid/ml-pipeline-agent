import os
import json
from typing import Dict, Any
from llms import LLMClient
import litellm


component_specific_hints = {
    "Driver Creation": [
        "Focus on major inputs like raw data paths (e.g., BigQuery table paths) and SQL query parameters.",
        "Output should only be the very final driver table/dataset. It is often also saved to GCS (e.g. parquet, CSV).",
        "Intermediate table results should NEVER be included (e.g. positive, negative, base tables etc.). Focus on the major inputs and FINAL output table(s) of the entire driver creation process.",
        #"The final driver dataset contains the all of the basic rows and metadata all in one table (e.g. class labels (0, 1), class weights, split category (train, val, test/OOT)).",
        "If the different splits (train, validation, OOT (test)) are saved in separate tables/datasets, include those as output attributes as well."
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
        "Input is train dataset path(s), candidate feature lists, meta feature lists, target column lists, etc.",
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
    "User specified a custom component name, use your best judgment of what input & output attributes exist for this component that should be made configurable"
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
    print(f"Running attribute identification for {file_name} which has ~{line_count} lines of code, with identified components: {identified_components} ...")

    attribute_identification_result = ""

    # Identify attributes for each of the identified components separately for improved accuracy
    for component, component_details in component_dict.items():
        line_range = component_details["line_range"]
        formatted_component_hints = get_component_hints(component, component_specific_hints)
        attribute_prompt = f"""### SETTING:
You are analyzing python code which comes from a jupyter notebook in a ML workflow. You will be provided with the code itself and a machine learning (ML) component that was identified to be present in the code. Your task is to determine the input and output attributes for this component.

### INSTRUCTIONS
1. Examine the component's code carefully, leveraging the line number ranges given for the component for rough guidance. 
2. Identify all input attribute names and values. For example:
    - Local/GCS data paths (e.g., '/data/train.csv', 'gs://bucket/data.parquet')
    - Column/feature lists and names (e.g., features = ['age', 'income'], meta_columns = ['cust_id', 'weight'], target_col = 'target')
    - Model parameters (e.g., learning_rate=0.01, loss='binary_crossentropy', epochs=5, batch_size=512)
    - Other pipeline-relevant attributes
3. Identify all output attribute names and values. For example:
    - Local/GCS data paths (e.g., '/data/train.csv', 'gs://bucket/data.parquet')
    - Model artifact paths (e.g., '/saved_model_ume/model.m')
4. For each attribute identified, provide:
    a. The attribute name
    b. The current value in the code

### ADDITIONAL GUIDANCE
    - Focus only on input/output attributes that should be configurable in a rerunnable pipeline. Pay special attention to hardcoded values that might change between pipeline runs!
    - Look for patterns like:
        - File paths in string literals
        - Configuration parameters passed to functions
        - Constants defined at the top of files
        - Command line arguments or gsutil commands
        - Values written to or read from config files
    - Include only static, configurable variables. Exclude function/method calls and file name lists.
    - You may abbreviate the value for an attribute if it is especially long (e.g. feature list with 10+ hard coded feature names)
    - Make sure each attribute in your output has a corresponding attribute name followed by its value
    
### OUTPUT FORMAT:
[Component Name]:
    Inputs:
        - [Attribute Name]: [Attribute Value - abbreviated if a long list of values]
    Outputs:
        - [Attribute Name]: [Attribute Value - abbreviated if a long list of values]

### IDENTIFIED ML COMPONENT:
{component}

### LINE RANGE
{line_range}

### COMPONENT SPECIFIC HINTS FOR IDENTIFYING ATTRIBUTES:
{formatted_component_hints}
        
### CURRENT FILE'S CODE:
{clean_code}
    """
        #print(attribute_prompt)
        llm_client = LLMClient(model_name="gpt-4o")
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
        attribute_identification_result += attribute_text + "\n"
    return attribute_identification_result



