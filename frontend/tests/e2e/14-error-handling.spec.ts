import { expect, test } from './fixtures';

test.describe('14 error handling - real failure cases through the UI', () => {
  test('an invalid/nonexistent run ID on Comparison shows a real error, not a blank page', async ({ page }) => {
    await page.goto('/compare');
    const fakeId = '00000000-0000-0000-0000-000000000001';
    await page.getByLabel(/base run id/i).fill(fakeId);
    await page.getByLabel(/compare run id/i).fill(fakeId);
    await page.getByRole('button', { name: /compare runs/i }).click();

    await expect(page.getByText(/not found/i)).toBeVisible();
    await expect(page.locator('body')).not.toBeEmpty();
  });

  test('malformed advanced-JSON payload shows a real client-side error, not a crash', async ({ page }) => {
    await page.goto('/compare');
    await page.getByLabel(/base run id/i).fill('11111111-1111-1111-1111-111111111111');
    await page.getByLabel(/compare run id/i).fill('22222222-2222-2222-2222-222222222222');
    await page.getByRole('button', { name: /show advanced provenance payloads/i }).click();
    await page.getByLabel(/base provenance json/i).fill('{not valid json');
    await page.getByRole('button', { name: /compare runs/i }).click();

    await expect(page.getByText(/must be valid json/i)).toBeVisible();
  });

  test('the app degrades gracefully (real error, no blank page) when the backend is briefly unreachable', async ({
    page,
  }) => {
    // A real network failure: the browser only ever calls the relative
    // /api/v1/* path (Vite's dev-server proxy forwards it to the
    // backend server-side - the browser itself never sees the backend's
    // own origin), so that's the pattern to abort at the browser level
    // for the frontend's own fetch() to genuinely fail.
    await page.route('**/api/v1/**', (route) => route.abort('connectionrefused'));

    await page.goto('/projects');
    await expect(page.getByText(/couldn't load data/i)).toBeVisible();
    await expect(page.getByRole('button', { name: /retry/i })).toBeVisible();

    await page.unroute('**/api/v1/**');
    await page.getByRole('button', { name: /retry/i }).click();
    await expect(page.getByText(/couldn't load data/i)).not.toBeVisible();
  });

  test('creating a project while the backend is unreachable shows a real error, not a silent failure', async ({
    page,
  }) => {
    await page.goto('/projects');
    await page.route('**/api/v1/projects', (route) => route.abort('connectionrefused'));

    await page.getByLabel(/^name$/i).fill('Offline Test');
    await page.getByLabel(/^slug$/i).fill(`offline-${Date.now()}`);
    await page.getByRole('button', { name: /create project/i }).click();

    await expect(page.getByText(/could not reach the reprox api/i)).toBeVisible();
    await page.unroute('**/api/v1/projects');
  });
});
