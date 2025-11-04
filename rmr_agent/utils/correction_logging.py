import json
import yaml
from typing import Dict, List, Any, Tuple, Set
import copy


def get_component_key(component: Dict[str, Any]) -> str:
    """
    Generate a unique key for a component based on its name and file.
    This is used for comparing components.
    """
    name = component.get("name", "")
    file_name = component.get("file_name", "")
    return f"{name}:{file_name}"


def log_component_corrections(original_components: List[Dict[str, Any]],
                             verified_components: List[Dict[str, Any]]) -> Dict[str, Any]:
    """
    Compare original agent-identified components with human-verified components
    and log the differences.

    Args:
        original_components: List of component dictionaries from component_parsing step
        verified_components: List of component dictionaries after human verification

    Returns:
        Dictionary with structured data about:
        - Added components (not in original but in verified)
        - Deleted components (in original but not in verified)
        - Modified components (with specific properties changed)
        - Summary statistics
    """
    corrections = {
        "added": [],
        "deleted": [],
        "modified": [],
        "summary": {
            "total_original": len(original_components),
            "total_verified": len(verified_components),
            "added_count": 0,
            "deleted_count": 0,
            "modified_count": 0,
            "correction_ratio": 0.0
        }
    }

    # Create dictionaries with component key -> component data for easy lookup
    original_dict = {}
    for comp in original_components:
        # Handle component dict with nested structures (component_parsing output)
        if not isinstance(comp, dict):
            continue

        # Handle special case where the dict might have a file_name as key
        if len(comp.keys()) == 1 and isinstance(comp[list(comp.keys())[0]], dict):
            file_name = list(comp.keys())[0]
            for comp_name, comp_data in comp[file_name].items():
                # Add file_name to the component data
                comp_data = comp_data.copy() if comp_data else {}
                comp_data["name"] = comp_name
                comp_data["file_name"] = file_name
                key = get_component_key(comp_data)
                original_dict[key] = comp_data
        else:
            # Regular component dict (direct mapping)
            key = get_component_key(comp)
            original_dict[key] = comp

    verified_dict = {}
    for comp in verified_components:
        if not isinstance(comp, dict):
            continue
        key = get_component_key(comp)
        verified_dict[key] = comp

    # Find added components (in verified but not in original)
    for key, comp in verified_dict.items():
        if key not in original_dict:
            corrections["added"].append(comp)
            corrections["summary"]["added_count"] += 1

    # Find deleted components (in original but not in verified)
    for key, comp in original_dict.items():
        if key not in verified_dict:
            corrections["deleted"].append(comp)
            corrections["summary"]["deleted_count"] += 1

    # Find modified components (in both but with different properties)
    for key, verified_comp in verified_dict.items():
        if key in original_dict:
            original_comp = original_dict[key]
            changes = {}

            # Compare all properties in both components
            all_props = set(original_comp.keys()) | set(verified_comp.keys())

            for prop in all_props:
                original_value = original_comp.get(prop)
                verified_value = verified_comp.get(prop)

                # Skip comparing name and file_name as they're used for the key
                if prop in ["name", "file_name"]:
                    continue

                # Check if property exists in both and has different values
                if original_value != verified_value:
                    changes[prop] = {
                        "original": original_value,
                        "modified": verified_value
                    }

            # If any properties were changed, add to the modified list
            if changes:
                corrections["modified"].append({
                    "name": verified_comp.get("name", ""),
                    "file_name": verified_comp.get("file_name", ""),
                    "changed_properties": list(changes.keys()),
                    "changes": changes
                })
                corrections["summary"]["modified_count"] += 1

    # Calculate correction ratio (percentage of components that were modified in any way)
    total_corrections = (corrections["summary"]["added_count"] +
                         corrections["summary"]["deleted_count"] +
                         corrections["summary"]["modified_count"])

    total_components = max(corrections["summary"]["total_original"], 1)  # Avoid division by zero
    corrections["summary"]["correction_ratio"] = round(total_corrections / total_components * 100, 2)

    return corrections


def parse_dag_yaml(dag_yaml: str) -> Dict[str, Any]:
    """
    Parse a DAG YAML string into a dictionary.
    """
    try:
        return yaml.safe_load(dag_yaml) or {}
    except Exception as e:
        print(f"Error parsing DAG YAML: {e}")
        return {}


def extract_edges_from_dag(dag_data: Dict[str, Any]) -> List[Dict[str, Any]]:
    """
    Extract a standardized list of edges from DAG data.
    """
    edges = []
    if dag_data and "edges" in dag_data and isinstance(dag_data["edges"], list):
        for edge in dag_data["edges"]:
            if isinstance(edge, dict) and "from" in edge and "to" in edge:
                edges.append({
                    "from": edge["from"],
                    "to": edge["to"],
                    "attributes": {k: v for k, v in edge.items() if k not in ["from", "to"]}
                })
    return edges


def extract_nodes_from_dag(dag_data: Dict[str, Any]) -> Dict[str, Dict[str, Any]]:
    """
    Extract a standardized dictionary of nodes from DAG data.
    """
    nodes = {}
    if dag_data and "nodes" in dag_data and isinstance(dag_data["nodes"], list):
        for node_item in dag_data["nodes"]:
            if isinstance(node_item, dict) and len(node_item) == 1:
                node_name = list(node_item.keys())[0]
                node_details = node_item[node_name]
                if isinstance(node_details, dict):
                    nodes[node_name] = node_details
    return nodes


def get_edge_key(edge: Dict[str, Any]) -> str:
    """
    Generate a unique key for an edge based on from/to.
    """
    return f"{edge.get('from', '')}:{edge.get('to', '')}"


def log_dag_corrections(original_dag: str, verified_dag: str) -> Dict[str, Any]:
    """
    Compare original agent-generated DAG with human-verified DAG
    and log the differences.

    Args:
        original_dag: Original DAG YAML string
        verified_dag: Human-verified DAG YAML string

    Returns:
        Dictionary with structured data about:
        - Added edges (not in original but in verified)
        - Deleted edges (in original but not in verified)
        - Modified edge properties
        - Modified node attributes
        - Summary statistics
    """
    corrections = {
        "added_edges": [],
        "deleted_edges": [],
        "modified_edges": [],
        "modified_nodes": [],
        "summary": {
            "total_edges_original": 0,
            "total_edges_verified": 0,
            "total_nodes_original": 0,
            "total_nodes_verified": 0,
            "added_edge_count": 0,
            "deleted_edge_count": 0,
            "modified_edge_count": 0,
            "modified_node_count": 0,
            "correction_ratio": 0.0
        }
    }

    # Parse YAML strings to dictionaries
    original_dag_data = parse_dag_yaml(original_dag)
    verified_dag_data = parse_dag_yaml(verified_dag)

    # Extract edges and nodes
    original_edges = extract_edges_from_dag(original_dag_data)
    verified_edges = extract_edges_from_dag(verified_dag_data)

    original_nodes = extract_nodes_from_dag(original_dag_data)
    verified_nodes = extract_nodes_from_dag(verified_dag_data)

    # Update summary counts
    corrections["summary"]["total_edges_original"] = len(original_edges)
    corrections["summary"]["total_edges_verified"] = len(verified_edges)
    corrections["summary"]["total_nodes_original"] = len(original_nodes)
    corrections["summary"]["total_nodes_verified"] = len(verified_nodes)

    # Create dictionaries with edge key -> edge data for easy lookup
    original_edges_dict = {get_edge_key(edge): edge for edge in original_edges}
    verified_edges_dict = {get_edge_key(edge): edge for edge in verified_edges}

    # Find added edges (in verified but not in original)
    for key, edge in verified_edges_dict.items():
        if key not in original_edges_dict:
            corrections["added_edges"].append(edge)
            corrections["summary"]["added_edge_count"] += 1

    # Find deleted edges (in original but not in verified)
    for key, edge in original_edges_dict.items():
        if key not in verified_edges_dict:
            corrections["deleted_edges"].append(edge)
            corrections["summary"]["deleted_edge_count"] += 1

    # Find modified edges (in both but with different attributes)
    for key, verified_edge in verified_edges_dict.items():
        if key in original_edges_dict:
            original_edge = original_edges_dict[key]
            original_attrs = original_edge.get("attributes", {})
            verified_attrs = verified_edge.get("attributes", {})

            changes = {}
            # Compare all attributes
            all_attrs = set(original_attrs.keys()) | set(verified_attrs.keys())

            for attr in all_attrs:
                original_value = original_attrs.get(attr)
                verified_value = verified_attrs.get(attr)

                if original_value != verified_value:
                    changes[attr] = {
                        "original": original_value,
                        "modified": verified_value
                    }

            # If any attributes were changed, add to the modified list
            if changes:
                corrections["modified_edges"].append({
                    "from": verified_edge.get("from", ""),
                    "to": verified_edge.get("to", ""),
                    "changed_attributes": list(changes.keys()),
                    "changes": changes
                })
                corrections["summary"]["modified_edge_count"] += 1

    # Find modified nodes (in both but with different attributes)
    for node_name, verified_node in verified_nodes.items():
        if node_name in original_nodes:
            original_node = original_nodes[node_name]
            changes = {}

            # Compare all properties
            all_props = set(original_node.keys()) | set(verified_node.keys())

            for prop in all_props:
                original_value = original_node.get(prop)
                verified_value = verified_node.get(prop)

                if original_value != verified_value:
                    changes[prop] = {
                        "original": original_value,
                        "modified": verified_value
                    }

            # If any properties were changed, add to the modified list
            if changes:
                corrections["modified_nodes"].append({
                    "name": node_name,
                    "changed_properties": list(changes.keys()),
                    "changes": changes
                })
                corrections["summary"]["modified_node_count"] += 1

    # Calculate correction ratio (percentage of edges + nodes that were modified in any way)
    total_corrections = (
        corrections["summary"]["added_edge_count"] +
        corrections["summary"]["deleted_edge_count"] +
        corrections["summary"]["modified_edge_count"] +
        corrections["summary"]["modified_node_count"]
    )

    total_items = max(
        corrections["summary"]["total_edges_original"] +
        corrections["summary"]["total_nodes_original"],
        1  # Avoid division by zero
    )

    corrections["summary"]["correction_ratio"] = round(total_corrections / total_items * 100, 2)

    return corrections


def format_component_corrections_for_pr(corrections: Dict[str, Any]) -> str:
    """
    Format component corrections into a markdown string for the PR body.
    """
    md_parts = ["### ML Component Corrections\n"]

    summary = corrections.get("summary", {})
    md_parts.append(f"- **Original components:** {summary.get('total_original', 0)}")
    md_parts.append(f"- **Final components:** {summary.get('total_verified', 0)}")
    md_parts.append(f"- **Added:** {summary.get('added_count', 0)}")
    md_parts.append(f"- **Deleted:** {summary.get('deleted_count', 0)}")
    md_parts.append(f"- **Modified:** {summary.get('modified_count', 0)}")
    md_parts.append(f"- **Correction ratio:** {summary.get('correction_ratio', 0)}%")

    # Add details about modifications
    modified = corrections.get("modified", [])
    if modified:
        md_parts.append("\n**Modified Components:**")
        for mod in modified[:5]:  # Limit to 5 for brevity
            name = mod.get("name", "Unnamed")
            props = ", ".join(mod.get("changed_properties", []))
            md_parts.append(f"- `{name}`: Changed {props}")

        if len(modified) > 5:
            md_parts.append(f"- *(and {len(modified) - 5} more modified components)*")

    return "\n".join(md_parts)


def format_dag_corrections_for_pr(corrections: Dict[str, Any]) -> str:
    """
    Format DAG corrections into a markdown string for the PR body.
    """
    md_parts = ["### DAG Structure Corrections\n"]

    summary = corrections.get("summary", {})
    md_parts.append(f"- **Original edges:** {summary.get('total_edges_original', 0)}")
    md_parts.append(f"- **Final edges:** {summary.get('total_edges_verified', 0)}")
    md_parts.append(f"- **Added edges:** {summary.get('added_edge_count', 0)}")
    md_parts.append(f"- **Deleted edges:** {summary.get('deleted_edge_count', 0)}")
    md_parts.append(f"- **Modified edges:** {summary.get('modified_edge_count', 0)}")
    md_parts.append(f"- **Modified nodes:** {summary.get('modified_node_count', 0)}")
    md_parts.append(f"- **Correction ratio:** {summary.get('correction_ratio', 0)}%")

    # Add details about edge modifications
    modified_edges = corrections.get("modified_edges", [])
    if modified_edges:
        md_parts.append("\n**Modified Edges:**")
        for mod in modified_edges[:5]:  # Limit to 5 for brevity
            source = mod.get("from", "Unknown")
            target = mod.get("to", "Unknown")
            attrs = ", ".join(mod.get("changed_attributes", []))
            md_parts.append(f"- `{source}` → `{target}`: Changed {attrs}")

        if len(modified_edges) > 5:
            md_parts.append(f"- *(and {len(modified_edges) - 5} more modified edges)*")

    # Add details about node modifications
    modified_nodes = corrections.get("modified_nodes", [])
    if modified_nodes:
        md_parts.append("\n**Modified Nodes:**")
        for mod in modified_nodes[:5]:  # Limit to 5 for brevity
            name = mod.get("name", "Unnamed")
            props = ", ".join(mod.get("changed_properties", []))
            md_parts.append(f"- `{name}`: Changed {props}")

        if len(modified_nodes) > 5:
            md_parts.append(f"- *(and {len(modified_nodes) - 5} more modified nodes)*")

    return "\n".join(md_parts)