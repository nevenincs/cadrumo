import { buildPath } from "../../../scripts/build-paths.mjs";
import { defineConfig } from "@playwright/test";
import { resolve } from "node:path";
import { fileURLToPath } from "node:url";

// The live project: the shared agent specs, unchanged, against the packaged
// desktop. The lane (`just desktop-agent-live`) starts the desktop with a
// loopback DevTools port and names it in CADRUMO_DEV_DESKTOP_LIVE_ENDPOINT. This
// configuration starts no server and no browser; it only attaches. The lane
// runs one project per run: `live`, or `ledger-privacy` with its
// `--ledger-privacy` option.
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
  projects: [
    {
      name: "live",
      // The attachment check first, then the shared specs.
      testMatch: [
        /live\/attach\.live\.ts$/,
        /scenarios\/agent\.spec\.ts$/,
        /scenarios\/agent-prompts\.spec\.ts$/,
        /scenarios\/agent-live-skills\.spec\.ts$/,
        /scenarios\/agent-live-mentions\.spec\.ts$/,
      ],
      metadata: { agentHost: "live" },
      expect: { timeout: 3 * 60_000 },
      use: { trace: "retain-on-failure", screenshot: "only-on-failure" },
    },
    {
      // The Ledger page on the person's own ledger: nothing of the window may
      // be recorded, so this project keeps no trace, screenshot or video,
      // and the lane refuses to run it if any of them is turned on. Its
      // actions time out well inside the test, so their errors, which can
      // quote the page, reach the spec's own handling first.
      name: "ledger-privacy",
      testMatch: /live\/ledger-privacy\.live\.ts$/,
      metadata: { agentHost: "live" },
      timeout: 10 * 60_000,
      expect: { timeout: 30_000 },
      use: {
        trace: "off",
        screenshot: "off",
        video: "off",
        actionTimeout: 30_000,
        navigationTimeout: 60_000,
      },
    },
  ],
});
