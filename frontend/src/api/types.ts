// Hand-written TypeScript types mirroring backend/app/schemas/*.py.
// Not code-generated - kept in sync manually, matching this project's
// scope-conscious style elsewhere (no OpenAPI-codegen dependency added
// for 3 pages' worth of endpoints).

export interface Page<T> {
  items: T[];
  total: number;
  limit: number;
  offset: number;
}

export interface Project {
  id: string;
  name: string;
  slug: string;
  description: string | null;
  owner_user_id: string;
  created_at: string;
  updated_at: string;
}

export interface ProjectCreate {
  name: string;
  slug: string;
  description?: string | null;
}

export interface Experiment {
  id: string;
  project_id: string;
  name: string;
  description: string | null;
  workload_type: string;
  entrypoint_script: string;
  created_at: string;
  updated_at: string;
}

export interface ExperimentCreate {
  project_id: string;
  name: string;
  description?: string | null;
  workload_type?: string;
  entrypoint_script: string;
}

export interface RecentExperiment {
  id: string;
  name: string;
  project_id: string;
}

export interface Dashboard {
  total_projects: number;
  total_experiments: number;
  total_runs: number;
  reproducible_runs: number;
  partial_reproductions: number;
  failed_reproductions: number;
  insufficient_evidence: number;
  active_jobs: number;
  recent_experiments: RecentExperiment[];
}

export interface ApiErrorBody {
  error: {
    code: string;
    message: string;
    details: Record<string, unknown>;
  };
}
