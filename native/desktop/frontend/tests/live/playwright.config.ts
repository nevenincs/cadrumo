import { buildPath } from "../../../scripts/build-paths.mjs";
import { defineConfig } from "@playwright/test";
import { resolve } from "node:path";
import { fileURLToPath } from "node:url";

// The live project: the shared agent specs, unchanged, against the packaged
// desktop. The lane (`just desktop-agent-live`) starts the desktop with a
// loopback DevTools port and names it in CADRUMO_DEV_DESKTOP_LIVE_ENDPOINT. This
// configuration starts no server and no browser; it only attaches.
//
// The tsconfig beside this file resolves "@playwright/test" to the live
// fixture, so the specs receive the desktop's window as their page. Checks
// only the scenario host can satisfy read `metadata.agentHost`, which is
// "live" here and absent on the scenario project.
const here = fileURLToPath(new URL(".", import.meta.url));
const results =
  process.env.CADRUMO_DEV_DESKTOP_LIVE_RESULTS ||
  resolve(buildPath("desktop_results"), "agent-live");

export default defineConfig({
  testDir: resolve(here, ".."),
  tsconfig: resolve(here, "tsconfig.json"),
  // Playwright empties this directory when a run starts. The lane scans it,
  // traces and screenshots included, for provider keys after the run.
  outputDir: resolve(results, "browser"),
  reporter: [
    ["list"],
    ["json", { outputFile: resolve(results, "results.json") }],
  ],
  // One desktop window serves every test, so they run one at a time.
  workers: 1,
  fullyParallel: false,
  // A real model answers; replies take far longer than the scenario host's.
  timeout: 10 * 60_000,
  use: { trace: "retain-on-failure", screenshot: "only-on-failure" },
  projects: [
    {
      name: "live",
      // The attachment check first, then the shared specs.
      testMatch: [
        /live\/attach\.live\.ts$/,
        /scenarios\/agent\.spec\.ts$/,
        /scenarios\/agent-prompts\.spec\.ts$/,
      ],
      metadata: { agentHost: "live" },
      expect: { timeout: 3 * 60_000 },
    },
  ],
});
