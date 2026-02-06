"use client";

import { GitBranch, Activity, CheckCircle2, XCircle, Clock, Loader2 } from "lucide-react";

const WORKFLOW_STEPS = [
  { key: "fork_and_clone_repository", label: "Clone Repository" },
  { key: "summarize", label: "Summarize Code" },
  { key: "component_identification", label: "Identify Components" },
  { key: "component_parsing", label: "Parse Components" },
  { key: "human_verification_of_components", label: "Verify Components" },
  { key: "attribute_identification", label: "Identify Attributes" },
  { key: "attribute_parsing", label: "Parse Attributes" },
  { key: "node_aggregator", label: "Aggregate Nodes" },
  { key: "edge_identification", label: "Identify Edges" },
  { key: "generate_dag_yaml", label: "Generate DAG" },
  { key: "human_verification_of_dag", label: "Verify DAG" },
  { key: "config_agent", label: "Generate Config" },
  { key: "notebook_agent", label: "Generate Notebooks" },
  { key: "code_editor_agent", label: "Edit Code" },
  { key: "create_pr_body", label: "Create PR Body" },
  { key: "push_code_changes", label: "Push Changes" },
  { key: "create_pull_request", label: "Create PR" },
];

interface SidebarProps {
  repoName: string;
  runId: string;
  currentStep: string;
  status: string;
}

export function Sidebar({ repoName, runId, currentStep, status }: SidebarProps) {
  const currentStepIndex = WORKFLOW_STEPS.findIndex((s) => s.key === currentStep);

  const getStepIcon = (stepKey: string, index: number) => {
    if (currentStep === "complete" || index < currentStepIndex) {
      return <CheckCircle2 className="w-4 h-4 text-green-500" />;
    }
    if (stepKey === currentStep) {
      if (status === "failed") {
        return <XCircle className="w-4 h-4 text-red-500" />;
      }
      return <Loader2 className="w-4 h-4 text-blue-500 animate-spin" />;
    }
    return <Clock className="w-4 h-4 text-gray-300" />;
  };

  return (
    <aside className="w-72 bg-white border-r border-gray-200 flex flex-col">
      {/* Header */}
      <div className="p-6 border-b border-gray-200">
        <div className="flex items-center gap-3">
          <div className="w-10 h-10 bg-gradient-to-br from-blue-500 to-purple-600 rounded-lg flex items-center justify-center">
            <Activity className="w-6 h-6 text-white" />
          </div>
          <div>
            <h1 className="font-bold text-gray-900">RMR Agent</h1>
            <p className="text-xs text-gray-500">ML Pipeline Automation</p>
          </div>
        </div>
      </div>

      {/* Current Run Info */}
      {repoName && (
        <div className="p-4 border-b border-gray-200 bg-gray-50">
          <div className="flex items-center gap-2 text-sm">
            <GitBranch className="w-4 h-4 text-gray-400" />
            <span className="font-medium text-gray-700 truncate">{repoName}</span>
          </div>
          {runId && (
            <div className="mt-1 text-xs text-gray-500">Run ID: {runId}</div>
          )}
        </div>
      )}

      {/* Workflow Steps */}
      <div className="flex-1 overflow-auto p-4">
        <h2 className="text-xs font-semibold text-gray-400 uppercase tracking-wider mb-3">
          Workflow Steps
        </h2>
        <div className="space-y-1">
          {WORKFLOW_STEPS.map((step, index) => (
            <div
              key={step.key}
              className={`flex items-center gap-3 px-3 py-2 rounded-lg text-sm transition-colors ${
                step.key === currentStep
                  ? "bg-blue-50 text-blue-700"
                  : index < currentStepIndex || currentStep === "complete"
                  ? "text-gray-600"
                  : "text-gray-400"
              }`}
            >
              {getStepIcon(step.key, index)}
              <span className="truncate">{step.label}</span>
            </div>
          ))}
        </div>
      </div>

      {/* Footer */}
      <div className="p-4 border-t border-gray-200">
        <div className="text-xs text-gray-400">
          Status:{" "}
          <span
            className={`font-medium ${
              status === "running"
                ? "text-blue-600"
                : status === "complete"
                ? "text-green-600"
                : status === "failed"
                ? "text-red-600"
                : "text-gray-600"
            }`}
          >
            {status || "Idle"}
          </span>
        </div>
      </div>
    </aside>
  );
}
