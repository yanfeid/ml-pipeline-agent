import os
import json
import yaml
from rmr_agent.workflow import CHECKPOINT_BASE_PATH
from pyvis.network import Network
import streamlit as st
from streamlit import rerun
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

def render_dag_graph(edges, nodes):
    net = Network(height="450px", directed=True)
    for node in nodes:
        net.add_node(
            node,
            label=node,
            shape="box",  
            size=30,
            
            color={
                "background": "#ffffff",  
                "border": "#000000",      
                "highlight": {
                    "background": "#eeeeee",  
                    "border": "#333333"       
                }
            },
            font={
            "color": "#000000",
            "size": 35,
            "face": "Arial"
        }
        )
    for src, tgt in edges:
        net.add_edge(
            src,
            tgt,
            color="#444444",
            width=2,
            length=3,  
            arrows="to"
        )

    net.set_options("""
    {
      "layout": {
        "hierarchical": {
          "enabled": true,
          "direction": "UD",
          "sortMethod": "directed",
          "nodeSpacing": 300
        }
      },
      "physics": {
        "enabled": false
      },
      "edges": {
        "arrows": {
          "to": {
            "enabled": true
          }
        }
      }
    }
    """)


    temp_path = tempfile.NamedTemporaryFile(suffix=".html", delete=False)
    net.save_graph(temp_path.name)
    return temp_path.name

def dag_edge_editor(edited_dag_yaml):
    st.subheader("DAG Visualizer")
    edges, nodes = parse_dag_edges_from_yaml(edited_dag_yaml)

    # Load to session state if not already
    if "edges_state" not in st.session_state:
        st.session_state.edges_state = edges.copy()
    if "nodes_state" not in st.session_state:
        st.session_state.nodes_state = nodes.copy()

    node_names = [name for name, _ in st.session_state.nodes_state]

    # Render DAG
    html_path = render_dag_graph(
        [(e[0], e[1]) for e in st.session_state.edges_state],
        node_names
    )
    components.html(open(html_path, "r", encoding="utf-8").read(), height=450, scrolling=True)


    # --------- edit edges ---------
    if st.session_state.edges_state:
        st.markdown("### Edit Edge Attributes")
        edge_to_edit = st.selectbox(
            "Select edge to edit",
            st.session_state.edges_state,
            format_func=lambda e: f"{e[0]} -> {e[1]}",
            key="edit_edge_selector"
        )

        src_edit = edge_to_edit[0]
        tgt_edit = edge_to_edit[1]
        current_attrs = edge_to_edit[2].get("attributes", {})

        source_node_attrs = dict(st.session_state.nodes_state).get(src_edit, {})
        output_attrs = source_node_attrs.get("outputs", {})
        candidate_keys = list(output_attrs.keys())
        current_selected_keys = [k for k in current_attrs if k in candidate_keys]

        with st.expander("Edit Attributes"):
            selected_keys = st.multiselect(
                "Select output attributes",
                candidate_keys,
                default=current_selected_keys,
                key="edit_attr_select"
            )
            updated_attr_dict = {k: output_attrs[k] for k in selected_keys}

            st.markdown("---")
            st.markdown("Edit / Add custom attribute")
            custom_key = st.text_input("Custom Attribute Key", key="edit_custom_key")
            custom_val = st.text_input("Custom Attribute Value", key="edit_custom_val")
            if custom_key and custom_val:
                updated_attr_dict[custom_key] = custom_val

        if st.button("Save Attribute Changes"):
            st.session_state.edges_state.remove(edge_to_edit)
            new_edge = {"from": src_edit, "to": tgt_edit, "attributes": updated_attr_dict}
            st.session_state.edges_state.append((src_edit, tgt_edit, new_edge))
            st.success("Edge updated.")
            rerun()

    # Modify edges
    st.markdown("### Add Edge")
    col1, col2 = st.columns(2)
    with col1:
        src = st.selectbox("Source Node", node_names, key="src_node")
    with col2:
        tgt = st.selectbox("Target Node", node_names, key="tgt_node")

    # --------- Edge Attribute UI ---------
    with st.expander("Optional: Add Edge Attributes"):
    
        source_node_attrs = dict(st.session_state.nodes_state).get(src, {})
        output_attrs = source_node_attrs.get("outputs", {})

        candidate_keys = list(output_attrs.keys())
        selected_keys = st.multiselect("Select output attributes to attach", candidate_keys)

        attr_dict = {key: output_attrs[key] for key in selected_keys}
        st.markdown("---")
        st.markdown("Add custom attribute (optional)")
        custom_key = st.text_input("Custom Attribute Key", key="custom_attr_key")
        custom_val = st.text_input("Custom Attribute Value", key="custom_attr_val")

        if custom_key and custom_val:
            attr_dict[custom_key] = custom_val

    # --------- add edge ---------
    if st.button("Add Edge"):
        try:
            new_edge = {"from": src, "to": tgt, "attributes": attr_dict}
            st.session_state.edges_state.append((src, tgt, new_edge))
            st.success("Edge added.")
            rerun()
        except Exception as e:
            st.error(f"Failed to add edge: {e}")


    # ---------remove edge ---------
    if st.session_state.edges_state:
        st.markdown("### Remove Edge")
        edge_to_remove = st.selectbox(
            "Select edge to remove",
            st.session_state.edges_state,
            format_func=lambda e: f"{e[0]} -> {e[1]}",
            key="remove_edge_selector"
        )
        if st.button("Remove Selected Edge"):
            st.session_state.edges_state.remove(edge_to_remove)
            st.success("Edge removed.")
            rerun()

    # Reconstruct YAML
    reconstructed_nodes = [{name: attrs} for name, attrs in st.session_state.nodes_state]
    reconstructed_edges = [edge_dict for _, _, edge_dict in st.session_state.edges_state]

    new_yaml = yaml.dump({
        "nodes": reconstructed_nodes,
        "edges": reconstructed_edges
    }, sort_keys=False)

    # st.markdown("### Preview Updated YAML")
    # st.text_area("DAG YAML", new_yaml, height=300, key="updated_yaml_preview")
    st.markdown("---")
    st.markdown("Use the buttons below to **save your changes locally** or **submit the verified DAG** to the system.")

    if st.button("Save Changes"):
        return new_yaml

    return None

