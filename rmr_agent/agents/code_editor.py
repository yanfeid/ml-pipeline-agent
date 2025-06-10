from rmr_agent.utils import py_to_notebook
import difflib
import re
import json
from rmr_agent.llms import LLMClient
from collections import defaultdict

def infer_section_name(code_lines, attribute_parsing_json):
    pattern = re.compile(r'section_name\s*=\s*["\']([\w_]+)["\']')
    for line in code_lines:
        match = pattern.search(line)
        if match:
            raw = match.group(1)
            section_candidate = raw.replace("_", " ").title()
            break
    else:
        section_candidate = None

    section_names = []
    for block in attribute_parsing_json.get("attribute_parsing", []):
        section_names.extend(block.keys())

    if section_candidate in section_names:
        print(f"📌 Exact section name match: {section_candidate}")
        return section_candidate

    closest_matches = difflib.get_close_matches(section_candidate or "", section_names, n=1, cutoff=0.4)
    if closest_matches:
        print(f"🤖 Section name '{section_candidate}' not found. Using closest match: {closest_matches[0]}")
        return closest_matches[0]

    print("❌ Could not determine section name from code or JSON.")
    return None

def scoped_variable_renaming(code_lines, value_to_newname):
    has_modifications = False
    updated_lines = list(code_lines)
    for value, new_var_name in value_to_newname.items():
        i = 0
        while i < len(updated_lines):
            line = updated_lines[i]
            if line is None:
                i += 1
                continue
            m = re.match(r'^\s*(\w+)\s*=\s*([\'"])(.+?)\2', line)
            if m:
                var_name = m.group(1)
                var_value = m.group(3)
                if var_value == value:
                    print(f"🔄 Scoped replacing {var_name} → {new_var_name} for value={value} (deleting line {i+1})")
                    updated_lines[i] = None  
                    j = i + 1
                    while j < len(updated_lines):
                        next_line = updated_lines[j]
                        if next_line is None:
                            j += 1
                            continue
                        if re.match(rf'^\s*{re.escape(var_name)}\s*=', next_line, flags=re.IGNORECASE):
                            break
                        replaced = re.sub(rf'\b{re.escape(var_name)}\b', new_var_name, next_line)
                        if replaced != next_line:
                            has_modifications = True
                        updated_lines[j] = replaced
                        j += 1
            i += 1
    new_lines = [l for l in updated_lines if l is not None]
    return new_lines, has_modifications


def code_editor_agent(python_file_path: str, attribute_parsing_json: dict, llm_model: str = "gpt-4o") -> str:

    with open(python_file_path, "r", encoding="utf-8") as f:
        code_lines = f.readlines()

    code_text = "".join(code_lines)

    section_name = infer_section_name(code_lines, attribute_parsing_json)
    if not section_name:
        print(f"❌ Could not find section_name in {python_file_path}")
        return code_text
    print(f"📌 Inferred section name: '{section_name}'")

    relevant_vars = []
    for block in attribute_parsing_json.get("attribute_parsing", []):
        if section_name in block:
            section = block[section_name]
            relevant_vars.extend(section.get("inputs", []))
            relevant_vars.extend(section.get("outputs", []))

    if not relevant_vars:
        print(f"❌ Section '{section_name}' not found in attribute_parsing.")
        return code_text

    value_to_newname = {}
    for var in relevant_vars:
        if var.get("already_exists") and var.get("renamed"):
            print(f"[mapping] {var.get('value')} → {var.get('name')}")
            value_to_newname[var.get("value")] = var.get("name")
    code_lines, scope_mod = scoped_variable_renaming(code_lines, value_to_newname)

    new_lines = []
    has_modifications = scope_mod  
    skip_until_idx = -1

    # Build value → [name1, name2, ...] mapping
    value_to_names = defaultdict(list)
    for var in relevant_vars:
        val = var["value"]
        val_key = str(val[0]) if isinstance(val, list) else str(val)
        value_to_names[val_key].append(var["name"])
    
    for idx, line in enumerate(code_lines):
        if idx < skip_until_idx:
            continue 

        if "config.get" in line:
            new_lines.append(line)
            continue


        modified_line = line
        processed_values = set() 

        # print(f"🔍 Variables in section '{section_name}':")
        for var in relevant_vars:
            # print(f"   - {var.get('name')} | already_exists={var.get('already_exists')} | renamed={var.get('renamed')}")
            name = var.get("name")
            value = var.get("value")
            already_exists = var.get("already_exists", False)
            renamed = var.get("renamed", False)


            if already_exists and not renamed:
                if re.match(rf"^\s*{re.escape(name)}\s*=", line, flags=re.IGNORECASE):
 
                    if not line.rstrip().endswith('\\') and all(k == 0 for k in [
                        line.count('(') - line.count(')'),
                        line.count('[') - line.count(']'),
                        line.count('{') - line.count('}')
                    ]):
                      
                        modified_line = None
                    else:
                        statement_lines = [line]
                        open_parens = line.count('(') - line.count(')')
                        open_brackets = line.count('[') - line.count(']')
                        open_braces = line.count('{') - line.count('}')
                        continuation = line.rstrip().endswith('\\')

                        next_idx = idx + 1
                        while (open_parens > 0 or open_brackets > 0 or open_braces > 0 or continuation) and next_idx < len(code_lines):
                            next_line = code_lines[next_idx]
                            statement_lines.append(next_line)
                            open_parens += next_line.count('(') - next_line.count(')')
                            open_brackets += next_line.count('[') - next_line.count(']')
                            open_braces += next_line.count('{') - next_line.count('}')
                            continuation = next_line.rstrip().endswith('\\')
                            next_idx += 1

                        skip_until_idx = next_idx  
                        modified_line = None
                    has_modifications = True
                    continue


            elif not already_exists and modified_line:
                single_value = value[0] if isinstance(value, list) else value
                single_value_str = str(single_value)
                if single_value_str in processed_values:
                    continue

                is_ambiguous = len(value_to_names[single_value_str]) > 1

                if isinstance(value, list) and all(isinstance(v, str) for v in value):
                    # construct：'PAN',\s*'NO_AVS',...
                    values_pattern = ',\s*'.join([rf'["\']{re.escape(v)}["\']' for v in value])
                    full_tuple_pattern = re.compile(rf'\(\s*{values_pattern}\s*\)')

                    if full_tuple_pattern.search(modified_line):
                        modified_line = full_tuple_pattern.sub(name, modified_line)
                        has_modifications = True

                elif not is_ambiguous:
                    pattern_value = re.compile(
                        rf'(?:["\']{re.escape(single_value_str)}["\']|(?<!\w){re.escape(single_value_str)}(?!\w))'
                    )
                    if pattern_value.search(modified_line):
                        modified_line = pattern_value.sub(name, modified_line)
                        has_modifications = True

                else:
                    # ⚠️ One-to-many mapping: multiple variable names share the same value
                    print(f"⚠️ Ambiguous value `{single_value_str}` shared by: {value_to_names[single_value_str]}")
                    usage_lines = [
                        (i, line) for i, line in enumerate(code_lines) if single_value_str in line
                    ]

                    if usage_lines:
                        context_blocks = [
                            {
                                "line_index": idx,
                                "context": "\n".join(code_lines[max(0, idx - 3): idx + 4])
                            }
                            for idx, _ in usage_lines
                        ]
                    else:
                        print(f"⚠️ No usage lines found for value `{single_value_str}` → skipping LLM disambiguation.")
                        processed_values.add(single_value_str)
                        continue

                    if not context_blocks:
                        print(f"⚠️ No code context generated for value `{single_value_str}` → skipping LLM step.")
                        processed_values.add(single_value_str)
                        continue

                    llm_client = LLMClient(model_name=llm_model)

                    prompt = f"""
                        You are an expert Python code refactoring assistant.

                        We are replacing hardcoded values with config variable names.
                        However, the same value `{single_value_str}` appears multiple times in the code
                        and maps to more than one candidate variable name: {value_to_names[single_value_str]}

                        Your task:
                        - Read each code context provided below.
                        - For each occurrence, choose the best-matching config variable name from the list above.
                        - Use only the local code context to make your decision.

                        Instructions:
                        - Return a JSON list of objects: one for each usage.
                        - Each object must contain:
                            - `line_index`: the line number in the original file
                            - `name`: the best variable name from the candidate list

                        Example Output:
                        [
                        {{ "line_index": 27, "name": "train_parquet_path" }},
                        {{ "line_index": 32, "name": "val_parquet_path" }}
                        ]
                        Now analyze the following code contexts:
                        {json.dumps(context_blocks, indent=2)}
                        """                  
                    response_text = llm_client.call_llm(
                        prompt=prompt,
                        max_tokens=500,
                        temperature=0,
                        repetition_penalty=1.0,
                        top_p=0.1
                        )
                        
 
                    raw_content = response_text['choices'][0]['message']['content']
                    # Remove markdown code block markers
                    cleaned = re.sub(r"^```json\s*|\s*```$", "", raw_content.strip())

                        # Now parse JSON
                    try:
                        result = json.loads(cleaned)
                    except json.JSONDecodeError as e:
                        print("❌ Failed to parse LLM output:", e)
                        processed_values.add(single_value_str)
                        continue

                    for mapping in result:
                        idx = mapping["line_index"]
                        target_name = mapping["name"]
                        line = code_lines[idx]
                        pattern = re.compile(
                            rf'(?:["\']{re.escape(single_value_str)}["\']|(?<!\w){re.escape(single_value_str)}(?!\w))'
                        )
                        new_line = pattern.sub(target_name, line, count=1)
                        code_lines[idx] = new_line
                        has_modifications = True

                # record
                processed_values.add(single_value_str)
        if modified_line is not None:
            new_lines.append(modified_line)
        else:
            new_lines.append(None)  
            has_modifications = True

    final_code = "\n".join(line.rstrip("\n") for line in new_lines if line is not None) + "\n"

    if has_modifications:
        with open(python_file_path, "w", encoding="utf-8") as f:
            f.write(final_code)
        print(f"✅ Code overwritten: {python_file_path}")
    else:
        print("✅ No modifications were made to the code.")

    py_to_notebook(python_file_path)
    return final_code



# # ============= for test ================
# json_file = "/Users/yanfdai/Desktop/codespace/DAG_FULLSTACK/rmr_agent/rmr_agent/checkpoints/bt-retry-v2/3/attribute_parsing.json"
# # python_code = "/Users/yanfdai/Desktop/codespace/DAG_FULLSTACK/rmr_agent/rmr_agent/repos/bt-retry-v2/notebooks_test/1_driver_creation_2.py"
# python_code = "/Users/yanfdai/Desktop/codespace/DAG_FULLSTACK/rmr_agent/rmr_agent/repos/bt-retry-v2/notebooks/1_driver_creation_2.py"


# with open(json_file, "r", encoding="utf-8") as f:
#     attribute_config = json.load(f)
# edited_code = code_editor_agent(python_code, attribute_config)



