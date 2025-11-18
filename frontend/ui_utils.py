"""
UI Utilities for RMR Agent DAG Editor
This module provides utilities for displaying and editing DAG workflows in the Streamlit UI.
"""

import os
import json
import yaml
import re
import tempfile
from typing import Dict, List, Tuple, Any, Optional

from rmr_agent.workflow import CHECKPOINT_BASE_PATH
from pyvis.network import Network
import streamlit as st
from streamlit import rerun
from streamlit_mermaid import st_mermaid
import streamlit.components.v1 as components
from rmr_agent.utils.logging_config import setup_logger

# Set up module logger
logger = setup_logger(__name__)


# ============================================================================
# FILE PATH UTILITIES
# ============================================================================

def clean_file_path(file_path: str, repo_name: str, repos_base_dir: str = "rmr_agent/repos/") -> str:
    """
    Clean file path to show only relative path from repo root.
    
    Args:
        file_path: Full file path
        repo_name: Repository name
        repos_base_dir: Base directory for repos
    
    Returns:
        Cleaned relative file path
    """
    prefix = repos_base_dir + repo_name + "/"
    if file_path.startswith(prefix):
        cleaned = file_path[len(prefix):]
    else:
        cleaned = file_path
    # Convert .py back to .ipynb
    cleaned = cleaned.replace('.py', '.ipynb')
    return cleaned


def remove_line_numbers(code_lines: List[str]) -> List[str]:
    """Remove line numbers from code lines."""
    return [line.split('|')[-1] for line in code_lines]


def clean_line_range(line_range: str) -> str:
    """Clean and normalize line range string."""
    return line_range.lower().split('lines')[-1].strip()


# ============================================================================
# DATA LOADING FUNCTIONS
# ============================================================================

def get_components(repo_name: str, run_id: str) -> List[Dict]:
    """Load component parsing results from checkpoint."""
    try:
        file_path = os.path.join(CHECKPOINT_BASE_PATH, repo_name, run_id, 'component_parsing.json')
        with open(file_path, 'r') as file:
            content = json.load(file)
        return content['component_parsing']
    except FileNotFoundError:
        raise FileNotFoundError(f"Component parsing file not found for repo: {repo_name}, run_id: {run_id}")
    except json.JSONDecodeError as e:
        raise json.JSONDecodeError(f"Invalid JSON in component parsing file: {e.msg}", e.doc, e.pos)
    except IOError as e:
        raise IOError(f"Error reading component parsing file: {str(e)}")


def get_verified_components(repo_name: str, run_id: str) -> List[Dict]:
    """Get verified components from human verification step if available."""
    try:
        file_path = os.path.join(CHECKPOINT_BASE_PATH, repo_name, run_id, 'human_verification_of_components.json')
        with open(file_path, 'r') as file:
            content = json.load(file)
        return content.get('verified_components', [])
    except (FileNotFoundError, json.JSONDecodeError, IOError):
        # Fall back to original components
        return get_components(repo_name, run_id)


def get_component_details_from_verified(repo_name: str, run_id: str) -> Dict[str, Dict]:
    """
    Get component details including file names and line ranges.
    
    Returns:
        Dictionary mapping normalized component names to their details
    """
    try:
        file_path = os.path.join(CHECKPOINT_BASE_PATH, repo_name, run_id, 'human_verification_of_components.json')
        with open(file_path, 'r') as file:
            content = json.load(file)
        verified_components = content.get('verified_components', [])
    except (FileNotFoundError, json.JSONDecodeError, IOError) as e:
        logger.warning(f"Could not load verified components: {e}")
        try:
            verified_components = get_components(repo_name, run_id)
        except Exception as e2:
            logger.error(f"Could not load any components: {e2}")
            return {}
    
    component_details = {}
    
    for file_components_dict in verified_components:
        if isinstance(file_components_dict, dict):
            for comp_name, comp_data in file_components_dict.items():
                if isinstance(comp_data, dict):
                    file_name = comp_data.get("file_name", "unknown")
                    line_range = comp_data.get("line_range", "unknown")
                    cleaned_file = clean_file_path(file_name, repo_name)
                    normalized_name = normalize_node_name(comp_name)
                    
                    component_details[normalized_name] = {
                        "file": cleaned_file,
                        "line_range": line_range,
                        "full_path": file_name
                    }
    
    return component_details


def get_cleaned_code(repo_name: str, run_id: str) -> Dict[str, str]:
    """Load cleaned code from summarization step."""
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
        raise KeyError(f"Missing 'cleaned_code' key in summarize file")
    except IOError as e:
        raise IOError(f"Error reading summarize file: {str(e)}")


def get_dag_yaml(repo_name: str, run_id: str) -> str:
    """Load DAG YAML from checkpoint."""
    try:
        file_path = os.path.join(CHECKPOINT_BASE_PATH, repo_name, run_id, 'dag.yaml')
        with open(file_path, 'r') as file:
            dag_yaml_str = file.read()
        logger.info("Successfully loaded dag.yaml")
        return dag_yaml_str
    except FileNotFoundError:
        raise FileNotFoundError(f"DAG YAML file not found for repo: {repo_name}, run_id: {run_id}")
    except yaml.YAMLError as e:
        raise yaml.YAMLError(f"Invalid YAML in DAG file: {str(e)}")
    except IOError as e:
        raise IOError(f"Error reading DAG YAML file: {str(e)}")


def get_pr_url(repo_name: str, run_id: str) -> str:
    """Get PR URL from checkpoint."""
    try:
        file_path = os.path.join(CHECKPOINT_BASE_PATH, repo_name, run_id, 'create_pull_request.json')
        with open(file_path, 'r') as file:
            content = json.load(file)
        return content['pr_url']
    except FileNotFoundError:
        raise FileNotFoundError(f"PR URL file not found for repo: {repo_name}, run_id: {run_id}")
    except IOError as e:
        raise IOError(f"Error reading PR URL file: {str(e)}")


def get_pr_body(repo_name: str, run_id: str) -> str:
    """Get PR body content from checkpoint."""
    try:
        file_path = os.path.join(CHECKPOINT_BASE_PATH, repo_name, run_id, 'create_pr_body.json')
        with open(file_path, 'r') as file:
            content = json.load(file)
        return content['pr_body']
    except FileNotFoundError:
        raise FileNotFoundError(f"PR body file not found for repo: {repo_name}, run_id: {run_id}")
    except IOError as e:
        raise IOError(f"Error reading PR body file: {str(e)}")


# ============================================================================
# UI DISPLAY FUNCTIONS
# ============================================================================

def show_rmr_agent_results(repo_name: str, run_id: str) -> None:
    """Display RMR Agent workflow results including PR URL and body."""
    # Display PR URL
    pr_url = get_pr_url(repo_name, run_id)
    if pr_url:
        st.markdown(f"### Pull Request Created: [View PR]({pr_url})", unsafe_allow_html=True)
    else:
        st.error("Could not retrieve the PR URL.")

    # Load PR body
    pr_body = get_pr_body(repo_name, run_id)
    if not pr_body:
        st.warning("No PR body available to display.")
        return
    
    # Find and render Mermaid diagram
    mermaid_pattern = re.compile(r"```mermaid\n(.*?)\n```", re.DOTALL)
    match = mermaid_pattern.search(pr_body)

    if match:
        markdown_before = pr_body[:match.start()].strip()
        mermaid_code = match.group(1).strip()
        markdown_after = pr_body[match.end():].strip()

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
        st.markdown(pr_body, unsafe_allow_html=True)
        st.info("No Mermaid diagram found in the PR body.")


def get_default_line_range(selected_components: List, cleaned_code: Dict) -> str:
    """Get default line range for components."""
    if len(selected_components) == 1:
        return f"1-{len(cleaned_code)}"
    return "Specify line range here (e.g. 1-40)"


def get_steps_could_start_from(repo_name: str, run_id: str, all_steps: List[str]) -> List[str]:
    """Get list of steps that workflow could start from."""
    directory_path = os.path.join(CHECKPOINT_BASE_PATH, repo_name, run_id)
    if not os.path.isdir(directory_path):
        logger.warning(f"Directory does not exist: {directory_path}")
        return []
    
    # Get list of completed steps
    json_files = set()
    for filename in os.listdir(directory_path):
        if filename.endswith(".json"):
            step_name = os.path.splitext(filename)[0]
            json_files.add(step_name)

    # Find available steps
    available_steps = []
    for step in all_steps:
        available_steps.append(step)
        if step not in json_files:
            break
    
    # Format for display
    display_steps = []
    for i, step in enumerate(available_steps):
        display_step = f"{i + 1}. {step.replace('_', ' ').title()}"
        display_steps.append(display_step)
    
    return display_steps


# ============================================================================
# DAG PROCESSING FUNCTIONS
# ============================================================================

def normalize_node_name(name: str) -> str:
    """Normalize node names to handle variations in formatting."""
    if not name:
        return ""
    return " ".join(name.split()).strip()


def get_valid_node_names_from_components(repo_name: str, run_id: str) -> set:
    """Get set of valid node names from verified components."""
    try:
        component_details = get_component_details_from_verified(repo_name, run_id)
        return set(component_details.keys())
    except Exception as e:
        logger.error(f"Error getting valid node names: {e}")
        return set()

def parse_dag_edges_from_yaml(
    dag_yaml: str,
    repo_name: Optional[str] = None,
    run_id: Optional[str] = None,
    add_missing_from_components: bool = False  # Default to False
) -> Tuple[List, List]:
    """
    Parse DAG YAML and include component details for tooltips.
    
    Args:
        dag_yaml: YAML string
        repo_name: Repository name
        run_id: Run ID
        add_missing_from_components: Whether to add nodes from components that aren't in YAML
    
    Returns:
        Tuple of (edges, nodes)
    """
    data = yaml.safe_load(dag_yaml)
    if not isinstance(data, dict):
        raise ValueError("Parsed YAML is not a dictionary.")

    # Get component details if available
    component_details = {}
    if repo_name and run_id:
        try:
            component_details = get_component_details_from_verified(repo_name, run_id)
        except Exception as e:
            st.warning(f"Could not load component details: {e}")

    # Parse nodes from YAML
    raw_nodes = data.get("nodes", [])
    nodes = []
    node_names_in_dag = set()

    for item in raw_nodes:
        if isinstance(item, dict):
            for node_name, attrs in item.items():
                normalized_name = normalize_node_name(node_name)
                
                # Add component details if available (but only for nodes already in DAG)
                if normalized_name in component_details:
                    # Preserve existing component_details if already present
                    if 'component_details' not in attrs:
                        attrs['component_details'] = component_details[normalized_name]
                
                nodes.append((normalized_name, attrs))
                node_names_in_dag.add(normalized_name)

    # Only add missing nodes from components if explicitly requested
    # This should be False when loading a verified DAG
    if add_missing_from_components and component_details:
        for comp_name, details in component_details.items():
            if comp_name not in node_names_in_dag:
                attrs = {'component_details': details}
                nodes.append((comp_name, attrs))
                node_names_in_dag.add(comp_name)
                logger.info(f"Added missing node from components: {comp_name}")
    
    # Parse edges
    raw_edges = data.get("edges", [])
    edges = []
    invalid_edges = []

    for edge in raw_edges:
        if isinstance(edge, dict) and "from" in edge and "to" in edge:
            src = normalize_node_name(edge["from"])
            tgt = normalize_node_name(edge["to"])

            if src in node_names_in_dag and tgt in node_names_in_dag:
                edge["from"] = src
                edge["to"] = tgt
                edges.append((src, tgt, edge))
            else:
                invalid_edges.append((src, tgt))
                if src not in node_names_in_dag:
                    st.warning(f"⚠️ Edge source '{src}' not found in nodes")
                if tgt not in node_names_in_dag:
                    st.warning(f"⚠️ Edge target '{tgt}' not found in nodes")

    if invalid_edges:
        st.error(f"❌ {len(invalid_edges)} invalid edge(s) were filtered out")
    
    return edges, nodes
# ============================================================================
# DAG VISUALIZATION
# ============================================================================

def _get_node_file_info(node_attrs: Dict) -> Tuple[str, str]:
    """
    Extract file and line range info from node attributes.
    Handles both component_details and direct attributes.
    """
    # Try component_details first
    comp_details = node_attrs.get('component_details', {})
    file_name = comp_details.get('file', None)
    line_range = comp_details.get('line_range', None)
    
    # Fallback to direct attributes
    if not file_name and 'file_name' in node_attrs:
        raw_file_name = node_attrs.get('file_name', 'Unknown file')
        if 'rmr_agent/repos/' in raw_file_name:
            parts = raw_file_name.split('/')
            if len(parts) > 3:
                repo_name = parts[2]
                file_name = clean_file_path(raw_file_name, repo_name)
            else:
                file_name = raw_file_name
        else:
            file_name = raw_file_name
    
    if not line_range and 'line_range' in node_attrs:
        line_range = node_attrs.get('line_range', 'Unknown lines')
    
    # Set defaults
    file_name = file_name or 'Unknown file'
    line_range = line_range or 'Unknown lines'
    
    return file_name, line_range

def calculate_node_positions(edges: List, nodes: List) -> Dict[str, Tuple[float, float]]:
    """
    Calculate optimal positions for nodes using topological sorting.
    Returns a dict mapping node names to (x, y) positions.
    """
    # Build adjacency list and in-degree count
    node_names = [normalize_node_name(n[0] if isinstance(n, tuple) else n) for n in nodes]
    adj_list = {name: [] for name in node_names}
    in_degree = {name: 0 for name in node_names}
    
    # Process edges
    for edge_info in edges:
        if isinstance(edge_info, tuple) and len(edge_info) >= 2:
            src, tgt = normalize_node_name(edge_info[0]), normalize_node_name(edge_info[1])
            if src in adj_list and tgt in in_degree:
                adj_list[src].append(tgt)
                in_degree[tgt] += 1
    
    # Topological sort to determine layers
    layers = []
    current_layer = [n for n in node_names if in_degree[n] == 0]
    visited = set()
    
    while current_layer:
        layers.append(sorted(current_layer))  # Sort for consistent ordering
        next_layer = []
        for node in current_layer:
            visited.add(node)
            for neighbor in adj_list[node]:
                in_degree[neighbor] -= 1
                if in_degree[neighbor] == 0 and neighbor not in visited:
                    next_layer.append(neighbor)
        current_layer = next_layer
    
    # Add any remaining nodes (in case of cycles)
    remaining = [n for n in node_names if n not in visited]
    if remaining:
        layers.append(sorted(remaining))
    
    # Calculate positions with INCREASED SPACING
    positions = {}
    y_spacing = 150  # Increased vertical spacing between layers (was 150)
    x_spacing = 250  # Increased horizontal spacing between nodes (was 200)
    
    for layer_idx, layer in enumerate(layers):
        y_pos = layer_idx * y_spacing
        
        # Calculate x positions to center the layer
        layer_width = (len(layer) - 1) * x_spacing
        start_x = -layer_width / 2
        
        for node_idx, node_name in enumerate(layer):
            x_pos = start_x + node_idx * x_spacing
            positions[node_name] = (x_pos, y_pos)
    
    return positions
# Find the render_dag_graph function in ui_utils.py (around line 330)
# Replace the "Add edges" section with this code:

# Modified render_dag_graph with auto-fit view
# Modified render_dag_graph with better auto-fit
def render_dag_graph(edges: List, nodes: List) -> str:
    """
    Render DAG graph with file and line info in tooltips.
    
    Returns:
        Path to the generated HTML file
    """
    # Use larger canvas for better initial view
    net = Network(height="450px", width="100%", directed=True, notebook=False, cdn_resources='in_line')
    valid_nodes = set()
    
    # Calculate positions first
    positions = calculate_node_positions(edges, nodes)
    
    # Color palette for different files
    file_colors = {}
    color_palette = [
        "#87CEEB", "#98FB98", "#DDA0DD", "#F0E68C", "#B0E0E6",
        "#4ECDC4", "#95E77E", "#FFE4B5", "#D8BFD8", "#F0FFFF"
    ]
    color_index = 0
    
    # Track min/max positions for setting initial view
    min_x, max_x = float('inf'), float('-inf')
    min_y, max_y = float('inf'), float('-inf')
    
    # Add nodes with fixed positions
    for node in nodes:
        if isinstance(node, tuple):
            node_name = node[0]
            node_attrs = node[1] if len(node) > 1 else {}
        else:
            node_name = node
            node_attrs = {}
        
        node_name = normalize_node_name(node_name)
        
        if node_name:
            try:
                # Get file info
                file_name, line_range = _get_node_file_info(node_attrs)
                
                # Create tooltip
                tooltip = f"Component: {node_name}\nFile: {file_name}\nLines: {line_range}"
                
                # Assign color by file
                if file_name not in file_colors and file_name != 'Unknown file':
                    file_colors[file_name] = color_palette[color_index % len(color_palette)]
                    color_index += 1
                
                node_color = file_colors.get(file_name, "#F0F8FF")
                
                # Get position
                pos = positions.get(node_name, (0, 0))
                
                # Track bounds
                min_x = min(min_x, pos[0])
                max_x = max(max_x, pos[0])
                min_y = min(min_y, pos[1])
                max_y = max(max_y, pos[1])
                
                # Add node to network with fixed position
                net.add_node(
                    node_name,
                    label=node_name,
                    title=tooltip,
                    shape="box",
                    size=30,
                    font={"size": 14, "bold": True},
                    borderWidth=2,
                    x=pos[0],
                    y=pos[1],
                    physics=False,
                    margin=15,
                    color={
                        "background": node_color,
                        "border": "#2B7CE9",
                        "highlight": {
                            "background": "#E6F2FF",
                            "border": "#1A1A1A"
                        }
                    }
                )
                valid_nodes.add(node_name)
            except Exception as e:
                st.warning(f"Could not add node '{node_name}': {e}")
    
    # Process edges (keep your existing edge code)
    target_count = {}
    for edge_info in edges:
        if isinstance(edge_info, tuple) and len(edge_info) >= 2:
            src, tgt = edge_info[0], edge_info[1]
        else:
            src, tgt = edge_info, None
        
        if not tgt:
            continue
        
        tgt = normalize_node_name(tgt)
        target_count[tgt] = target_count.get(tgt, 0) + 1
    
    # Add edges with curve adjustments
    target_index = {}
    failed_edges = []
    
    for edge_info in edges:
        if isinstance(edge_info, tuple) and len(edge_info) >= 2:
            src, tgt = edge_info[0], edge_info[1]
        else:
            src, tgt = edge_info, None
        
        if not tgt:
            continue
        
        src = normalize_node_name(src)
        tgt = normalize_node_name(tgt)
        
        if src not in valid_nodes:
            failed_edges.append(f"{src} → {tgt} (source missing)")
            continue
        if tgt not in valid_nodes:
            failed_edges.append(f"{src} → {tgt} (target missing)")
            continue
        
        try:
            if tgt not in target_index:
                target_index[tgt] = 0
            target_index[tgt] += 1
            
            if target_count[tgt] > 1:
                edge_idx = target_index[tgt]
                
                if edge_idx == 1:
                    net.add_edge(src, tgt, smooth={"type": "curvedCW", "roundness": 0.2})
                elif edge_idx == 2:
                    net.add_edge(src, tgt, smooth={"type": "curvedCCW", "roundness": 0.2})
                elif edge_idx == 3:
                    net.add_edge(src, tgt, smooth={"type": "curvedCW", "roundness": 0.4})
                else:
                    if edge_idx % 2 == 0:
                        net.add_edge(src, tgt, smooth={"type": "curvedCCW", "roundness": min(0.6, 0.2 + edge_idx * 0.1)})
                    else:
                        net.add_edge(src, tgt, smooth={"type": "curvedCW", "roundness": min(0.6, 0.2 + edge_idx * 0.1)})
            else:
                net.add_edge(src, tgt)
                
        except Exception as e:
            failed_edges.append(f"{src} → {tgt} ({str(e)})")
    
    if failed_edges:
        with st.expander(f"⚠️ {len(failed_edges)} edge(s) could not be added", expanded=False):
            for failed in failed_edges:
                st.text(f"• {failed}")
    
    # Calculate appropriate scale for initial view
    if min_x != float('inf'):
        x_range = max_x - min_x + 400  # Add padding
        y_range = max_y - min_y + 400
        # Calculate scale to fit all nodes
        scale = min(0.7, 700 / max(x_range, y_range))
    else:
        scale = 0.5
    
    # Set options with initial scale and position
    net.set_options(f"""
    {{
        "physics": {{
            "enabled": false
        }},
        "edges": {{
            "arrows": {{
                "to": {{"enabled": true, "scaleFactor": 1}}
            }},
            "smooth": {{
                "enabled": true,
                "type": "cubicBezier"
            }},
            "color": {{"color": "#848484", "inherit": false}},
            "width": 2
        }},
        "interaction": {{
            "hover": true,
            "tooltipDelay": 100,
            "zoomView": true,
            "dragView": true,
            "navigationButtons": true,
            "keyboard": true
        }},
        "manipulation": {{
            "enabled": false
        }}
    }}
    """)
    
    # Generate HTML and modify it
    temp_path = tempfile.NamedTemporaryFile(suffix=".html", delete=False)
    net.save_graph(temp_path.name)
    
    # Read the HTML and add custom JavaScript
    with open(temp_path.name, 'r', encoding='utf-8') as f:
        html_content = f.read()
    
    # Add custom JavaScript for auto-fit
    custom_js = """
    <script type="text/javascript">
        // Wait for the network to be fully loaded
        var checkExist = setInterval(function() {
            if (typeof network !== 'undefined') {
                clearInterval(checkExist);
                
                // Fit all nodes with animation
                setTimeout(function() {
                    network.fit({
                        nodes: network.body.nodeIndices,
                        animation: {
                            duration: 1000,
                            easingFunction: "easeInOutQuad"
                        }
                    });
                }, 100);
                
                // Add a fit button for user convenience
                var fitButton = document.createElement('button');
                fitButton.innerHTML = 'Fit All';
                fitButton.style.position = 'absolute';
                fitButton.style.top = '10px';
                fitButton.style.right = '10px';
                fitButton.style.zIndex = '1000';
                fitButton.style.padding = '5px 10px';
                fitButton.style.backgroundColor = '#4CAF50';
                fitButton.style.color = 'white';
                fitButton.style.border = 'none';
                fitButton.style.borderRadius = '4px';
                fitButton.style.cursor = 'pointer';
                fitButton.onclick = function() {
                    network.fit({
                        animation: {
                            duration: 500,
                            easingFunction: "easeInOutQuad"
                        }
                    });
                };
                document.querySelector('#mynetwork').parentElement.appendChild(fitButton);
            }
        }, 100);
    </script>
    """
    
    # Insert the custom JavaScript before closing body tag
    html_content = html_content.replace('</body>', custom_js + '</body>')
    
    # Write modified HTML back
    with open(temp_path.name, 'w', encoding='utf-8') as f:
        f.write(html_content)
    
    return temp_path.name


# Also ensure calculate_node_positions has good spacing
def calculate_node_positions(edges: List, nodes: List) -> Dict[str, Tuple[float, float]]:
    """
    Calculate optimal positions for nodes using topological sorting.
    Returns a dict mapping node names to (x, y) positions.
    """
    # Build adjacency list and in-degree count
    node_names = [normalize_node_name(n[0] if isinstance(n, tuple) else n) for n in nodes]
    adj_list = {name: [] for name in node_names}
    in_degree = {name: 0 for name in node_names}
    
    # Process edges
    for edge_info in edges:
        if isinstance(edge_info, tuple) and len(edge_info) >= 2:
            src, tgt = normalize_node_name(edge_info[0]), normalize_node_name(edge_info[1])
            if src in adj_list and tgt in in_degree:
                adj_list[src].append(tgt)
                in_degree[tgt] += 1
    
    # Topological sort to determine layers
    layers = []
    current_layer = [n for n in node_names if in_degree[n] == 0]
    visited = set()
    
    while current_layer:
        layers.append(sorted(current_layer))
        next_layer = []
        for node in current_layer:
            visited.add(node)
            for neighbor in adj_list[node]:
                in_degree[neighbor] -= 1
                if in_degree[neighbor] == 0 and neighbor not in visited:
                    next_layer.append(neighbor)
        current_layer = next_layer
    
    # Add any remaining nodes
    remaining = [n for n in node_names if n not in visited]
    if remaining:
        layers.append(sorted(remaining))
    
    # Calculate positions with good spacing
    positions = {}
    y_spacing = 150  # Vertical spacing between layers
    x_spacing = 250  # Horizontal spacing between nodes
    
    for layer_idx, layer in enumerate(layers):
        y_pos = layer_idx * y_spacing
        
        # Calculate x positions to center the layer
        layer_width = (len(layer) - 1) * x_spacing
        start_x = -layer_width / 2
        
        for node_idx, node_name in enumerate(layer):
            x_pos = start_x + node_idx * x_spacing
            positions[node_name] = (x_pos, y_pos)
    
    return positions

def get_node_order(nodes: List) -> Dict[str, int]:
    """Create a mapping of node names to their order for sorting."""
    return {name: idx for idx, (name, _) in enumerate(nodes)}


def sort_edges_by_topology(edges: List, nodes: List) -> List:
    """Sort edges in a logical order based on node positions."""
    node_order = get_node_order(nodes)
    
    def edge_sort_key(edge):
        src, tgt, _ = edge
        src_order = node_order.get(src, float('inf'))
        tgt_order = node_order.get(tgt, float('inf'))
        return (src_order, tgt_order)
    
    return sorted(edges, key=edge_sort_key)


def find_edge_index(edges: List, src: str, tgt: str) -> int:
    """Find the index of an edge with given source and target."""
    for idx, edge in enumerate(edges):
        if edge[0] == src and edge[1] == tgt:
            return idx
    return -1


# ============================================================================
# MAIN DAG EDITOR
# ============================================================================

def dag_edge_editor(
    edited_dag_yaml: str, 
    repo_name: Optional[str] = None, 
    run_id: Optional[str] = None
) -> Optional[str]:
    """
    Main DAG editor interface.
    
    Returns:
        Updated DAG YAML string if submitted, None otherwise
    """
    st.subheader("Human Verification Of Dag")
    
    # Always try to load the most recent verified DAG if it exists
    if repo_name and run_id:
        try:
            # Check if we have a verified DAG from a previous session
            verified_dag_path = os.path.join(CHECKPOINT_BASE_PATH, repo_name, run_id, 'human_verification_of_dag.json')
            if os.path.exists(verified_dag_path):
                with open(verified_dag_path, 'r') as file:
                    content = json.load(file)
                    if 'verified_dag' in content:
                        edited_dag_yaml = content['verified_dag']
                        logger.info("Using previously verified DAG as source")
            else:
                # Try to use the dag.yaml file which should be up-to-date
                dag_yaml_path = os.path.join(CHECKPOINT_BASE_PATH, repo_name, run_id, 'dag.yaml')
                if os.path.exists(dag_yaml_path):
                    with open(dag_yaml_path, 'r') as file:
                        edited_dag_yaml = file.read()
                        logger.info("Using dag.yaml file as source")
        except Exception as e:
            logger.error(f"Could not load saved DAG: {e}")
    
    # Initialize session state only if not already initialized
    if "edges_state" not in st.session_state or "nodes_state" not in st.session_state:
        try:
            # Parse WITHOUT adding missing nodes from components
            edges, nodes = parse_dag_edges_from_yaml(
                edited_dag_yaml, 
                repo_name, 
                run_id,
                add_missing_from_components=False  # Don't add nodes not in the DAG
            )
            st.session_state.edges_state = edges.copy()
            st.session_state.nodes_state = nodes.copy()
        except Exception as e:
            st.error(f"Error parsing DAG YAML: {e}")
            st.text_area("Current YAML", edited_dag_yaml, height=300)
            return None
    
    # Initialize other session state variables
    if "edge_index" not in st.session_state:
        st.session_state.edge_index = 0
    if "attr_rows" not in st.session_state:
        st.session_state.attr_rows = None
    if "prev_edge_index" not in st.session_state:
        st.session_state.prev_edge_index = -1
    
    # Step 1: Structure Verification
    _render_structure_verification()
    
    # Step 2: Attribute Verification
    _render_attribute_verification()
    
    # Step 3: Finalize and Export
    return _render_finalize_section()

def _render_structure_verification() -> None:
    """Render DAG structure verification section."""
    with st.expander("Step 1: Verify and Edit DAG Structure", expanded=True):
        # Render DAG visualization
        try:
            html_path = render_dag_graph(
                [(e[0], e[1]) for e in st.session_state.edges_state],
                st.session_state.nodes_state
            )
            components.html(open(html_path, "r", encoding="utf-8").read(), height=450, scrolling=True)
        except Exception as e:
            st.error(f"Error rendering DAG: {e}")
        
        # === Node rename section ===
        st.markdown("##### Rename Node")
        col1, col2, col3 = st.columns([3, 3, 2])
        
        current_node_names = [name for name, _ in st.session_state.nodes_state]
        
        with col1:
            if current_node_names:
                old_name = st.selectbox(
                    "Select node to rename",
                    current_node_names,
                    key="node_to_rename"
                )
            else:
                st.info("No nodes available to rename")
                old_name = None
        
        with col2:
            new_name = st.text_input(
                "New name",
                key="new_node_name",
                placeholder="Enter new name for the node"
            )
        
        with col3:
            if st.button("🔄 Rename", disabled=(not old_name), use_container_width=True):
                if new_name and new_name.strip():
                    new_name = new_name.strip()
                    
                    if new_name == old_name:
                        st.warning("New name is the same as old name!")
                    elif new_name in current_node_names:
                        st.error(f"Node '{new_name}' already exists! Please choose a different name.")
                    else:
                        _rename_node_in_dag(old_name, new_name)
                        st.success(f"✅ Renamed '{old_name}' to '{new_name}'")
                        st.rerun()
                else:
                    st.warning("Please enter a valid new name")
        
        # Show rename history without using an expander (since we're already in one)
        if 'node_renames' in st.session_state and st.session_state.node_renames:
            st.markdown("##### 📝 Rename History")
            rename_history = ""
            for orig, renamed in st.session_state.node_renames.items():
                rename_history += f"• {orig} → {renamed}\n"
            st.text(rename_history)
        
        st.divider()  # Add separator
        
        # Add edge controls
        _render_add_edge_controls(current_node_names)
        
        # Remove edge controls
        _render_remove_edge_controls()

def _rename_node_in_dag(old_name: str, new_name: str) -> None:
    """
    Rename a node in the DAG, updating all references and tracking renames.

    Args:
        old_name: Current name of the node
        new_name: New name for the node
    """
    # Initialize rename tracking if not exists
    if 'node_renames' not in st.session_state:
        st.session_state.node_renames = {}
    
    # Track the rename (handle chain renames)
    # If old_name was itself a renamed node, track from the original
    original_name = old_name
    for orig, renamed in st.session_state.node_renames.items():
        if renamed == old_name:
            original_name = orig
            break
    
    st.session_state.node_renames[original_name] = new_name
    
    # 1. Update nodes_state
    updated_nodes = []
    for name, attrs in st.session_state.nodes_state:
        if name == old_name:
            updated_nodes.append((new_name, attrs))
        else:
            updated_nodes.append((name, attrs))
    st.session_state.nodes_state = updated_nodes

    # 2. Update edges_state
    updated_edges = []
    for src, tgt, edge_data in st.session_state.edges_state:
        if src == old_name:
            src = new_name
        if tgt == old_name:
            tgt = new_name
        edge_data["from"] = src
        edge_data["to"] = tgt
        updated_edges.append((src, tgt, edge_data))
    st.session_state.edges_state = updated_edges

    # 3. Reset attribute editing state if needed
    if st.session_state.attr_rows is not None:
        st.session_state.attr_rows = None
        st.session_state.prev_edge_index = -1
    
    print(f"Renamed node: '{old_name}' -> '{new_name}'")
    print(f"Current rename tracking: {st.session_state.node_renames}")



def _render_add_edge_controls(node_names: List[str]) -> None:
    """Render controls for adding edges."""
    st.markdown("##### Add a New Edge")
    col1, col2 = st.columns(2)
    
    # 使用传入的 node_names 而不是从外部获取
    with col1:
        src = st.selectbox("Source Node", node_names, key="src_add")
    with col2:
        tgt = st.selectbox("Target Node", node_names, key="tgt_add")
    
    if st.button("Add Edge"):
        existing_idx = find_edge_index(st.session_state.edges_state, src, tgt)
        if existing_idx != -1:
            st.warning(f"Edge {src} → {tgt} already exists at position {existing_idx + 1}.")
        else:
            new_edge = {"from": src, "to": tgt, "attributes": {}}
            st.session_state.edges_state.append((src, tgt, new_edge))
            
            st.session_state.edges_state = sort_edges_by_topology(
                st.session_state.edges_state, 
                st.session_state.nodes_state
            )
            
            new_idx = find_edge_index(st.session_state.edges_state, src, tgt)
            if new_idx != -1:
                st.session_state.edge_index = new_idx
                st.session_state.attr_rows = None
                st.session_state.prev_edge_index = -1
                st.success(f"Edge {src} → {tgt} added at position {new_idx + 1}.")
            else:
                st.error("Failed to find the newly added edge.")
            
            rerun()


def _render_remove_edge_controls() -> None:
    """Render controls for removing edges."""
    st.markdown("##### Remove an Edge")
    
    if st.session_state.edges_state:
        edge_options = [(i, e) for i, e in enumerate(st.session_state.edges_state)]
        selected_edge_with_idx = st.selectbox(
            "Select edge to remove",
            edge_options,
            format_func=lambda x: f"{x[1][0]} → {x[1][1]} (Position {x[0] + 1})",
            key="edge_to_remove"
        )
        
        if st.button("Remove Selected Edge"):
            idx_to_remove, edge_to_remove = selected_edge_with_idx
            st.session_state.edges_state.pop(idx_to_remove)
            
            if st.session_state.edge_index >= len(st.session_state.edges_state):
                st.session_state.edge_index = max(0, len(st.session_state.edges_state) - 1) if st.session_state.edges_state else 0
            elif st.session_state.edge_index > idx_to_remove:
                st.session_state.edge_index -= 1
            
            st.session_state.attr_rows = None
            st.session_state.prev_edge_index = -1
            
            st.success(f"Edge {edge_to_remove[0]} → {edge_to_remove[1]} removed.")
            rerun()
    else:
        st.info("No edges to remove")


def _render_attribute_verification() -> None:
    """Render edge attribute verification section."""
    with st.expander("Step 2: Verify Attributes of Each Edge", expanded=True):
        if not st.session_state.edges_state:
            st.info("No edges to review.")
            return
        
        if st.session_state.edge_index >= len(st.session_state.edges_state):
            st.session_state.edge_index = 0
        
        index = st.session_state.edge_index
        src, tgt, edge_data = st.session_state.edges_state[index]
        attrs = edge_data.get("attributes", {})
        
        # Display current edge
        st.markdown(
            f"<p style='font-size:18px; font-weight:bold;'>Edge {index + 1} of {len(st.session_state.edges_state)}&nbsp;&nbsp;&nbsp;{src} → {tgt}</p>",
            unsafe_allow_html=True
        )
        
        # Get source node outputs
        source_node_attrs = dict(st.session_state.nodes_state).get(src, {})
        output_attrs = source_node_attrs.get("outputs", {})
        candidate_keys = list(output_attrs.keys())
        
        # Initialize attribute rows
        if st.session_state.attr_rows is None or st.session_state.prev_edge_index != index:
            st.session_state.attr_rows = [
                {"key": k, "value": v, "custom": k not in candidate_keys}
                for k, v in attrs.items()
            ]
            st.session_state.prev_edge_index = index
        
        # Edit attributes
        _render_attribute_editor(candidate_keys, output_attrs, index)
        
        # Control buttons
        _render_attribute_controls(index, src, tgt)
        
        # Navigation
        _render_edge_navigation(index)


def _render_attribute_editor(candidate_keys: List[str], output_attrs: Dict, index: int) -> None:
    """Render attribute editing interface."""
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
                continue
        
        updated_rows.append(row)
    
    st.session_state.attr_rows = updated_rows
    
    # Add attribute button
    if st.button("➕ Add Attribute"):
        used_keys = [r["key"] for r in st.session_state.attr_rows if r["key"]]
        default_key = next((k for k in candidate_keys if k not in used_keys), "")
        
        st.session_state.attr_rows.append({
            "key": default_key,
            "value": output_attrs.get(default_key, "") if default_key else "",
            "custom": False if default_key else True
        })
        st.rerun()


def _render_attribute_controls(index: int, src: str, tgt: str) -> None:
    """Render save/reset controls for attributes."""
    col_save, col_reset = st.columns([1, 1])
    
    with col_save:
        if st.button("💾 Save Attributes"):
            new_attr_dict = {
                row["key"]: row["value"]
                for row in st.session_state.attr_rows
                if row["key"]
            }
            new_edge_data = {"from": src, "to": tgt, "attributes": new_attr_dict}
            st.session_state.edges_state[index] = (src, tgt, new_edge_data)
            st.success("Attributes saved.")
    
    with col_reset:
        if st.button("🔄 Reset Attributes"):
            st.session_state.attr_rows = None
            st.session_state.prev_edge_index = -1
            st.rerun()


def _render_edge_navigation(index: int) -> None:
    """Render navigation controls for edges."""
    st.markdown("---")
    col1, col2, col3 = st.columns([1, 2, 1])
    
    with col1:
        if st.button("⬅️ Previous Edge", disabled=(index == 0)):
            st.session_state.edge_index -= 1
            st.session_state.attr_rows = None
            rerun()
    
    with col2:
        st.markdown(
            f"<center>Edge {index + 1} of {len(st.session_state.edges_state)}</center>", 
            unsafe_allow_html=True
        )
    
    with col3:
        if st.button("Next Edge ➡️", disabled=(index >= len(st.session_state.edges_state) - 1)):
            st.session_state.edge_index += 1
            st.session_state.attr_rows = None
            rerun()


def _render_finalize_section() -> Optional[str]:
    """Render finalization section and handle submission."""
    
    # Clean up orphan nodes (nodes not connected to any edges)
    if st.checkbox("Remove unconnected nodes", value=False, help="Remove nodes that have no incoming or outgoing edges"):
        connected_nodes = set()
        for src, tgt, _ in st.session_state.edges_state:
            connected_nodes.add(src)
            connected_nodes.add(tgt)
        
        # Filter nodes to only keep connected ones
        filtered_nodes = [(name, attrs) for name, attrs in st.session_state.nodes_state if name in connected_nodes]
        
        removed_count = len(st.session_state.nodes_state) - len(filtered_nodes)
        if removed_count > 0:
            st.session_state.nodes_state = filtered_nodes
            st.info(f"Removed {removed_count} unconnected node(s)")
            st.rerun()
    
    # Debug information
    with st.expander("🔍 Debug: Check Current State", expanded=False):
        st.write("**Current nodes in session_state:**")
        for i, (name, attrs) in enumerate(st.session_state.nodes_state):
            st.write(f"{i+1}. {name}")
        
        st.write("\n**Current edges in session_state:**")
        for i, (src, tgt, _) in enumerate(st.session_state.edges_state):
            st.write(f"{i+1}. {src} → {tgt}")
    
    # Reconstruct YAML
    reconstructed_nodes = []
    for name, attrs in st.session_state.nodes_state:
        reconstructed_nodes.append({name: attrs})
    
    reconstructed_edges = []
    for src, tgt, edge_dict in st.session_state.edges_state:
        edge_dict["from"] = src
        edge_dict["to"] = tgt
        reconstructed_edges.append(edge_dict)
    
    new_yaml = yaml.dump({
        "nodes": reconstructed_nodes,
        "edges": reconstructed_edges
    }, sort_keys=False, default_flow_style=False)
    
    # Display YAML preview
    with st.expander("Step 3: Finalize and Export YAML", expanded=True):
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