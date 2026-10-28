import { server } from "../scripts/configuration.mjs";
import { buildPath } from "../scripts/build-paths.mjs";
import { defineConfig } from "@playwright/test";
import { resolve } from "node:path";

const { previewPort, scenariosPort, hotPort } = server();
const preview = `http://127.0.0.1:${previewPort}`;
const scenarios = `http://127.0.0.1:${scenariosPort}`;
const hot = `http://127.0.0.1:${hotPort}`;
const viewport = { width: 1440, height: 1050 };

// Three projects, three servers, none of them the display `just dev` serves.
// A test never reuses a running server and never meets the developer's: each
// has a port of its own and a run that finds it taken fails.
//
// `product` drives the production build through `vite preview`, with no host
// or with a faked Tauri transport. `scenarios` drives the scenario host and
// the documentation fixture, which exist only in the development entry, as a
// build of it (`--mode scenarios`) served by `vite preview`: nothing watches
// the source tree, so a file saved while the tests run cannot reload a page
// in the middle of one. `hot-reload` is the one spec that needs Vite's own
// client, so it alone runs on a development server.
export default defineConfig({
  testDir: "./tests",
  // Playwright empties this directory when a run starts, so it is the run's
  // own: the benchmark, the catalogue screenshots and the packaged run keep
  // theirs beside it.
  outputDir: resolve(buildPath("desktop_results"), "browser"),
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
      testIgnore: /(scenarios|hot-reload)\//,
      use: { baseURL: preview },
    },
    {
      name: "scenarios",
      testMatch: /scenarios\/.*\.spec\.ts/,
      use: { baseURL: scenarios },
    },
    {
      name: "hot-reload",
      testMatch: /hot-reload\/.*\.spec\.ts/,
      use: { baseURL: hot },
    },
  ],
  webServer: [
    {
      name: "product",
      // Built by the run that tests it, so the product project and the
      // bundle check never read a stale build.
      command: "npx vite build && npx vite preview",
      url: preview,
      reuseExistingServer: false,
      timeout: 120_000,
    },
    {
      name: "scenarios",
      // Built by the run that tests it, into the testing directory beside
      // the benchmark's, never the product's.
      command:
        "npx vite build --mode scenarios && npx vite preview --mode scenarios",
      url: `${scenarios}/scenarios.html`,
      reuseExistingServer: false,
      timeout: 120_000,
    },
    {
      name: "hot-reload",
      command: "npx vite --mode scenarios",
      url: `${hot}/scenarios.html`,
      reuseExistingServer: false,
      timeout: 120_000,
    },
  ],
});
