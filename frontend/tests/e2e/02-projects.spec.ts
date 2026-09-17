import { Page } from '@playwright/test';
import { assertNoUnexpectedErrors, expect, test } from './fixtures';

function uniqueSlug(prefix: string) {
  return `${prefix}-${Date.now()}-${Math.floor(Math.random() * 10000)}`;
}

// This dev DB is shared/persistent across every E2E run in this session
// (real Postgres, no per-test reset), so names alone are not reliable
// locators once the suite has run more than once. The slug is always
// unique (timestamped + randomized per call) - scope every assertion to
// the single list row containing that slug.
function projectRow(page: Page, slug: string) {
  return page.locator('li').filter({ hasText: slug });
}

test.describe('02 projects - real create/list/persist through the UI', () => {
  test('creates a project with realistic data and it appears in the list', async ({ page, consoleErrors, networkFailures }) => {
    await page.goto('/projects');
    const slug = uniqueSlug('cifar10-resnet50');

    await page.getByLabel(/^name$/i).fill('CIFAR-10 ResNet50 Baseline');
    await page.getByLabel(/^slug$/i).fill(slug);
    await page.getByLabel(/^description$/i).fill('Baseline image classification run for reproducibility tracking.');
    await page.getByRole('button', { name: /create project/i }).click();

    const row = projectRow(page, slug);
    await expect(row).toBeVisible();
    await expect(row.getByText('CIFAR-10 ResNet50 Baseline')).toBeVisible();

    assertNoUnexpectedErrors(consoleErrors, networkFailures);
  });

  test('rejects an invalid slug with a real, specific validation message', async ({ page }) => {
    await page.goto('/projects');
    await page.getByLabel(/^name$/i).fill('Invalid Slug Project');
    await page.getByLabel(/^slug$/i).fill('Not A Valid Slug!');
    await page.getByRole('button', { name: /create project/i }).click();

    // Real bug fixed in the frontend hardening pass: this used to show a
    // generic "Request failed with status 422" - now shows the actual
    // Pydantic field_validator reason.
    await expect(page.getByText(/slug must be lowercase alphanumeric/i)).toBeVisible();
  });

  test('rejects a duplicate slug with a real conflict message', async ({ page }) => {
    await page.goto('/projects');
    const slug = uniqueSlug('dup-project');

    await page.getByLabel(/^name$/i).fill('First');
    await page.getByLabel(/^slug$/i).fill(slug);
    await page.getByRole('button', { name: /create project/i }).click();
    await expect(projectRow(page, slug)).toBeVisible();

    await page.getByLabel(/^name$/i).fill('Second');
    await page.getByLabel(/^slug$/i).fill(slug);
    await page.getByRole('button', { name: /create project/i }).click();
    await expect(page.getByText(/already exists/i)).toBeVisible();
  });

  test('a script-tag-shaped project name renders as inert text, never executes', async ({ page }) => {
    await page.goto('/projects');
    let alertFired = false;
    page.on('dialog', async (dialog) => {
      alertFired = true;
      await dialog.dismiss();
    });

    const slug = uniqueSlug('xss-probe');
    await page.getByLabel(/^name$/i).fill('<script>alert("xss")</script>XSSProbe');
    await page.getByLabel(/^slug$/i).fill(slug);
    await page.getByRole('button', { name: /create project/i }).click();

    const row = projectRow(page, slug);
    await expect(row.getByText('XSSProbe', { exact: false })).toBeVisible();
    expect(alertFired).toBe(false);
    const scriptTagCount = await page.locator('script:has-text("alert")').count();
    expect(scriptTagCount).toBe(0);
  });

  test('a long (but within the 200-char limit) unicode name is handled without breaking the page', async ({ page }) => {
    await page.goto('/projects');
    // ProjectCreate.name is max_length=200 (backend/app/schemas/project.py)
    // - stay just under it to test "long," not "over the limit."
    const longName = ('Long Project Name ' + 'エンド ').repeat(7).trim().slice(0, 199);
    const slug = uniqueSlug('unicode-long');
    await page.getByLabel(/^name$/i).fill(longName);
    await page.getByLabel(/^slug$/i).fill(slug);
    await page.getByRole('button', { name: /create project/i }).click();

    await expect(projectRow(page, slug).getByText(longName.slice(0, 40), { exact: false })).toBeVisible();
  });

  test('a name over the real 200-char backend limit shows the real validation reason', async ({ page }) => {
    await page.goto('/projects');
    const tooLongName = 'x'.repeat(201);
    await page.getByLabel(/^name$/i).fill(tooLongName);
    await page.getByLabel(/^slug$/i).fill(uniqueSlug('too-long-name'));
    await page.getByRole('button', { name: /create project/i }).click();

    await expect(page.getByText(/at most 200 characters/i)).toBeVisible();
  });

  test('a created project survives a real page refresh', async ({ page }) => {
    await page.goto('/projects');
    const slug = uniqueSlug('persist-check');
    await page.getByLabel(/^name$/i).fill('Persistence Check');
    await page.getByLabel(/^slug$/i).fill(slug);
    await page.getByRole('button', { name: /create project/i }).click();
    await expect(projectRow(page, slug)).toBeVisible();

    await page.reload({ waitUntil: 'networkidle' });
    await expect(projectRow(page, slug)).toBeVisible();
  });
});
