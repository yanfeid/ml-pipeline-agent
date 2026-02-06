"use client";

import { Loader2, XCircle, AlertCircle, CheckCircle2, Circle } from "lucide-react";

interface WorkflowProgressProps {
  step: string;
  status: string;
  error: string | null;
  onCancel: () => void;
}

const ALL_STEPS = [
  { key: "fork_and_clone_repository", label: "Fork & Clone Repository" },
  { key: "summarize", label: "Summarize Code" },
  { key: "component_identification", label: "Identify Components" },
  { key: "component_parsing", label: "Parse Components" },
  { key: "human_verification_of_components", label: "Human Verification (Components)" },
  { key: "attribute_identification", label: "Identify Attributes" },
  { key: "attribute_parsing", label: "Parse Attributes" },
  { key: "node_aggregator", label: "Aggregate Nodes" },
  { key: "edge_identification", label: "Identify Edges" },
  { key: "generate_dag_yaml", label: "Generate DAG" },
  { key: "human_verification_of_dag", label: "Human Verification (DAG)" },
  { key: "config_agent", label: "Create Config Files" },
  { key: "notebook_agent", label: "Generate Notebooks" },
  { key: "code_editor_agent", label: "Refactor Code" },
  { key: "create_pr_body", label: "Create PR Body" },
  { key: "push_code_changes", label: "Push Changes" },
  { key: "create_pull_request", label: "Create Pull Request" },
];

const STEP_DESCRIPTIONS: Record<string, string> = {
  fork_and_clone_repository: "Forking and cloning the repository...",
  summarize: "Analyzing and summarizing the code...",
  component_identification: "Identifying ML components in your code...",
  component_parsing: "Parsing component structures...",
  human_verification_of_components: "Waiting for human verification of components...",
  attribute_identification: "Extracting input/output attributes...",
  attribute_parsing: "Parsing attribute values...",
  node_aggregator: "Aggregating nodes for the DAG...",
  edge_identification: "Identifying dependencies between components...",
  generate_dag_yaml: "Generating the workflow DAG...",
  human_verification_of_dag: "Waiting for human verification of DAG...",
  config_agent: "Creating configuration files...",
  notebook_agent: "Generating production notebooks...",
  code_editor_agent: "Refactoring code with config variables...",
  create_pr_body: "Preparing pull request description...",
  push_code_changes: "Pushing changes to repository...",
  create_pull_request: "Creating the pull request...",
};

export function WorkflowProgress({
  step,
  status,
  error,
  onCancel,
}: WorkflowProgressProps) {
  console.log("📊 WorkflowProgress rendering:", { step, status, error });

  const description = STEP_DESCRIPTIONS[step] || `Processing: ${step}`;

  // Calculate progress
  const currentStepIndex = ALL_STEPS.findIndex(s => s.key === step);
  const totalSteps = ALL_STEPS.length;
  const completedSteps = currentStepIndex >= 0 ? currentStepIndex : 0;
  const progressPercentage = totalSteps > 0 ? Math.round((completedSteps / totalSteps) * 100) : 0;

  console.log("📊 Progress calculation:", {
    currentStepIndex,
    totalSteps,
    completedSteps,
    progressPercentage,
    description
  });

  if (status === "failed" || error) {
    return (
      <div className="max-w-2xl mx-auto text-center">
        <div className="bg-red-50 rounded-2xl p-8 border border-red-200">
          <XCircle className="w-16 h-16 text-red-500 mx-auto mb-4" />
          <h2 className="text-2xl font-bold text-gray-900 mb-2">
            Workflow Failed
          </h2>
          <p className="text-gray-600 mb-4">
            An error occurred during the workflow execution.
          </p>
          {error && (
            <div className="bg-red-100 rounded-lg p-4 text-left mb-6">
              <div className="flex items-start gap-2">
                <AlertCircle className="w-5 h-5 text-red-600 mt-0.5 flex-shrink-0" />
                <p className="text-sm text-red-800 font-mono">{error}</p>
              </div>
            </div>
          )}
          <button
            onClick={onCancel}
            className="px-6 py-3 bg-gray-900 text-white rounded-lg font-medium hover:bg-gray-800 transition-colors"
          >
            Start Over
          </button>
        </div>
      </div>
    );
  }

  return (
    <div className="max-w-3xl mx-auto">
      <div className="bg-white rounded-2xl shadow-sm border border-gray-200 p-8">
        {/* Animated Loader */}
        <div className="text-center mb-8">
          <div className="relative w-24 h-24 mx-auto mb-6">
            <div className="absolute inset-0 rounded-full border-4 border-blue-100"></div>
            <div className="absolute inset-0 rounded-full border-4 border-blue-600 border-t-transparent animate-spin"></div>
            <div className="absolute inset-4 rounded-full bg-gradient-to-br from-blue-500 to-purple-600 flex items-center justify-center">
              <Loader2 className="w-8 h-8 text-white animate-pulse" />
            </div>
          </div>

          <h2 className="text-2xl font-bold text-gray-900 mb-2">
            Workflow Running
          </h2>
          <p className="text-gray-600 mb-4">{description}</p>

          {/* Progress Bar */}
          <div className="max-w-md mx-auto mb-6">
            <div className="flex items-center justify-between text-sm text-gray-600 mb-2">
              <span>Progress</span>
              <span className="font-semibold">{completedSteps} / {totalSteps} steps</span>
            </div>
            <div className="w-full h-3 bg-gray-200 rounded-full overflow-hidden">
              <div
                className="h-full bg-gradient-to-r from-blue-500 to-purple-600 transition-all duration-500 ease-out"
                style={{ width: `${progressPercentage}%` }}
              />
            </div>
            <div className="text-center mt-2">
              <span className="text-2xl font-bold text-blue-600">{progressPercentage}%</span>
            </div>
          </div>

          {/* Current Step Badge */}
          <div className="inline-flex items-center gap-2 px-4 py-2 bg-blue-50 rounded-full text-sm text-blue-700 font-medium">
            <span className="w-2 h-2 bg-blue-600 rounded-full animate-pulse"></span>
            {step.replace(/_/g, " ").replace(/\b\w/g, (l) => l.toUpperCase())}
          </div>
        </div>

        {/* Detailed Steps List */}
        <details className="mt-8">
          <summary className="cursor-pointer text-sm font-semibold text-gray-700 hover:text-gray-900 mb-4">
            View Detailed Progress
          </summary>
          <div className="space-y-2 max-h-96 overflow-y-auto">
            {ALL_STEPS.map((stepInfo, index) => {
              const isCompleted = index < completedSteps;
              const isCurrent = stepInfo.key === step;
              const isPending = index > completedSteps;

              return (
                <div
                  key={stepInfo.key}
                  className={`flex items-center gap-3 p-3 rounded-lg transition-colors ${
                    isCurrent ? 'bg-blue-50 border border-blue-200' :
                    isCompleted ? 'bg-green-50' :
                    'bg-gray-50'
                  }`}
                >
                  {/* Icon */}
                  {isCompleted && (
                    <CheckCircle2 className="w-5 h-5 text-green-600 flex-shrink-0" />
                  )}
                  {isCurrent && (
                    <Loader2 className="w-5 h-5 text-blue-600 animate-spin flex-shrink-0" />
                  )}
                  {isPending && (
                    <Circle className="w-5 h-5 text-gray-300 flex-shrink-0" />
                  )}

                  {/* Step Info */}
                  <div className="flex-1 min-w-0">
                    <p className={`text-sm font-medium ${
                      isCurrent ? 'text-blue-900' :
                      isCompleted ? 'text-green-900' :
                      'text-gray-500'
                    }`}>
                      {index + 1}. {stepInfo.label}
                    </p>
                  </div>

                  {/* Status */}
                  {isCurrent && (
                    <span className="text-xs font-semibold text-blue-600 px-2 py-1 bg-blue-100 rounded">
                      Running
                    </span>
                  )}
                  {isCompleted && (
                    <span className="text-xs font-semibold text-green-600 px-2 py-1 bg-green-100 rounded">
                      Done
                    </span>
                  )}
                </div>
              );
            })}
          </div>
        </details>

        {/* Cancel Button */}
        <div className="text-center mt-8">
          <button
            onClick={onCancel}
            className="px-6 py-3 border border-gray-300 text-gray-700 rounded-lg font-medium hover:bg-gray-50 transition-colors"
          >
            Cancel Workflow
          </button>
        </div>
      </div>
    </div>
  );
}
