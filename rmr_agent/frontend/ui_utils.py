import os
import json
import yaml
import re
from rmr_agent.workflow import CHECKPOINT_BASE_PATH
from pyvis.network import Network
import streamlit as st
from streamlit import rerun
from streamlit_mermaid import st_mermaid
import streamlit.components.v1 as components
import tempfile

def clean_file_path(file_path, repo_name, repos_base_dir="rmr_agent/repos/"):
    prefix = repos_base_dir + repo_name + "/"
    cleaned_file_path = file_path.replace('.py', '.ipynb')
    if file_path.startswith(prefix):
        return cleaned_file_path[len(prefix):]
    return cleaned_file_path

def remove_line_numbers(code_lines):
    cleaned_lines = []
    for line in code_lines:
        cleaned_lines.append(line.split('|')[-1])
    return cleaned_lines

def clean_line_range(line_range: str):
    return line_range.lower().split('lines')[-1].strip()

def get_components(repo_name, run_id):
    try:
        file_path = os.path.join(CHECKPOINT_BASE_PATH, repo_name, run_id, 'component_parsing.json')
        with open(file_path, 'r') as file:
            components = json.load(file)
        return components['component_parsing']
    except FileNotFoundError:
        raise FileNotFoundError(f"Component parsing file not found for repo: {repo_name}, run_id: {run_id}")
    except json.JSONDecodeError as e:
        raise json.JSONDecodeError(f"Invalid JSON in component parsing file: {e.msg}", e.doc, e.pos)
    except IOError as e:
        raise IOError(f"Error reading component parsing file: {str(e)}")


def get_cleaned_code(repo_name, run_id):
    try:
        file_path = os.path.join(CHECKPOINT_BASE_PATH, repo_name, run_id, 'summarize.json')
        with open(file_path, 'r') as file:
            content = json.load(file)
        return content['cleaned_code']
    except FileNotFoundError:
        raise FileNotFoundError(f"Summarize file not found for repo: {repo_name}, run_id: {run_id}")
    except json.JSONDecodeError as e:
        raise json.JSONDecodeError(f"Invalid JSON in summarize file: {e.msg}", e.doc, e.pos)
    except KeyError:
        raise KeyError(f"Missing 'cleaned_code' key in summarize file for repo: {repo_name}, run_id: {run_id}")
    except IOError as e:
        raise IOError(f"Error reading summarize file: {str(e)}")


def get_dag_yaml(repo_name, run_id):
    try:
        file_path = os.path.join(CHECKPOINT_BASE_PATH, repo_name, run_id, 'dag.yaml')
        with open(file_path, 'r') as file:
            # dag_yaml = yaml.safe_load(file)
            dag_yaml_str = file.read()
            print("Successfully loaded dag.yaml")
        return dag_yaml_str
    except FileNotFoundError:
        raise FileNotFoundError(f"DAG YAML file not found for repo: {repo_name}, run_id: {run_id}")
    except yaml.YAMLError as e:
        raise yaml.YAMLError(f"Invalid YAML in DAG file: {str(e)}")
    except IOError as e:
        raise IOError(f"Error reading DAG YAML file: {str(e)}")
    
def get_pr_url(repo_name, run_id):
    try:
        file_path = os.path.join(CHECKPOINT_BASE_PATH, repo_name, run_id, 'create_pull_request.json')
        with open(file_path, 'r') as file:
            content = json.load(file)
        return content['pr_url'] 
    except FileNotFoundError:
        raise FileNotFoundError(f"PR URL file not found for repo: {repo_name}, run_id: {run_id}")
    except IOError as e:
        raise IOError(f"Error reading PR URL file: {str(e)}")
    
def get_pr_body(repo_name, run_id):
    try:
        file_path = os.path.join(CHECKPOINT_BASE_PATH, repo_name, run_id, 'create_pr_body.json')
        with open(file_path, 'r') as file:
            content = json.load(file)
        return content['pr_body'] 
    except FileNotFoundError:
        raise FileNotFoundError(f"PR body file not found for repo: {repo_name}, run_id: {run_id}")
    except IOError as e:
        raise IOError(f"Error reading PR body file: {str(e)}")
    
def show_rmr_agent_results(repo_name, run_id):
    # Load and display the PR URL in Markdown
    pr_url = get_pr_url(repo_name, run_id)
    if pr_url:
        st.markdown(f"### Pull Request Created: [View PR]({pr_url})", unsafe_allow_html=True)
    else:
        st.error("Could not retrieve the PR URL.")

    # Load the PR body
    pr_body = get_pr_body(repo_name, run_id)
    if not pr_body:
        st.warning("No PR body available to display.")
        return  # Exit early if there's no body
    
    # 3. Find and render the Mermaid diagram and surrounding markdown
    # Compile the regex pattern for efficiency and clarity
    mermaid_pattern = re.compile(r"```mermaid\n(.*?)\n```", re.DOTALL)
    match = mermaid_pattern.search(pr_body)

    if match:
        # extract content based on match position, avoiding a second regex pass
        markdown_before = pr_body[:match.start()].strip()
        mermaid_code = match.group(1).strip()
        markdown_after = pr_body[match.end():].strip()

        # Render the parts in order, preserving the document flow
        if markdown_before:
            st.markdown(markdown_before, unsafe_allow_html=True)

        with st.expander("View ML Pipeline", expanded=True):
            try:
                st_mermaid(mermaid_code)
            except Exception as e:
                st.error(f"Error rendering Mermaid diagram: {e}")
                st.code(mermaid_code, language="mermaid")
        
        if markdown_after:
            st.markdown(markdown_after, unsafe_allow_html=True)
            
    else:
        # If no diagram is found, just render the entire PR body
        st.markdown(pr_body, unsafe_allow_html=True)
        st.info("No Mermaid diagram found in the PR body.")
    

def get_default_line_range(selected_components, cleaned_code):
    if len(selected_components) == 1:
        return f"1-{len(cleaned_code)}"
    return "Specify line range here (e.g. 1-40)"

def get_steps_could_start_from(repo_name, run_id, all_steps):
    directory_path = os.path.join(CHECKPOINT_BASE_PATH, repo_name, run_id)
    if not os.path.isdir(directory_path):
        print(f"Directory does not exist: {directory_path}, so no start_from options will be shown")
        return []
    
    # Get list of JSON files in the directory
    json_files = set()
    for filename in os.listdir(directory_path):
        if filename.endswith(".json"):
            # Remove the .json extension
            step_name = os.path.splitext(filename)[0]
            json_files.add(step_name)

    # Accumulate steps until we find the first missing one
    available_steps = []
    for step in all_steps:
        available_steps.append(step)
        if step not in json_files:
            # Found first missing step, add it because it could be started from, then break
            break
    
    # Clean up step names
    display_available_steps = []
    for i, step in enumerate(available_steps):
        display_step = f"{i + 1}. {step.replace("_", " ").title()}"
        display_available_steps.append(display_step)

    
    return display_available_steps


# === for dag verification ===
# === Parsing Function ===
def parse_dag_edges_from_yaml(dag_yaml):
    data = yaml.safe_load(dag_yaml)
    if not isinstance(data, dict):
        raise ValueError("Parsed YAML is not a dictionary.")

    raw_edges = data.get("edges", [])
    edges = []
    for edge in raw_edges:
        if isinstance(edge, dict) and "from" in edge and "to" in edge:
            edges.append((edge["from"], edge["to"], edge))  # (src, tgt, full_edge_dict)

    raw_nodes = data.get("nodes", [])
    nodes = []
    for item in raw_nodes:
        if isinstance(item, dict):
            for node_name, attrs in item.items():
                nodes.append((node_name, attrs))

    return edges, nodes

# === DAG Renderer ===
def render_dag_graph(edges, nodes):
    net = Network(height="450px", directed=True)
    for node in nodes:
        net.add_node(
            node,
            label=node,
            shape="box",
            size=20,
            font={"size": 18},
            borderWidth=2,
            
        )

    for src, tgt in edges:
        net.add_edge(src, tgt)

#          "layout": {
#     "hierarchical": {
#       "enabled": true,
#       "direction": "UD",
#       "sortMethod": "directed",
#       "nodeSpacing": 120,
#       "levelSeparation": 150
#     }
#   },
#   "physics": {
#     "enabled": false
#   },

    net.set_options("""
    {
            "layout": {
    "hierarchical": {
      "enabled": true,
      "direction": "UD",
      "sortMethod": "directed",
      "nodeSpacing": 120,
      "levelSeparation": 150
    }
  },

    "edges": {
        "arrows": {
        "to": {
            "enabled": true
        }
        },
        "smooth": {
        "enabled": true,
        "type": "cubicBezier",
        "forceDirection": "vertical",
        "roundness": 0.4
        },
        "color": {
        "color": "#848484",
        "inherit": false
        }
    },
    "nodes": {
        "shape": "box",
        "margin": 10,
        "borderWidth": 2,
        "color": {
        "border": "#2B7CE9",
        "background": "#F0F8FF",
        "highlight": {
            "border": "#1A1A1A",
            "background": "#E6F2FF"
        }
        },
        "font": {
        "color": "#000000",
        "size": 18,
        "face": "Arial"
        }
    }
    }
    """)

    temp_path = tempfile.NamedTemporaryFile(suffix=".html", delete=False)
    net.save_graph(temp_path.name)
    return temp_path.name

# === Main DAG Editor App ===
def dag_edge_editor(edited_dag_yaml):
    st.subheader("Human Verification Of Dag")

    # Step 0: Parse
    edges, nodes = parse_dag_edges_from_yaml(edited_dag_yaml)
    node_names = [name for name, _ in nodes]

    if "edges_state" not in st.session_state:
        st.session_state.edges_state = edges.copy()
    if "nodes_state" not in st.session_state:
        st.session_state.nodes_state = nodes.copy()
    if "edge_index" not in st.session_state:
        st.session_state.edge_index = 0

    # === Step 1: Structure Verification ===
    with st.expander("Step 1: Verify and Edit DAG Structure", expanded=True):
        html_path = render_dag_graph(
            [(e[0], e[1]) for e in st.session_state.edges_state],
            node_names
        )
        components.html(open(html_path, "r", encoding="utf-8").read(), height=450, scrolling=True)

        st.markdown("##### Add a New Edge")
        col1, col2 = st.columns(2)
        with col1:
            src = st.selectbox("Source Node", node_names, key="src_add")
        with col2:
            tgt = st.selectbox("Target Node", node_names, key="tgt_add")

        if st.button("Add Edge"):
            new_edge = {"from": src, "to": tgt, "attributes": {}}
            st.session_state.edges_state.append((src, tgt, new_edge))
            st.success(f"Edge {src} → {tgt} added.")
            rerun()

        st.markdown("##### Remove an Edge")
        edge_to_remove = st.selectbox(
            "Select edge to remove",
            st.session_state.edges_state,
            format_func=lambda e: f"{e[0]} -> {e[1]}"
        )
        if st.button("Remove Selected Edge"):
            st.session_state.edges_state.remove(edge_to_remove)
            st.success("Edge removed.")
            rerun()

    # === Step 2: Attribute Verification ===
    with st.expander("Step 2: Verify Attributes of Each Edge", expanded=True):
        if not st.session_state.edges_state:
            st.info("No edges to review.")
        else:
            index = st.session_state.edge_index
            src, tgt, edge_data = st.session_state.edges_state[index]
            attrs = edge_data.get("attributes", {})

            st.markdown(
                f"<p style='font-size:18px; font-weight:bold;'>Edge {index + 1} of {len(st.session_state.edges_state)}&nbsp;&nbsp;&nbsp;{src} → {tgt}</p>",
                unsafe_allow_html=True
            )

            # Get source node outputs
            source_node_attrs = dict(st.session_state.nodes_state).get(src, {})
            output_attrs = source_node_attrs.get("outputs", {})
            candidate_keys = list(output_attrs.keys())

            # Init session state
            if ("attr_rows" not in st.session_state or st.session_state.attr_rows is None or st.session_state.get("prev_edge_index") != index):
                st.session_state.attr_rows = [
                    {"key": k, "value": v, "custom": k not in candidate_keys}
                    for k, v in attrs.items()
                ]
                st.session_state.prev_edge_index = index

            st.markdown("##### Edit / Add Attributes")

            updated_rows = []
            for i, row in enumerate(st.session_state.attr_rows):
                col1, col2, col3 = st.columns([4, 4, 1])

                with col1:
                    used_keys = [
                        r["key"] for j, r in enumerate(st.session_state.attr_rows)
                        if j != i and not r.get("custom", False) and r["key"]
                    ]
                    available_keys = [k for k in candidate_keys if k not in used_keys]
                    options = available_keys + ["Custom Attribute"]

                    if row.get("custom", False):
                        key = st.text_input("Select Attribute", value=row.get("key", ""), key=f"custom_key_{i}_{index}")
                        row["key"] = key
                    else:
                        selected = st.selectbox(
                            "Select Attribute",
                            options,
                            index=options.index(row["key"]) if row["key"] in options else 0,
                            key=f"key_select_{i}_{index}"
                        )
                        if selected == "Custom Attribute":
                            row["custom"] = True
                            row["key"] = ""
                            row["value"] = ""  # ✅ 这行是关键：清空 value
                            key = ""
                            st.rerun()
                        else:
                            row["custom"] = False
                            row["key"] = selected
                            key = selected
                     

                with col2:
                    if row.get("custom", False):
                        val = st.text_input("Value", value=row.get("value", ""), key=f"val_{i}_{index}")
                        row["value"] = val
                    else:
                        auto_val = output_attrs.get(row["key"], "")
                        val = st.text_input("Value", value=auto_val, key=f"val_{i}_{index}")
                        row["value"] = val

                with col3:
                    if st.checkbox("🗑️ Delete", key=f"delete_{i}_{index}"):
                        continue

                updated_rows.append(row)

            st.session_state.attr_rows = updated_rows

            # Add Attribute row
            if st.button("➕ Add Attribute"):
                default_key = next((k for k in candidate_keys if k not in [r["key"] for r in st.session_state.attr_rows]), "")
                st.session_state.attr_rows.append({
                    "key": default_key,
                    "value": output_attrs.get(default_key, "") if default_key else "",
                    "custom": False if default_key else True
                })
                st.rerun()

            # Save Attributes
            if st.button("💾 Save"):
                new_attr_dict = {
                    row["key"]: row["value"]
                    for row in st.session_state.attr_rows
                    if row["key"]
                }
                new_edge_data = {"from": src, "to": tgt, "attributes": new_attr_dict}
                st.session_state.edges_state[index] = (src, tgt, new_edge_data)
                st.success("Attributes updated.")
                st.session_state.attr_rows = None  # Reset

            # Navigation
            col1, col2 = st.columns([8, 0.67])
            with col1:
                if st.button("Previous Edge") and index > 0:
                    st.session_state.edge_index -= 1
                    st.session_state.attr_rows = None
                    rerun()
            with col2:
                if st.button("Next Edge") and index < len(st.session_state.edges_state) - 1:
                    st.session_state.edge_index += 1
                    st.session_state.attr_rows = None
                    rerun()



    # Step 3: Finalize and Export YAML (in expander)
    reconstructed_nodes = [{name: attrs} for name, attrs in st.session_state.nodes_state]
    reconstructed_edges = [edge_dict for _, _, edge_dict in st.session_state.edges_state]

    new_yaml = yaml.dump({
        "nodes": reconstructed_nodes,
        "edges": reconstructed_edges
    }, sort_keys=False)

    with st.expander("Step 3: Finalize and Export YAML", expanded=False):
        st.markdown("Here is the final DAG YAML you can review before saving or submitting.")
        st.text_area("Final DAG YAML", new_yaml, height=300, key="final_yaml_preview")

    # Save YAML into session state (can be submitted later)
    col1, col2 = st.columns([8, 0.75])
    with col1:
        if st.button("Save Changes"):
            st.session_state.final_dag_yaml = new_yaml
            st.success("YAML saved.")

    with col2:
        if st.button("Submit DAG"):
            if new_yaml:
                st.session_state.workflow_running = True
                return new_yaml
            else:
                st.warning("No DAG YAML to submit.")

    # default return if no action
    return None



