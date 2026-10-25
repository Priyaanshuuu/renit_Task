import { defineConfig } from "@playwright/test";

// Run against the two local development servers; no browser download required
// when Chrome is installed. Set PLAYWRIGHT_CHANNEL=msedge to use Edge instead.
export default defineConfig({
  testDir: "./tests",
  workers: 1,
  timeout: 30_000,
  use: {
    baseURL: process.env.APP_URL ?? "http://localhost:5173",
    channel: process.env.PLAYWRIGHT_CHANNEL ?? "chrome",
    viewport: { width: 1440, height: 1000 },
    screenshot: "only-on-failure",
    trace: "retain-on-failure",
  },
});
