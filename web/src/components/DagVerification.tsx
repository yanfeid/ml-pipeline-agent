"use client";

import { useState, useMemo, useCallback } from "react";
import { Check, X, Code, Eye, Edit3, Trash2, Plus, Save, ChevronLeft, ChevronRight } from "lucide-react";
import yaml from "js-yaml";

interface DagNode {
  name: string;
  attributes: {
    [key: string]: any;
  };
}

interface DagEdge {
  from: string;
  to: string;
  attributes: {
    [key: string]: any;
  };
}

interface DagVerificationProps {
  dagYaml: string;
  repoName: string;
  runId: string;
  onSubmit: (verifiedDag: string, githubUrl: string, inputFiles: string[]) => void;
  onCancel: () => void;
  githubUrl: string;
  inputFiles: string[];
}

export function DagVerification({
  dagYaml,
  repoName,
  runId,
  onSubmit,
  onCancel,
  githubUrl,
  inputFiles,
}: DagVerificationProps) {
  const [viewMode, setViewMode] = useState<"preview" | "edit">("preview");
  const [editedYaml, setEditedYaml] = useState(dagYaml);

  // Parse YAML using js-yaml library
  const parseYaml = useCallback((yamlString: string): any => {
    try {
      return yaml.load(yamlString) || { nodes: [], edges: [] };
    } catch (e) {
      console.error("YAML parse error:", e);
      return { nodes: [], edges: [] };
    }
  }, []);

  // Generate YAML string from data
  const generateYaml = useCallback((data: any): string => {
    try {
      return yaml.dump(data, {
        indent: 2,
        lineWidth: -1,
        noRefs: true,
        sortKeys: false
      });
    } catch (e) {
      console.error("YAML generate error:", e);
      return "";
    }
  }, []);

  // Parse YAML into nodes and edges
  const { nodes, edges, parseError } = useMemo(() => {
    try {
      const data = parseYaml(editedYaml);

      const parsedNodes: DagNode[] = [];
      const parsedEdges: DagEdge[] = [];

      // Parse nodes - handle different formats
      if (data.nodes && Array.isArray(data.nodes)) {
        data.nodes.forEach((nodeItem: any) => {
          if (typeof nodeItem === "string") {
            // Simple string node
            parsedNodes.push({ name: nodeItem, attributes: {} });
          } else if (typeof nodeItem === "object") {
            // Object node: { nodeName: { attrs } } or { name: "nodeName", ... }
            const keys = Object.keys(nodeItem);
            if (keys.length === 1 && keys[0] !== "name") {
              const nodeName = keys[0];
              parsedNodes.push({
                name: nodeName,
                attributes: nodeItem[nodeName] || {},
              });
            } else if (nodeItem.name) {
              parsedNodes.push({
                name: nodeItem.name,
                attributes: nodeItem.attributes || {},
              });
            }
          }
        });
      }

      // Parse edges
      if (data.edges && Array.isArray(data.edges)) {
        data.edges.forEach((edge: any) => {
          if (edge && typeof edge === "object") {
            parsedEdges.push({
              from: edge.from || "",
              to: edge.to || "",
              attributes: edge.attributes || {},
            });
          }
        });
      }

      return { nodes: parsedNodes, edges: parsedEdges, parseError: null };
    } catch (err) {
      return {
        nodes: [],
        edges: [],
        parseError: err instanceof Error ? err.message : "Failed to parse YAML"
      };
    }
  }, [editedYaml, parseYaml]);

  // State for structure editing
  const [localNodes, setLocalNodes] = useState<DagNode[]>([]);
  const [localEdges, setLocalEdges] = useState<DagEdge[]>([]);
  const [isStructureEditing, setIsStructureEditing] = useState(false);

  // Initialize local state when switching to structure edit
  const handleStartStructureEdit = () => {
    setLocalNodes(JSON.parse(JSON.stringify(nodes)));
    setLocalEdges(JSON.parse(JSON.stringify(edges)));
    setIsStructureEditing(true);
  };

  // State for edge attribute editing
  const [currentEdgeIndex, setCurrentEdgeIndex] = useState(0);
  const [editingAttributes, setEditingAttributes] = useState<{ [key: string]: any }>({});

  // Node operations
  const handleRenameNode = (oldName: string, newName: string) => {
    if (!newName.trim() || newName === oldName) return;

    setLocalNodes(prev => prev.map(node =>
      node.name === oldName ? { ...node, name: newName } : node
    ));

    setLocalEdges(prev => prev.map(edge => ({
      ...edge,
      from: edge.from === oldName ? newName : edge.from,
      to: edge.to === oldName ? newName : edge.to,
    })));
  };

  const handleAddEdge = (from: string, to: string) => {
    if (!from || !to) return;

    const exists = localEdges.some(e => e.from === from && e.to === to);
    if (exists) {
      alert(`Edge from "${from}" to "${to}" already exists`);
      return;
    }

    setLocalEdges(prev => [...prev, { from, to, attributes: {} }]);
  };

  const handleDeleteEdge = (index: number) => {
    setLocalEdges(prev => prev.filter((_, i) => i !== index));
    if (currentEdgeIndex >= localEdges.length - 1) {
      setCurrentEdgeIndex(Math.max(0, localEdges.length - 2));
    }
  };

  // Save structure changes back to YAML
  const handleSaveStructure = () => {
    try {
      const yamlData = {
        nodes: localNodes.map(node => ({
          [node.name]: node.attributes && Object.keys(node.attributes).length > 0
            ? node.attributes
            : null
        })),
        edges: localEdges.map(edge => ({
          from: edge.from,
          to: edge.to,
          ...(edge.attributes && Object.keys(edge.attributes).length > 0
            ? { attributes: edge.attributes }
            : {})
        }))
      };

      const newYaml = generateYaml(yamlData);
      setEditedYaml(newYaml);
      setIsStructureEditing(false);
    } catch (err) {
      alert("Error generating YAML: " + (err instanceof Error ? err.message : "Unknown error"));
    }
  };

  // Edge attribute operations
  const handleEditEdgeAttributes = (index: number) => {
    setCurrentEdgeIndex(index);
    setEditingAttributes(JSON.parse(JSON.stringify(localEdges[index].attributes)));
  };

  const handleSaveEdgeAttributes = () => {
    setLocalEdges(prev => prev.map((edge, i) =>
      i === currentEdgeIndex ? { ...edge, attributes: editingAttributes } : edge
    ));
  };

  const handleAddAttribute = () => {
    const key = prompt("Enter attribute key:");
    if (key && key.trim()) {
      setEditingAttributes(prev => ({ ...prev, [key.trim()]: "" }));
    }
  };

  const handleDeleteAttribute = (key: string) => {
    setEditingAttributes(prev => {
      const newAttrs = { ...prev };
      delete newAttrs[key];
      return newAttrs;
    });
  };

  const handleSubmit = () => {
    if (isStructureEditing) {
      handleSaveStructure();
    }
    onSubmit(editedYaml, githubUrl, inputFiles);
  };

  // DAG Visualization Component
  const DagVisualization = () => {
    const nodeNames = isStructureEditing ? localNodes.map(n => n.name) : nodes.map(n => n.name);
    const edgesList = isStructureEditing ? localEdges : edges;

    // Build adjacency list and calculate node positions using topological sort
    const inDegree = new Map<string, number>();
    const outEdges = new Map<string, string[]>();

    nodeNames.forEach(name => {
      inDegree.set(name, 0);
      outEdges.set(name, []);
    });

    edgesList.forEach(edge => {
      if (nodeNames.includes(edge.from) && nodeNames.includes(edge.to)) {
        inDegree.set(edge.to, (inDegree.get(edge.to) || 0) + 1);
        outEdges.get(edge.from)?.push(edge.to);
      }
    });

    // Topological sort to assign layers
    const layers: string[][] = [];
    const visited = new Set<string>();
    const nodeToLayer = new Map<string, number>();

    // Start with nodes that have no incoming edges
    let currentLayer = nodeNames.filter(name => inDegree.get(name) === 0);

    while (currentLayer.length > 0) {
      layers.push([...currentLayer]);
      currentLayer.forEach(node => {
        visited.add(node);
        nodeToLayer.set(node, layers.length - 1);
      });

      const nextLayer: string[] = [];
      currentLayer.forEach(node => {
        (outEdges.get(node) || []).forEach(target => {
          if (!visited.has(target)) {
            const newDegree = (inDegree.get(target) || 0) - 1;
            inDegree.set(target, newDegree);
            if (newDegree === 0) {
              nextLayer.push(target);
            }
          }
        });
      });

      currentLayer = nextLayer;
    }

    // Add remaining nodes (cycles or disconnected)
    const remaining = nodeNames.filter(name => !visited.has(name));
    if (remaining.length > 0) {
      layers.push(remaining);
      remaining.forEach(node => nodeToLayer.set(node, layers.length - 1));
    }

    // Calculate node positions
    const svgWidth = 800;
    const svgHeight = Math.max(500, layers.length * 120);
    const nodePositions = new Map<string, { x: number; y: number }>();

    layers.forEach((layer, layerIdx) => {
      const layerY = 60 + layerIdx * ((svgHeight - 120) / Math.max(layers.length - 1, 1));
      const layerWidth = svgWidth / (layer.length + 1);

      layer.forEach((nodeName, nodeIdx) => {
        nodePositions.set(nodeName, {
          x: (nodeIdx + 1) * layerWidth,
          y: layerY
        });
      });
    });

    // Color palette for layers
    const colorPalette = [
      "#93C5FD", "#86EFAC", "#FDE68A", "#FCA5A5", "#C4B5FD",
      "#67E8F9", "#FCD34D", "#F9A8D4", "#A5B4FC", "#6EE7B7"
    ];

    return (
      <div className="bg-white rounded-xl border border-gray-200 p-6 h-full overflow-auto">
        <div className="flex items-center justify-between mb-4">
          <h3 className="font-semibold text-gray-900">DAG Visualization</h3>
          <span className="text-sm text-gray-500">
            {nodeNames.length} nodes, {edgesList.length} edges
          </span>
        </div>

        <div className="relative bg-gray-50 rounded-lg border border-gray-200 overflow-auto">
          <svg
            width={svgWidth}
            height={svgHeight}
            viewBox={`0 0 ${svgWidth} ${svgHeight}`}
            className="min-w-full"
          >
            <defs>
              <marker
                id="arrowhead"
                markerWidth="10"
                markerHeight="7"
                refX="9"
                refY="3.5"
                orient="auto"
                markerUnits="strokeWidth"
              >
                <polygon points="0 0, 10 3.5, 0 7" fill="#6B7280" />
              </marker>
            </defs>

            {/* Draw edges */}
            {edgesList.map((edge, idx) => {
              const fromPos = nodePositions.get(edge.from);
              const toPos = nodePositions.get(edge.to);

              if (!fromPos || !toPos) return null;

              const fromY = fromPos.y + 20; // Bottom of from node
              const toY = toPos.y - 20;     // Top of to node

              // Calculate control points for smooth curve
              const midY = (fromY + toY) / 2;
              const dx = toPos.x - fromPos.x;

              // Offset for parallel edges
              const parallelEdges = edgesList.filter(e =>
                (e.from === edge.from && e.to === edge.to) ||
                (e.from === edge.to && e.to === edge.from)
              );
              const edgeIndex = parallelEdges.indexOf(edge);
              const offset = (edgeIndex - (parallelEdges.length - 1) / 2) * 20;

              const path = `M ${fromPos.x} ${fromY}
                           C ${fromPos.x + offset} ${midY},
                             ${toPos.x + offset} ${midY},
                             ${toPos.x} ${toY}`;

              return (
                <g key={`edge-${idx}`}>
                  <path
                    d={path}
                    fill="none"
                    stroke="#6B7280"
                    strokeWidth="2"
                    markerEnd="url(#arrowhead)"
                    className="hover:stroke-blue-500 transition-colors"
                  />
                  <title>{edge.from} → {edge.to}</title>
                </g>
              );
            })}

            {/* Draw nodes */}
            {nodeNames.map((nodeName) => {
              const pos = nodePositions.get(nodeName);
              if (!pos) return null;

              const layerIdx = nodeToLayer.get(nodeName) || 0;
              const color = colorPalette[layerIdx % colorPalette.length];
              const textWidth = Math.max(nodeName.length * 8, 80);
              const rectWidth = Math.min(textWidth + 24, 180);

              return (
                <g key={nodeName} className="cursor-pointer">
                  <rect
                    x={pos.x - rectWidth / 2}
                    y={pos.y - 20}
                    width={rectWidth}
                    height={40}
                    fill={color}
                    stroke="#374151"
                    strokeWidth="2"
                    rx="8"
                    className="hover:stroke-blue-500 hover:stroke-[3px] transition-all"
                  />
                  <text
                    x={pos.x}
                    y={pos.y + 5}
                    textAnchor="middle"
                    className="fill-gray-900 font-medium pointer-events-none select-none"
                    style={{ fontSize: "12px" }}
                  >
                    {nodeName.length > 18 ? nodeName.substring(0, 15) + "..." : nodeName}
                  </text>
                  <title>{nodeName}</title>
                </g>
              );
            })}
          </svg>
        </div>

        {/* Legend */}
        <div className="mt-4 flex flex-wrap gap-4 text-xs text-gray-600">
          <div className="flex items-center gap-2">
            <span>Layers:</span>
            {layers.slice(0, 5).map((_, idx) => (
              <div
                key={idx}
                className="w-4 h-4 rounded border border-gray-400"
                style={{ backgroundColor: colorPalette[idx] }}
                title={`Layer ${idx + 1}`}
              />
            ))}
            {layers.length > 5 && <span>...</span>}
          </div>
          <div className="flex items-center gap-1">
            <svg width="30" height="10">
              <line x1="0" y1="5" x2="25" y2="5" stroke="#6B7280" strokeWidth="2" markerEnd="url(#arrowhead)" />
            </svg>
            <span>Data flow</span>
          </div>
        </div>

        {/* Edge list */}
        {edgesList.length > 0 && (
          <details className="mt-4 pt-4 border-t border-gray-200">
            <summary className="cursor-pointer font-medium text-gray-700 text-sm hover:text-blue-600">
              View all edges ({edgesList.length})
            </summary>
            <div className="mt-2 grid grid-cols-2 gap-2 text-xs max-h-40 overflow-auto">
              {edgesList.map((edge, i) => (
                <div key={i} className="bg-gray-100 px-3 py-1.5 rounded font-mono text-gray-700">
                  {edge.from} → {edge.to}
                </div>
              ))}
            </div>
          </details>
        )}
      </div>
    );
  };

  return (
    <div className="max-w-7xl mx-auto">
      <div className="mb-6">
        <h1 className="text-3xl font-bold text-gray-900 mb-2">
          Verify DAG Structure
        </h1>
        <p className="text-gray-600">
          Review and edit the workflow DAG. You can modify the YAML directly or use the visual editor.
        </p>
      </div>

      {parseError && (
        <div className="bg-red-50 border border-red-200 rounded-xl p-4 mb-6">
          <p className="text-red-800 font-semibold">YAML Parse Error</p>
          <p className="text-sm text-red-600 mt-1">{parseError}</p>
        </div>
      )}

      {/* Mode Toggle */}
      <div className="flex items-center gap-2 mb-6">
        <button
          onClick={() => setViewMode("preview")}
          className={`px-4 py-2 rounded-lg font-medium flex items-center gap-2 transition-colors ${
            viewMode === "preview"
              ? "bg-blue-100 text-blue-700"
              : "text-gray-600 hover:bg-gray-100"
          }`}
        >
          <Eye className="w-4 h-4" />
          Preview
        </button>
        <button
          onClick={() => setViewMode("edit")}
          className={`px-4 py-2 rounded-lg font-medium flex items-center gap-2 transition-colors ${
            viewMode === "edit"
              ? "bg-blue-100 text-blue-700"
              : "text-gray-600 hover:bg-gray-100"
          }`}
        >
          <Edit3 className="w-4 h-4" />
          Edit YAML
        </button>
      </div>

      {/* Main grid layout */}
      <div className="grid grid-cols-2 gap-6 mb-6">
        {/* Left side: YAML Editor */}
        <div className="space-y-6">
          <div className="bg-white rounded-xl shadow-sm border border-gray-200 overflow-hidden">
            <div className="bg-gray-800 px-4 py-3 flex items-center gap-2">
              <Code className="w-5 h-5 text-gray-400" />
              <span className="text-sm text-gray-300 font-mono">dag.yaml</span>
            </div>
            {viewMode === "edit" ? (
              <textarea
                value={editedYaml}
                onChange={(e) => setEditedYaml(e.target.value)}
                className="w-full h-[400px] p-4 font-mono text-sm bg-gray-900 text-gray-100 focus:outline-none resize-none"
                spellCheck={false}
              />
            ) : (
              <pre className="p-4 font-mono text-sm bg-gray-900 text-gray-100 overflow-auto h-[400px]">
                <code>{editedYaml}</code>
              </pre>
            )}
          </div>

          {/* Quick Actions when editing structure */}
          {isStructureEditing && (
            <div className="bg-white rounded-xl shadow-sm border border-gray-200 p-4">
              <h3 className="font-semibold text-gray-800 mb-3 text-sm">Quick Actions</h3>

              {/* Rename Node */}
              <div className="mb-4">
                <label className="block text-xs font-medium text-gray-700 mb-1">Rename Node</label>
                <div className="flex gap-2">
                  <select
                    className="flex-1 text-sm px-2 py-1.5 border border-gray-300 rounded-lg"
                    id="rename-select"
                  >
                    <option value="">Select node...</option>
                    {localNodes.map(node => (
                      <option key={node.name} value={node.name}>{node.name}</option>
                    ))}
                  </select>
                  <input
                    type="text"
                    placeholder="New name"
                    className="flex-1 text-sm px-2 py-1.5 border border-gray-300 rounded-lg"
                    id="rename-input"
                  />
                  <button
                    onClick={() => {
                      const select = document.getElementById("rename-select") as HTMLSelectElement;
                      const input = document.getElementById("rename-input") as HTMLInputElement;
                      if (select.value && input.value) {
                        handleRenameNode(select.value, input.value);
                        input.value = "";
                      }
                    }}
                    className="px-3 py-1.5 text-sm bg-blue-600 text-white rounded-lg font-medium hover:bg-blue-700"
                  >
                    Rename
                  </button>
                </div>
              </div>

              {/* Add Edge */}
              <div className="mb-4">
                <label className="block text-xs font-medium text-gray-700 mb-1">Add Edge</label>
                <div className="flex gap-2">
                  <select
                    className="flex-1 text-sm px-2 py-1.5 border border-gray-300 rounded-lg"
                    id="edge-from"
                  >
                    <option value="">From...</option>
                    {localNodes.map(node => (
                      <option key={node.name} value={node.name}>{node.name}</option>
                    ))}
                  </select>
                  <select
                    className="flex-1 text-sm px-2 py-1.5 border border-gray-300 rounded-lg"
                    id="edge-to"
                  >
                    <option value="">To...</option>
                    {localNodes.map(node => (
                      <option key={node.name} value={node.name}>{node.name}</option>
                    ))}
                  </select>
                  <button
                    onClick={() => {
                      const fromSelect = document.getElementById("edge-from") as HTMLSelectElement;
                      const toSelect = document.getElementById("edge-to") as HTMLSelectElement;
                      if (fromSelect.value && toSelect.value) {
                        handleAddEdge(fromSelect.value, toSelect.value);
                      }
                    }}
                    className="px-3 py-1.5 text-sm bg-green-600 text-white rounded-lg font-medium hover:bg-green-700 flex items-center gap-1"
                  >
                    <Plus className="w-3 h-3" />
                    Add
                  </button>
                </div>
              </div>

              {/* Delete Edge */}
              <div>
                <label className="block text-xs font-medium text-gray-700 mb-1">Delete Edge</label>
                <div className="flex gap-2">
                  <select
                    className="flex-1 text-sm px-2 py-1.5 border border-gray-300 rounded-lg"
                    id="edge-delete"
                  >
                    <option value="">Select edge...</option>
                    {localEdges.map((edge, i) => (
                      <option key={i} value={i}>{edge.from} → {edge.to}</option>
                    ))}
                  </select>
                  <button
                    onClick={() => {
                      const select = document.getElementById("edge-delete") as HTMLSelectElement;
                      if (select.value !== "") {
                        handleDeleteEdge(parseInt(select.value));
                      }
                    }}
                    className="px-3 py-1.5 text-sm bg-red-600 text-white rounded-lg font-medium hover:bg-red-700 flex items-center gap-1"
                  >
                    <Trash2 className="w-3 h-3" />
                    Delete
                  </button>
                </div>
              </div>
            </div>
          )}
        </div>

        {/* Right side: DAG Visualization */}
        <div className="h-full">
          <DagVisualization />
        </div>
      </div>

      {/* Structure Editing Controls */}
      <div className="bg-white rounded-xl shadow-sm border border-gray-200 p-6 mb-6">
        <div className="flex items-center justify-between">
          <h2 className="text-xl font-semibold text-gray-900">
            Edit DAG Structure
          </h2>
          {!isStructureEditing ? (
            <button
              onClick={handleStartStructureEdit}
              className="px-4 py-2 bg-blue-600 text-white rounded-lg font-medium hover:bg-blue-700 transition-colors flex items-center gap-2"
            >
              <Edit3 className="w-4 h-4" />
              Start Editing
            </button>
          ) : (
            <div className="flex gap-2">
              <button
                onClick={() => setIsStructureEditing(false)}
                className="px-4 py-2 border border-gray-300 text-gray-700 rounded-lg font-medium hover:bg-gray-50 transition-colors"
              >
                Cancel
              </button>
              <button
                onClick={handleSaveStructure}
                className="px-4 py-2 bg-green-600 text-white rounded-lg font-medium hover:bg-green-700 transition-colors flex items-center gap-2"
              >
                <Save className="w-4 h-4" />
                Save Changes
              </button>
            </div>
          )}
        </div>
        {isStructureEditing && (
          <p className="text-sm text-gray-600 mt-2">
            Use the controls on the left side to rename nodes, add edges, or delete edges. The visualization updates in real-time.
          </p>
        )}
      </div>

      {/* Edge Attributes Editing */}
      {isStructureEditing && localEdges.length > 0 && (
        <div className="bg-white rounded-xl shadow-sm border border-gray-200 p-6 mb-6">
          <h2 className="text-xl font-semibold text-gray-900 mb-4">
            Edit Edge Attributes
          </h2>

          <div className="flex items-center justify-between mb-4">
            <div className="flex items-center gap-3">
              <button
                onClick={() => setCurrentEdgeIndex(Math.max(0, currentEdgeIndex - 1))}
                disabled={currentEdgeIndex === 0}
                className="p-2 border border-gray-300 rounded-lg disabled:opacity-50"
              >
                <ChevronLeft className="w-4 h-4" />
              </button>
              <span className="text-sm font-medium text-gray-700">
                Edge {currentEdgeIndex + 1} of {localEdges.length}:{" "}
                <span className="font-mono text-blue-600">
                  {localEdges[currentEdgeIndex].from} → {localEdges[currentEdgeIndex].to}
                </span>
              </span>
              <button
                onClick={() => setCurrentEdgeIndex(Math.min(localEdges.length - 1, currentEdgeIndex + 1))}
                disabled={currentEdgeIndex >= localEdges.length - 1}
                className="p-2 border border-gray-300 rounded-lg disabled:opacity-50"
              >
                <ChevronRight className="w-4 h-4" />
              </button>
            </div>
            <button
              onClick={() => handleEditEdgeAttributes(currentEdgeIndex)}
              className="px-4 py-2 bg-blue-600 text-white rounded-lg font-medium hover:bg-blue-700"
            >
              Load Attributes
            </button>
          </div>

          <div className="space-y-2 mb-4">
            {Object.entries(editingAttributes).map(([key, value]) => (
              <div key={key} className="flex gap-2">
                <input
                  type="text"
                  value={key}
                  disabled
                  className="w-1/3 px-3 py-2 border border-gray-300 rounded-lg bg-gray-50"
                />
                <input
                  type="text"
                  value={value as string}
                  onChange={(e) => setEditingAttributes(prev => ({ ...prev, [key]: e.target.value }))}
                  className="flex-1 px-3 py-2 border border-gray-300 rounded-lg"
                />
                <button
                  onClick={() => handleDeleteAttribute(key)}
                  className="p-2 text-red-600 hover:bg-red-50 rounded-lg"
                >
                  <Trash2 className="w-4 h-4" />
                </button>
              </div>
            ))}
          </div>

          <div className="flex gap-2">
            <button
              onClick={handleAddAttribute}
              className="px-4 py-2 bg-green-600 text-white rounded-lg font-medium hover:bg-green-700 flex items-center gap-2"
            >
              <Plus className="w-4 h-4" />
              Add Attribute
            </button>
            <button
              onClick={handleSaveEdgeAttributes}
              className="px-4 py-2 bg-blue-600 text-white rounded-lg font-medium hover:bg-blue-700 flex items-center gap-2"
            >
              <Save className="w-4 h-4" />
              Save Attributes
            </button>
          </div>
        </div>
      )}

      {/* Action Buttons */}
      <div className="flex items-center justify-between">
        <button
          onClick={onCancel}
          className="px-6 py-3 border border-gray-300 text-gray-700 rounded-lg font-medium hover:bg-gray-50 transition-colors flex items-center gap-2"
        >
          <X className="w-5 h-5" />
          Cancel
        </button>
        <button
          onClick={handleSubmit}
          disabled={!!parseError}
          className="px-8 py-3 bg-blue-600 text-white rounded-lg font-medium hover:bg-blue-700 disabled:opacity-50 disabled:cursor-not-allowed transition-colors flex items-center gap-2"
        >
          <Check className="w-5 h-5" />
          Confirm DAG
        </button>
      </div>
    </div>
  );
}
