import os
import json
from llms import call_codepal_gpt
import litellm
from llms import LLMClient


def component_identification_agent(python_file_path, full_file_list, code_summary, model="gpt-4o", temperature=0, max_tokens=2048, 
                 frequency_penalty=0, presence_penalty=0):
    base_name = os.path.basename(python_file_path)  
    file_name = base_name.replace('.py', '.ipynb')
    print(f"Running component identification for {file_name}")

    classification_prompt = f"""Analyze the provided code summary to identify MAJOR ML components — substantial, primary elements that could function as independent ML workflow nodes. Use only the ML component categories defined below.

ML COMPONENT CATEGORIES:
    - Driver Creation: Typically the first step in the entire pipeline, it is the initial data loading and extraction (ETL) via SQL (often BigQuery) to create the “driver” dataset. This dataset contains the basic rows and metadata (e.g. class labels (0, 1), class weights, split category (train, val, test/OOT)). It can also sometimes include feature engineering and transformation in the SQL. The final driver dataset will typically be saved to GCS (e.g. parquet, PIG, CSV).
    - Feature Engineering: Creating new features, typically using SQL (most often in BigQuery), for predictive modeling. This involves applying transformations, aggregations, and derivations to raw data. The engineered features are intended to be joined with the driver dataset to enrich the final feature set.
    - Data Pulling: Enriching the driver dataset with additional data/features from a feature store/variable mart (typically with a proprietary API/SDK such as Data Fetcher, PyOFS, QPull, MadMen, PyDPU, mdlc.dataset).
    - Feature Consolidation: Merging multiple datasets into a unified feature set for modeling (distinct from driver creation joins).
    - Data Preprocessing: Cleaning/transforming data (e.g., imputation, handling outliers, encoding categorical variables, transforming to WOE, or normalization/scaling of features). Can include saving the preprocessors/transformers used (that is not a separate component). A commonly used proprietary library for preprocessing is Shifu.
    - Feature Selection: Selecting key features for modeling. Common proprietary libraries include Shifu and model_automation. Jobs may be submitting for execution on GCP Dataproc. Final variable list is saved. 
    - TFRecord Conversion: Converting data into TFRecord format. Typically a tfrecord convert function is submitted for execution on GCP Dataproc.
    - Model Training: Fitting models on training data. Can include Hyperparameter Tuning. Libraries commonly used in our company are TensorFlow, LightGBM, PyTorch. A train function may be submitted for execution on GCP Dataproc or VertexAI. The model can be saved using library-specific formats (e.g., .h5 for TensorFlow, .model for LightGBM, .pt for PyTorch).
    - Model Packaging: Saving trained models into deployment-ready formats (e.g. ONNX, UME, SavedModel, PMML, txt, etc.). This step may include bundling preprocessing/normalization logic (often from Shifu) with the model.
    - Model Scoring: Inferencing the trained model on the unseen test/OOT dataset. The commonly used proprietary tool is PyScoring.
    - Model Evaluation: Calculating performance metrics or running validation techniques.
    - Model Deployment: Saving/serving models for online or offline inference.

CLASSIFICATION RULES:
1. Use only the predefined ML component categories listed above. Do not invent new categories.
2. List multiple (>1) component categories ONLY if the code can be divided by a single, distinct line of separation, AND each resulting component can be confidently identified as one of the predefined ML component categories.
    - If you think more than one major component is present, justify why they warrant separate major nodes and confirm a specific line enables physical separation.
    - If separation lacks strong justification, or you cannot separate the components by a single line, combine them into a single component.
    - Do not split SQL into separate components.
3. For the identified component(s), provide:
    - Line Range: A merged, non-overlapping range (e.g., Lines 50-100).
    - Evidence: Key quotes from the summary supporting this classification, with a brief explanation of their relevance.
    - (If multiple components are listed) Why This Is Separate: Explain why this one merits splitting into a distinct ML workflow node, and provide verification there is no overlap with other identified components' line ranges. 
4. Identified components should be UNIQUE. Do not repeat a component category multiple times. 
5. If you are uncertain about any classification, DO NOT include it.
6. If none of these components can be confidently identified from the code summary, state: “Could not identify any major ML components.”

RESPONSE FORMAT:
MAJOR COMPONENTS IDENTIFIED: [list of components identified]
DETAILS FOR EACH:
[Component 1]:
    - Line Range: [Merged, non-overlapping range (e.g., Lines 0-49)]
    - Evidence:
        - [Quote/paraphrase 1] – [Why it supports this category]
        - [Quote/paraphrase 2] – [Why it supports this category]
    - (If multiple components identified) Why This Is Separate: [Justification for being a distinct ML workflow node; verification of no overlap with other components' line ranges]

[Component 2]: (if applicable)
    - Line Range: [Merged, non-overlapping range (e.g., Lines 50-100)]
    - Evidence:
        - [Quote/paraphrase 1] – [Why it supports this category]
        - [Quote/paraphrase 2] – [Why it supports this category]
    - Why This Is Separate: [Justification for being a distinct ML workflow node; verification of no overlap with other components' line ranges]

FULL ML PIPELINE FILE LIST:
{full_file_list}

CURRENT FILE'S NAME:
{file_name}

CURRENT FILE'S CODE SUMMARY:
{code_summary}
"""
    llm_client = LLMClient(model_name="gpt-4o")
    response: litellm.types.utils.ModelResponse = llm_client.call_llm(
        prompt=classification_prompt,
        max_tokens=2048,
        temperature=0.0,
        repetition_penalty=1.0,
        top_p=0.3,
    )
    choices: litellm.types.utils.Choices = response.choices
    classification = choices[0].message.content or ""
    print("Components identified:")
    print(classification)
    return classification


def parse_component_identification(response_text):
    """
    Parse component identification response, extracting components with their line ranges,
    evidence, and why_separate sections.
    
    Args:
        response_text (str): The raw LLM response text
        
    Returns:
        dict: A dictionary where:
            - keys are component names
            - values are dictionaries with:
                - 'line_range' (str): The full line range text
                - 'evidence' (list): List of evidence items
                - 'why_separate' (str or None): Explanation of why this component is separate
        
    Raises:
        ValueError: If no components are identified or if the response format is invalid
    """

    parse_prompt = f"""Parse the following component identification response and return a JSON object with the following structure:
{{
    "Component Name": {{
        "line_range": "The exact line range as specified (e.g., 'Lines 258-287, 300-311')",
        "evidence": [
            "Full evidence item text including the quoted part and description",
            "Another evidence item text"
        ],
        "why_separate": "The explanation of why this component is separate (or null if not present)"
    }}
}}

Make sure to:
1. Keep the line range exactly as specified in the text
2. Extract all evidence items with their descriptions
3. Include the "why_separate" section if present, otherwise set to null
4. Ignore any additional text that appears after the last component

Here's the content to parse:

{response_text}
"""

    result = call_codepal_gpt(
        prompt=parse_prompt,
        temperature=0  
    )
    parsed_text = result['generated_text']
    print("Parsed classification response:")
    print(parsed_text)
    return parsed_text



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