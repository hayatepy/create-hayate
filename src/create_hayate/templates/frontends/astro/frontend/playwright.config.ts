import { defineConfig, devices } from "@playwright/test";

const backendPort = process.env.HAYATE_E2E_BACKEND_PORT || "8000";
const frontendPort = process.env.HAYATE_E2E_FRONTEND_PORT || "4321";
const backendOrigin = `http://127.0.0.1:$${backendPort}`;
const frontendOrigin = `http://127.0.0.1:$${frontendPort}`;
const isolated = process.env.HAYATE_E2E_ISOLATED === "1";

export default defineConfig({
  testDir: "./tests",
  fullyParallel: true,
  forbidOnly: Boolean(process.env.CI),
  retries: process.env.CI ? 2 : 0,
  reporter: process.env.CI ? "github" : "list",
  use: {
    baseURL: frontendOrigin,
    trace: "on-first-retry",
  },
  projects: [
    {
      name: "chromium",
      use: { ...devices["Desktop Chrome"] },
    },
  ],
  webServer: [
    {
      command:
        `uv run --project .. uvicorn app:app --app-dir ../src --host 127.0.0.1 --port $${backendPort}`,
      url: `$${backendOrigin}/api/health`,
      reuseExistingServer: !process.env.CI && !isolated,
      timeout: 120_000,
    },
    {
      command: `npm run dev -- --port $${frontendPort}`,
      url: frontendOrigin,
      env: {
        ASTRO_DEV_BACKGROUND: "1",
        HAYATE_DEV_ORIGIN: backendOrigin,
      },
      reuseExistingServer: !process.env.CI && !isolated,
      timeout: 120_000,
    },
  ],
});
