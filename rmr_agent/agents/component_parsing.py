import json
import litellm
from rmr_agent.llms import LLMClient
from rmr_agent.utils import convert_to_dict, preprocess_python_file


def retry_component_identification(python_file_path, full_file_list, code_summary, model="gpt-4o", temperature=0, max_tokens=2048, 
                 frequency_penalty=0, presence_penalty=0):
    pass

def get_relevant_component_definitions(component_identification_response):
    try:
        # Convert the JSON response into a Python dictionary
        component_identification_dict = convert_to_dict(component_identification_response)

        if component_identification_dict == None:
            raise ValueError("No JSON object found in the LLM component identification response")
        
        # Load all component definitions
        with open('rmr_agent/ml_components/component_definitions.json', 'r') as f:
            component_definitions = json.load(f)

        relevant_component_definitions = ""
        for component_name in component_identification_dict.keys():
            if component_name in component_definitions:
                relevant_component_definitions += f"    - {component_name}: {component_definitions[component_name]}\n"
            else:
                print("Component definition not found for component:", component_name)
        
        return relevant_component_definitions
    except Exception as e:
        print(f"Error in get_relevant_component_definitions: {e}")
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
  "Component Name": {{
    "line_range": "A single, merged line range (e.g., 0-49)",
    "evidence": [
      {{
        "quote_or_paraphrase": "Quote/paraphrase text",
        "support_reason": "Reason text"
      }},
      {{
        "quote_or_paraphrase": "Quote/paraphrase text",
        "support_reason": "Reason text"
      }}
    ],
    "why_this_is_separate": "The explanation of why this component is separate (or null if not present)"
    }}
}}

### Component Identification Response:
{component_identification_response}

### Component Definitions To Help Resolve Overlaps:
{relevant_component_definitions}
"""

    llm_client = LLMClient(model_name="gpt-4o")
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
    # Add the file name to each identified component
    for component, metadata in parsed_dict.items():
        if component not in allowed_components:
            print(f'Found identified component outside of allowed set of components for {file}: "{component}"')
            # Delete this extra component category
            del parsed_dict[component]
            continue
            
            
        metadata['file_name'] = file

        if len(parsed_dict) == 1:
            # when only one component identified in the file, just take all of the lines in the file for that component. 
            cleaned_code = preprocess_python_file(file)
            num_lines = len(cleaned_code.splitlines())
            metadata['line_range'] = f"1-{num_lines}"

    return parsed_text, parsed_dict



