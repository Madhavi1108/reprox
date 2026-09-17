import { codeProvenance, createTwoRuns, submitComparisonViaUi } from './comparison-helpers';
import { expect, test } from './fixtures';

// There is no dedicated Provenance Explorer page anywhere in REPROX's
// frontend (documented N/A-through-UI, see
// docs/E2E_CHROME_TEST_REPORT.md's UI inventory). The Comparison page's
// per-category sections (Code/Dataset/Environment/Configuration/
// Randomness/Metrics) are the only place provenance is genuinely shown
// through the UI - tested here for real, against the real backend.
test.describe('05 provenance - no dedicated explorer page; tested via Comparison page sections', () => {
  test('without any inline provenance, every category honestly shows NOT_COMPARABLE', async ({ page, request }) => {
    const { baseRun, compareRun } = await createTwoRuns(request, 'prov-none');
    await submitComparisonViaUi(page, baseRun.id, compareRun.id, null, null);

    for (const label of ['Code', 'Dataset', 'Environment', 'Configuration', 'Randomness', 'Metrics']) {
      const headerRow = page.getByRole('heading', { name: label, exact: true }).locator('..');
      await expect(headerRow.getByText('NOT_COMPARABLE')).toBeVisible();
    }
  });

  test('real inline code provenance renders a real Code section with SAME status', async ({ page, request }) => {
    const { baseRun, compareRun } = await createTwoRuns(request, 'prov-code-same');
    const same = codeProvenance('abc123', 'hash-same');
    await submitComparisonViaUi(page, baseRun.id, compareRun.id, { code: same }, { code: same });

    const headerRow = page.getByRole('heading', { name: 'Code', exact: true }).locator('..');
    await expect(headerRow.getByText('SAME')).toBeVisible();
  });
});
