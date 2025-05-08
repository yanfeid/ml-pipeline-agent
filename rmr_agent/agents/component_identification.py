import os
import json
import litellm
from rmr_agent.llms import LLMClient
    
def get_component_definitions_str():
    with open('rmr_agent/ml_components/component_definitions.json', 'r') as f:
        component_definitions = json.load(f)
    component_def_str = ""
    for component_name, definition in component_definitions.items():
        component_def_str += f"    - {component_name}: {definition}\n"
    return component_def_str

def component_identification_agent(python_file_path, full_file_list, code_summary, model="gpt-4o", temperature=0, max_tokens=2048, 
                 frequency_penalty=0, presence_penalty=0):
    base_name = os.path.basename(python_file_path)  
    file_name = base_name.replace('.py', '.ipynb')
    print(f"Running component identification for {file_name}")

    # Get the component definitions as a string
    component_definitions_str = get_component_definitions_str()

    classification_prompt = f"""Analyze the provided code summary to identify MAJOR ML components — substantial, primary elements that should function as independent ML workflow nodes. Use only the ML component categories defined below.

### ML Component Categories:
{component_definitions_str}

### Classification Rules:
1. Use only the predefined ML component categories listed above. **Do not invent new categories!**
2. Only identify multiple components if you are absolutely sure the code can be divided by a single, distinct line of separation (components should never overlap!). You must be extremely confident that each resulting component after the split can be identified as one of the predefined ML component categories.
    - If you think more than one major component is present, justify why they warrant separate major nodes, and confirm you could split them based on a single line.
    - If you cannot separate the components by a single line, DO NOT IDENTIFY THEM AS SEPARATE COMPONENTS. Keep it as one major component.
    - Do not split SQL into separate components.
3. For the identified component(s), provide:
    - Line Range: A merged, non-overlapping range (e.g., Lines 50-100).
    - Evidence: Top 3 most important quotes from the summary supporting your classification decision, with a brief explanation of their relevance.
    - (If multiple components are listed) Why This Is Separate: Provide verification there is no overlap with other identified components' line ranges. Then explain why you think we should split this code into a distinct ML workflow node that should be run separately. Then explain why this split results in one of the ML component categories defined above. 
4. Identified components should be **unique**. Do not repeat a component category multiple times. 
5. If you are uncertain about any classification, DO NOT include it.
6. If none of these components can be confidently identified from the code summary, leave component name as "Undetermined", line range as "None", and give evidence why this does not fit any category.

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
    
### Current File's Name:
{file_name}

### Full ML Pipeline File List:
{full_file_list}

### Current File's Code Summary:
{code_summary}
"""
    llm_client = LLMClient()
    response: litellm.types.utils.ModelResponse = llm_client.call_llm(
        prompt=classification_prompt,
        max_tokens=2048,
        temperature=0.0,
        repetition_penalty=1.0,
        top_p=0.3,
    )
    choices: litellm.types.utils.Choices = response.choices
    component_id_str = choices[0].message.content or ""
    #print("Components identified:")
    #print(classification)
    return component_id_str