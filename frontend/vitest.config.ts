import react from '@vitejs/plugin-react'
import { defineConfig } from 'vitest/config'

export default defineConfig({
  plugins: [react()],
  test: {
    environment: 'jsdom',
    setupFiles: ['./src/test/setup.ts'],
    css: false,
    // tests/e2e/**/*.spec.ts are Playwright specs (real-Chrome E2E,
    // run via `npm run test:e2e`), not Vitest component tests - Vitest's
    // default include glob would otherwise pick them up and fail trying
    // to run them with the wrong test runner's `test`/`expect`.
    exclude: ['**/node_modules/**', 'tests/e2e/**'],
  },
})
