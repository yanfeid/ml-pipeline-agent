// Use Next.js rewrite proxy to avoid CORS issues
// In production, set NEXT_PUBLIC_API_URL to your deployed API endpoint
const API_BASE = process.env.NEXT_PUBLIC_API_URL || "/api";

export interface FileDetectionResponse {
  ml_files: string[];
  confidence: number;
  reasoning: string;
  repo_name: string;
  local_repo_path: string;
  status: string;
  error?: string;
}

export interface WorkflowStatus {
  step: string;
  status: string;
  error?: string;
  component_parsing?: any[];
  verified_components?: any[];
  dag_yaml?: string;
  verified_dag?: string;
  pr_url?: string;
  [key: string]: any;
}

export interface ComponentData {
  [componentName: string]: {
    file_name: string;
    line_range: string;
    evidence?: any[];
    why_this_is_separate?: string;
  };
}

export const api = {
  // Detect ML files in a repository
  async detectMLFiles(githubUrl: string): Promise<FileDetectionResponse> {
    const response = await fetch(`${API_BASE}/detect-ml-files`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ github_url: githubUrl }),
    });

    if (!response.ok) {
      throw new Error(`API error: ${response.status}`);
    }

    return response.json();
  },

  // Start a new workflow
  async startWorkflow(
    repoName: string,
    githubUrl: string,
    inputFiles: string[],
    runId?: string,
    startFrom?: string,
    existingConfigPath?: string
  ): Promise<{ repo_name: string; run_id: string; step: string; status: string }> {
    // Build URL with optional run_id
    let url = `${API_BASE}/run-workflow?repo_name=${repoName}`;
    if (runId) {
      url += `&run_id=${runId}`;
    }

    // Build request body
    const body: any = {
      github_url: githubUrl,
      input_files: inputFiles,
    };

    if (runId) {
      body.run_id = runId;
    }

    if (startFrom) {
      body.start_from = startFrom;
    }

    if (existingConfigPath) {
      body.existing_config_path = existingConfigPath;
    }

    const response = await fetch(url, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(body),
    });

    if (!response.ok) {
      throw new Error(`API error: ${response.status}`);
    }

    return response.json();
  },

  // Get workflow status
  async getWorkflowStatus(repoName: string, runId: string): Promise<WorkflowStatus> {
    const response = await fetch(
      `${API_BASE}/workflow-status/${repoName}?run_id=${runId}`
    );

    if (!response.ok) {
      throw new Error(`API error: ${response.status}`);
    }

    return response.json();
  },

  // Submit component verification
  async submitComponentVerification(
    repoName: string,
    runId: string,
    verifiedComponents: any[]
  ): Promise<any> {
    const response = await fetch(`${API_BASE}/run-workflow?repo_name=${repoName}&run_id=${runId}`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ verified_components: verifiedComponents }),
    });

    if (!response.ok) {
      throw new Error(`API error: ${response.status}`);
    }

    return response.json();
  },

  // Submit DAG verification
  async submitDagVerification(
    repoName: string,
    runId: string,
    verifiedDag: string,
    githubUrl: string,
    inputFiles: string[]
  ): Promise<any> {
    const response = await fetch(`${API_BASE}/run-workflow?repo_name=${repoName}&run_id=${runId}`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({
        verified_dag: verifiedDag,
        github_url: githubUrl,
        input_files: inputFiles,
      }),
    });

    if (!response.ok) {
      throw new Error(`API error: ${response.status}`);
    }

    return response.json();
  },

  // Cancel workflow
  async cancelWorkflow(repoName: string, runId: string): Promise<any> {
    const response = await fetch(
      `${API_BASE}/cancel-workflow/${repoName}?run_id=${runId}`,
      { method: "POST" }
    );

    if (!response.ok) {
      throw new Error(`API error: ${response.status}`);
    }

    return response.json();
  },
};
