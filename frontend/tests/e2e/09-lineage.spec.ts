import { createTwoRuns, submitComparisonViaUi } from './comparison-helpers';
import { expect, test } from './fixtures';

// No Lineage/Provenance Explorer graph UI exists anywhere in the
// frontend (documented N/A-through-UI). Phase 15's lineage graph is
// real backend logic reachable only via GET /api/v1/lineage/{run_id} -
// verified directly here, not through a UI that doesn't exist.
test.describe('09 lineage - no graph UI; real backend endpoint verified directly', () => {
  test('a real COMPARES_WITH edge exists for two runs just compared', async ({ page, request }) => {
    const { baseRun, compareRun } = await createTwoRuns(request, 'lineage-check');
    await submitComparisonViaUi(page, baseRun.id, compareRun.id, null, null);

    const lineageResponse = await request.get(`http://127.0.0.1:8000/api/v1/lineage/${baseRun.id}`);
    expect(lineageResponse.ok()).toBe(true);
    const lineage = await lineageResponse.json();
    const hasComparesWith = lineage.edges.some(
      (edge: { from_run_id: string; to_run_id: string; edge_type: string }) =>
        edge.from_run_id === baseRun.id && edge.to_run_id === compareRun.id && edge.edge_type === 'COMPARES_WITH'
    );
    expect(hasComparesWith).toBe(true);
  });
});
