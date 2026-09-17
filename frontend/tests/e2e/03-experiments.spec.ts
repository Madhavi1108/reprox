import { Page } from '@playwright/test';
import { assertNoUnexpectedErrors, expect, test } from './fixtures';

function uniqueSlug(prefix: string) {
  return `${prefix}-${Date.now()}-${Math.floor(Math.random() * 10000)}`;
}

function experimentRow(page: Page, uniqueText: string) {
  return page.locator('li').filter({ hasText: uniqueText });
}

/** Creates a project via the real UI and returns its unique name (used
 * as the <option> label text in the Experiments page's project select). */
async function createProjectViaUi(page: Page, prefix: string): Promise<string> {
  await page.goto('/projects');
  const slug = uniqueSlug(prefix);
  const name = `${slug} project`;
  await page.getByLabel(/^name$/i).fill(name);
  await page.getByLabel(/^slug$/i).fill(slug);
  await page.getByRole('button', { name: /create project/i }).click();
  await expect(page.locator('li').filter({ hasText: slug })).toBeVisible();
  return name;
}

test.describe('03 experiments - real create/list/persist through the UI', () => {
  test('creates a realistic experiment tied to a real project', async ({ page, consoleErrors, networkFailures }) => {
    const projectName = await createProjectViaUi(page, 'resnet-proj');

    await page.goto('/experiments');
    const experimentName = `CIFAR-10 ResNet50 seed42 ${Date.now()}`;
    await page.getByLabel(/project/i).selectOption({ label: projectName });
    await page.getByLabel(/experiment name/i).fill(experimentName);
    await page.getByLabel(/workload type/i).fill('sklearn_tabular');
    await page.getByLabel(/entrypoint script/i).fill('train_resnet50.py');
    await page.getByRole('button', { name: /create experiment/i }).click();

    await expect(experimentRow(page, experimentName)).toBeVisible();
    assertNoUnexpectedErrors(consoleErrors, networkFailures);
  });

  test('the create button is disabled until a project is selected', async ({ page }) => {
    await page.goto('/experiments');
    const button = page.getByRole('button', { name: /create experiment/i });
    // Only meaningful if at least one project exists (select starts
    // unselected due to the disabled placeholder <option>) - the button
    // must not be clickable with no project chosen, regardless of how
    // many projects exist in this shared dev DB.
    await expect(button).toBeDisabled();
  });

  test('a created experiment survives a real page refresh', async ({ page }) => {
    await createProjectViaUi(page, 'persist-proj');
    await page.goto('/experiments');
    const experimentName = `Persistence Check Experiment ${Date.now()}`;
    const projects = page.getByLabel(/project/i);
    await projects.selectOption({ index: 1 });
    await page.getByLabel(/experiment name/i).fill(experimentName);
    await page.getByLabel(/workload type/i).fill('sklearn_tabular');
    await page.getByLabel(/entrypoint script/i).fill('train.py');
    await page.getByRole('button', { name: /create experiment/i }).click();

    await expect(experimentRow(page, experimentName)).toBeVisible();

    await page.reload({ waitUntil: 'networkidle' });
    await expect(experimentRow(page, experimentName)).toBeVisible();
  });

  test('navigating away and back preserves the experiment in the list', async ({ page }) => {
    await createProjectViaUi(page, 'navaway-proj');
    await page.goto('/experiments');
    const experimentName = `Nav Away Check ${Date.now()}`;
    await page.getByLabel(/project/i).selectOption({ index: 1 });
    await page.getByLabel(/experiment name/i).fill(experimentName);
    await page.getByLabel(/workload type/i).fill('sklearn_tabular');
    await page.getByLabel(/entrypoint script/i).fill('train.py');
    await page.getByRole('button', { name: /create experiment/i }).click();
    await expect(experimentRow(page, experimentName)).toBeVisible();

    await page.goto('/');
    await page.goto('/experiments');
    await expect(experimentRow(page, experimentName)).toBeVisible();
  });
});
