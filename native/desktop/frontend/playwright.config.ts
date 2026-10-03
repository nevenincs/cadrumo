import { defineConfig } from "@playwright/test";
import { isAbsolute, resolve } from "node:path";

const binaryDir = process.env.CADRUMO_CMAKE_BINARY_DIR;
if (!binaryDir || !isAbsolute(binaryDir))
  throw new Error("Select an absolute CMake build directory.");

export default defineConfig({
  testDir: "./tests",
  outputDir: resolve(binaryDir, "desktop/test-results"),
  reporter: [
    ["list"],
    ["json", { outputFile: resolve(binaryDir, "desktop/test-results.json") }],
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
