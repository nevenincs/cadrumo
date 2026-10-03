import { spawn } from "node:child_process";
import { once } from "node:events";
import { mkdirSync, writeFileSync } from "node:fs";
import { createRequire } from "node:module";
import { createServer } from "node:net";
import { isAbsolute, resolve } from "node:path";
import { setTimeout as delay } from "node:timers/promises";

const require = createRequire(
  new URL("../frontend/package.json", import.meta.url),
);
const { chromium, expect } = require("@playwright/test");
const binaryDir = process.env.CADRUMO_CMAKE_BINARY_DIR;
if (!binaryDir || !isAbsolute(binaryDir))
  throw new Error("Select an absolute CMake build directory.");
if (process.platform !== "win32")
  throw new Error("This smoke check requires the Windows WebView2 host.");
const evidence = resolve(binaryDir, "desktop/verification");
mkdirSync(evidence, { recursive: true });
const reservation = createServer();
reservation.listen(0, "127.0.0.1");
await once(reservation, "listening");
const address = reservation.address();
if (!address || typeof address === "string")
  throw new Error("No local debug port.");
await new Promise((resolveClose, reject) =>
  reservation.close((error) => (error ? reject(error) : resolveClose())),
);
const child = spawn(resolve(binaryDir, "cargo/desktop/debug/cadrumo.exe"), [], {
  windowsHide: true,
  stdio: ["ignore", "ignore", "pipe"],
  env: {
    ...process.env,
    CADRUMO_DESKTOP_PREVIEW_DATA_DIR: resolve(evidence, "webview"),
    WEBVIEW2_ADDITIONAL_BROWSER_ARGUMENTS: `--remote-debugging-port=${address.port} --remote-debugging-address=127.0.0.1`,
  },
});
let launchError;
let diagnostic = "";
child.stderr.on("data", (chunk) => {
  diagnostic = (diagnostic + chunk.toString()).slice(-8192);
});
child.on("error", (error) => {
  launchError = error;
});
let browser;
try {
  const endpoint = `http://127.0.0.1:${address.port}`;
  const deadline = Date.now() + 30000;
  let connected = false;
  while (Date.now() < deadline) {
    if (launchError) throw launchError;
    if (child.exitCode !== null)
      throw new Error(`Native host exited: ${child.exitCode}`);
    try {
      const response = await fetch(`${endpoint}/json/version`, {
        signal: AbortSignal.timeout(500),
      });
      if (response.ok) {
        connected = true;
        break;
      }
    } catch {
      /* The owned WebView has not opened its debugging endpoint yet. */
    }
    await delay(200);
  }
  if (!connected)
    throw new Error(
      "Native WebView did not become inspectable within 30 seconds.",
    );
  browser = await chromium.connectOverCDP(endpoint);
  const context = browser.contexts()[0];
  if (!context) throw new Error("No native WebView context.");
  const page = context.pages()[0] ?? (await context.waitForEvent("page"));
  await expect(
    page.getByRole("heading", { name: "Textual workbench" }),
  ).toBeVisible();
  if (!/^(https?:\/\/tauri\.localhost|tauri:\/\/localhost)/.test(page.url()))
    throw new Error(`Unexpected native asset origin: ${page.url()}`);
  await context.setOffline(true);
  await page
    .getByRole("button", { name: "How your records become tax figures" })
    .click();
  await expect(
    page.getByRole("heading", { name: "Tracing a number back to the law" }),
  ).toBeVisible();
  await page.getByRole("button", { name: "Toggle console panel" }).click();
  await expect(page.locator(".xterm")).toHaveCount(2);
  await page.screenshot({ path: resolve(evidence, "native-window.png") });
  writeFileSync(
    resolve(evidence, "native-smoke.json"),
    JSON.stringify(
      {
        result: "pass",
        origin: page.url(),
        platform: process.platform,
        frontend: "bundled",
        offlineNavigation: true,
        terminalViewports: 2,
        nativePty: "not integrated",
        storageTracing: "not performed",
      },
      null,
      2,
    ),
  );
  console.log(
    "Native WebView: bundled assets, offline docs and both terminal viewports passed.",
  );
} catch (error) {
  writeFileSync(
    resolve(evidence, "native-smoke.json"),
    JSON.stringify(
      {
        result: "failed",
        error: String(error),
        diagnostic,
        nativePty: "not integrated",
        storageTracing: "not performed",
      },
      null,
      2,
    ),
  );
  throw error;
} finally {
  try {
    if (browser) await browser.close();
  } finally {
    if (child.exitCode === null && child.pid) {
      const exited = once(child, "exit");
      child.kill();
      await exited;
    }
  }
}
