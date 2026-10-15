import assert from "node:assert/strict";
import { spawn } from "node:child_process";
import { createHash } from "node:crypto";
import { copyFile, mkdir, readFile, writeFile } from "node:fs/promises";
import { resolve } from "node:path";
import { before, after, test } from "node:test";
import { buildPath } from "../scripts/build-paths.mjs";
import { packagedHost } from "./packaged/host.mjs";
import { DesktopInput, freePort } from "./packaged/os.mjs";
import { chromium, devtoolsEndpoint, waitFor } from "./packaged/session.mjs";

const root = resolve(
  buildPath("desktop_testing"),
  "startup",
  new Date().toISOString().replace(/[:.]/g, "-"),
);
const packageRoot = resolve(root, "app");
const input = new DesktopInput();
let contract;

before(async () => {
  const source = process.env.CADRUMO_DESKTOP_PACKAGE_ROOT;
  assert(
    source,
    "Select an assembled package with CADRUMO_DESKTOP_PACKAGE_ROOT",
  );
  contract = JSON.parse(
    await readFile(process.env.CADRUMO_NATIVE_CONTRACT, "utf8"),
  );
  await mkdir(packageRoot, { recursive: true });
  await new Promise((done, reject) => {
    const copy = spawn(
      "robocopy.exe",
      [
        source,
        packageRoot,
        "/E",
        "/MT:16",
        "/NFL",
        "/NDL",
        "/NJH",
        "/NJS",
        "/NP",
      ],
      { windowsHide: true, stdio: "ignore" },
    );
    copy.once("error", reject);
    copy.once("exit", (code) =>
      code < 8
        ? done()
        : reject(new Error(`Package fixture copy failed: ${code}`)),
    );
  });
  const image = resolve(packageRoot, "cadrumo.exe");
  await copyFile(packagedHost().executable, image);
  const manifestPath = resolve(
    packageRoot,
    contract.layout.files.package_manifest,
  );
  const manifest = JSON.parse(await readFile(manifestPath, "utf8"));
  manifest.files["cadrumo.exe"] = createHash("sha256")
    .update(await readFile(image))
    .digest("hex");
  await writeFile(manifestPath, JSON.stringify(manifest, null, 2));
});
after(() => input.close());

async function settled(exit) {
  let timer;
  try {
    return await Promise.race([
      exit,
      new Promise((done) => {
        timer = setTimeout(() => done("timeout"), 45000);
      }),
    ]);
  } finally {
    clearTimeout(timer);
  }
}

async function launch(t, name, overrides = {}) {
  const storage = resolve(root, name);
  await mkdir(storage, { recursive: true });
  const port = await freePort();
  const env = Object.fromEntries(
    Object.entries(process.env).filter(
      ([key]) => !/^(CADRUMO_|WEBVIEW2_)/i.test(key),
    ),
  );
  Object.assign(
    env,
    {
      CADRUMO_DESKTOP_PACKAGE_ROOT: packageRoot,
      CADRUMO_LOCAL_STORAGE_ROOT: storage,
      WEBVIEW2_ADDITIONAL_BROWSER_ARGUMENTS: `--remote-debugging-port=${port}`,
      [contract.desktop_defaults.output_language_variable]: "en",
    },
    overrides,
  );
  const child = spawn(resolve(packageRoot, "cadrumo.exe"), ["--gui"], {
    env,
    cwd: root,
    windowsHide: true,
    stdio: ["ignore", "ignore", "pipe"],
  });
  let stderr = "";
  child.stderr.on("data", (data) => {
    stderr += data;
  });
  const exit = new Promise((done, reject) => {
    child.once("exit", (code) => done(code));
    child.once("error", reject);
  });
  let browser;
  t.after(async () => {
    if (child.exitCode === null) {
      await input.post(child.pid, "close").catch(() => undefined);
      const result = await settled(exit);
      if (result === "timeout") {
        child.kill();
        await exit;
        assert.fail("Startup shutdown did not settle");
      }
    }
    await browser?.close().catch(() => undefined);
  });
  await devtoolsEndpoint(port, 20000);
  browser = await (await chromium()).connectOverCDP(`http://127.0.0.1:${port}`);
  const page = await waitFor(
    () =>
      browser
        .contexts()
        .flatMap((context) => context.pages())
        .find((candidate) => candidate.url().endsWith("/startup.html")),
    { what: "the real loading document" },
  );
  await page.waitForSelector("main");
  if (name !== "failure") {
    assert.equal(await page.locator("main").getAttribute("aria-busy"), "true");
    assert((await page.locator(".spinner").boundingBox()).width > 0);
  }
  await page.screenshot({ path: resolve(storage, "loading.png") });
  return { page, child, exit, storage, stderr: () => stderr };
}

async function close(run, code) {
  assert.equal((await input.post(run.child.pid, "close")).posted, true);
  const result = await settled(run.exit);
  assert.equal(result, code, run.stderr());
  await waitFor(
    async () => {
      const processes = await input.processes([
        "python.exe",
        "cadrumo-runtime.exe",
        "cadrumo-agent-service.exe",
        "aeat.exe",
      ]);
      return !processes.some((process) =>
        process.commandLine.toLowerCase().includes(packageRoot.toLowerCase()),
      );
    },
    { timeout: 15000, what: "startup-owned backend processes to exit" },
  );
}

test(
  "packaged startup reaches a rendered main window with verified runtime readiness",
  { timeout: 180000 },
  async (t) => {
    const run = await launch(t, "ready");
    await waitFor(
      async () => {
        const text = await readFile(
          resolve(run.storage, "logs/cadrumo-native.jsonl"),
          "utf8",
        );
        const records = text
          .trim()
          .split("\n")
          .map(JSON.parse)
          .filter((event) => event.hostPid === run.child.pid);
        const failure = records.find(
          (event) => event.kind === "failure" && event.stage === "manager",
        );
        assert(!failure, `Runtime startup failed: ${failure?.failure?.code}`);
        return records.some(
          (event) => event.stage === "manager" && event.outcome === "ready",
        );
      },
      {
        timeout: 100000,
        what: "verified runtime readiness",
        fatal: (error) => error.code === "ERR_ASSERTION",
      },
    );
    await waitFor(
      async () => (await input.client(run.child.pid)).width >= 520,
      { timeout: 30000, what: "the main workspace window" },
    );
    const controls = await waitFor(
      async () => {
        const elements = await input.request("accessible", {
          pid: run.child.pid,
        });
        return (
          elements.some(
            (element) =>
              element.role === "ControlType.Button" &&
              element.name === "Settings",
          ) && elements
        );
      },
      { timeout: 30000, what: "rendered workspace controls" },
    );
    await writeFile(
      resolve(run.storage, "main-controls.json"),
      JSON.stringify(controls, null, 2),
    );
    await close(run, 0);
  },
);

test(
  "closing while the runtime starts cancels startup and settles the native host",
  { timeout: 120000 },
  async (t) => {
    const run = await launch(t, "cancel");
    await run.page
      .locator('main[data-phase="runtime"]')
      .waitFor({ timeout: 60000 });
    await close(run, 0);
  },
);

test(
  "package preparation failure remains readable until the window is closed",
  { timeout: 60000 },
  async (t) => {
    const run = await launch(t, "failure", {
      CADRUMO_DESKTOP_PACKAGE_ROOT: resolve(root, "missing-package"),
    });
    await run.page.locator("#failure:not([hidden])").waitFor();
    assert.match(
      await run.page.locator("#failure").innerText(),
      /package_unavailable/,
    );
    assert.equal(
      await run.page.locator("main").getAttribute("aria-busy"),
      "false",
    );
    await run.page.screenshot({ path: resolve(run.storage, "failure.png") });
    await close(run, 1);
  },
);
