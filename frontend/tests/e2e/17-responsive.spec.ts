import { expect, test } from './fixtures';

const VIEWPORTS = [
  [320, 800],
  [375, 812],
  [414, 896],
  [768, 1024],
  [1024, 768],
  [1280, 720],
  [1440, 900],
  [1920, 1080],
] as const;

const ROUTES = ['/', '/projects', '/experiments', '/compare'];

test.describe('17 responsive - all 8 requested viewports on every real page', () => {
  for (const [width, height] of VIEWPORTS) {
    for (const path of ROUTES) {
      test(`${width}x${height} on ${path}: no horizontal overflow`, async ({ browser }) => {
        const context = await browser.newContext({ viewport: { width, height } });
        const page = await context.newPage();
        await page.goto(path, { waitUntil: 'networkidle' });

        const hasOverflow = await page.evaluate(
          () => document.documentElement.scrollWidth > document.documentElement.clientWidth + 1
        );
        expect(hasOverflow, `horizontal overflow at ${width}x${height} on ${path}`).toBe(false);

        // Nav must remain reachable at every size (no clipped/hidden
        // primary navigation).
        await expect(page.getByRole('link', { name: 'Dashboard' })).toBeVisible();

        await context.close();
      });
    }
  }
});
