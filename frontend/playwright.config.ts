import { defineConfig, devices } from '@playwright/test';

// Real Google Chrome end-to-end suite (docs/E2E_CHROME_TEST_REPORT.md).
// Deliberately separate from vitest.config.ts (component/unit tests) -
// this drives the real installed Chrome, not jsdom or Playwright's
// bundled Chromium, against the real running dev server + real backend.
export default defineConfig({
  testDir: './tests/e2e',
  fullyParallel: false,
  retries: 0,
  // This suite drives one shared, stateful backend process (real
  // Postgres + real uvicorn, not one instance per worker) and creating
  // a run triggers a real background Docker sandbox attempt (Phase 17) -
  // a real resource-contention source under high parallelism, not
  // something to paper over with retries. Capped lower than Playwright's
  // CPU-count default after a flake was observed at 8 workers and not
  // reproducible at lower concurrency.
  workers: 4,
  reporter: [['list'], ['html', { open: 'never', outputFolder: 'tests/e2e/report' }]],
  outputDir: 'tests/e2e/test-results',
  use: {
    channel: 'chrome',
    baseURL: 'http://localhost:5173',
    viewport: { width: 1280, height: 900 },
    screenshot: 'only-on-failure',
    video: 'retain-on-failure',
    trace: 'retain-on-failure',
    // The Chrome sandbox is unavailable in this environment's process
    // model (chromium.launch() with the sandbox enabled fails to spawn
    // at all here - confirmed during the frontend hardening pass).
    // Disabling it is required to launch real Chrome in this specific
    // dev environment, not a general security posture for the app.
    launchOptions: {
      args: ['--no-sandbox'],
    },
  },
  projects: [
    {
      name: 'chrome',
      use: { ...devices['Desktop Chrome'], channel: 'chrome' },
    },
  ],
});
