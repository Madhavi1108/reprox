import { expect, test } from './fixtures';

function uniqueSlug(prefix: string) {
  return `${prefix}-${Date.now()}-${Math.floor(Math.random() * 10000)}`;
}

test.describe('15 security - real payloads against the real running app', () => {
  test('an HTML-injection-shaped description never renders as live markup', async ({ page }) => {
    await page.goto('/projects');
    await page.getByLabel(/^name$/i).fill('HTML Injection Probe');
    await page.getByLabel(/^slug$/i).fill(uniqueSlug('html-inject'));
    await page.getByLabel(/^description$/i).fill('<img src=x onerror="window.__injected=true">');
    await page.getByRole('button', { name: /create project/i }).click();

    await expect(page.getByText('HTML Injection Probe')).toBeVisible();
    const injected = await page.evaluate(() => (window as unknown as { __injected?: boolean }).__injected);
    expect(injected).toBeUndefined();
    expect(await page.locator('img[src="x"]').count()).toBe(0);
  });

  test('a malicious query string on a deep-linked URL is handled safely, no reflected script execution', async ({
    page,
  }) => {
    let dialogFired = false;
    page.on('dialog', async (d) => {
      dialogFired = true;
      await d.dismiss();
    });

    await page.goto('/compare?run=<script>alert(1)</script>&x="><svg onload=alert(2)>');
    await expect(page.locator('body')).not.toBeEmpty();
    expect(dialogFired).toBe(false);
  });

  test('no secret appears in localStorage, sessionStorage, or console after normal use', async ({
    page,
    consoleErrors,
  }) => {
    await page.goto('/projects');
    await page.getByLabel(/^name$/i).fill('Secret Check');
    await page.getByLabel(/^slug$/i).fill(uniqueSlug('secret-check'));
    await page.getByRole('button', { name: /create project/i }).click();
    await page.goto('/');

    const storageDump = await page.evaluate(() =>
      JSON.stringify({ local: { ...window.localStorage }, session: { ...window.sessionStorage } })
    );
    expect(storageDump).not.toMatch(/api[_-]?key|secret|password|bearer\s+[a-z0-9]/i);

    const consoleDump = consoleErrors.join('\n');
    expect(consoleDump).not.toMatch(/api[_-]?key|secret|password/i);
  });

  test('no backend response ever includes a secret-shaped field value', async ({ request }) => {
    const dashboard = await (await request.get('http://127.0.0.1:8000/api/v1/dashboard')).json();
    const projects = await (await request.get('http://127.0.0.1:8000/api/v1/projects')).json();
    const combined = JSON.stringify({ dashboard, projects });
    expect(combined).not.toMatch(/anthropic_api_key|openai_api_key|database_url|postgresql:\/\//i);
  });

  test('a SQL-injection-shaped project name/slug is stored and rendered safely, no data loss', async ({ page }) => {
    await page.goto('/projects');
    await page.getByLabel(/^name$/i).fill("Robert'); DROP TABLE projects;--");
    await page.getByLabel(/^slug$/i).fill(uniqueSlug('sqli-probe'));
    await page.getByRole('button', { name: /create project/i }).click();

    await expect(page.getByText("Robert'); DROP TABLE projects;--")).toBeVisible();
    // Prove the table wasn't actually dropped: the list is still queryable.
    await page.reload({ waitUntil: 'networkidle' });
    await expect(page.getByText("Robert'); DROP TABLE projects;--")).toBeVisible();
  });
});
