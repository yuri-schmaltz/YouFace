import { defineConfig, devices } from "@playwright/test";

/**
 * Playwright E2E config for the YouFace cockpit.
 *
 * Tests live in `e2e/` and run against a locally-running backend (default:
 * http://127.0.0.1:8000). To run:
 *
 *   # 1. Boot the backend
 *   python run_api.py &
 *
 *   # 2. Boot the frontend (separate terminal)
 *   cd frontend && npm run start &
 *
 *   # 3. Run the tests
 *   cd frontend && npx playwright test
 *
 * The CI workflow (.github/workflows/ci.yml) runs the same commands in
 * a single job (e2e).
 */
export default defineConfig({
  testDir: "./e2e",
  fullyParallel: true,
  forbidOnly: !!process.env.CI,
  retries: process.env.CI ? 2 : 0,
  workers: process.env.CI ? 1 : undefined,
  reporter: process.env.CI ? "github" : "list",
  use: {
    baseURL: process.env.E2E_BASE_URL ?? "http://127.0.0.1:3000",
    trace: "on-first-retry",
    screenshot: "only-on-failure",
  },
  projects: [
    {
      name: "chromium",
      use: { ...devices["Desktop Chrome"] },
    },
  ],
  webServer: process.env.E2E_BASE_URL
    ? undefined
    : {
        command: "npm run start",
        url: "http://127.0.0.1:3000",
        reuseExistingServer: !process.env.CI,
        timeout: 60_000,
      },
});
