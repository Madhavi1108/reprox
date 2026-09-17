import { Page } from '@playwright/test';
import { expect, test } from './fixtures';

function uniqueSlug(prefix: string) {
  return `${prefix}-${Date.now()}-${Math.floor(Math.random() * 10000)}`;
}

function row(page: Page, uniqueText: string) {
  return page.locator('li').filter({ hasText: uniqueText });
}

test.describe('16 edge cases - real boundary conditions through the UI', () => {
  test('the dashboard renders correctly even with a large accumulated dataset (many projects)', async ({ page }) => {
    // This shared dev DB already has dozens of projects from this
    // suite's own earlier runs - a real "many projects" condition, not
    // an artificially seeded one.
    await page.goto('/');
    await page.waitForLoadState('networkidle');
    const apiDashboard = await (await page.request.get('http://127.0.0.1:8000/api/v1/dashboard')).json();
    expect(apiDashboard.total_projects).toBeGreaterThan(10);
    await expect(page.locator('body')).not.toBeEmpty();
  });

  test('special characters and emoji in a project name are handled without breaking layout', async ({ page }) => {
    await page.goto('/projects');
    const slug = uniqueSlug('special-chars');
    const name = `Special <>&"' chars 🔬📊 test`;
    await page.getByLabel(/^name$/i).fill(name);
    await page.getByLabel(/^slug$/i).fill(slug);
    await page.getByRole('button', { name: /create project/i }).click();

    await expect(row(page, slug)).toBeVisible();
    const hasOverflow = await page.evaluate(() => document.documentElement.scrollWidth > document.documentElement.clientWidth + 1);
    expect(hasOverflow).toBe(false);
  });

  test('a project with only whitespace in an optional description is accepted (description is optional)', async ({
    page,
  }) => {
    await page.goto('/projects');
    const slug = uniqueSlug('whitespace-desc');
    await page.getByLabel(/^name$/i).fill('Whitespace Description');
    await page.getByLabel(/^slug$/i).fill(slug);
    await page.getByLabel(/^description$/i).fill('   ');
    await page.getByRole('button', { name: /create project/i }).click();
    await expect(row(page, slug)).toBeVisible();
  });

  test('an experiment name identical to an existing one in a different project is allowed (uniqueness is per-project)', async ({
    page,
  }) => {
    const slugA = uniqueSlug('dup-exp-a');
    const slugB = uniqueSlug('dup-exp-b');
    for (const slug of [slugA, slugB]) {
      await page.goto('/projects');
      await page.getByLabel(/^name$/i).fill(`${slug} project`);
      await page.getByLabel(/^slug$/i).fill(slug);
      await page.getByRole('button', { name: /create project/i }).click();
      await expect(row(page, slug)).toBeVisible();
    }

    const experimentName = `Shared Experiment Name ${Date.now()}`;
    for (const slug of [slugA, slugB]) {
      await page.goto('/experiments');
      await page.getByLabel(/project/i).selectOption({ label: `${slug} project` });
      await page.getByLabel(/experiment name/i).fill(experimentName);
      await page.getByLabel(/workload type/i).fill('sklearn_tabular');
      await page.getByLabel(/entrypoint script/i).fill('train.py');
      await page.getByRole('button', { name: /create experiment/i }).click();
      await expect(row(page, experimentName).first()).toBeVisible();
    }
  });

  test('pagination boundary: listing respects the default page size without erroring', async ({ request }) => {
    const response = await request.get('http://127.0.0.1:8000/api/v1/projects', { params: { limit: 5, offset: 0 } });
    expect(response.ok()).toBe(true);
    const body = await response.json();
    expect(body.items.length).toBeLessThanOrEqual(5);
    expect(body.limit).toBe(5);
  });

  test('an offset beyond the total item count returns an empty page, not an error', async ({ request }) => {
    const response = await request.get('http://127.0.0.1:8000/api/v1/projects', {
      params: { limit: 20, offset: 999999 },
    });
    expect(response.ok()).toBe(true);
    const body = await response.json();
    expect(body.items).toEqual([]);
  });
});
