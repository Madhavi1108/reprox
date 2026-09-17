import { Page } from '@playwright/test';
import { createExperimentApi, createProjectApi, createRunApi } from './api-bridge';
import { API_BASE } from './fixtures';
import type { APIRequestContext } from '@playwright/test';

export function uniqueSlug(prefix: string) {
  return `${prefix}-${Date.now()}-${Math.floor(Math.random() * 10000)}`;
}

/** Creates a real project + experiment + 2 real runs via the API bridge
 * (see api-bridge.ts's docstring for why - no "create run" UI exists). */
export async function createTwoRuns(request: APIRequestContext, label: string) {
  const slug = uniqueSlug(label);
  const project = await createProjectApi(request, `${slug} project`, slug);
  const experiment = await createExperimentApi(request, project.id, `${slug} experiment`);
  const baseRun = await createRunApi(request, experiment.id);
  const compareRun = await createRunApi(request, experiment.id);
  return { project, experiment, baseRun, compareRun };
}

/** Drives the REAL Comparison page's UI: fills both run IDs, opens the
 * (real, existing) advanced-provenance JSON section, fills both
 * payloads, and submits - a genuine UI interaction, not an API call. */
export async function submitComparisonViaUi(
  page: Page,
  baseRunId: string,
  compareRunId: string,
  baseProvenance: Record<string, unknown> | null,
  compareProvenance: Record<string, unknown> | null
) {
  await page.goto('/compare');
  await page.getByLabel(/base run id/i).fill(baseRunId);
  await page.getByLabel(/compare run id/i).fill(compareRunId);

  if (baseProvenance || compareProvenance) {
    await page.getByRole('button', { name: /show advanced provenance payloads/i }).click();
    if (baseProvenance) {
      await page.getByLabel(/base provenance json/i).fill(JSON.stringify(baseProvenance));
    }
    if (compareProvenance) {
      await page.getByLabel(/compare provenance json/i).fill(JSON.stringify(compareProvenance));
    }
  }

  await page.getByRole('button', { name: /compare runs/i }).click();
}

export function codeProvenance(commitSha: string, treeHash: string) {
  return {
    vcs_present: true,
    git_commit_sha: commitSha,
    git_branch: 'main',
    is_dirty: false,
    is_detached_head: false,
    is_shallow_clone: false,
    tree_fingerprint_hash: treeHash,
    fingerprint_version: '1.0.0',
  };
}

// Field names match app/provenance/dataset.py's DatasetProvenance
// dataclass exactly - the backend constructs it via **blob, so every
// required field must be present or the request 422s.
export function datasetProvenance(contentHash: string, rowCount = 1000) {
  return {
    content_hash: contentHash,
    file_size_bytes: 1_048_576,
    row_count: rowCount,
    column_count: 10,
    schema: { feature_1: 'float64', label: 'int64' },
  };
}

// Field names match app/provenance/configuration.py's
// ConfigurationProvenance dataclass. The comparator's fast path uses
// configuration_fingerprint_hash, so that's the field that must differ
// to signal a real configuration change.
export function configurationProvenance(fingerprintHash: string, raw: Record<string, unknown>) {
  return {
    raw,
    canonical_json: JSON.stringify(raw),
    configuration_fingerprint_hash: fingerprintHash,
  };
}

// Field names match app/provenance/randomness.py's RandomnessProvenance
// dataclass and app/db/models/enums.py's DeterminismIntent/
// DeterminismClassification.
export function randomnessProvenance(seed: number, fingerprintHash: string) {
  return {
    python_seed: seed,
    numpy_seed: seed,
    other_seeds: {},
    determinism_intent: 'REQUESTED',
    determinism_classification: 'DETERMINISTIC',
    randomness_fingerprint_hash: fingerprintHash,
  };
}

export async function getReproducibilityApi(request: APIRequestContext, comparisonId: string) {
  const res = await request.get(`${API_BASE}/reproducibility/${comparisonId}`);
  if (!res.ok()) throw new Error(`getReproducibilityApi failed: ${res.status()}`);
  return res.json();
}
