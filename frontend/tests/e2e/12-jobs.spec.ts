import { assertNoUnexpectedErrors, expect, test } from './fixtures';

// No dedicated Jobs page/monitoring UI exists anywhere in the frontend
// (documented N/A-through-UI). Job status IS surfaced indirectly:
// creating a run (bridged via API - no "create run" UI either, see
// 04-runs.spec.ts) implicitly creates a job, and the Dashboard's
// "Active Jobs" count is real UI reading real backend job-tracker state.
test.describe('12 jobs - no dedicated UI; Dashboard active-jobs count and real API verified', () => {
  test('the Dashboard active jobs count matches the real API, and stays consistent across a refresh', async ({
    page,
    consoleErrors,
    networkFailures,
  }) => {
    const apiDashboard = await (
      await page.request.get('http://127.0.0.1:8000/api/v1/dashboard')
    ).json();

    await page.goto('/');
    await page.waitForLoadState('networkidle');
    const bodyText = await page.textContent('body');
    expect(bodyText).toContain(String(apiDashboard.active_jobs));

    await page.reload({ waitUntil: 'networkidle' });
    const apiDashboardAfter = await (
      await page.request.get('http://127.0.0.1:8000/api/v1/dashboard')
    ).json();
    const bodyTextAfter = await page.textContent('body');
    expect(bodyTextAfter).toContain(String(apiDashboardAfter.active_jobs));

    assertNoUnexpectedErrors(consoleErrors, networkFailures);
  });

  test('GET /jobs and GET /jobs/{id} are real and reachable', async ({ request }) => {
    const listResponse = await request.get('http://127.0.0.1:8000/api/v1/jobs');
    expect(listResponse.ok()).toBe(true);

    const unknownJob = await request.get(
      'http://127.0.0.1:8000/api/v1/jobs/00000000-0000-0000-0000-000000000000'
    );
    expect(unknownJob.status()).toBe(404);
  });
});
