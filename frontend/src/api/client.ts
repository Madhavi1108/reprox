import type {
  ApiErrorBody,
  Comparison,
  CompareRequest,
  Dashboard,
  Experiment,
  ExperimentCreate,
  Page,
  Project,
  ProjectCreate,
  Reproducibility,
} from "./types";

const API_BASE = "/api/v1";

export class ApiError extends Error {
  code: string;
  details: Record<string, unknown>;

  constructor(code: string, message: string, details: Record<string, unknown>) {
    super(message);
    this.code = code;
    this.details = details;
  }
}

async function request<T>(path: string, init?: RequestInit): Promise<T> {
  let response: Response;
  try {
    response = await fetch(`${API_BASE}${path}`, {
      headers: { "Content-Type": "application/json" },
      ...init,
    });
  } catch {
    throw new ApiError("network_error", "Could not reach the REPROX API.", {});
  }

  if (!response.ok) {
    let body: ApiErrorBody | null = null;
    try {
      body = await response.json();
    } catch {
      // response wasn't JSON - fall through to the generic error below
    }
    if (body?.error) {
      throw new ApiError(body.error.code, body.error.message, body.error.details);
    }
    throw new ApiError("http_error", `Request failed with status ${response.status}`, {});
  }

  return response.json() as Promise<T>;
}

export function getDashboard(): Promise<Dashboard> {
  return request<Dashboard>("/dashboard");
}

export function listProjects(limit = 20, offset = 0): Promise<Page<Project>> {
  return request<Page<Project>>(`/projects?limit=${limit}&offset=${offset}`);
}

export function createProject(payload: ProjectCreate): Promise<Project> {
  return request<Project>("/projects", { method: "POST", body: JSON.stringify(payload) });
}

export function listExperiments(limit = 20, offset = 0): Promise<Page<Experiment>> {
  return request<Page<Experiment>>(`/experiments?limit=${limit}&offset=${offset}`);
}

export function createExperiment(payload: ExperimentCreate): Promise<Experiment> {
  return request<Experiment>("/experiments", { method: "POST", body: JSON.stringify(payload) });
}

export function compareRuns(runId: string, payload: CompareRequest): Promise<Comparison> {
  return request<Comparison>(`/runs/${runId}/compare`, { method: "POST", body: JSON.stringify(payload) });
}

export function getComparison(comparisonId: string): Promise<Comparison> {
  return request<Comparison>(`/comparisons/${comparisonId}`);
}

export function getReproducibility(comparisonId: string): Promise<Reproducibility> {
  return request<Reproducibility>(`/reproducibility/${comparisonId}`);
}
