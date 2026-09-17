import { codeProvenance, createTwoRuns, submitComparisonViaUi } from './comparison-helpers';
import { expect, test } from './fixtures';

// No Investigation Center UI exists anywhere in the frontend (documented
// N/A-through-UI). The master prompt's critical requirement -
// "verify a NEW run is created, verify original run is untouched" -
// doesn't apply as stated either: Phase 22 only generates an
// investigation *plan* (what to hold constant / what to vary), it does
// not execute a controlled rerun or create a new run at all
// (docs/INVESTIGATION_ENGINE.md - by design, not a gap this pass
// introduces). What IS real and checkable: the plan itself, and that the
// original run's data is never mutated by requesting one.
test.describe('10 investigation - no UI; plan generation verified via real API (no rerun-execution exists)', () => {
  test('generating an investigation plan never mutates the original run', async ({ page, request }) => {
    const { baseRun, compareRun } = await createTwoRuns(request, 'investigation-check');
    const beforeResponse = await request.get(`http://127.0.0.1:8000/api/v1/runs/${baseRun.id}`);
    const before = await beforeResponse.json();

    const [compareResponse] = await Promise.all([
      page.waitForResponse((res) => res.url().includes('/compare') && res.request().method() === 'POST'),
      submitComparisonViaUi(
        page,
        baseRun.id,
        compareRun.id,
        { code: codeProvenance('inv-a', 'inv-tree-a'), metrics: { accuracy: 0.95 } },
        { code: codeProvenance('inv-b', 'inv-tree-b'), metrics: { accuracy: 0.4 } }
      ),
    ]);
    const comparison = await compareResponse.json();

    const investigationResponse = await request.post('http://127.0.0.1:8000/api/v1/investigations', {
      data: { comparison_id: comparison.id },
    });
    expect(investigationResponse.ok()).toBe(true);
    const plan = await investigationResponse.json();
    expect(plan.base_run_id).toBe(baseRun.id);
    expect(plan.held_constant.length).toBeGreaterThan(0);

    const afterResponse = await request.get(`http://127.0.0.1:8000/api/v1/runs/${baseRun.id}`);
    const after = await afterResponse.json();
    expect(after).toEqual(before);
  });
});
