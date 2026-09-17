import {
  codeProvenance,
  configurationProvenance,
  createTwoRuns,
  datasetProvenance,
  randomnessProvenance,
  submitComparisonViaUi,
} from './comparison-helpers';
import { expect, test } from './fixtures';

// Master prompt Phase 12's Scenario A-G difference matrix, driven end-
// to-end through the REAL Comparison page (the "advanced provenance
// JSON" inputs genuinely exist there) against the REAL backend. Category
// statuses (SAME/DIFFERENT) are deterministic per
// docs/COMPARISON_ENGINE.md, so those ARE asserted directly; the overall
// reproducibility *classification* is cross-checked against the live
// API instead of hard-coded (07-reproducibility.spec.ts) per the master
// prompt's own instruction not to hard-code an expected classification.
function headerRow(page: import('@playwright/test').Page, label: string) {
  return page.getByRole('heading', { name: label, exact: true }).locator('..');
}

test.describe('06 comparison - real Scenario A-G difference matrix through the UI', () => {
  test('Scenario A: identical code + identical metrics -> Code SAME, Metrics SAME', async ({ page, request }) => {
    const { baseRun, compareRun } = await createTwoRuns(request, 'scenario-a');
    const code = codeProvenance('same-sha', 'same-tree');
    await submitComparisonViaUi(
      page,
      baseRun.id,
      compareRun.id,
      { code, metrics: { accuracy: 0.9 } },
      { code, metrics: { accuracy: 0.9 } }
    );
    await expect(headerRow(page, 'Code').getByText('SAME')).toBeVisible();
    await expect(headerRow(page, 'Metrics').getByText('SAME')).toBeVisible();
  });

  test('Scenario B: dataset-only change is detected as a Dataset difference, Code stays SAME', async ({ page, request }) => {
    const { baseRun, compareRun } = await createTwoRuns(request, 'scenario-b');
    const code = codeProvenance('same-sha-b', 'same-tree-b');
    await submitComparisonViaUi(
      page,
      baseRun.id,
      compareRun.id,
      { code, dataset: datasetProvenance('hash-a') },
      { code, dataset: datasetProvenance('hash-b') }
    );
    await expect(headerRow(page, 'Code').getByText('SAME')).toBeVisible();
    await expect(headerRow(page, 'Dataset').getByText('DIFFERENCE')).toBeVisible();
  });

  test('Scenario D: configuration (learning rate) change is detected as a Configuration difference', async ({
    page,
    request,
  }) => {
    const { baseRun, compareRun } = await createTwoRuns(request, 'scenario-d');
    await submitComparisonViaUi(
      page,
      baseRun.id,
      compareRun.id,
      { configuration: configurationProvenance('cfg-hash-lr-0.001', { learning_rate: 0.001, batch_size: 64 }) },
      { configuration: configurationProvenance('cfg-hash-lr-0.01', { learning_rate: 0.01, batch_size: 64 }) }
    );
    await expect(headerRow(page, 'Configuration').getByText('DIFFERENCE')).toBeVisible();
  });

  test('Scenario E: random seed change is detected as a Randomness difference', async ({ page, request }) => {
    const { baseRun, compareRun } = await createTwoRuns(request, 'scenario-e');
    await submitComparisonViaUi(
      page,
      baseRun.id,
      compareRun.id,
      { randomness: randomnessProvenance(42, 'rand-hash-42') },
      { randomness: randomnessProvenance(43, 'rand-hash-43') }
    );
    await expect(headerRow(page, 'Randomness').getByText('DIFFERENCE')).toBeVisible();
  });

  test('Scenario F: modified code (different commit) is detected as a Code difference', async ({ page, request }) => {
    const { baseRun, compareRun } = await createTwoRuns(request, 'scenario-f');
    await submitComparisonViaUi(
      page,
      baseRun.id,
      compareRun.id,
      { code: codeProvenance('sha-original', 'tree-original') },
      { code: codeProvenance('sha-modified', 'tree-modified') }
    );
    await expect(headerRow(page, 'Code').getByText('DIFFERENCE')).toBeVisible();
  });

  test('Scenario G: multiple simultaneous factor changes are all displayed as differences', async ({ page, request }) => {
    const { baseRun, compareRun } = await createTwoRuns(request, 'scenario-g');
    await submitComparisonViaUi(
      page,
      baseRun.id,
      compareRun.id,
      {
        code: codeProvenance('sha-g-base', 'tree-g-base'),
        configuration: configurationProvenance('cfg-hash-g-base', { learning_rate: 0.001 }),
        randomness: randomnessProvenance(42, 'rand-hash-g-base'),
      },
      {
        code: codeProvenance('sha-g-changed', 'tree-g-changed'),
        configuration: configurationProvenance('cfg-hash-g-changed', { learning_rate: 0.05 }),
        randomness: randomnessProvenance(999, 'rand-hash-g-changed'),
      }
    );
    await expect(headerRow(page, 'Code').getByText('DIFFERENCE')).toBeVisible();
    await expect(headerRow(page, 'Configuration').getByText('DIFFERENCE')).toBeVisible();
    await expect(headerRow(page, 'Randomness').getByText('DIFFERENCE')).toBeVisible();

    // Each difference should also produce a real evidence row (field/old
    // value/new value/severity/confidence), not just a status badge.
    const diffRows = page.locator('table tbody tr');
    expect(await diffRows.count()).toBeGreaterThanOrEqual(3);
  });
});
