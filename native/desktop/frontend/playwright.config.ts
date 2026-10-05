import { server } from "../scripts/configuration.mjs";
import { buildPath } from "../scripts/build-paths.mjs";
import { defineConfig } from "@playwright/test";
import { resolve } from "node:path";

const { devPort, previewPort } = server();
const preview = `http://127.0.0.1:${previewPort}`;
const development = `http://127.0.0.1:${devPort}`;
const viewport = { width: 1440, height: 1050 };

// Two projects, two servers. `product` drives the production build through
// `vite preview`, with no host or with a faked Tauri transport. `scenarios`
// drives the development entry on the development server, which is the only
// place the scenario host and the documentation fixture exist.
export default defineConfig({
  testDir: "./tests",
  outputDir: buildPath("desktop_results"),
  reporter: [
    ["list"],
    [
      "json",
      { outputFile: resolve(buildPath("desktop_results"), "results.json") },
    ],
  ],
  use: { viewport, trace: "retain-on-failure" },
  projects: [
    {
      name: "product",
      testIgnore: /scenarios\//,
      use: { baseURL: preview },
    },
    {
      name: "scenarios",
      testMatch: /scenarios\/.*\.spec\.ts/,
      use: { baseURL: development },
    },
  ],
  webServer: [
    { command: "npm run preview", url: preview, reuseExistingServer: false },
    {
      command: "npm run dev",
      url: `${development}/scenarios.html`,
      // A developer usually has this server open already.
      reuseExistingServer: true,
    },
  ],
});
