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

def extract_cross_section_variables(code_text: str, attribute_parsing_json: dict, current_section_name: str) -> list:
    """
    Extracts config variables from other sections (not the current section or 'general') 
    based on config.get('section', 'key') calls found in the code.

    Args:
        code_text (str): The source code as a string.
        attribute_parsing_json (dict): The JSON containing all section definitions.
        current_section_name (str): The original name of the current section (e.g., "Model Evaluation").

    Returns:
        list: A list of variable dictionaries (same format as in JSON) to be added to relevant_vars.
    """
    def normalize(name: str) -> str:
        return name.lower().replace(" ", "_")

    # Build mapping from normalized section names → actual section names
    section_name_map = {}
    for block in attribute_parsing_json.get("attribute_parsing", []):
        for actual_name in block.keys():
            section_name_map[normalize(actual_name)] = actual_name

    current_section_norm = normalize(current_section_name)

    # Regex to match: config.get('some_section', 'some_key')
    config_get_pattern = re.compile(r"config\.get\(\s*([^\s,]+)\s*,\s*'([^']+)'\s*\)")

    extra_vars = []
    for match in config_get_pattern.finditer(code_text):
        ref_section_raw, ref_key = match.groups()

        # Skip 'general' section and dynamic config.get(section_name, ...)
        if ref_section_raw == "'general'" or ref_section_raw == "section_name":
            continue

        # Strip quotes and normalize section name
        ref_section_clean = ref_section_raw.strip("'")
        ref_section_norm = normalize(ref_section_clean)

        # Skip if referring to the current section (redundant)
        if ref_section_norm == current_section_norm:
            continue

        # Look up actual section name from normalized version
        actual_section_name = section_name_map.get(ref_section_norm)
        if not actual_section_name:
            print(f"⚠️ No matching section in JSON for '{ref_section_clean}'")
            continue

        found = False
        for block in attribute_parsing_json.get("attribute_parsing", []):
            if actual_section_name in block:
                section_data = block[actual_section_name]
                all_vars = section_data.get("inputs", []) + section_data.get("outputs", [])
                for var in all_vars:
                    if var["name"] == ref_key:
                        print(f"✅ Found cross-section variable: {actual_section_name}.{ref_key}")
                        extra_vars.append(var)
                        found = True
                        break
                break

        if not found:
            print(f"⚠️ Could not find variable '{ref_key}' in section '{actual_section_name}'")

    return extra_vars

def code_editor_agent(python_file_path: str, attribute_parsing_json: dict, llm_model: str = "gpt-4o") -> str:
    with open(python_file_path, "r", encoding="utf-8") as f:
        code_lines = f.readlines()
    code_text = "".join(code_lines)

    # infer current section
    section_name = infer_section_name(code_lines, attribute_parsing_json)
    if not section_name:
        print(f"❌ Could not find section_name in {python_file_path}")
        return code_text
    print(f"📌 Inferred section name: '{section_name}'")

    # collect vars from attribute_parsing_json 
    relevant_vars = []
    for block in attribute_parsing_json.get("attribute_parsing", []):
        if section_name in block:
            section = block[section_name]
            relevant_vars.extend(section.get("inputs", []))
            relevant_vars.extend(section.get("outputs", []))

    cross_section_vars = extract_cross_section_variables(code_text, attribute_parsing_json, section_name)
    relevant_vars.extend(cross_section_vars)

    print("✅ Final relevant_vars:")
    print(json.dumps(relevant_vars, indent=2, ensure_ascii=False))

    if not relevant_vars:
        print(f"❌ Section '{section_name}' not found in attribute_parsing.")
        return code_text
    
    #  initial mapping
    value_to_newname = {}
    for var in relevant_vars:
        if var.get("already_exists") and var.get("renamed"):
            print(f"[mapping] {var['value']} → {var['name']}")
            value_to_newname[var["value"]] = var["name"]

    # use scoped_variable_renaming handle renamed
    code_lines, scope_mod = scoped_variable_renaming(code_lines, value_to_newname)
    new_lines = []
    has_modifications = scope_mod
    skip_until_idx = -1

    # initial to record processed values
    processed_values = set()
    value_to_names = defaultdict(list)
    for var in relevant_vars:
        val = var["value"]
        key = str(val[0] if isinstance(val, list) else val)
        value_to_names[key].append(var["name"])

    for idx, line in enumerate(code_lines):
        if idx < skip_until_idx:
            continue

        modified_line = line
        # skip config.get
        if "config.get" in line:
            new_lines.append(line)
            continue

        for var in relevant_vars:
            name = var["name"]
            value = var["value"]
            already_exists = var.get("already_exists", False)
            renamed = var.get("renamed", False)

            if already_exists and not renamed:
                # match “name = …”, ignorecase
                if re.match(rf"^\s*{re.escape(name)}\s*=", line, flags=re.IGNORECASE):
                    # single row vs multiple rows
                    if (not line.rstrip().endswith('\\')
                        and (line.count('(') - line.count(')') == 0)
                        and (line.count('[') - line.count(']') == 0)
                        and (line.count('{') - line.count('}') == 0)
                    ):
                        modified_line = None
                    else:
                        statement_lines = [line]
                        open_p = line.count('(') - line.count(')')
                        open_b = line.count('[') - line.count(']')
                        open_c = line.count('{') - line.count('}')
                        cont = line.rstrip().endswith('\\')
                        nxt = idx + 1
                        while (open_p > 0 or open_b > 0 or open_c > 0 or cont) and nxt < len(code_lines):
                            nl = code_lines[nxt]
                            statement_lines.append(nl)
                            open_p += nl.count('(') - nl.count(')')
                            open_b += nl.count('[') - nl.count(']')
                            open_c += nl.count('{') - nl.count('}')
                            cont = nl.rstrip().endswith('\\')
                            nxt += 1
                        skip_until_idx = nxt
                        modified_line = None
                    has_modifications = True
                    continue

            elif not already_exists and modified_line:
                single_value = value[0] if isinstance(value, list) else value
                single_value_str = str(single_value)

                if single_value_str in processed_values:
                    continue
                is_ambiguous = len(value_to_names[single_value_str]) > 1

                # list replacement
                if isinstance(value, list) and all(isinstance(v, str) for v in value):
                    pat_vals = ',\s*'.join(rf'["\']{re.escape(v)}["\']' for v in value)
                    full_pat = re.compile(rf'\(\s*{pat_vals}\s*\)')
                    if full_pat.search(modified_line):
                        modified_line = full_pat.sub(name, modified_line)
                        has_modifications = True

                # single value replacement
                elif not is_ambiguous:
                    pat = re.compile(
                        rf'(?:["\']{re.escape(single_value_str)}["\']|(?<!\w){re.escape(single_value_str)}(?!\w))'
                    )
                    if pat.search(modified_line):
                        modified_line = pat.sub(name, modified_line)
                        has_modifications = True

                # ambigious value with LLM disambiguation
                else:
                    print(f"⚠️ Ambiguous value `{single_value_str}` shared by: {value_to_names[single_value_str]}")
                    # 找到所有出现该值的行
                    usage_lines = [(i, l) for i, l in enumerate(code_lines) if single_value_str in l]
                    if not usage_lines:
                        print(f"⚠️ No usage lines found for value `{single_value_str}` → skipping LLM disambiguation.")
                        processed_values.add(single_value_str)
                        continue

                    # collect contexts
                    context_blocks = []
                    for i, _ in usage_lines:
                        block = "\n".join(code_lines[max(0, i - 3) : i + 4])
                        context_blocks.append({"line_index": i, "context": block})
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
                    response = llm_client.call_llm(
                        prompt=prompt,
                        max_tokens=500,
                        temperature=0,
                        repetition_penalty=1.0,
                        top_p=0.1
                    )
                    raw = response["choices"][0]["message"]["content"]
                    cleaned = re.sub(r"^```json\s*|\s*```$", "", raw.strip())
                    try:
                        mappings = json.loads(cleaned)
                    except json.JSONDecodeError as e:
                        print("❌ Failed to parse LLM output:", e)
                        processed_values.add(single_value_str)
                        continue

                    for m in mappings:
                        i2 = m["line_index"]
                        tgt = m["name"]
                        pat = re.compile(
                            rf'(?:["\']{re.escape(single_value_str)}["\']|(?<!\w){re.escape(single_value_str)}(?!\w))'
                        )
                        updated = pat.sub(tgt, code_lines[i2], count=1)
                        code_lines[i2] = updated
                        if i2 == idx:
                            modified_line = updated
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

    # convert .py to Notebooks
    py_to_notebook(python_file_path)
    return final_code


# # ============= for test ================
# json_file = "/Users/yanfdai/Desktop/codespace/DAG_FULLSTACK/rmr_agent/rmr_agent/checkpoints/bt-retry-v2/3/attribute_parsing.json"
# # python_code = "/Users/yanfdai/Desktop/codespace/DAG_FULLSTACK/rmr_agent/rmr_agent/repos/bt-retry-v2/notebooks_test/1_driver_creation_2.py"
# python_code = "/Users/yanfdai/Desktop/codespace/DAG_FULLSTACK/rmr_agent/rmr_agent/repos/bt-retry-v2/notebooks/1_driver_creation_2.py"

# #充分测试！

# with open(json_file, "r", encoding="utf-8") as f:
#     attribute_config = json.load(f)
# edited_code = code_editor_agent(python_code, attribute_config)