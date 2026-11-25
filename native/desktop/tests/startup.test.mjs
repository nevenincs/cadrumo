import assert from "node:assert/strict";
import { spawn } from "node:child_process";
import { createHash, randomBytes } from "node:crypto";
import { copyFile, mkdir, readFile, writeFile } from "node:fs/promises";
import { resolve } from "node:path";
import { DatabaseSync } from "node:sqlite";
import { before, after, test } from "node:test";
import { pathToFileURL } from "node:url";
import { buildPath } from "../scripts/build-paths.mjs";
import { packagedHost } from "./packaged/host.mjs";
import { DesktopInput, freePort } from "./packaged/os.mjs";
import {
  chromium,
  devtoolsEndpoint,
  sleep,
  waitFor,
} from "./packaged/session.mjs";

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

/**
 * Starts the host on its own storage. `debugging` names the variables that give
 * a window the free port: by default the loading window's browser takes it.
 */
async function startHost(
  t,
  name,
  overrides = {},
  debugging = (port) => ({
    WEBVIEW2_ADDITIONAL_BROWSER_ARGUMENTS: `--remote-debugging-port=${port}`,
  }),
) {
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
      CADRUMO_STORAGE_ROOT: storage,
      ...debugging(port),
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
  const run = {
    port,
    child,
    exit,
    storage,
    stderr: () => stderr,
    browser: null,
  };
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
    await run.browser?.close().catch(() => undefined);
  });
  return run;
}

async function attach(run, timeout) {
  await devtoolsEndpoint(run.port, timeout);
  run.browser = await (
    await chromium()
  ).connectOverCDP(`http://127.0.0.1:${run.port}`);
}

async function launch(t, name, overrides = {}) {
  const run = await startHost(t, name, overrides);
  await attach(run, 20000);
  const page = await waitFor(
    () =>
      run.browser
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
  await page.screenshot({ path: resolve(run.storage, "loading.png") });
  return { ...run, page };
}

/** The structured log records of the run's host process. */
async function hostEvents(run) {
  const text = await readFile(
    resolve(run.storage, "logs/cadrumo-native.jsonl"),
    "utf8",
  );
  return text
    .trim()
    .split("\n")
    .map(JSON.parse)
    .filter((event) => event.hostPid === run.child.pid);
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
        const records = await hostEvents(run);
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

const TYPED_TEXT_STORES = {
  "Web Data": [
    "autofill",
    "autofill_edge_field_values",
    "autofill_edge_field_client_info",
  ],
  "Login Data": ["logins"],
};
// WebView2 commits its web database on a timer of about ten seconds.
const WEB_DATABASE_COMMIT_MS = 15000;

function holds(value, marker) {
  return (
    (typeof value === "string" && value.includes(marker)) ||
    (value instanceof Uint8Array && Buffer.from(value).includes(marker))
  );
}

/** Reads a closed profile store's tables, never changing the file. */
function storedRows(file, names, marker) {
  const url = new URL(`${pathToFileURL(file).href}?immutable=1`);
  const database = new DatabaseSync(url, { readOnly: true });
  try {
    const present = new Set(
      database
        .prepare("SELECT name FROM sqlite_master WHERE type = 'table'")
        .all()
        .map(({ name }) => name),
    );
    const tables = {};
    for (const table of names) {
      if (!present.has(table)) continue;
      const rows = database.prepare(`SELECT * FROM "${table}"`).all();
      tables[table] = {
        rows: rows.length,
        holdingMarker: rows.filter((row) =>
          Object.values(row).some((value) => holds(value, marker)),
        ).length,
      };
    }
    return tables;
  } finally {
    database.close();
  }
}

/** Adds a real form to the page, above whatever the page is showing. */
function addForm(page, { id, target, action, fields }) {
  return page.evaluate(
    ({ id, target, action, fields }) => {
      const form = document.createElement("form");
      form.id = id;
      form.method = action ? "get" : "post";
      form.action = `${location.origin}/${action ?? id}`;
      if (target) {
        const sink = document.createElement("iframe");
        sink.name = target;
        sink.hidden = true;
        document.body.append(sink);
        form.target = target;
      }
      form.style.cssText =
        "position:fixed;top:0;left:0;z-index:2147483647;background:#fff";
      for (const { name, type, autocomplete } of fields) {
        const field = document.createElement("input");
        field.type = type;
        field.name = name;
        field.autocomplete = autocomplete;
        form.append(field);
      }
      const submit = document.createElement("button");
      submit.type = "submit";
      submit.textContent = "Submit";
      form.append(submit);
      document.body.append(form);
    },
    { id, target, action, fields },
  );
}

/** Types into each field as a person does, leaving it with Tab, then submits. */
async function typeAndSubmit(page, id, values) {
  for (const [name, text] of Object.entries(values)) {
    const field = page.locator(`#${id} [name="${name}"]`);
    await field.click();
    await page.keyboard.type(text, { delay: 10 });
    await page.keyboard.press("Tab");
    assert.equal(await field.inputValue(), text);
  }
  // Kept across the navigation a form that leaves the page starts.
  await page.evaluate((id) => {
    document.getElementById(id).addEventListener("submit", () => {
      sessionStorage.setItem(id, "submitted");
    });
  }, id);
  await page.locator(`#${id} [type="submit"]`).click({ noWaitAfter: true });
  await waitFor(
    () => page.evaluate((id) => sessionStorage.getItem(id) !== null, id),
    { timeout: 10000, what: `the ${id} form to submit` },
  );
}

test(
  "text typed and submitted in the workspace window stays out of the webview's stores",
  { timeout: 240000 },
  async (t) => {
    // The workspace's own DevTools port keeps it in the data directory the
    // product gives it, under this run's storage.
    const run = await startHost(t, "form-history", {}, (port) => ({
      CADRUMO_DEV_DESKTOP_DEVTOOLS_PORT: String(port),
    }));
    await attach(run, 120000);
    const webview = resolve(run.storage, contract.desktop_defaults.webview);
    const shell = await waitFor(
      () =>
        run.browser
          .contexts()
          .flatMap((context) => context.pages())
          .find((page) => new URL(page.url()).hostname === "tauri.localhost"),
      { timeout: 120000, what: "the workspace document" },
    );
    await shell.waitForLoadState("load");
    const browsers = async () =>
      (await input.processes(["msedgewebview2.exe"])).filter((process) =>
        process.commandLine.toLowerCase().includes(webview.toLowerCase()),
      );
    assert(
      (await browsers()).length > 0,
      "The webview is not in the run's own storage",
    );

    const marker = `CadrumoFormHistoryProbe${randomBytes(8).toString("hex")}`;
    // The loading page in this webview: the shell's sign-in dialog, which opens
    // by itself, would hold the focus and the pointer.
    await shell.goto(new URL("/startup.html", shell.url()).href);
    await addForm(shell, {
      id: "form-history-probe",
      target: "form-history-sink",
      fields: [
        { name: "organization", type: "text", autocomplete: "organization" },
        { name: "comment", type: "text", autocomplete: "on" },
      ],
    });
    await typeAndSubmit(shell, "form-history-probe", {
      organization: `${marker}A`,
      comment: `${marker}B`,
    });
    await sleep(WEB_DATABASE_COMMIT_MS);
    // A password is offered for saving when its form leaves the page.
    await addForm(shell, {
      id: "password-probe",
      action: "startup.html",
      fields: [
        { name: "username", type: "text", autocomplete: "username" },
        {
          name: "password",
          type: "password",
          autocomplete: "current-password",
        },
      ],
    });
    await typeAndSubmit(shell, "password-probe", {
      username: `${marker}U`,
      password: `${marker}P`,
    });
    await sleep(WEB_DATABASE_COMMIT_MS);
    // The close guard still asks the shell this test navigated away from; a
    // second close while that goes unanswered closes the window.
    assert.equal((await input.post(run.child.pid, "close")).posted, true);
    await close(run, 0);
    await waitFor(async () => (await browsers()).length === 0, {
      timeout: 30000,
      what: "the webview processes to exit",
    });

    const observed = {};
    for (const [store, names] of Object.entries(TYPED_TEXT_STORES)) {
      const file = resolve(webview, "EBWebView/Default", store);
      const bytes = await readFile(file);
      observed[store] = {
        tables: storedRows(file, names, marker),
        raw:
          bytes.includes(marker) ||
          bytes.includes(Buffer.from(marker, "utf16le")),
      };
    }
    t.diagnostic(`typed text stores: ${JSON.stringify(observed)}`);
    for (const [store, names] of Object.entries(TYPED_TEXT_STORES)) {
      const { tables, raw } = observed[store];
      assert(tables[names[0]], `${store} has no ${names[0]} table to inspect`);
      // A new profile holds nothing in these; a field's client metadata
      // appears without the text, so rows are counted as well as searched.
      for (const [table, { rows, holdingMarker }] of Object.entries(tables)) {
        assert.equal(holdingMarker, 0, `${table} kept the typed text`);
        assert.equal(rows, 0, `${table} recorded the form`);
      }
      assert.equal(raw, false, `${store} holds the typed text`);
    }
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
    // The window says what happened in words; the code is for the log.
    assert.equal(
      await run.page.locator("#failure").innerText(),
      "The application could not finish starting.",
    );
    assert.equal(
      await run.page.locator("main").getAttribute("aria-busy"),
      "false",
    );
    await run.page.screenshot({ path: resolve(run.storage, "failure.png") });
    await close(run, 1);
    const events = await hostEvents(run);
    assert(
      events.some(
        (event) =>
          event.kind === "failure" &&
          event.failure?.code === "package_unavailable",
      ),
      "The log does not name the package failure",
    );
    assert.equal(
      events.find((event) => event.kind === "host_stopped")?.hostExitCode,
      1,
    );
  },
);
