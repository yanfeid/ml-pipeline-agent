"use client";

import { useState, useCallback, useEffect, useRef } from "react";
import { api, WorkflowStatus } from "@/lib/api";

interface WorkflowState {
  step: string;
  status: string;
  repoName: string;
  runId: string;
  githubUrl: string;
  selectedFiles: string[];
  detectedFiles: string[];
  components: any[];
  dagYaml: string;
  prUrl: string;
  prBody: string;
  error: string | null;
  cleanedCode: { [fileName: string]: string };
  detectionConfidence: number;
  detectionReasoning: string;
}

export function useWorkflow() {
  const [state, setState] = useState<WorkflowState>({
    step: "",
    status: "idle",
    repoName: "",
    runId: "",
    githubUrl: "",
    selectedFiles: [],
    detectedFiles: [],
    components: [],
    dagYaml: "",
    prUrl: "",
    prBody: "",
    error: null,
    cleanedCode: {},
    detectionConfidence: 0,
    detectionReasoning: "",
  });

  const pollingRef = useRef<NodeJS.Timeout | null>(null);

  // Helper to update state partially
  const updateState = useCallback((updates: Partial<WorkflowState>) => {
    setState((prev) => ({ ...prev, ...updates }));
  }, []);

  // Setters for form inputs
  const setGithubUrl = useCallback((url: string) => {
    updateState({ githubUrl: url, detectedFiles: [], selectedFiles: [] });
  }, [updateState]);

  const setSelectedFiles = useCallback((files: string[]) => {
    updateState({ selectedFiles: files });
  }, [updateState]);

  // Detect ML files
  const detectFiles = useCallback(async () => {
    if (!state.githubUrl) {
      console.error("detectFiles: no githubUrl");
      return;
    }

    try {
      console.log("detectFiles: calling API with URL:", state.githubUrl);
      updateState({ status: "detecting", error: null });
      const result = await api.detectMLFiles(state.githubUrl);
      console.log("detectFiles: API result:", result);

      if (result.status === "success") {
        console.log("detectFiles: success, repoName =", result.repo_name);
        updateState({
          detectedFiles: result.ml_files,
          selectedFiles: result.ml_files,
          repoName: result.repo_name,
          status: "idle",
          detectionConfidence: result.confidence,
          detectionReasoning: result.reasoning,
        });
      } else {
        console.error("detectFiles: failed:", result.reasoning);
        updateState({
          error: result.reasoning || "Failed to detect files",
          status: "idle",
        });
      }
    } catch (err) {
      console.error("detectFiles: exception:", err);
      updateState({
        error: err instanceof Error ? err.message : "Failed to detect files",
        status: "idle",
      });
    }
  }, [state.githubUrl, updateState]);

  // Track polling error count
  const pollingErrorCountRef = useRef<number>(0);
  const MAX_POLLING_ERRORS = 5;

  // Poll for workflow status
  const startPolling = useCallback((repoName: string, runId: string) => {
    if (pollingRef.current) {
      clearInterval(pollingRef.current);
    }

    // Reset error count when starting new polling
    pollingErrorCountRef.current = 0;

    pollingRef.current = setInterval(async () => {
      try {
        const status = await api.getWorkflowStatus(repoName, runId);
        console.log("📡 Poll result:", { step: status.step, status: status.status, hasComponents: !!(status.component_parsing?.length || status.verified_components?.length) });

        // Reset error count on successful poll
        pollingErrorCountRef.current = 0;

        updateState({
          step: status.step,
          status: status.status,
          components: status.component_parsing || status.verified_components || [],
          dagYaml: status.dag_yaml || status.verified_dag || "",
          prUrl: status.pr_url || "",
          prBody: status.pr_body || "",
          error: status.error || null,
          cleanedCode: status.cleaned_code || {},
        });

        // Stop polling on completion, failure, or human verification steps
        if (
          status.step === "complete" ||
          status.status === "failed" ||
          status.status === "cancelled" ||
          status.step === "human_verification_of_components" ||
          status.step === "human_verification_of_dag"
        ) {
          console.log("🛑 Stopping polling at step:", status.step);
          if (pollingRef.current) {
            clearInterval(pollingRef.current);
            pollingRef.current = null;
          }
        }
      } catch (err) {
        console.error("Polling error:", err);
        pollingErrorCountRef.current += 1;

        // Stop polling after too many consecutive errors
        if (pollingErrorCountRef.current >= MAX_POLLING_ERRORS) {
          console.error(`Stopping polling after ${MAX_POLLING_ERRORS} consecutive errors`);
          if (pollingRef.current) {
            clearInterval(pollingRef.current);
            pollingRef.current = null;
          }
          updateState({
            status: "failed",
            error: `Lost connection to server after ${MAX_POLLING_ERRORS} failed attempts. Please try again.`,
          });
        }
      }
    }, 2000);
  }, [updateState]);

  // Start workflow
  const startWorkflow = useCallback(async (
    runId?: string,
    startFrom?: string,
    configPath?: string
  ) => {
    console.log("startWorkflow called with:", { runId, startFrom, configPath });
    console.log("Current state:", { repoName: state.repoName, selectedFiles: state.selectedFiles });

    if (!state.repoName || state.selectedFiles.length === 0) {
      console.error("Cannot start workflow: missing repoName or selectedFiles");
      return;
    }

    try {
      updateState({ status: "starting", error: null });
      console.log("Calling API startWorkflow...");

      const result = await api.startWorkflow(
        state.repoName,
        state.githubUrl,
        state.selectedFiles,
        runId,
        startFrom,
        configPath
      );

      console.log("API response:", result);

      const newState = {
        runId: result.run_id,
        step: result.step,
        status: result.status,
      };
      console.log("Updating state with:", newState);
      updateState(newState);

      console.log("State should now be:", {
        ...state,
        ...newState
      });

      // Start polling for status
      console.log("Starting polling for", state.repoName, result.run_id);
      startPolling(state.repoName, result.run_id);
    } catch (err) {
      console.error("startWorkflow error:", err);
      updateState({
        error: err instanceof Error ? err.message : "Failed to start workflow",
        status: "idle",
      });
    }
  }, [state.repoName, state.githubUrl, state.selectedFiles, updateState, startPolling]);

  // Submit component verification
  const submitComponentVerification = useCallback(async (verifiedComponents: any[]) => {
    try {
      updateState({ status: "submitting" });

      await api.submitComponentVerification(
        state.repoName,
        state.runId,
        verifiedComponents
      );

      // Resume polling
      startPolling(state.repoName, state.runId);
    } catch (err) {
      updateState({
        error: err instanceof Error ? err.message : "Failed to submit verification",
      });
    }
  }, [state.repoName, state.runId, updateState, startPolling]);

  // Submit DAG verification
  const submitDagVerification = useCallback(async (
    verifiedDag: string,
    githubUrl: string,
    inputFiles: string[]
  ) => {
    try {
      updateState({ status: "submitting" });

      await api.submitDagVerification(
        state.repoName,
        state.runId,
        verifiedDag,
        githubUrl,
        inputFiles
      );

      // Resume polling
      startPolling(state.repoName, state.runId);
    } catch (err) {
      updateState({
        error: err instanceof Error ? err.message : "Failed to submit DAG verification",
      });
    }
  }, [state.repoName, state.runId, updateState, startPolling]);

  // Cancel workflow
  const cancelWorkflow = useCallback(async () => {
    if (!state.repoName || !state.runId) return;

    try {
      await api.cancelWorkflow(state.repoName, state.runId);

      if (pollingRef.current) {
        clearInterval(pollingRef.current);
        pollingRef.current = null;
      }

      // Reset to initial state
      setState({
        step: "",
        status: "idle",
        repoName: "",
        runId: "",
        githubUrl: state.githubUrl, // Keep the GitHub URL
        selectedFiles: [],
        detectedFiles: state.detectedFiles, // Keep detected files
        components: [],
        dagYaml: "",
        prUrl: "",
        prBody: "",
        error: null,
        cleanedCode: {},
        detectionConfidence: state.detectionConfidence,
        detectionReasoning: state.detectionReasoning,
      });
    } catch (err) {
      console.error("Cancel error:", err);
    }
  }, [state.repoName, state.runId, state.githubUrl, state.detectedFiles, state.detectionConfidence, state.detectionReasoning]);

  // Reset workflow
  const resetWorkflow = useCallback(() => {
    if (pollingRef.current) {
      clearInterval(pollingRef.current);
      pollingRef.current = null;
    }

    setState({
      step: "",
      status: "idle",
      repoName: "",
      runId: "",
      githubUrl: "",
      selectedFiles: [],
      detectedFiles: [],
      components: [],
      dagYaml: "",
      prUrl: "",
      prBody: "",
      error: null,
      cleanedCode: {},
      detectionConfidence: 0,
      detectionReasoning: "",
    });
  }, []);

  // Cleanup on unmount
  useEffect(() => {
    return () => {
      if (pollingRef.current) {
        clearInterval(pollingRef.current);
      }
    };
  }, []);

  return {
    ...state,
    setGithubUrl,
    setSelectedFiles,
    detectFiles,
    startWorkflow,
    submitComponentVerification,
    submitDagVerification,
    cancelWorkflow,
    resetWorkflow,
  };
}
