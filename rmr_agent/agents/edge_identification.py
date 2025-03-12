import litellm
from llms import LLMClient
    


def edge_identification_agent(nodes_yaml_str):

    edge_identification_prompt = f"""You will be provided with a list of machine learning (ML) pipeline components, each containing their identified input and output attributes, file name, and line number ranges. Your task is to identify edges that connect these components, where an edge is defined as an output from one component being used as an input to another. An edge should include the source component, the target component, and the specific attribute(s) that connect them.

### Instructions:
1. Analyze the inputs and outputs of each component to find matching attribute values (e.g., file paths, dataset identifiers).
2. For each identified edge:
   - Use the component names (e.g., "Driver Creation", "Feature Pull") as `from` and `to` fields
   - List the shared attribute(s) and their value(s) under `attributes`.
3. If no edges are found, return an empty `edges` list in YAML format.
4. Output the identified edges in YAML format, following the structure shown in the example below.

### Example Input:
```yaml
- Driver Creation:
    file_name: "data_pipeline.ipynb"
    line_range: "Lines 10-50"
    inputs: {{}}
    outputs:
        driver_path: "gs://my-bucket/data/driverset.parquet"
- Feature Pull:
    file_name: "data_pipeline.ipynb"
    line_range: "Lines 60-100"
    inputs:
        driver_path: "gs://my-bucket/data/driverset.parquet"
        feature_list: "columns/features.txt"
    outputs:
        train_data_path: "gs://my-bucket/data/train_data.parquet"
        test_data_path: "gs://my-bucket/data/test_data.parquet"
- Data Normalization:
    file_name: "feature_engineering.ipynb"
    line_range: "Lines 35-70"
    inputs:
      train_data_path: "gs://my-bucket/data/train_data.parquet"
      test_data_path: "gs://my-bucket/data/test_data.parquet"
    outputs:
      normalized_train_data_path: "gs://my-bucket/data/processed/normalized_train_data.parquet"
```

### Example Output:
edges:
  - from: Driver Creation
    to: Feature Pull
    attributes:
      driver_path: "gs://my-bucket/data/driverset.parquet"
  - from: Feature Pull
    to: Data Normalization
    attributes:
      train_data_path: "gs://my-bucket/data/train_data.parquet"
      test_data_path: "gs://my-bucket/data/test_data.parquet"

### Notes:
    - Ensure attribute values match EXACTLY when identifying edges. If it is not an exact match, do not include it as an edge. 
    - A component may have no inputs or outputs; skip it unless it connects to another component.
    - Do not infer edges unless explicitly supported by matching input/output values.

### ML Components:
{nodes_yaml_str}
"""
    
    llm_client = LLMClient(model_name="gpt-4o")
    response: litellm.types.utils.ModelResponse = llm_client.call_llm(
        prompt=edge_identification_prompt,
        max_tokens=2048,
        temperature=0,
        repetition_penalty=1.0,
        top_p=0.3,
    )
    choices: litellm.types.utils.Choices = response.choices
    edge_identification = choices[0].message.content or ""
    return edge_identification