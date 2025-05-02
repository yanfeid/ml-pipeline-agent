import litellm
from rmr_agent.llms import LLMClient
from rmr_agent.utils import yaml_to_dict, dict_to_yaml
    

def clean_edges(edge_yaml_str, nodes_yaml_str):
    """
    Clean and validate edges from edge_yaml_str based on nodes_yaml_str.
    Returns the cleaned edges as a YAML string.
    """
    # Parse YAML strings into dictionaries
    nodes_dict_list = yaml_to_dict(nodes_yaml_str)  # {ComponentName: {inputs: {}, outputs: {}}}
    edge_dict = yaml_to_dict(edge_yaml_str)   # {'edges': [{from: ..., to: ..., attributes: {...}}]}


    # Validate and clean edges
    cleaned_edges = []
    for edge in edge_dict.get('edges', []):  # Access 'edges' list, default to empty
        from_component_name = edge.get('from')


        # Get outputs of 'from' component
        for node_dict in nodes_dict_list:
            if from_component_name in node_dict:
                from_outputs = node_dict[from_component_name].get('outputs', {})
                break 
        else:
            # the component not found in nodes - may have been hallucinated
            continue

        if not from_outputs:
            continue  # Skip if no outputs exist

        # Filter attributes: keep only those where the name exists in from_outputs
        edge_attributes = edge.get('attributes', {})
        valid_attributes = {
            name: value for name, value in edge_attributes.items()
            if name in from_outputs
            # Optional: and from_outputs[name] == value  # Uncomment to enforce value matching
        }

        # Only keep edge if it has valid attributes
        if valid_attributes:
            edge['attributes'] = valid_attributes
            cleaned_edges.append(edge)
        

    # Construct the cleaned edge dictionary
    cleaned_edge_dict = {'edges': cleaned_edges}

    # Convert back to YAML string
    return dict_to_yaml(cleaned_edge_dict)

def edge_identification_agent(nodes_yaml_str):

    edge_identification_prompt = f"""You will receive a list of machine learning (ML) pipeline components. Each component includes its input and output attributes, file name, and line number ranges. Your task is to identify edges connecting these components, where an edge exists when an output attribute from one component is used as an input attribute in another. Each edge must specify the source component, target component, and the connecting attribute(s).

### Instructions:
  1. Analyze the inputs and outputs of each component.
  2. Find where an output from one component matches an input to another.
      - An edge is valid only if an attribute is explicitly listed in the output of the source component and the input of the target component.
      - Attribute **values** must match exactly. The attribute name may be slightly different across components. If the values differ, do not consider it an edge. If only the names differ, keep the attribute name from the source component.
      - Do not infer edges; only use explicit matches supported by identical attribute values!
  3. For each identified edge:
      - Set the `from` field to the source component name (e.g., "Model Training").
      - Set the `to` field to the target component name (e.g., "Model Evaluation").
      - Under `attributes`, list the source component's attribute name and value from it's output section (e.g., model_artifact_path: /projects/username/models/model.txt).
      - **Rule**: If multiple attributes connect the same `from` and `to` pair, include all matching attributes in a single edge. Each `from`-`to` pair of component names must be unique.
  4. Format the output as a YAML list of edges

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

### Output Format (YAML):
edges:
  - from: [Source Component Name]
    to: [Target Component Name]
    attributes:
      [shared_attribute_1_name]: [Shared attribute 1 value]
      [shared_attribute_2_name]: [Shared attribute 2 value]

### ML Components:
{nodes_yaml_str}
"""
    
    llm_client = LLMClient()
    response: litellm.types.utils.ModelResponse = llm_client.call_llm(
        prompt=edge_identification_prompt,
        max_tokens=2048,
        temperature=0,
        repetition_penalty=1.0,
        top_p=0.3,
    )
    choices: litellm.types.utils.Choices = response.choices
    edge_identification = choices[0].message.content or ""

    # Filter out any edge attributes which are not actually the output of the `from` component 
    filtered_edges = clean_edges(edge_identification, nodes_yaml_str)

    return filtered_edges