import os
import json
import litellm
from llms import LLMClient
    
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

    classification_prompt = f"""Analyze the provided code summary to identify MAJOR ML components — substantial, primary elements that could function as independent ML workflow nodes. Use only the ML component categories defined below.

ML COMPONENT CATEGORIES:
{component_definitions_str}

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
6. If none of these components can be confidently identified from the code summary, leave component name as "Undetermined", line range as "None", and give evidence why this does not fit any category.

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
    component_identification = choices[0].message.content or ""
    #print("Components identified:")
    #print(classification)
    return component_identification