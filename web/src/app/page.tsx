"use client";

import { useState } from "react";
import { Sidebar } from "@/components/Sidebar";
import { WelcomePage } from "@/components/WelcomePage";
import { WorkflowProgress } from "@/components/WorkflowProgress";
import { ComponentVerification } from "@/components/ComponentVerification";
import { DagVerification } from "@/components/DagVerification";
import { ResultsPage } from "@/components/ResultsPage";
import { useWorkflow } from "@/hooks/useWorkflow";

export default function Home() {
  const {
    step,
    status,
    repoName,
    runId,
    githubUrl,
    setGithubUrl,
    selectedFiles,
    setSelectedFiles,
    detectedFiles,
    components,
    dagYaml,
    prUrl,
    prBody,
    error,
    cleanedCode,
    detectionConfidence,
    detectionReasoning,
    detectFiles,
    startWorkflow,
    submitComponentVerification,
    submitDagVerification,
    cancelWorkflow,
    resetWorkflow,
  } = useWorkflow();

  // Determine which view to show based on workflow state
  const renderMainContent = () => {
    console.log("🎯 renderMainContent - Current state:", { status, step, repoName, runId });

    if (!status || status === "idle" || status === "detecting") {
      console.log("→ Showing WelcomePage");
      return (
        <WelcomePage
          githubUrl={githubUrl}
          setGithubUrl={setGithubUrl}
          detectedFiles={detectedFiles}
          selectedFiles={selectedFiles}
          setSelectedFiles={setSelectedFiles}
          onDetectFiles={detectFiles}
          onStartWorkflow={startWorkflow}
          error={error}
          status={status}
          detectionConfidence={detectionConfidence}
          detectionReasoning={detectionReasoning}
        />
      );
    }

    if (step === "human_verification_of_components") {
      console.log("→ Showing ComponentVerification");
      return (
        <ComponentVerification
          components={components}
          cleanedCode={cleanedCode}
          repoName={repoName}
          onSubmit={submitComponentVerification}
          onCancel={cancelWorkflow}
        />
      );
    }

    if (step === "human_verification_of_dag") {
      console.log("→ Showing DagVerification");
      return (
        <DagVerification
          dagYaml={dagYaml}
          repoName={repoName}
          runId={runId}
          onSubmit={submitDagVerification}
          onCancel={cancelWorkflow}
          githubUrl={githubUrl}
          inputFiles={selectedFiles}
        />
      );
    }

    if (step === "complete") {
      console.log("→ Showing ResultsPage");
      return (
        <ResultsPage
          prUrl={prUrl}
          prBody={prBody}
          repoName={repoName}
          runId={runId}
          onReset={resetWorkflow}
        />
      );
    }

    // Default: show workflow progress
    console.log("→ Showing WorkflowProgress (default)");
    return (
      <WorkflowProgress
        step={step}
        status={status}
        error={error}
        onCancel={cancelWorkflow}
      />
    );
  };

  return (
    <div className="flex h-screen">
      <Sidebar
        repoName={repoName}
        runId={runId}
        currentStep={step}
        status={status}
      />
      <main className="flex-1 overflow-auto p-8">
        {renderMainContent()}
      </main>
    </div>
  );
}
