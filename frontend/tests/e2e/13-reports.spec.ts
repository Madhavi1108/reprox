import { codeProvenance, createTwoRuns, submitComparisonViaUi } from './comparison-helpers';
import { expect, test } from './fixtures';

// No Reports page or download button exists anywhere in the frontend
// (documented N/A-through-UI). GET /api/v1/reports/{id} and
// GET /api/v1/exports/excel are real and verified directly - the same
// endpoints docs/BACKEND_TEST_REPORT.md already exercised live, re-
// confirmed here in the context of a comparison this suite's own UI
// interactions actually produced.
test.describe('13 reports - no UI/download button; real report + Excel export verified directly', () => {
  test('a real report contains real experiment/run/provenance/classification content', async ({ page, request }) => {
    const { baseRun, compareRun, experiment } = await createTwoRuns(request, 'report-check');
    const [compareResponse] = await Promise.all([
      page.waitForResponse((res) => res.url().includes('/compare') && res.request().method() === 'POST'),
      submitComparisonViaUi(
        page,
        baseRun.id,
        compareRun.id,
        { code: codeProvenance('report-a', 'report-tree-a'), metrics: { accuracy: 0.9 } },
        { code: codeProvenance('report-b', 'report-tree-b'), metrics: { accuracy: 0.6 } }
      ),
    ]);
    const comparison = await compareResponse.json();

    const reportResponse = await request.get(`http://127.0.0.1:8000/api/v1/reports/${comparison.id}`);
    expect(reportResponse.ok()).toBe(true);
    const report = await reportResponse.json();

    expect(report.comparison_id).toBe(comparison.id);
    expect(report.experiment.id).toBe(experiment.id);
    expect(report.original_run.id).toBe(baseRun.id);
    expect(report.reproduction_run.id).toBe(compareRun.id);
    expect(Array.isArray(report.differences)).toBe(true);
    expect(Array.isArray(report.limitations)).toBe(true);
    expect(report.reproducibility.classification).toBeTruthy();
  });

  test('the Excel export is a real, downloadable, non-empty spreadsheet file', async ({ request }) => {
    const response = await request.get('http://127.0.0.1:8000/api/v1/exports/excel');
    expect(response.ok()).toBe(true);
    expect(response.headers()['content-type']).toContain('spreadsheetml');
    const body = await response.body();
    expect(body.length).toBeGreaterThan(1000);
    // A real .xlsx is a real zip archive - starts with the PK signature.
    expect(body.subarray(0, 2).toString('utf-8')).toBe('PK');
  });
});
