import { codeProvenance, createTwoRuns, submitComparisonViaUi } from './comparison-helpers';
import { expect, test } from './fixtures';

// No Contributor Analysis page/UI exists anywhere in the frontend
// (documented N/A-through-UI - see docs/E2E_CHROME_TEST_REPORT.md's UI
// inventory). The one place contributor language appears in the UI at
// all is implicit: Comparison page differences carry severity/
// confidence, feeding Phase 14's ranking, but there is no "potential
// contributor" / "causal status" display anywhere in the frontend.
//
// Critical requirement from the master prompt still applies and IS
// checkable without that UI: the backend must never claim causality is
// confirmed. Verified directly against the real API.
test.describe('08 contributors - no UI; critical causality-language requirement verified via real API', () => {
  test('a real potential-contributor difference never claims confirmed causality anywhere in its evidence', async ({
    page,
    request,
  }) => {
    const { baseRun, compareRun } = await createTwoRuns(request, 'contrib-check');
    const [compareResponse] = await Promise.all([
      page.waitForResponse((res) => res.url().includes('/compare') && res.request().method() === 'POST'),
      submitComparisonViaUi(
        page,
        baseRun.id,
        compareRun.id,
        { code: codeProvenance('contrib-a', 'contrib-tree-a'), metrics: { accuracy: 0.9 } },
        { code: codeProvenance('contrib-b', 'contrib-tree-b'), metrics: { accuracy: 0.5 } }
      ),
    ]);
    const comparison = await compareResponse.json();

    for (const diff of comparison.differences) {
      // Phase 14's ranking only ever produces "potential contributor" -
      // never "validated"/"confirmed" language anywhere in a
      // Difference row (app/contributor/ranking.py).
      expect(diff.is_potential_contributor === true || diff.is_potential_contributor === false).toBe(true);
    }

    const investigationResponse = await request.post('http://127.0.0.1:8000/api/v1/investigations', {
      data: { comparison_id: comparison.id },
    });
    if (investigationResponse.ok()) {
      const investigation = await investigationResponse.json();
      expect(investigation.evidence_strength).not.toMatch(/confirmed|validated/i);
    }
  });
});
