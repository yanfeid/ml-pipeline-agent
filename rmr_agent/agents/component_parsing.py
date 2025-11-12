import json
import litellm
import logging
from rmr_agent.llms import LLMClient
from rmr_agent.utils import convert_to_dict, preprocess_python_file
from rmr_agent.utils.logging_config import setup_logger

# 设置模块日志记录器
logger = setup_logger(__name__)

def retry_component_identification(python_file_path, full_file_list, code_summary, model="gpt-4o", temperature=0, max_tokens=2048, 
                 frequency_penalty=0, presence_penalty=0):
    pass

def get_relevant_component_definitions(component_identification_response):
    try:
        # Convert the JSON response into a Python dictionary
        component_identification_dict = convert_to_dict(component_identification_response)

        if not component_identification_dict:
            logger.warning("No JSON object found in the LLM component identification response")
            return ""
        
        # Load all component definitions
        with open('rmr_agent/ml_components/component_definitions.json', 'r') as f:
            component_definitions = json.load(f)

        relevant_component_definitions = ""
        for component_name in component_identification_dict.keys():
            if component_name in component_definitions:
                relevant_component_definitions += f"    - {component_name}: {component_definitions[component_name]}\n"
            else:
                logger.warning("Component definition not found for component: %s", component_name)
        
        return relevant_component_definitions
    except Exception as e:
        logger.error("Error in get_relevant_component_definitions: %s", e)
        return ""

def parse_component_identification(component_identification_response, file):
    """
    Parse component identification response, extracting components with their line ranges,
    evidence, and why_separate sections.
    
    Args:
        component_identification_response (str): The raw LLM response text
        
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
    relevant_component_definitions = get_relevant_component_definitions(component_identification_response)

    parse_prompt = f"""You are tasked with reviewing and correcting a JSON string that represents identified ML components from a Python file in an ML pipeline. You will produce a valid, accurate JSON output.

### Instructions:
    1. Parse the JSON String:
        - Read the input JSON string containing ML components, each with details like line ranges, evidence for this component being identified, and why it is separate from other identified components.
    2. Ensure Each Component Has a Merged Line Range:
        - If a component's line range shows multiple ranges, merge all line ranges into a single range using the minimum start value and maximum end value (e.g., '258-311' for '258-287, 300-311'), even if there are gaps.
    3. Keep all "quote_or_paraphrase" and "support_reason" items for each component in your output, as well as the "why_separate" section if present (otherwise set to null).
    4. **Identify Overlapping Line Ranges**: 
        - Compare the merged line ranges of all components to identify overlaps.
    5. **Resolve Overlaps**:
        - For each identified line range overlap:
            - If one component’s line range is fully contained in another componet's line range, keep the larger one.
            - If partial overlap occurs, keep the component with stronger classification evidence matching it's component definition
        - Ensure there is at least one component left - do not remove them all. 

### Response Format (JSON):
{{
  "<ML_COMPONENT_NAME_HERE>": {{ 
    "line_range": "<MERGED_NON_OVERLAPPING_LINE_RANGE>", // Example: "0-49", "55-72"
    "evidence": [
      {{
        "quote_or_paraphrase": "<RELEVANT_QUOTE_OR_PARAPHRASE_1>",
        "support_reason": "<EXPLANATION_WHY_EVIDENCE_1_SUPPORTS_THIS_COMPONENT>"
      }},
      {{
        "quote_or_paraphrase": "<RELEVANT_QUOTE_OR_PARAPHRASE_2>",
        "support_reason": "<EXPLANATION_WHY_EVIDENCE_2_SUPPORTS_THIS_COMPONENT>"
      }},
      {{
        "quote_or_paraphrase": "<RELEVANT_QUOTE_OR_PARAPHRASE_3>",
        "support_reason": "<EXPLANATION_WHY_EVIDENCE_3_SUPPORTS_THIS_COMPONENT>"
      }}
    ],
    "why_this_is_separate": "<JUSTIFICATION_FOR_THIS_COMPONENT_BEING_SEPARATE_AND_VERIFICATION_OF_NOT_OVERLAPPING>"
    }}
}}

### Component Identification Response:
{component_identification_response}

### Component Definitions To Help Resolve Overlaps:
{relevant_component_definitions}
"""

    llm_client = LLMClient()
    response: litellm.types.utils.ModelResponse = llm_client.call_llm(
        prompt=parse_prompt,
        max_tokens=2048,
        temperature=0.0,
        repetition_penalty=1.0,
        top_p=0.3,
    )
    choices: litellm.types.utils.Choices = response.choices
    parsed_text = choices[0].message.content or ""

    with open('rmr_agent/ml_components/component_definitions.json', 'r') as f:
        component_definitions = json.load(f)
    allowed_components = list(component_definitions.keys())

    # Create dictionary with parsed data
    parsed_dict = convert_to_dict(parsed_text)
    if not parsed_dict:
        logger.warning("No components identified in the response for file: %s", file)
    
    # Add the file name to each identified component and filter out invalid components
    components_to_delete = []
    for component, metadata in parsed_dict.items():
        # Check if component is in the allowed set of components
        if component not in allowed_components:
            logger.warning('Found identified component outside of allowed set of components for %s: "%s"', file, component)
            # Delete this extra component category (do later so we do not edit dictionary we are iterating over)
            components_to_delete.append(component)
            continue
            
        metadata['file_name'] = file
    
    # Delete the invalid components
    for component in components_to_delete:
        del parsed_dict[component]

    # Handle single component case
    if len(parsed_dict) == 1:
        # when only one component identified in the file, just take all of the lines in the file for that component. 
        cleaned_code = preprocess_python_file(file)
        num_lines = len(cleaned_code.splitlines())
        metadata['line_range'] = f"1-{num_lines}"

    return parsed_text, parsed_dict