"use client";

import { useState } from "react";
import { Search, Play, FileCode, Check, Loader2, AlertCircle, Info } from "lucide-react";

// All workflow steps (from workflow.py)
const ALL_STEPS = [
  "fork_and_clone_repository",
  "summarize",
  "component_identification",
  "component_parsing",
  "human_verification_of_components",
  "attribute_identification",
  "attribute_parsing",
  "node_aggregator",
  "edge_identification",
  "generate_dag_yaml",
  "human_verification_of_dag",
  "config_agent",
  "notebook_agent",
  "code_editor_agent",
  "create_pr_body",
  "push_code_changes",
  "create_pull_request",
];

interface WelcomePageProps {
  githubUrl: string;
  setGithubUrl: (url: string) => void;
  detectedFiles: string[];
  selectedFiles: string[];
  setSelectedFiles: (files: string[]) => void;
  onDetectFiles: () => Promise<void>;
  onStartWorkflow: (runId?: string, startFrom?: string, configPath?: string) => Promise<void>;
  error?: string | null;
  status?: string;
  detectionConfidence?: number;
  detectionReasoning?: string;
}

export function WelcomePage({
  githubUrl,
  setGithubUrl,
  detectedFiles,
  selectedFiles,
  setSelectedFiles,
  onDetectFiles,
  onStartWorkflow,
  error,
  status,
  detectionConfidence,
  detectionReasoning,
}: WelcomePageProps) {
  const [isDetecting, setIsDetecting] = useState(false);
  const [isStarting, setIsStarting] = useState(false);
  const [runId, setRunId] = useState("");
  const [startFrom, setStartFrom] = useState("");
  const [configPath, setConfigPath] = useState("");
  const isLoading = status === "detecting" || isDetecting;

  const handleDetect = async () => {
    setIsDetecting(true);
    try {
      await onDetectFiles();
    } finally {
      setIsDetecting(false);
    }
  };

  const handleStart = async () => {
    console.log("🚀 handleStart called");
    console.log("Parameters:", { runId, startFrom, configPath });
    console.log("Selected files:", selectedFiles);

    setIsStarting(true);
    try {
      console.log("Calling onStartWorkflow...");
      await onStartWorkflow(runId || undefined, startFrom || undefined, configPath || undefined);
      console.log("onStartWorkflow completed");
    } catch (error) {
      console.error("handleStart error:", error);
    } finally {
      setIsStarting(false);
      console.log("handleStart finished");
    }
  };

  // Format step name for display
  const formatStepName = (step: string) => {
    return step.replace(/_/g, " ").replace(/\b\w/g, (l) => l.toUpperCase());
  };

  const toggleFile = (file: string) => {
    if (selectedFiles.includes(file)) {
      setSelectedFiles(selectedFiles.filter((f) => f !== file));
    } else {
      setSelectedFiles([...selectedFiles, file]);
    }
  };

  return (
    <div className="max-w-3xl mx-auto">
      {/* Header */}
      <div className="text-center mb-12">
        <h1 className="text-4xl font-bold text-gray-900 mb-4">
          Welcome to RMR Agent
        </h1>
        <p className="text-lg text-gray-600">
          Automatically refactor your ML research code into production-ready pipelines
        </p>
      </div>

      {/* GitHub URL Input */}
      <div className="bg-white rounded-xl shadow-sm border border-gray-200 p-6 mb-6">
        <label className="block text-sm font-medium text-gray-700 mb-2">
          GitHub Repository URL
        </label>
        <div className="flex gap-3">
          <input
            type="text"
            value={githubUrl}
            onChange={(e) => setGithubUrl(e.target.value)}
            placeholder="https://github.com/org/repo"
            className="flex-1 px-4 py-3 border border-gray-300 rounded-lg focus:ring-2 focus:ring-blue-500 focus:border-blue-500 outline-none transition-all"
          />
          <button
            onClick={handleDetect}
            disabled={!githubUrl || isLoading}
            className="px-6 py-3 bg-blue-600 text-white rounded-lg font-medium hover:bg-blue-700 disabled:opacity-50 disabled:cursor-not-allowed flex items-center gap-2 transition-colors"
          >
            {isLoading ? (
              <Loader2 className="w-5 h-5 animate-spin" />
            ) : (
              <Search className="w-5 h-5" />
            )}
            {isLoading ? "Detecting..." : "Detect Files"}
          </button>
        </div>
      </div>

      {/* Error Display */}
      {error && (
        <div className="bg-red-50 border border-red-200 rounded-xl p-4 mb-6">
          <div className="flex items-start gap-3">
            <AlertCircle className="w-5 h-5 text-red-500 mt-0.5 flex-shrink-0" />
            <div>
              <h3 className="font-medium text-red-800">Error</h3>
              <p className="text-sm text-red-700 mt-1">{error}</p>
            </div>
          </div>
        </div>
      )}

      {/* Detection Confidence */}
      {detectedFiles.length > 0 && detectionConfidence !== undefined && (
        <div className="bg-white rounded-xl shadow-sm border border-gray-200 p-6 mb-6">
          <div className="grid grid-cols-4 gap-4">
            <div className="col-span-1">
              <div className="text-sm text-gray-500 mb-1">Detection Confidence</div>
              <div className={`text-2xl font-bold ${
                detectionConfidence > 0.7 ? 'text-green-600' :
                detectionConfidence > 0.4 ? 'text-yellow-600' :
                'text-red-600'
              }`}>
                {Math.round(detectionConfidence * 100)}%
              </div>
            </div>
            <div className="col-span-3">
              <details className="text-sm">
                <summary className="cursor-pointer text-gray-600 hover:text-gray-900 font-medium flex items-center gap-2">
                  <Info className="w-4 h-4" />
                  AI Detection Reasoning
                </summary>
                <p className="mt-2 text-gray-600 bg-gray-50 p-3 rounded-lg">
                  {detectionReasoning || "No reasoning available"}
                </p>
              </details>
            </div>
          </div>
        </div>
      )}

      {/* Detected Files */}
      {detectedFiles.length > 0 && (
        <div className="bg-white rounded-xl shadow-sm border border-gray-200 p-6 mb-6">
          <div className="flex items-center justify-between mb-4">
            <h2 className="text-lg font-semibold text-gray-900">
              Detected ML Files
            </h2>
            <span className="text-sm text-gray-500">
              {selectedFiles.length} of {detectedFiles.length} selected
            </span>
          </div>

          <div className="space-y-2 max-h-64 overflow-auto">
            {detectedFiles.map((file) => (
              <label
                key={file}
                className="flex items-center gap-3 p-3 rounded-lg border border-gray-200 cursor-pointer hover:bg-gray-50 transition-colors"
              >
                <div
                  className={`w-5 h-5 rounded border-2 flex items-center justify-center transition-colors ${
                    selectedFiles.includes(file)
                      ? "bg-blue-600 border-blue-600"
                      : "border-gray-300"
                  }`}
                >
                  {selectedFiles.includes(file) && (
                    <Check className="w-3 h-3 text-white" />
                  )}
                </div>
                <FileCode className="w-5 h-5 text-gray-400" />
                <span className="text-sm text-gray-700 font-mono">{file}</span>
                <input
                  type="checkbox"
                  checked={selectedFiles.includes(file)}
                  onChange={() => toggleFile(file)}
                  className="sr-only"
                />
              </label>
            ))}
          </div>
        </div>
      )}

      {/* Advanced Options */}
      {selectedFiles.length > 0 && (
        <div className="bg-white rounded-xl shadow-sm border border-gray-200 p-6 mb-6">
          <details>
            <summary className="cursor-pointer text-lg font-semibold text-gray-900 hover:text-blue-600">
              Advanced Options (Optional)
            </summary>
            <div className="mt-4 space-y-4">
              {/* Run ID */}
              <div>
                <label className="block text-sm font-medium text-gray-700 mb-2">
                  Run ID
                </label>
                <input
                  type="text"
                  value={runId}
                  onChange={(e) => setRunId(e.target.value)}
                  placeholder="e.g., 1, 2, 3..."
                  className="w-full px-4 py-2 border border-gray-300 rounded-lg focus:ring-2 focus:ring-blue-500 focus:border-blue-500 outline-none transition-all"
                />
                <p className="text-xs text-gray-500 mt-1">
                  Enter an existing run ID to resume a previous workflow, or leave blank for a new run
                </p>
              </div>

              {/* Start From */}
              <div>
                <label className="block text-sm font-medium text-gray-700 mb-2">
                  Start From Step
                </label>
                <select
                  value={startFrom}
                  onChange={(e) => setStartFrom(e.target.value)}
                  className="w-full px-4 py-2 border border-gray-300 rounded-lg focus:ring-2 focus:ring-blue-500 focus:border-blue-500 outline-none transition-all"
                >
                  <option value="">Start from beginning</option>
                  {ALL_STEPS.map((step, index) => (
                    <option key={step} value={step}>
                      {index + 1}. {formatStepName(step)}
                    </option>
                  ))}
                </select>
                <p className="text-xs text-gray-500 mt-1">
                  Choose a step to start from (useful for resuming from a specific point)
                </p>
              </div>

              {/* Config File Path */}
              <div>
                <label className="block text-sm font-medium text-gray-700 mb-2">
                  Existing Config File Path
                </label>
                <input
                  type="text"
                  value={configPath}
                  onChange={(e) => setConfigPath(e.target.value)}
                  placeholder="e.g., config/environment.ini"
                  className="w-full px-4 py-2 border border-gray-300 rounded-lg focus:ring-2 focus:ring-blue-500 focus:border-blue-500 outline-none transition-all"
                />
                <p className="text-xs text-gray-500 mt-1">
                  Provide path to an existing configuration file (relative to repo root)
                </p>
              </div>
            </div>
          </details>
        </div>
      )}

      {/* Start Button */}
      {selectedFiles.length > 0 && (
        <button
          onClick={handleStart}
          disabled={isStarting}
          className="w-full py-4 bg-gradient-to-r from-blue-600 to-purple-600 text-white rounded-xl font-semibold text-lg hover:from-blue-700 hover:to-purple-700 disabled:opacity-50 disabled:cursor-not-allowed flex items-center justify-center gap-3 transition-all shadow-lg"
        >
          {isStarting ? (
            <Loader2 className="w-6 h-6 animate-spin" />
          ) : (
            <Play className="w-6 h-6" />
          )}
          Start Workflow
        </button>
      )}
    </div>
  );
}
