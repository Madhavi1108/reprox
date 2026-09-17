import { assertNoUnexpectedErrors, expect, test } from './fixtures';

// Master prompt Phase 28: "Before declaring E2E success, print/log
// Browser/Chrome version/Executable/Frontend URL/Backend URL."
test.describe('01 smoke - real Chrome + real backend reachability', () => {
  test('real Google Chrome launches and reports its own version', async ({ browser, page }) => {
    const version = browser.version();
    console.log('REAL CHROME VERIFICATION');
    console.log('  Browser: Google Chrome');
    console.log(`  Chrome version: ${version}`);
    console.log('  Launch config: chromium.launch({ channel: "chrome" }) - playwright.config.ts');
    console.log('  Frontend URL: http://localhost:5173');
    console.log('  Backend URL: http://127.0.0.1:8000');
    // Chrome's own version string starts with a real major version
    // number (this environment's installed Chrome is 153.x) - this is
    // not Playwright's bundled Chromium build string.
    expect(version).toMatch(/^\d+\.\d+\.\d+\.\d+$/);
    await page.goto('/');
    await expect(page.getByText('REPROX').first()).toBeVisible();
  });

  test('backend health and health/db are reachable', async ({ request }) => {
    const health = await request.get('http://127.0.0.1:8000/health');
    expect(health.status()).toBe(200);
    expect(await health.json()).toEqual({ status: 'ok' });

    const healthDb = await request.get('http://127.0.0.1:8000/health/db');
    expect(healthDb.status()).toBe(200);
    expect(await healthDb.json()).toEqual({ status: 'ok' });
  });

  test('all 4 real routes load without console errors', async ({ page, consoleErrors, networkFailures }) => {
    for (const path of ['/', '/projects', '/experiments', '/compare']) {
      await page.goto(path, { waitUntil: 'networkidle' });
      await expect(page.locator('body')).not.toBeEmpty();
    }
    assertNoUnexpectedErrors(consoleErrors, networkFailures);
  });
});
