import yaml
import litellm
import logging
from rmr_agent.llms import LLMClient
from rmr_agent.utils import yaml_to_dict, dict_to_yaml
from rmr_agent.utils.logging_config import setup_logger

# Set up module logger
logger = setup_logger(__name__)


def identify_strict_edges_from_dicts(nodes_dict_list):
    """
    Identifies edges between components based on exact value matching
    of output attributes from one component to input attributes of another,
    using a pre-parsed list of component dictionaries.

    Args:
        nodes_dict_list (list): A list of dictionaries, where each dictionary
                                represents a component. Each component dictionary is
                                expected to have a single key (the component name),
                                and its value is another dictionary containing
                                'inputs' and 'outputs' (which are themselves
                                dictionaries of attribute-value pairs).
                                Example: [{'ComponentA': {'inputs': {}, 'outputs': {}}}, ...]

    Returns:
        list: A list of dictionaries, where each dictionary represents an edge
              with 'from', 'to', and 'attributes' keys.
              The 'attributes' dictionary contains source_output_name: shared_value pairs.
              Returns an empty list if errors occur or no edges are found.
    """
    if not isinstance(nodes_dict_list, list):
        logger.error("Error: Expected a list of component dictionaries.")
        return []
    if not nodes_dict_list:
        return []

    # Standardize node structure for easier processing
    processed_nodes = []
    for i, item in enumerate(nodes_dict_list):
        if not isinstance(item, dict) or len(item) != 1:
            logger.warning(f"Skipping item at index {i} as it's not a single-key dictionary representing a component: {item}")
            continue
        
        component_name = list(item.keys())[0]
        component_data = item[component_name]

        if not isinstance(component_data, dict):
            logger.warning(f"Skipping component '{component_name}' as its data is not a dictionary.")
            continue
            
        # Ensure inputs and outputs are dictionaries, defaulting to empty if null/missing in component_data
        inputs = component_data.get('inputs') or {}
        outputs = component_data.get('outputs') or {}

        if not isinstance(inputs, dict):
            logger.warning(f"Inputs for component '{component_name}' is not a dictionary. Treating as empty.")
            inputs = {}
        if not isinstance(outputs, dict):
            logger.warning(f"Outputs for component '{component_name}' is not a dictionary. Treating as empty.")
            outputs = {}

        processed_nodes.append({
            'name': component_name,
            'inputs': inputs,
            'outputs': outputs
        })
    logger.debug("Processed nodes: %s", processed_nodes)

    edges_map = {}  # To store "from_name" -> "to_name" -> {attributes} to consolidate

    # Iterate through each node as a potential source
    for source_node_idx, source_node in enumerate(processed_nodes):
        source_name = source_node['name']
        source_outputs = source_node['outputs']

        if not source_outputs:  # Skip if the source node has no outputs
            continue

        # Iterate through each node as a potential target
        for target_node_idx, target_node in enumerate(processed_nodes):
            if source_node_idx == target_node_idx:  # Skip connecting a node to itself
                continue

            target_name = target_node['name']
            target_inputs = target_node['inputs']

            if not target_inputs:  # Skip if the target node has no inputs
                continue

            # Find matching attributes based on value
            current_matching_attributes = {}
            for out_attr_name, out_value in source_outputs.items():
                if out_value is None: # Skip matching None values
                    continue
                
                for in_attr_name, in_value in target_inputs.items():
                    if out_value == in_value: # Exact value match
                        current_matching_attributes[out_attr_name] = out_value
            
            if current_matching_attributes:
                edge_key = (source_name, target_name)
                if edge_key not in edges_map:
                    edges_map[edge_key] = {
                        'from': source_name,
                        'to': target_name,
                        'attributes': {}
                    }
                edges_map[edge_key]['attributes'].update(current_matching_attributes)
    
    logger.debug("Edges map after processing: %s", edges_map)
    final_edges_list = list(edges_map.values())
    return final_edges_list


def clean_edges(edge_yaml_str, nodes_yaml_str):
    """
    Clean and validate edges from edge_yaml_str based on nodes_yaml_str.
    Returns the cleaned edges as a YAML string.
    """
    logger.info("Cleaning edges based on nodes YAML string...")
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

    # First we will find edges between components programmatically based on exact value matching
    nodes_dict_list = yaml_to_dict(nodes_yaml_str)  # Convert YAML string to list of dictionaries:  {ComponentName: {inputs: {}, outputs: {}}}
    logger.debug("Nodes dictionary list: %s", nodes_dict_list)
    if not nodes_dict_list:
        raise ValueError("No valid components found in the provided YAML string.")
    strict_edges = identify_strict_edges_from_dicts(nodes_dict_list)
    logger.debug("Strict edges: %s", strict_edges)
    if strict_edges:
        pre_identified_edges_yaml_str = yaml.dump({'edges': strict_edges}, sort_keys=False, indent=2)
        logger.debug("Pre-identified edges YAML string: %s", pre_identified_edges_yaml_str)
    else:
        pre_identified_edges_yaml_str = """No exact matches were found. Plase use the following output format (YAML):
edges:
  - from: [Source Component Name]
    to: [Target Component Name]
    attributes:
      [shared_attribute_1_name]: [shared_attribute_1_value]
      [shared_attribute_2_name]: [shared_attribute_2_value]
"""
        logger.info("No strict edges found based on exact value matching.")

    

    # Now we will use the LLM to improve edge identification by considering the context of components
    edge_refinement_and_augmentation_prompt = f"""You will receive two inputs:
1.  `ML Components`: A YAML list of machine learning (ML) pipeline components, each with its input/output attributes.
2.  `Pre-identified Edges`: A YAML list of edges found by a programmatic scan. This scan strictly matched components where an output attribute **value** from a source component was identical to an input attribute **value** in a target component.

Your task is to refine the `Pre-identified Edges` list and augment it by identifying additional, meaningful connections using heuristic (fuzzy) matching. The goal is to produce a final, comprehensive, and accurate list of edges representing the primary data and artifact flow.

### General ML Pipeline Flow Hint:
ML pipeline components often follow a typical sequence. The list below represents a common, generalized flow. **This is a guideline to help you assess likely connections and is not a rigid rule; actual pipelines can have variations, or add/omit steps. Use this hint to inform your judgment, especially when considering heuristic matches where exact data links are not perfectly explicit.** A common order is:
Driver Creation -> Feature Pull -> Data Normalization -> Model Training -> Model Packaging -> Model Scoring -> Model Evaluation 
This order suggests that outputs from earlier stages are frequently inputs to later stages in many scenarios.

### Instructions:

1.  **Understand Inputs:**
    * `ML Components`: This is the source of truth for all component inputs and outputs.
    * `Pre-identified Edges`: These are edges identified programmatically based on **exact value matches**. Assume these are correct according to that strict rule. Your primary task with these is to ensure they represent significant connections and are correctly formatted for the final output.

2.  **Review and Refine Pre-identified Edges:**
    * **Validate Formatting:** For each edge in `Pre-identified Edges`:
        * Ensure the `attributes` listed use the attribute **name and value from the source component's output section**. (The programmatic script should already do this, but it's a good verification).
        * Confirm that each `from`-`to` pair is unique, with all connecting attributes consolidated under it.
    * **Filter for Significance (Important):**
        * Your primary goal is to retain edges that represent the flow of **major data artifacts, models, or critical operational outputs/inputs**.
        * You may filter out (remove) pre-identified edges if they seem to represent minor or less relevant connections. Examples of potentially less relevant connections could be those based on secondary log files, very generic configuration parameters that don't define a core data dependency (unless the parameter itself is a key artifact), or temporary intermediate files not central to the main pipeline flow.
        * **Guideline for Filtering**: If an edge connects components that are part of the 'General ML Pipeline Flow Hint' and involves attributes whose names suggest primary datasets (e.g., ending in `_path`, `_data`, `_uri`, `_table`) or models (e.g., `model_`, `artifact_`), it's very likely important and should be kept. If unsure about a pre-identified edge's importance, lean towards keeping it unless it clearly appears trivial or redundant with a more significant connection.

3.  **Identify Additional Edges via Heuristic (Fuzzy) Matching:**
    * Carefully analyze the `ML Components` to find **new edges not present** in the (potentially filtered) list of `Pre-identified Edges`.
    * Apply the following heuristic matching rules, primarily for connections between components that are typically sequential (see 'General ML Pipeline Flow Hint'):
        * **Condition A:** The source and target components are part of a common, expected sequence in an ML pipeline.
        * **Condition B:** The output attribute of the source and input attribute of the target conceptually refer to the **same type of artifact** (e.g., source `trained_model_output_location` and target `model_to_deploy_input_uri`).
        * **Condition C:** Their **values (typically file paths or resource locators) are highly similar** and very likely refer to the same logical file/resource, differing only by minor, common variations such as:
            * Small differences in file names (e.g., `model.pkl` vs `final_model.pkl` within the same directory).
            * Versioning, run ID, or timestamp differences in the path or filename (e.g., `.../run_123/model.joblib` vs `.../run_124/model.joblib`, or `data_v1.csv` vs `data_v2.csv`).
            * Minor, justifiable variations in parent directories if the core file/resource name and its semantic purpose clearly align (e.g., `gs://bucket/models/my_model/v1` vs `gs://bucket/models/my_model/v1.1`).
        * **Action for Heuristic Match**: If ALL conditions (A, B, C) are met, form a new edge. For this edge, use the attribute **name AND value from the source component's output section**.
    * **Caution**: Apply this heuristic matching judiciously. Prioritize clear, defensible connections. Avoid inferring edges where similarity is low or the conceptual link is weak. Do not add edges if the value similarity is poor, even if components are sequential.

4.  **Combine and Finalize Edges:**
    * Create a final list of edges by merging your refined (filtered) `Pre-identified Edges` with the newly identified `Heuristic Edges`.
    * Ensure the final list has no duplicate `from`-`to` pairs. All attributes connecting a given pair should be under a single edge entry.
    * The output should be a single YAML list under the top-level key `edges`.

### Example: Input `ML Components` (Partial)
```yaml
- Driver Creation:
    file_name: "driver.py"
    line_range: "Lines 1-50"
    inputs: 
        target_date: '2025-01-15'
    outputs:
        driver_output_path: "gs://my-bucket/data/driverset.parquet"
- Feature Pull:
    file_name: "feature_engineering.py"
    line_range: "Lines 20-80"
    inputs:
        driver_path: "gs://my-bucket/data/driverset.parquet" # Exact value match
        # other inputs...
    outputs:
        training_feature_set_path: "gs://my-bucket/features/training_set_run_abcdef.parquet"
        evaluation_feature_set_path: "gs://my-bucket/features/eval_set_run_abcdef.parquet" 
- Model Training:
    file_name: "train_model.py"
    line_range: "Lines 1-75"
    inputs:
        training_data_location: "gs://my-bucket/features/training_set_run_abcdef.parquet" # Exact value match
        evaluation_data_location: "gs://my-bucket/features_final/eval_set_run_abcdef.parquet" # Potential heuristic match
    outputs:
        trained_model_artifact_path: "gs://my-bucket/models/prod_model_v2.0/model.txt"
- Model Packaging:
    file_name: "train_model.py"
    line_range: "Lines 75-85"
    inputs:
        model_input_path: "gs://my-bucket/models/prod_model_v2.0.1_candidate/model.txt" # Potential heuristic match
    outputs:
        packaged_model_uri: "gs://my-bucket/packages/prod_model_v2.onnx"
```

### Example: Input `Pre-identified Edges` (From programmatic step)
```yaml
edges:
  - from: Driver Creation
    to: Feature Pull
    attributes:
      driver_output_path: "gs://my-bucket/data/driverset.parquet"
  - from: Feature Pull
    to: Model Training
    attributes:
      training_feature_set_path: "gs://my-bucket/features/training_set_run_abcdef.parquet"
```

### Desired Final Output Format (Illustrative YAML):
```yaml
edges:
  - from: Driver Creation
    to: Feature Pull
    attributes:
      driver_output_path: "gs://my-bucket/data/driverset.parquet"
  - from: Feature Pull
    to: Model Training
    attributes:
      training_feature_set_path: "gs://my-bucket/features/training_set_run_abcdef.parquet"
      evaluation_feature_set_path: "gs://my-bucket/features/eval_set_run_abcdef.parquet" # Newly added from heuristic match
  - from: Model Training # Brand new edge identified heuristically
    to: Model Packaging
    attributes:
      trained_model_artifact_path: "gs://my-bucket/models/prod_model_v2.0/model.txt"
```

Inputs Provided Below:

ML Components:
{nodes_yaml_str}

Pre-identified Edges:
{pre_identified_edges_yaml_str}
"""
  
    
    llm_client = LLMClient()
    response: litellm.types.utils.ModelResponse = llm_client.call_llm(
        prompt=edge_refinement_and_augmentation_prompt,
        max_tokens=2048,
        temperature=0,
        repetition_penalty=1.0,
        top_p=0.3,
    )
    choices: litellm.types.utils.Choices = response.choices
    edge_identification_response = choices[0].message.content or ""
    logger.debug("Edge identification response from LLM: %s", edge_identification_response)

    # Extract only the edges YAML content, and filter out any edge attributes which are not actually the output of the `from` component 
    filtered_edges = clean_edges(edge_identification_response, nodes_yaml_str)

    return filtered_edges, edge_identification_response