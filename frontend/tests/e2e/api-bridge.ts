// Direct-API helpers used ONLY to bridge workflow steps that have no UI
// at all (there is no "create run"/"execute"/"generate report" button
// anywhere in the 4 real pages - see docs/E2E_CHROME_TEST_REPORT.md).
// Every step that DOES have UI is driven through the real browser
// elsewhere in this suite, never through these helpers.
import type { APIRequestContext } from '@playwright/test';
import { API_BASE } from './fixtures';

export async function createProjectApi(request: APIRequestContext, name: string, slug: string) {
  const res = await request.post(`${API_BASE}/projects`, { data: { name, slug } });
  if (!res.ok()) throw new Error(`createProjectApi failed: ${res.status()} ${await res.text()}`);
  return res.json();
}

export async function createExperimentApi(
  request: APIRequestContext,
  projectId: string,
  name: string,
  entrypointScript = 'train.py'
) {
  const res = await request.post(`${API_BASE}/experiments`, {
    data: { project_id: projectId, name, entrypoint_script: entrypointScript },
  });
  if (!res.ok()) throw new Error(`createExperimentApi failed: ${res.status()} ${await res.text()}`);
  return res.json();
}

export async function createRunApi(request: APIRequestContext, experimentId: string) {
  const res = await request.post(`${API_BASE}/experiments/${experimentId}/runs`, { data: {} });
  if (!res.ok()) throw new Error(`createRunApi failed: ${res.status()} ${await res.text()}`);
  const body = await res.json();
  return body.run as { id: string; status: string };
}

export async function getReportApi(request: APIRequestContext, comparisonId: string) {
  const res = await request.get(`${API_BASE}/reports/${comparisonId}`);
  if (!res.ok()) throw new Error(`getReportApi failed: ${res.status()} ${await res.text()}`);
  return res.json();
}
