
def generage_dag_yaml(aggregated_nodes: str, edges: str) -> str:
    # Get nodes yaml string
    nodes_yaml_str = "nodes:\n" + aggregated_nodes.replace("```yaml", "").replace("```", "")
    # Get edges yaml string
    cleaned = edges.replace("```yaml", "").replace("```", "").replace("edges:", "")
    lines = cleaned.strip().split("\n")
    non_empty_lines = [line for line in lines if line.strip()]

    # Process edge lines to ensure proper indentation
    processed_edge_lines = []
    for line in non_empty_lines:
        # First check if line starts with "- from:" to identify a new edge
        if line.strip().startswith("- from:"):
            processed_edge_lines.append(line.strip())  # Keep the - at the beginning of a new edge
        else:
            # For other lines, check indentation level
            stripped = line.lstrip()
            # If it's a property of the edge (to:, attributes:), align with from:
            if stripped.startswith("to:") or stripped.startswith("attributes:"):
                processed_edge_lines.append("  " + stripped)
            # If it's a nested property under attributes, add more indentation
            elif ":" in stripped:
                processed_edge_lines.append("    " + stripped)
            else:
                # Any other line, preserve but with proper indentation
                processed_edge_lines.append("  " + stripped)

    edges_yaml_str = "edges:\n" + "\n".join(processed_edge_lines)

    # Full DAG yaml string
    dag_yaml = nodes_yaml_str + "\n" + edges_yaml_str
    return dag_yaml
