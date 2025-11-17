import json
import yaml
from typing import Dict, List, Any, Tuple, Set
import copy
from rmr_agent.utils.logging_config import setup_logger

# Set up module logger
logger = setup_logger(__name__)


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
        logger.error(f"Error parsing DAG YAML: {e}")
        return {}


def extract_edges_from_dag(dag_data: Dict[str, Any]) -> List[Dict[str, Any]]:
    """
    Extract a standardized list of edges from DAG data.
    """
    edges = []
    if dag_data and "edges" in dag_data and isinstance(dag_data["edges"], list):
        for edge in dag_data["edges"]:
            if isinstance(edge, dict) and "from" in edge and "to" in edge:
                # Extract attributes (everything except 'from' and 'to')
                attributes = edge.get("attributes", {})
                # If no explicit 'attributes' key, collect all other keys as attributes
                if not attributes:
                    attributes = {k: v for k, v in edge.items() if k not in ["from", "to"]}
                    
                edges.append({
                    "from": edge["from"].strip() if isinstance(edge["from"], str) else edge["from"],
                    "to": edge["to"].strip() if isinstance(edge["to"], str) else edge["to"],
                    "attributes": attributes
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
                    # Normalize node name
                    normalized_name = node_name.strip() if isinstance(node_name, str) else node_name
                    nodes[normalized_name] = node_details
    return nodes


def get_edge_key(edge: Dict[str, Any]) -> str:
    """
    Generate a unique key for an edge based on from/to.
    Ensures consistent formatting.
    """
    from_node = edge.get("from", "")
    to_node = edge.get("to", "")
    
    # Normalize node names (remove extra spaces, ensure consistent format)
    if isinstance(from_node, str):
        from_node = " ".join(from_node.split()).strip()
    if isinstance(to_node, str):
        to_node = " ".join(to_node.split()).strip()
    
    return f"{from_node}:{to_node}"


def normalize_value(val: Any) -> Any:
    """
    Normalize a value for comparison.
    Treats empty containers and empty strings as None.
    """
    if val == {} or val == [] or val == '' or val is None:
        return None
    # Also normalize string 'None' to actual None
    if isinstance(val, str) and val.lower() == 'none':
        return None
    return val


def are_dicts_semantically_equivalent(dict1: Dict, dict2: Dict) -> bool:
    """
    Check if two dictionaries are semantically equivalent,
    ignoring system-generated naming variations.
    
    System often auto-corrects attribute names, e.g.:
    - 'age_labels' → 'age_bin_labels' 
    - 'model_path' → 'model_artifact_path'
    - 'trained_model_path' → 'model_artifact_path'
    
    These should NOT be counted as human modifications.
    """
    # If exact match, they're equivalent
    if dict1 == dict2:
        return True
    
    # Build a mapping of all keys to their normalized forms
    def normalize_key(key: str) -> str:
        """Normalize a key to its canonical form."""
        # Define equivalence groups (all map to the first item)
        equivalence_groups = [
            ['age_labels', 'age_bin_labels', 'age_label', 'age_bin_label'],
            ['model_path', 'model_artifact_path', 'trained_model_path', 'model_file_path'],
            ['scaler_path', 'scaler_save_path', 'scaler_file_path'],
            ['data_path', 'data_file_path', 'input_data_path'],
            ['output_path', 'output_file_path', 'result_path'],
        ]
        
        key_lower = key.lower()
        for group in equivalence_groups:
            if key_lower in [k.lower() for k in group]:
                return group[0]  # Return canonical form
        return key  # Return original if no match
    
    # Normalize both dictionaries
    norm_dict1 = {normalize_key(k): v for k, v in dict1.items()}
    norm_dict2 = {normalize_key(k): v for k, v in dict2.items()}
    
    # If normalized versions match, they're equivalent
    return norm_dict1 == norm_dict2


def are_values_equivalent(val1: Any, val2: Any, key: str = None) -> bool:
    """
    Check if two values are equivalent for DAG comparison purposes.
    Ignores system-generated variations that are not human modifications.
    
    Args:
        val1: First value
        val2: Second value
        key: Optional key name for special handling (e.g., 'inputs', 'outputs')
    
    Returns:
        True if values should be considered equivalent (no human modification)
    """
    # Normalize both values
    norm_val1 = normalize_value(val1)
    norm_val2 = normalize_value(val2)
    
    # For inputs/outputs, special handling
    if key in ['inputs', 'outputs']:
        # Treat None and {} as equivalent
        if (norm_val1 is None or norm_val1 == {}) and (norm_val2 is None or norm_val2 == {}):
            return True
            
        # If both are dicts, check semantic equivalence
        if isinstance(norm_val1, dict) and isinstance(norm_val2, dict):
            return are_dicts_semantically_equivalent(norm_val1, norm_val2)
    
    return norm_val1 == norm_val2


def debug_dag_differences(original_dag: str, verified_dag: str) -> None:
    """
    Debug function to print the exact differences between original and verified DAG.
    This will help identify why changes are being detected when none were made.
    """
    logger.debug("\n" + "="*80)
    logger.debug("DAG DIFFERENCES DEBUG REPORT")
    logger.debug("="*80)
    
    # Parse both DAGs
    orig_data = parse_dag_yaml(original_dag)
    ver_data = parse_dag_yaml(verified_dag)
    
    # Extract nodes
    orig_nodes = extract_nodes_from_dag(orig_data)
    ver_nodes = extract_nodes_from_dag(ver_data)
    
    # Check Feature Engineering specifically
    if "Feature Engineering" in orig_nodes and "Feature Engineering" in ver_nodes:
        logger.debug("\n🔍 FEATURE ENGINEERING NODE COMPARISON:")
        logger.debug("-" * 40)
        
        orig_fe = orig_nodes["Feature Engineering"]
        ver_fe = ver_nodes["Feature Engineering"]
        
        # Compare all attributes
        all_keys = set(orig_fe.keys()) | set(ver_fe.keys())
        
        for key in sorted(all_keys):
            orig_val = orig_fe.get(key)
            ver_val = ver_fe.get(key)
            
            if key == "inputs":
                logger.debug(f"\n📌 INPUTS comparison:")
                logger.debug(f"  Original type: {type(orig_val)}")
                logger.debug(f"  Original value: {repr(orig_val)}")
                logger.debug(f"  Verified type: {type(ver_val)}")
                logger.debug(f"  Verified value: {repr(ver_val)}")

                if orig_val != ver_val:
                    logger.debug(f"  ⚠️ INPUTS ARE DIFFERENT!")
                    
                    # If they're dicts, compare keys
                    if isinstance(orig_val, dict) and isinstance(ver_val, dict):
                        orig_keys = set(orig_val.keys())
                        ver_keys = set(ver_val.keys())
                        
                        logger.debug(f"  Keys only in original: {orig_keys - ver_keys}")
                        logger.debug(f"  Keys only in verified: {ver_keys - orig_keys}")
                        logger.debug(f"  Common keys with different values:")

                        for k in orig_keys & ver_keys:
                            if orig_val[k] != ver_val[k]:
                                logger.debug(f"    '{k}': {repr(orig_val[k])} -> {repr(ver_val[k])}")
                else:
                    logger.debug(f"  ✅ Inputs are identical")
            
            elif orig_val != ver_val:
                logger.debug(f"\n{key}:")
                logger.debug(f"  Original: {repr(orig_val)}")
                logger.debug(f"  Verified: {repr(ver_val)}")
    
    logger.debug("\n" + "="*80)


def log_dag_corrections(original_dag: str, verified_dag: str, debug: bool = False) -> Dict[str, Any]:
    """
    Compare original agent-generated DAG with human-verified DAG
    and log only the ACTUAL differences (not formatting differences).
    
    Args:
        original_dag: Original DAG YAML string
        verified_dag: Human-verified DAG YAML string
        debug: If True, print debug information
    """
    # Optional debugging
    if debug:
        debug_dag_differences(original_dag, verified_dag)
    
    corrections = {
        "renamed_nodes": {},
        "added_nodes": [],
        "deleted_nodes": [],
        "added_edges": [],
        "deleted_edges": [],
        "modified_edges": [],
        "modified_nodes": [],
        "summary": {
            "total_edges_original": 0,
            "total_edges_verified": 0,
            "total_nodes_original": 0,
            "total_nodes_verified": 0,
            "renamed_node_count": 0,
            "added_node_count": 0,
            "deleted_node_count": 0,
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

    # ========== Detect renamed nodes ==========
    original_node_names = set(original_nodes.keys())
    verified_node_names = set(verified_nodes.keys())
    
    potentially_deleted = original_node_names - verified_node_names
    potentially_added = verified_node_names - original_node_names
    
    renamed_nodes = {}
    
    # Try to match renamed nodes based on file_name and line_range
    for deleted_name in potentially_deleted:
        deleted_node = original_nodes[deleted_name]
        deleted_file = deleted_node.get('file_name', '')
        deleted_lines = deleted_node.get('line_range', '')
        
        for added_name in potentially_added:
            if added_name in renamed_nodes.values():
                continue
                
            added_node = verified_nodes[added_name]
            added_file = added_node.get('file_name', '')
            added_lines = added_node.get('line_range', '')
            
            # Check if this is likely a rename (same file and line range)
            if (deleted_file and added_file and deleted_file == added_file and 
                deleted_lines and added_lines and deleted_lines == added_lines):
                renamed_nodes[deleted_name] = added_name
                break
    
    # Record renamed nodes
    corrections["renamed_nodes"] = renamed_nodes
    corrections["summary"]["renamed_node_count"] = len(renamed_nodes)
    
    # Identify truly deleted/added nodes
    actually_deleted = potentially_deleted - set(renamed_nodes.keys())
    actually_added = potentially_added - set(renamed_nodes.values())
    
    # Record deleted nodes
    for name in actually_deleted:
        corrections["deleted_nodes"].append({
            "name": name,
            "attributes": original_nodes[name]
        })
    corrections["summary"]["deleted_node_count"] = len(actually_deleted)
    
    # Record added nodes
    for name in actually_added:
        corrections["added_nodes"].append({
            "name": name,
            "attributes": verified_nodes[name]
        })
    corrections["summary"]["added_node_count"] = len(actually_added)

    # ========== Process edges with rename awareness ==========
    
    # Build edge dictionaries with normalized keys
    original_edges_dict = {}
    for edge in original_edges:
        # Apply renames to get normalized key
        from_node = renamed_nodes.get(edge["from"], edge["from"])
        to_node = renamed_nodes.get(edge["to"], edge["to"])
        normalized_edge = {
            "from": from_node,
            "to": to_node,
            "attributes": edge["attributes"]
        }
        key = get_edge_key(normalized_edge)
        original_edges_dict[key] = edge  # Store original edge
    
    verified_edges_dict = {}
    for edge in verified_edges:
        key = get_edge_key(edge)
        verified_edges_dict[key] = edge
    
    # Find edge differences
    original_keys = set(original_edges_dict.keys())
    verified_keys = set(verified_edges_dict.keys())
    
    # Added edges
    for key in verified_keys - original_keys:
        corrections["added_edges"].append(verified_edges_dict[key])
    corrections["summary"]["added_edge_count"] = len(verified_keys - original_keys)
    
    # Deleted edges
    for key in original_keys - verified_keys:
        corrections["deleted_edges"].append(original_edges_dict[key])
    corrections["summary"]["deleted_edge_count"] = len(original_keys - verified_keys)
    
    # Modified edges (same endpoints but different attributes)
    for key in original_keys & verified_keys:
        orig_attrs = original_edges_dict[key].get("attributes", {})
        ver_attrs = verified_edges_dict[key].get("attributes", {})
        
        # Normalize and compare attributes
        norm_orig = {k: normalize_value(v) for k, v in orig_attrs.items()}
        norm_ver = {k: normalize_value(v) for k, v in ver_attrs.items()}
        
        # Remove any keys with None values for comparison
        norm_orig = {k: v for k, v in norm_orig.items() if v is not None}
        norm_ver = {k: v for k, v in norm_ver.items() if v is not None}
        
        if norm_orig != norm_ver:
            changes = {}
            all_keys = set(norm_orig.keys()) | set(norm_ver.keys())
            
            for attr_key in all_keys:
                orig_val = norm_orig.get(attr_key)
                ver_val = norm_ver.get(attr_key)
                if orig_val != ver_val:
                    changes[attr_key] = {
                        "original": orig_val,
                        "modified": ver_val
                    }
            
            if changes:
                corrections["modified_edges"].append({
                    "from": verified_edges_dict[key]["from"],
                    "to": verified_edges_dict[key]["to"],
                    "changed_attributes": list(changes.keys()),
                    "changes": changes
                })
                corrections["summary"]["modified_edge_count"] += 1

    # ========== Process node modifications ==========
    # Only compare nodes that exist in both (not renamed/added/deleted)
    IGNORE_NODE_ATTRS = {'component_details'}  # Attributes to ignore
    
    for node_name in original_node_names & verified_node_names:
        if node_name not in renamed_nodes and node_name not in renamed_nodes.values():
            original_node = original_nodes[node_name]
            verified_node = verified_nodes[node_name]
            
            # Filter out ignored attributes
            orig_attrs = {k: v for k, v in original_node.items() if k not in IGNORE_NODE_ATTRS}
            ver_attrs = {k: v for k, v in verified_node.items() if k not in IGNORE_NODE_ATTRS}
            
            # Collect all keys to check
            all_keys = set(orig_attrs.keys()) | set(ver_attrs.keys())
            
            changes = {}
            for key in all_keys:
                orig_val = orig_attrs.get(key)
                ver_val = ver_attrs.get(key)
                
                # Use the enhanced equivalence check
                if not are_values_equivalent(orig_val, ver_val, key):
                    # Only record as change if values are meaningfully different
                    norm_orig = normalize_value(orig_val)
                    norm_ver = normalize_value(ver_val)
                    
                    # Final check: don't record if both normalize to None
                    if not (norm_orig is None and norm_ver is None):
                        changes[key] = {
                            "original": orig_val,
                            "modified": ver_val
                        }
            
            if changes:
                corrections["modified_nodes"].append({
                    "name": node_name,
                    "changed_properties": list(changes.keys()),
                    "changes": changes
                })
                corrections["summary"]["modified_node_count"] += 1

    # Calculate correction ratio
    total_corrections = sum([
        corrections["summary"]["renamed_node_count"],
        corrections["summary"]["added_node_count"],
        corrections["summary"]["deleted_node_count"],
        corrections["summary"]["added_edge_count"],
        corrections["summary"]["deleted_edge_count"],
        corrections["summary"]["modified_edge_count"],
        corrections["summary"]["modified_node_count"]
    ])

    total_items = max(
        corrections["summary"]["total_edges_original"] +
        corrections["summary"]["total_nodes_original"],
        1
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
    
    # Only show if there were actual changes
    if summary.get('correction_ratio', 0) == 0:
        md_parts.append("*No corrections were made to the DAG structure.*")
        return "\n".join(md_parts)
    
    md_parts.append(f"- **Original edges:** {summary.get('total_edges_original', 0)}")
    md_parts.append(f"- **Final edges:** {summary.get('total_edges_verified', 0)}")
    
    # Only show non-zero counts
    if summary.get('added_edge_count', 0) > 0:
        md_parts.append(f"- **Added edges:** {summary['added_edge_count']}")
    if summary.get('deleted_edge_count', 0) > 0:
        md_parts.append(f"- **Deleted edges:** {summary['deleted_edge_count']}")
    if summary.get('modified_edge_count', 0) > 0:
        md_parts.append(f"- **Modified edges:** {summary['modified_edge_count']}")
    if summary.get('renamed_node_count', 0) > 0:
        md_parts.append(f"- **Renamed nodes:** {summary['renamed_node_count']}")
    if summary.get('modified_node_count', 0) > 0:
        md_parts.append(f"- **Modified nodes:** {summary['modified_node_count']}")
    
    md_parts.append(f"- **Correction ratio:** {summary.get('correction_ratio', 0)}%")

    # Show renamed nodes
    renamed_nodes = corrections.get("renamed_nodes", {})
    if renamed_nodes:
        md_parts.append("\n**Renamed Nodes:**")
        for old_name, new_name in list(renamed_nodes.items())[:5]:
            md_parts.append(f"- `{old_name}` → `{new_name}`")
        if len(renamed_nodes) > 5:
            md_parts.append(f"- *(and {len(renamed_nodes) - 5} more renamed nodes)*")

    # Add details about edge modifications
    modified_edges = corrections.get("modified_edges", [])
    if modified_edges:
        md_parts.append("\n**Modified Edges:**")
        for mod in modified_edges[:5]:
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
        for mod in modified_nodes[:5]:
            name = mod.get("name", "Unnamed")
            props = ", ".join(mod.get("changed_properties", []))
            md_parts.append(f"- `{name}`: Changed {props}")
        if len(modified_nodes) > 5:
            md_parts.append(f"- *(and {len(modified_nodes) - 5} more modified nodes)*")

    return "\n".join(md_parts)