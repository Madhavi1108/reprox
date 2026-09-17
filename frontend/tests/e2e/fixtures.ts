import { test as base, expect } from '@playwright/test';

// Shared console/network monitoring for every E2E spec (master prompt
// Phase 25: "Do not ignore browser console errors just because the page
// visually works"). Every test gets `consoleErrors`/`networkFailures`
// arrays populated automatically; call `assertNoUnexpectedErrors` at the
// end of a test, passing the HTTP statuses that test itself deliberately
// triggered (e.g. 422/409 from an invalid-input test) so genuinely
// unexpected failures still fail the test.

interface Fixtures {
  consoleErrors: string[];
  networkFailures: { url: string; status: number }[];
}

export const test = base.extend<Fixtures>({
  // Playwright's fixture callback's 2nd param is just a name we choose,
  // not a fixed API - named `provideValue` (not `use`) so oxlint's
  // react-hooks rule doesn't mistake it for React's `use()` hook.
  consoleErrors: async ({ page }, provideValue) => {
    const errors: string[] = [];
    page.on('console', (msg) => {
      if (msg.type() === 'error') errors.push(msg.text());
    });
    page.on('pageerror', (err) => errors.push(`pageerror: ${err.message}`));
    await provideValue(errors);
  },
  networkFailures: async ({ page }, provideValue) => {
    const failures: { url: string; status: number }[] = [];
    page.on('response', (response) => {
      if (response.status() >= 400) {
        failures.push({ url: response.url(), status: response.status() });
      }
    });
    await provideValue(failures);
  },
});

export { expect };

export function assertNoUnexpectedErrors(
  consoleErrors: string[],
  networkFailures: { url: string; status: number }[],
  allowedStatuses: number[] = []
) {
  const unexpectedNetwork = networkFailures.filter((f) => !allowedStatuses.includes(f.status));
  const unexpectedConsole = consoleErrors.filter((msg) => {
    const m = /status of (\d+)/.exec(msg);
    if (m && allowedStatuses.includes(Number(m[1]))) return false;
    return true;
  });
  expect(unexpectedConsole, `Unexpected console errors: ${JSON.stringify(unexpectedConsole)}`).toEqual([]);
  expect(unexpectedNetwork, `Unexpected network failures: ${JSON.stringify(unexpectedNetwork)}`).toEqual([]);
}

export const API_BASE = 'http://127.0.0.1:8000/api/v1';
