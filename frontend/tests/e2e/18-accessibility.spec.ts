import { expect, test } from './fixtures';

async function tabToLabel(page: import('@playwright/test').Page, labelPattern: RegExp, maxTabs = 20) {
  for (let i = 0; i < maxTabs; i++) {
    await page.keyboard.press('Tab');
    const active = await page.evaluate(() => {
      const el = document.activeElement as HTMLElement | null;
      if (!el) return null;
      const label = el.closest('label')?.textContent ?? document.querySelector(`label[for="${el.id}"]`)?.textContent;
      return { tag: el.tagName, label, ariaLabel: el.getAttribute('aria-label'), text: el.textContent };
    });
    if (active && (labelPattern.test(active.label ?? '') || labelPattern.test(active.ariaLabel ?? '') || labelPattern.test(active.text ?? ''))) {
      return true;
    }
  }
  return false;
}

test.describe('18 accessibility - keyboard navigation and labels on every real page', () => {
  test('every form input on Projects is reachable and identifiable via keyboard alone', async ({ page }) => {
    await page.goto('/projects');
    expect(await tabToLabel(page, /^name$/i)).toBe(true);
    expect(await tabToLabel(page, /^slug$/i)).toBe(true);
  });

  test('a project can be created using only the keyboard (no mouse)', async ({ page }) => {
    await page.goto('/projects');
    await page.keyboard.press('Tab'); // nav: Dashboard
    await page.keyboard.press('Tab'); // nav: Projects
    await page.keyboard.press('Tab'); // nav: Experiments
    await page.keyboard.press('Tab'); // nav: Compare
    await page.keyboard.press('Tab'); // Name field
    const focusedIsName = await page.evaluate(() => document.activeElement?.id === 'project-name');
    // Regardless of exact tab count (nav item count may change), keep
    // tabbing until the Name field is actually focused, then type.
    if (!focusedIsName) {
      for (let i = 0; i < 10 && (await page.evaluate(() => document.activeElement?.id)) !== 'project-name'; i++) {
        await page.keyboard.press('Tab');
      }
    }
    await page.keyboard.type('Keyboard Only Project');
    await page.keyboard.press('Tab');
    const slug = `kbd-only-${Date.now()}`;
    await page.keyboard.type(slug);
    // Submit via Enter on a text input inside the form.
    await page.keyboard.press('Enter');

    await expect(page.locator('li').filter({ hasText: slug })).toBeVisible();
  });

  test('every input on Projects/Experiments/Comparison has a real accessible name', async ({ page }) => {
    for (const path of ['/projects', '/experiments', '/compare']) {
      await page.goto(path);
      const unlabeled = await page.evaluate(() => {
        const controls = Array.from(document.querySelectorAll('input, textarea, select'));
        return controls
          .filter((el) => {
            const hasAriaLabel = el.getAttribute('aria-label') || el.getAttribute('aria-labelledby');
            const id = el.id;
            const hasFor = id && document.querySelector(`label[for="${id}"]`);
            return !hasAriaLabel && !hasFor;
          })
          .map((el) => el.outerHTML.slice(0, 80));
      });
      expect(unlabeled, `unlabeled controls on ${path}: ${JSON.stringify(unlabeled)}`).toEqual([]);
    }
  });

  test('the retry button on an error state is keyboard-activatable', async ({ page }) => {
    await page.route('**/api/v1/**', (route) => route.abort('connectionrefused'));
    await page.goto('/projects');
    await expect(page.getByRole('button', { name: /retry/i })).toBeVisible();

    await page.unroute('**/api/v1/**');
    await page.getByRole('button', { name: /retry/i }).focus();
    await page.keyboard.press('Enter');
    await expect(page.getByText(/couldn't load data/i)).not.toBeVisible();
  });
});
