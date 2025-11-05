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

def get_verified_components(repo_name, run_id):
    """Get the verified components from human verification step if available"""
    try:
        file_path = os.path.join(CHECKPOINT_BASE_PATH, repo_name, run_id, 'human_verification_of_components.json')
        with open(file_path, 'r') as file:
            content = json.load(file)
        return content.get('verified_components', [])
    except (FileNotFoundError, json.JSONDecodeError, IOError):
        # If verified components don't exist, fall back to original components
        return get_components(repo_name, run_id)

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
        display_step = f"{i + 1}. {step.replace('_', ' ').title()}"
        display_available_steps.append(display_step)

    
    return display_available_steps


# === for dag verification ===
def normalize_node_name(name):
    """Normalize node names to handle variations in formatting"""
    if not name:
        return ""
    # Remove extra spaces and standardize case
    return " ".join(name.split()).strip()

def get_valid_node_names_from_components(repo_name, run_id):
    """Get valid node names from verified components"""
    components = get_verified_components(repo_name, run_id)
    valid_names = set()
    
    for comp in components:
        # Try different possible name fields
        name = comp.get("name") or comp.get("id") or comp.get("component_name")
        if name:
            valid_names.add(normalize_node_name(name))
    
    return valid_names

# === Parsing Function ===
def parse_dag_edges_from_yaml(dag_yaml, repo_name=None, run_id=None):
    """Parse DAG YAML and validate against actual components"""
    data = yaml.safe_load(dag_yaml)
    if not isinstance(data, dict):
        raise ValueError("Parsed YAML is not a dictionary.")
    
    # Get valid component names if repo_name and run_id are provided
    valid_component_names = set()
    if repo_name and run_id:
        try:
            valid_component_names = get_valid_node_names_from_components(repo_name, run_id)
        except Exception as e:
            st.warning(f"Could not load verified components: {e}")
    
    # Parse nodes
    raw_nodes = data.get("nodes", [])
    nodes = []
    node_names_in_dag = set()
    
    for item in raw_nodes:
        if isinstance(item, dict):
            for node_name, attrs in item.items():
                normalized_name = normalize_node_name(node_name)
                nodes.append((normalized_name, attrs))
                node_names_in_dag.add(normalized_name)
    
    # If we have valid component names, reconcile with DAG nodes
    if valid_component_names:
        # Find nodes that are in components but not in DAG
        missing_in_dag = valid_component_names - node_names_in_dag
        if missing_in_dag:
            st.info(f"ℹ️ Components not in DAG: {', '.join(missing_in_dag)}")
            # Add missing nodes to DAG
            for missing_node in missing_in_dag:
                nodes.append((missing_node, {}))
                node_names_in_dag.add(missing_node)
        
        # Find nodes that are in DAG but not in components  
        extra_in_dag = node_names_in_dag - valid_component_names
        if extra_in_dag:
            st.warning(f"⚠️ DAG nodes not in components: {', '.join(extra_in_dag)}")
    
    # Parse edges and validate
    raw_edges = data.get("edges", [])
    edges = []
    invalid_edges = []
    
    for edge in raw_edges:
        if isinstance(edge, dict) and "from" in edge and "to" in edge:
            src = normalize_node_name(edge["from"])
            tgt = normalize_node_name(edge["to"])
            
            # Check if both nodes exist
            src_valid = src in node_names_in_dag or src in valid_component_names
            tgt_valid = tgt in node_names_in_dag or tgt in valid_component_names
            
            if src_valid and tgt_valid:
                # Update edge with normalized names
                edge["from"] = src
                edge["to"] = tgt
                edges.append((src, tgt, edge))
            else:
                invalid_edges.append((src, tgt))
                if not src_valid:
                    st.warning(f"⚠️ Edge source '{src}' not found in nodes")
                if not tgt_valid:
                    st.warning(f"⚠️ Edge target '{tgt}' not found in nodes")
    
    if invalid_edges:
        st.error(f"❌ {len(invalid_edges)} invalid edge(s) were filtered out")
    
    return edges, nodes

# === DAG Renderer ===
def render_dag_graph(edges, nodes):
    """Render DAG graph with robust error handling"""
    net = Network(height="450px", directed=True)
    
    # Create a set of valid nodes for validation
    valid_nodes = set()
    
    # Add all nodes first
    for node in nodes:
        # Handle both string nodes and (name, attrs) tuples
        if isinstance(node, tuple):
            node_name = node[0]
        else:
            node_name = node
            
        node_name = normalize_node_name(node_name)
        
        if node_name:  # Only add non-empty nodes
            try:
                net.add_node(
                    node_name,
                    label=node_name,
                    shape="box",
                    size=20,
                    font={"size": 18},
                    borderWidth=2,
                )
                valid_nodes.add(node_name)
            except Exception as e:
                st.warning(f"Could not add node '{node_name}': {e}")
    
    # Track edge addition failures
    failed_edges = []
    
    # Add edges with validation
    for edge_info in edges:
        # Handle both (src, tgt) tuples and more complex structures
        if isinstance(edge_info, tuple) and len(edge_info) >= 2:
            src, tgt = edge_info[0], edge_info[1]
        else:
            src, tgt = edge_info, None
            
        if not tgt:
            continue
            
        src = normalize_node_name(src)
        tgt = normalize_node_name(tgt)
        
        # Validate before adding
        if src not in valid_nodes:
            failed_edges.append(f"{src} → {tgt} (source missing)")
            continue
        if tgt not in valid_nodes:
            failed_edges.append(f"{src} → {tgt} (target missing)")
            continue
            
        try:
            net.add_edge(src, tgt)
        except Exception as e:
            failed_edges.append(f"{src} → {tgt} ({str(e)})")
    
    # Report failures if any
    if failed_edges:
        with st.expander(f"⚠️ {len(failed_edges)} edge(s) could not be added", expanded=False):
            for failed in failed_edges:
                st.text(f"• {failed}")
    
    # Set network options
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

# === New sorting functions ===
def get_node_order(nodes):
    """Create a mapping of node names to their order for sorting"""
    return {name: idx for idx, (name, _) in enumerate(nodes)}

def sort_edges_by_topology(edges, nodes):
    """Sort edges in a more logical order based on node positions"""
    node_order = get_node_order(nodes)
    
    def edge_sort_key(edge):
        src, tgt, _ = edge
        # Sort by source node position first, then by target node position
        src_order = node_order.get(src, float('inf'))
        tgt_order = node_order.get(tgt, float('inf'))
        return (src_order, tgt_order)
    
    return sorted(edges, key=edge_sort_key)

def find_edge_index(edges, src, tgt):
    """Find the index of an edge with given source and target"""
    for idx, edge in enumerate(edges):
        if edge[0] == src and edge[1] == tgt:
            return idx
    return -1

# === Main DAG Editor App ===
def dag_edge_editor(edited_dag_yaml, repo_name=None, run_id=None):
    st.subheader("Human Verification Of Dag")
    
    # Step 0: Parse with validation
    try:
        edges, nodes = parse_dag_edges_from_yaml(edited_dag_yaml, repo_name, run_id)
    except Exception as e:
        st.error(f"Error parsing DAG YAML: {e}")
        st.text_area("Current YAML", edited_dag_yaml, height=300)
        return None
    
    node_names = [name for name, _ in nodes]
    
    # Initialize session state
    if "edges_state" not in st.session_state:
        st.session_state.edges_state = edges.copy()
    if "nodes_state" not in st.session_state:
        st.session_state.nodes_state = nodes.copy()
    if "edge_index" not in st.session_state:
        st.session_state.edge_index = 0
    if "attr_rows" not in st.session_state:
        st.session_state.attr_rows = None
    if "prev_edge_index" not in st.session_state:
        st.session_state.prev_edge_index = -1
    
    # === Step 1: Structure Verification ===
    with st.expander("Step 1: Verify and Edit DAG Structure", expanded=True):
        try:
            html_path = render_dag_graph(
                [(e[0], e[1]) for e in st.session_state.edges_state],
                node_names
            )
            components.html(open(html_path, "r", encoding="utf-8").read(), height=450, scrolling=True)
        except Exception as e:
            st.error(f"Error rendering DAG: {e}")
        
        st.markdown("##### Add a New Edge")
        col1, col2 = st.columns(2)
        with col1:
            src = st.selectbox("Source Node", node_names, key="src_add")
        with col2:
            tgt = st.selectbox("Target Node", node_names, key="tgt_add")
        
        if st.button("Add Edge"):
            # Check if edge already exists
            existing_idx = find_edge_index(st.session_state.edges_state, src, tgt)
            if existing_idx != -1:
                st.warning(f"Edge {src} → {tgt} already exists at position {existing_idx + 1}.")
            else:
                new_edge = {"from": src, "to": tgt, "attributes": {}}
                st.session_state.edges_state.append((src, tgt, new_edge))
                
                # Sort edges to maintain logical order
                st.session_state.edges_state = sort_edges_by_topology(
                    st.session_state.edges_state, 
                    st.session_state.nodes_state
                )
                
                # Find the index of the newly added edge
                new_idx = find_edge_index(st.session_state.edges_state, src, tgt)
                if new_idx != -1:
                    st.session_state.edge_index = new_idx
                    # Reset attribute rows for the new edge
                    st.session_state.attr_rows = None
                    st.session_state.prev_edge_index = -1
                    st.success(f"Edge {src} → {tgt} added at position {new_idx + 1}.")
                else:
                    st.error("Failed to find the newly added edge.")
                
                rerun()
        
        st.markdown("##### Remove an Edge")
        if st.session_state.edges_state:
            # Create options with index for uniqueness
            edge_options = [(i, e) for i, e in enumerate(st.session_state.edges_state)]
            selected_edge_with_idx = st.selectbox(
                "Select edge to remove",
                edge_options,
                format_func=lambda x: f"{x[1][0]} → {x[1][1]} (Position {x[0] + 1})",
                key="edge_to_remove"
            )
            
            if st.button("Remove Selected Edge"):
                idx_to_remove, edge_to_remove = selected_edge_with_idx
                
                # Remove the edge
                st.session_state.edges_state.pop(idx_to_remove)
                
                # Adjust edge_index if necessary
                if st.session_state.edge_index >= len(st.session_state.edges_state):
                    st.session_state.edge_index = max(0, len(st.session_state.edges_state) - 1) if st.session_state.edges_state else 0
                elif st.session_state.edge_index > idx_to_remove:
                    st.session_state.edge_index -= 1
                
                # Reset attribute rows
                st.session_state.attr_rows = None
                st.session_state.prev_edge_index = -1
                
                st.success(f"Edge {edge_to_remove[0]} → {edge_to_remove[1]} removed.")
                rerun()
        else:
            st.info("No edges to remove")
    
    # === Step 2: Attribute Verification ===
    with st.expander("Step 2: Verify Attributes of Each Edge", expanded=True):
        if not st.session_state.edges_state:
            st.info("No edges to review.")
        else:
            # Validate and fix edge_index
            if st.session_state.edge_index >= len(st.session_state.edges_state):
                st.session_state.edge_index = 0
            
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
            
            # Initialize or reset attr_rows when edge changes
            if (st.session_state.attr_rows is None or 
                st.session_state.prev_edge_index != index):
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
                        key = st.text_input("Attribute Key", value=row.get("key", ""), key=f"custom_key_{i}_{index}")
                        row["key"] = key
                    else:
                        # Ensure the current key is in options or default to first option
                        current_key = row.get("key", "")
                        if current_key and current_key in options:
                            default_idx = options.index(current_key)
                        elif options:
                            default_idx = 0
                        else:
                            default_idx = None
                            
                        if options and default_idx is not None:
                            selected = st.selectbox(
                                "Select Attribute",
                                options,
                                index=default_idx,
                                key=f"key_select_{i}_{index}"
                            )
                            if selected == "Custom Attribute":
                                row["custom"] = True
                                row["key"] = ""
                                row["value"] = ""
                                st.rerun()
                            else:
                                row["custom"] = False
                                row["key"] = selected
                        else:
                            st.info("No available attributes")
                            continue
                
                with col2:
                    if row.get("custom", False):
                        val = st.text_input("Value", value=row.get("value", ""), key=f"val_{i}_{index}")
                        row["value"] = val
                    else:
                        auto_val = output_attrs.get(row["key"], row.get("value", ""))
                        val = st.text_input("Value", value=auto_val, key=f"val_{i}_{index}")
                        row["value"] = val
                
                with col3:
                    if st.button("🗑️", key=f"delete_{i}_{index}"):
                        continue  # Skip this row, effectively deleting it
                
                updated_rows.append(row)
            
            st.session_state.attr_rows = updated_rows
            
            # Add Attribute row
            if st.button("➕ Add Attribute"):
                # Find a default key that's not already used
                used_keys = [r["key"] for r in st.session_state.attr_rows if r["key"]]
                default_key = next((k for k in candidate_keys if k not in used_keys), "")
                
                st.session_state.attr_rows.append({
                    "key": default_key,
                    "value": output_attrs.get(default_key, "") if default_key else "",
                    "custom": False if default_key else True
                })
                st.rerun()
            
            # Save Attributes
            col_save, col_reset = st.columns([1, 1])
            with col_save:
                if st.button("💾 Save Attributes"):
                    new_attr_dict = {
                        row["key"]: row["value"]
                        for row in st.session_state.attr_rows
                        if row["key"]  # Only include non-empty keys
                    }
                    new_edge_data = {"from": src, "to": tgt, "attributes": new_attr_dict}
                    st.session_state.edges_state[index] = (src, tgt, new_edge_data)
                    st.success("Attributes saved.")
                    # Don't reset attr_rows here to keep the state
            
            with col_reset:
                if st.button("🔄 Reset Attributes"):
                    st.session_state.attr_rows = None
                    st.session_state.prev_edge_index = -1
                    st.rerun()
            
            # Navigation
            st.markdown("---")
            col1, col2, col3 = st.columns([1, 2, 1])
            with col1:
                if st.button("⬅️ Previous Edge", disabled=(index == 0)):
                    st.session_state.edge_index -= 1
                    st.session_state.attr_rows = None
                    rerun()
            with col2:
                st.markdown(f"<center>Edge {index + 1} of {len(st.session_state.edges_state)}</center>", unsafe_allow_html=True)
            with col3:
                if st.button("Next Edge ➡️", disabled=(index >= len(st.session_state.edges_state) - 1)):
                    st.session_state.edge_index += 1
                    st.session_state.attr_rows = None
                    rerun()
    
    # Step 3: Finalize and Export YAML
    reconstructed_nodes = [{name: attrs} for name, attrs in st.session_state.nodes_state]
    reconstructed_edges = [edge_dict for _, _, edge_dict in st.session_state.edges_state]
    
    new_yaml = yaml.dump({
        "nodes": reconstructed_nodes,
        "edges": reconstructed_edges
    }, sort_keys=False, default_flow_style=False)
    
    with st.expander("Step 3: Finalize and Export YAML", expanded=False):
        st.markdown("Here is the final DAG YAML you can review before saving or submitting.")
        st.text_area("Final DAG YAML", new_yaml, height=300, key="final_yaml_preview")
    
    # Save and Submit buttons
    col1, col2 = st.columns([8, 1])
    with col1:
        if st.button("💾 Save DAG Changes", type="primary"):
            st.session_state.final_dag_yaml = new_yaml
            st.success("DAG YAML saved to session.")
    
    with col2:
        if st.button("✅ Submit DAG", type="primary"):
            if new_yaml:
                st.session_state.workflow_running = True
                return new_yaml
            else:
                st.warning("No DAG YAML to submit.")
    
    return None