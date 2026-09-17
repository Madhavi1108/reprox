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

// FastAPI's own native validation-error shape (emitted directly by
// Pydantic/FastAPI for request-schema violations - e.g. a failing
// field_validator like ProjectCreate's slug pattern - distinct from
// app/core/errors.py's ReproxError handler, which only wraps
// application-raised errors like NotFoundError/ConflictError).
export interface FastApiValidationErrorBody {
  detail: Array<{ loc: (string | number)[]; msg: string; type: string }>;
}

export type ComparisonStatus = "SAME" | "DIFFERENT" | "UNKNOWN" | "PARTIALLY_MATCHING" | "NOT_COMPARABLE";

export type DifferenceCategory = "CODE" | "DATASET" | "ENVIRONMENT" | "CONFIGURATION" | "RANDOMNESS" | "METRICS";

export type Severity = "LOW" | "MEDIUM" | "HIGH" | "CRITICAL";
export type Confidence = "HIGH" | "MEDIUM" | "LOW";

export type ReproducibilityClassification =
  | "EXACTLY_REPRODUCIBLE"
  | "REPRODUCIBLE_WITHIN_TOLERANCE"
  | "CONDITIONALLY_REPRODUCIBLE"
  | "PARTIALLY_REPRODUCIBLE"
  | "NOT_REPRODUCIBLE"
  | "INSUFFICIENT_EVIDENCE"
  | "NOT_COMPARABLE";

export interface Difference {
  id: string;
  category: DifferenceCategory;
  field: string;
  old_value: string | null;
  new_value: string | null;
  difference_type: string;
  evidence_source: string;
  severity: Severity;
  confidence: Confidence;
  is_potential_contributor: boolean;
}

export interface Comparison {
  id: string;
  base_run_id: string;
  compare_run_id: string;
  code_status: ComparisonStatus;
  dataset_status: ComparisonStatus;
  environment_status: ComparisonStatus;
  configuration_status: ComparisonStatus;
  randomness_status: ComparisonStatus;
  metrics_status: ComparisonStatus;
  comparison_algorithm_version: string;
  created_at: string;
  differences: Difference[];
}

export interface Reproducibility {
  id: string;
  comparison_id: string;
  classification: ReproducibilityClassification;
  rationale: Record<string, unknown>;
  algorithm_version: string;
  created_at: string;
}

export interface RunProvenanceIn {
  code?: Record<string, unknown> | null;
  dataset?: Record<string, unknown> | null;
  environment?: Record<string, unknown> | null;
  configuration?: Record<string, unknown> | null;
  randomness?: Record<string, unknown> | null;
  metrics?: Record<string, number> | null;
}

export interface CompareRequest {
  compare_run_id: string;
  base?: RunProvenanceIn | null;
  compare?: RunProvenanceIn | null;
}
