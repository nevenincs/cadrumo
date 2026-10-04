import { buildPath } from "../scripts/build-paths.mjs";
import { defineConfig } from "@playwright/test";
import { resolve } from "node:path";

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
  use: {
    baseURL: "http://127.0.0.1:1421",
    viewport: { width: 1440, height: 1050 },
    trace: "retain-on-failure",
  },
  webServer: {
    command: "npm run preview",
    url: "http://127.0.0.1:1421",
    reuseExistingServer: false,
  },
});
