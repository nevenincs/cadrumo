// The packaged end-to-end test of the desktop window. It launches the test
// host (built with webview2-remote-debugging) against an assembled package,
// drives the window over the WebView2 DevTools protocol and real desktop input,
// and writes one PASS, FAIL, SKIP or INFO line per check to a results
// directory. It needs an interactive desktop session; see run-packaged.ps1.
import assert from "node:assert/strict";
import { spawn, spawnSync } from "node:child_process";
import { createHash, randomBytes } from "node:crypto";
import {
  copyFileSync,
  existsSync,
  mkdirSync,
  openSync,
  readFileSync,
  readdirSync,
  statSync,
} from "node:fs";
import { dirname, isAbsolute, resolve } from "node:path";
import { test } from "node:test";

import { buildPath } from "../scripts/build-paths.mjs";
import { docsOrigin as docsOriginOf } from "../scripts/configuration.mjs";
import { docsProbe, pagefindSearch, pasteInto } from "./packaged/browser.mjs";
import { hostRefusals, refusalProbe, tokenCheck } from "./packaged/probes.mjs";
import { packagedHost, packagedHostPaths } from "./packaged/host.mjs";
import { SignInFixture } from "./packaged/sign-in.mjs";
import { docsUiChecks } from "./packaged/docs-ui.mjs";
import {
  DesktopInput,
  descendants,
  freePort,
  survivors,
} from "./packaged/os.mjs";
import { Results } from "./packaged/results.mjs";
import {
  connect,
  devtoolsEndpoint,
  sleep,
  waitFor,
} from "./packaged/session.mjs";
import {
  FAIL,
  PASS,
  channelFetchVerdict,
  closeVerdict,
  creditVerdict,
  cspVerdict,
  everyByteVerdict,
  framesVerdict,
  noEffectVerdict,
  pagefindVerdict,
  terminalVerdict,
} from "./packaged/verdicts.mjs";

const SKIP = "SKIP";
const INFO = "INFO";
const REMOTE = "WEBVIEW2_ADDITIONAL_BROWSER_ARGUMENTS";
const PROCESS_NAMES = [
  "cadrumo.exe",
  "python.exe",
  "pwsh.exe",
  "powershell.exe",
  "conhost.exe",
  "OpenConsole.exe",
  "msedgewebview2.exe",
  "cadrumo-runtime.exe",
];

function settings() {
  const packageRoot = process.env.CADRUMO_DESKTOP_PACKAGE_ROOT;
  assert(
    packageRoot && isAbsolute(packageRoot),
    "Set CADRUMO_DESKTOP_PACKAGE_ROOT to an assembled package that carries docs/user/manifest.json.",
  );
  const stamp = new Date().toISOString().replace(/[:.]/g, "-");
  const run = resolve(buildPath("desktop_testing"), "packaged", "runs", stamp);
  return {
    stamp,
    packageRoot,
    storageVariable:
      process.env.CADRUMO_STORAGE_ROOT_VARIABLE || "CADRUMO_LOCAL_STORAGE_ROOT",
    run,
    storage: resolve(run, "storage"),
    results:
      process.env.CADRUMO_PACKAGED_RESULTS ||
      resolve(buildPath("desktop_results"), "packaged", stamp),
    allowBrowser: process.env.CADRUMO_PACKAGED_ALLOW_BROWSER === "1",
  };
}

/** The host's environment: the caller's, without CADRUMO_ or WEBVIEW2_ variables. */
function hostEnvironment(config, extra = {}) {
  const removed = [];
  const env = {};
  for (const [key, value] of Object.entries(process.env)) {
    if (/^(CADRUMO_|WEBVIEW2_)/i.test(key)) removed.push(key);
    else env[key] = value;
  }
  env[config.storageVariable] = config.storage;
  env.CADRUMO_DESKTOP_PACKAGE_ROOT = config.packageRoot;
  return { env: { ...env, ...extra }, removed };
}

function htmlTitle(file) {
  const match = /<title>([\s\S]*?)<\/title>/i.exec(readFileSync(file, "utf8"));
  if (!match) return null;
  return match[1]
    .replace(/&lt;/g, "<")
    .replace(/&gt;/g, ">")
    .replace(/&quot;/g, '"')
    .replace(/&#39;|&#x27;/g, "'")
    .replace(/&#8212;/g, "—")
    .replace(/&#8211;/g, "–")
    .replace(/&nbsp;/g, " ")
    .replace(/&amp;/g, "&")
    .trim();
}

/** Runs the host's own projection query and keeps only the paths it declares. */
function projection(config, packageRoot, env) {
  const contract = JSON.parse(
    readFileSync(process.env.CADRUMO_NATIVE_CONTRACT, "utf8"),
  );
  const query = readFileSync(
    new URL("../src-tauri/src/python/environment.py", import.meta.url),
    "utf8",
  );
  const result = spawnSync(
    resolve(packageRoot, contract.layout.paths.executable),
    ["-I", "-c", query],
    {
      cwd: config.run,
      env,
      encoding: "utf8",
      timeout: 60000,
      windowsHide: true,
    },
  );
  if (result.status !== 0)
    throw new Error(
      `projection query exited ${result.status}: ${result.stderr.slice(0, 300)}`,
    );
  const value = JSON.parse(result.stdout);
  return {
    storage: value.storage,
    webview: value.webview,
    logs: value.logs,
    logFile: value.log_file,
    outputLanguage: value.output_language,
    home: value.home,
  };
}

function sha256(text) {
  return createHash("sha256").update(text).digest("hex");
}

function launch(executable, args, { env, cwd, out, err }) {
  const child = spawn(executable, args, {
    cwd,
    env,
    stdio: ["ignore", openSync(out, "w"), openSync(err, "w")],
    windowsHide: false,
  });
  const exit = new Promise((done) =>
    child.on("exit", (code) => done({ code, at: Date.now() })),
  );
  return { child, exit };
}

async function exited(exit, ms) {
  return Promise.race([exit, sleep(ms).then(() => null)]);
}

test("packaged desktop window", { timeout: 45 * 60 * 1000 }, async (t) => {
  const config = settings();
  mkdirSync(config.storage, { recursive: true });
  const results = new Results(config.results);
  const startedAt = new Date().toISOString();
  const summary = {};
  const input = new DesktopInput();
  let session = null;
  let host = null;
  let hostPid = null;
  let projected = null;
  let webviewPids = [];
  let signIn = null;

  const record = async (kind, id, title, run) => {
    let outcome;
    try {
      outcome = await run();
    } catch (error) {
      outcome = { verdict: FAIL, detail: `error: ${error?.message ?? error}` };
    }
    const entry = results.record({ kind, id, title, ...outcome });
    await t.test(
      `${entry.verdict} ${id}`,
      { skip: entry.verdict === SKIP && entry.detail },
      () => {
        if (entry.verdict === FAIL) assert.fail(`${title}: ${entry.detail}`);
      },
    );
    return entry;
  };
  const check = (id, title, run) => record("check", id, title, run);
  const experiment = (id, title, run) => record("experiment", id, title, run);
  const evidence = (name, value) => results.evidence(name, value);

  try {
    // Preflight ----------------------------------------------------------
    const testHost = packagedHost();
    const desktop = await input.session();
    summary.host = testHost.executable;
    summary.hostSha256 = testHost.sha256;
    summary.package = config.packageRoot;
    summary.storage = config.storage;
    summary.sessionId = desktop.sessionId;
    const preflight = await check(
      "preflight",
      "interactive desktop, test host and documentation",
      async () => {
        const problems = [];
        if (!desktop.inputDesktop || desktop.sessionId === 0)
          problems.push(
            `session ${desktop.sessionId} has no interactive input desktop`,
          );
        if (!existsSync(resolve(config.packageRoot, "docs/user/manifest.json")))
          problems.push("the package has no docs/user/manifest.json");
        return problems.length
          ? { verdict: FAIL, detail: problems.join("; ") }
          : {
              verdict: PASS,
              detail: `session ${desktop.sessionId}, host ${testHost.sha256.slice(0, 12)} with ${testHost.features.join(", ")}`,
            };
      },
    );
    if (preflight.verdict !== PASS) return;

    const tauri = JSON.parse(
      readFileSync(packagedHostPaths().configuration, "utf8"),
    );
    const window = tauri.app.windows[0];
    const scheme = window.useHttpsScheme ? "https" : "http";
    const shellOrigins = [`${scheme}://tauri.localhost`];
    const docsOrigin = docsOriginOf(window);
    const ipcPrefix = `${scheme}://ipc.localhost/`;
    const manifest = JSON.parse(
      readFileSync(
        resolve(config.packageRoot, "docs/user/manifest.json"),
        "utf8",
      ),
    );
    projected = projection(
      config,
      config.packageRoot,
      hostEnvironment(config).env,
    );
    summary.webview = projected.webview;
    evidence("projection.json", projected);

    signIn = new SignInFixture({
      config,
      env: hostEnvironment(config).env,
      contract: JSON.parse(
        readFileSync(process.env.CADRUMO_NATIVE_CONTRACT, "utf8"),
      ),
      results,
    });
    const fixture = await check(
      "sign-in-fixture",
      "canonical profile creation and explicitly owned packaged runtime",
      () => signIn.start(),
    );
    if (fixture.verdict !== PASS) return;

    // The test build admits only a single remote debugging port --------------
    await check(
      "override-refused",
      "the test host refuses every other WebView2 override",
      async () => {
        const port = await freePort();
        const cases = [
          {
            [REMOTE]: `--remote-debugging-port=${port} --remote-allow-origins=*`,
          },
          {
            [REMOTE]: `--remote-debugging-port=${port}`,
            WEBVIEW2_USER_DATA_FOLDER: resolve(config.run, "elsewhere"),
          },
        ];
        const outcomes = [];
        for (const [index, extra] of cases.entries()) {
          const { env } = hostEnvironment(config, extra);
          const out = resolve(config.run, `refused-${index}.out`);
          const err = resolve(config.run, `refused-${index}.err`);
          const started = launch(testHost.executable, ["--gui"], {
            env,
            cwd: config.run,
            out,
            err,
          });
          const done = await exited(started.exit, 60000);
          if (!done) started.child.kill();
          const stderr = readFileSync(err, "utf8");
          let code = null;
          try {
            code = JSON.parse(stderr.trim().split("\n").pop()).code;
          } catch {
            code = stderr.slice(0, 120);
          }
          outcomes.push({
            variables: Object.keys(extra),
            exit: done?.code ?? "running",
            code,
          });
        }
        evidence("override-refused.json", outcomes);
        const bad = outcomes.filter(
          (o) => o.exit !== 1 || o.code !== "environment_failed",
        );
        return bad.length
          ? {
              verdict: FAIL,
              detail: `not refused: ${JSON.stringify(bad)}`,
              data: outcomes,
            }
          : {
              verdict: PASS,
              detail: "both refused with environment_failed, exit 1",
              data: outcomes,
            };
      },
    );

    // Launch ----------------------------------------------------------------
    const port = await freePort();
    const { env: hostEnv, removed } = hostEnvironment(config, {
      [REMOTE]: `--remote-debugging-port=${port}`,
    });
    summary.removedVariables = removed.join(", ") || "none";
    host = launch(testHost.executable, ["--gui"], {
      env: hostEnv,
      cwd: config.run,
      out: resolve(config.results, "host-stdout.txt"),
      err: resolve(config.results, "host-stderr.txt"),
    });
    hostPid = host.child.pid;
    const launched = await check(
      "launch",
      "the window opens with the DevTools endpoint",
      async () => {
        const early = host.exit.then((done) => {
          throw new Error(`the host exited with ${done.code}`);
        });
        early.catch(() => undefined);
        const endpoint = await Promise.race([
          devtoolsEndpoint(port, 90000),
          early,
        ]);
        session = await connect({
          endpoint,
          shellOrigins,
          docsOrigin,
          ipcPrefix,
          blockExternal: !config.allowBrowser,
        });
        const cdp = await session.browser.newBrowserCDPSession();
        const version = await cdp.send("Browser.getVersion");
        summary.webview2 = `${version.product} (${version.userAgent.match(/Edg\/[\d.]+/)?.[0] ?? "?"})`;
        return { verdict: PASS, detail: `${endpoint}, ${version.product}` };
      },
    );
    if (launched.verdict !== PASS) return;
    const { page } = session;
    const environment = await session.call("desktop_environment");
    evidence("desktop-environment.json", environment);
    await session.waitDocs(60000);
    await results.screenshot(page, "01-loaded");

    const webviewProcesses = async () =>
      (await input.processes(["msedgewebview2.exe"])).filter((p) =>
        p.commandLine.toLowerCase().includes(projected.webview.toLowerCase()),
      );
    webviewPids = (await webviewProcesses()).map((p) => p.pid);
    await experiment(
      "webview2-interfaces",
      "WebView2 runtime exposes ICoreWebView2_22 and ICoreWebView2Settings3",
      async () => ({
        verdict: INFO,
        detail: `the host started, so its probe found both interfaces and read its settings back; runtime ${summary.webview2}; ${webviewPids.length} webview processes under the projected profile`,
      }),
    );

    // Origins and title -----------------------------------------------------
    const entries = environment.ok ? environment.value.docs.languages : [];
    await check(
      "docs-origin",
      "the shell loads and the documentation frame is on the docs origin",
      async () => {
        const frame = session.docsFrame();
        const entry = entries.find(
          (language) => language.entry === frame?.url(),
        );
        const relative = entry && manifest.entries[entry.code];
        const expectedTitle = relative
          ? htmlTitle(resolve(config.packageRoot, "docs/user", relative))
          : "<the frame is not on a published language entry>";
        return framesVerdict({
          shellUrl: page.url(),
          shellOrigins,
          docsUrl: frame?.url(),
          docsOrigin: environment.ok
            ? environment.value.docs.origin
            : docsOrigin,
          docsTitle: await frame?.title(),
          expectedTitle,
        });
      },
    );

    const authenticated = await check(
      "canonical-sign-in",
      "real password form signs in through the packaged CLI",
      () => signIn.signIn(session, input, hostPid),
    );

    // Terminals -------------------------------------------------------------
    await check(
      "python-prompt",
      "the Python tab shows the REPL prompt",
      async () =>
        terminalVerdict(
          await session
            .waitRows("python", (rows) => rows.includes(">>>"), {
              timeout: 60000,
            })
            .catch(() => session.rows("python")),
          [">>>"],
          "REPL prompt",
        ),
    );
    await check(
      "python-unicode",
      'print("á漢") echoes the two characters',
      async () => {
        await session.type("python", 'print("á漢")');
        const rows = await session
          .waitRows("python", (text) => /^á漢\s*$/m.test(text), {
            timeout: 15000,
          })
          .catch(() => session.rows("python"));
        return terminalVerdict(rows, [/^á漢\s*$/m], "Unicode output line");
      },
    );
    const runtime = resolve(config.packageRoot, "bin", "cadrumo-runtime.exe");
    await check(
      "console-runtime",
      "the Console tab shows a prompt and resolves cadrumo-runtime into the package bin",
      async () => {
        await session.waitRows("console", (rows) => /PS .+>/.test(rows), {
          timeout: 60000,
        });
        await session.type(
          "console",
          `"S10-RT=" + ((Get-Command cadrumo-runtime).Source -eq '${runtime}')`,
        );
        const rows = await session
          .waitRows("console", (text) => /^S10-RT=(True|False)/m.test(text), {
            timeout: 20000,
          })
          .catch(() => session.rows("console"));
        return terminalVerdict(
          rows,
          [/PS .+>/, /^S10-RT=True/m],
          `prompt and ${runtime}`,
        );
      },
    );
    await check(
      "tui-alternate-screen",
      "the TUI pane enters the alternate screen",
      async () => {
        if (authenticated.verdict !== PASS)
          return {
            verdict: SKIP,
            detail: "canonical sign-in failed; TUI remains gated",
          };
        const state = await waitFor(
          async () => {
            const value = await session.terminal("tui");
            return value?.altScreen || value?.exited ? value : null;
          },
          { timeout: 90000, what: "the TUI alternate screen" },
        ).catch(() => session.terminal("tui"));
        await results.screenshot(page, "02-terminals");
        if (state?.altScreen)
          return {
            verdict: PASS,
            detail: `\\x1b[?1049h after ${state.dataBytes} bytes`,
          };
        return {
          verdict: FAIL,
          detail: `no alternate screen${state?.exited ? `; the TUI exited with ${state.exited.code}` : ""}`,
          data: { rows: (await session.rows("tui"))?.slice(-800) },
        };
      },
    );

    // Token -----------------------------------------------------------------
    await check(
      "token",
      "the shell read the token once and the docs frame cannot read it",
      async () => {
        const { observed, ...verdict } = await tokenCheck(session);
        evidence("token.json", observed);
        return verdict;
      },
    );

    // Logs ------------------------------------------------------------------
    const logNonce = `S10-LOG-${randomBytes(6)
      .toString("base64url")
      .replace(/[^A-Za-z]/g, "q")}`;
    await check(
      "logs-flyout",
      "a Python child's log line reaches the Logs tab",
      async () => {
        await session.type(
          "python",
          `import logging; from cadrumo.core.logging import configure_logging; configure_logging(); logging.getLogger("cadrumo.s10").warning("${logNonce}")`,
        );
        const found = await waitFor(
          () =>
            session.shell(
              (nonce) =>
                window.__s10.logs.records.find(
                  (r) => r.source === "python" && r.message.includes(nonce),
                ),
              logNonce,
            ),
          { timeout: 20000, what: "the log record" },
        ).catch(() => null);
        await session.showTab("logs");
        const shown = await page
          .locator(".logview-list")
          .innerText({ timeout: 5000 })
          .then((text) => text.includes(logNonce))
          .catch(() => false);
        await results.screenshot(page, "03-logs");
        const hostRecords = await session.shell(
          () =>
            window.__s10.logs.records.filter((r) => r.source === "host").length,
        );
        await session.showTab("python");
        if (!found)
          return {
            verdict: FAIL,
            detail: "no python record carried the probe line",
          };
        if (!shown)
          return {
            verdict: FAIL,
            detail: "the record arrived but the Logs tab does not show it",
          };
        return {
          verdict: PASS,
          detail: `${found.level} ${found.logger} shown; ${hostRecords} host record(s)`,
        };
      },
    );

    // Documentation: CSP, search and a localized root ---------------------------
    const shown = session.docsFrame()?.url();
    const shownEntry = entries.find((language) => language.entry === shown);
    const localized = entries.find(
      (language) => language.code !== shownEntry?.code,
    );
    const docsVisits = [];
    const visit = async (url, settle) => {
      const frame = session.docsFrame();
      await frame.goto(url, { waitUntil: "load", timeout: 60000 });
      await session.waitDocs(30000);
      if (settle) await settle(session.docsFrame());
      await sleep(1500);
      docsVisits.push({ url, frames: await session.frames() });
    };
    let pagefind = null;
    let pageResults = 0;
    await visit(shown);
    const searchBase = shownEntry
      ? shown.replace(/[^/]*$/, "")
      : `${docsOrigin}/`;
    await visit(`${searchBase}search.html?q=modelo`, async (frame) => {
      pageResults = await waitFor(
        () => frame.locator(".cadrumo-search-page-list li").count(),
        { timeout: 20000, what: "search page results" },
      ).catch(() => 0);
      pagefind = await frame
        .evaluate(pagefindSearch, {
          query: "modelo",
          bundle: "pagefind/pagefind.js",
        })
        .catch((error) => ({
          results: 0,
          error: String(error?.message ?? error),
        }));
    });
    await results.screenshot(page, "04-search");
    if (localized) await visit(localized.entry);
    await visit(shown);
    await docsUiChecks({ session, check, visit, shown, localized, docsOrigin });
    const shellState = (await session.frames())[0];
    evidence("docs-visits.json", docsVisits);
    await check(
      "csp-zero",
      "zero CSP violations in both frames across index, search and a localized root",
      async () => {
        const frames = [
          shellState,
          ...docsVisits
            .map((v) => v.frames.find((f) => f.role === "docs"))
            .filter(Boolean),
        ];
        const verdict = cspVerdict(
          frames,
          session.console.map((entry) => entry.text),
        );
        return {
          ...verdict,
          detail: `${verdict.detail}; visited ${docsVisits.map((v) => new URL(v.url).pathname + new URL(v.url).search).join(", ")}${localized ? "" : " (no second language in the package)"}`,
        };
      },
    );
    await check(
      "pagefind-search",
      "a Pagefind query returns results without the main-thread fallback",
      async () =>
        pagefindVerdict({
          results: pagefind?.results,
          pageResults,
          consoleTexts: [
            ...session.console.map((entry) => entry.text),
            ...docsVisits.flatMap((v) =>
              v.frames.flatMap((f) => f.console.map((c) => c.text)),
            ),
          ],
        }),
    );
    await experiment(
      "pagefind-worker",
      "Pagefind's worker on the custom scheme",
      async () => ({
        verdict: INFO,
        detail: `bundle search ${JSON.stringify(pagefind)}; a fallback warning would fail pagefind-search`,
      }),
    );
    await experiment(
      "bridge-postmessage",
      "postMessage between the shell and docs origins in both directions",
      async () => {
        const shell = shellState.messages.filter(
          (m) => m.origin === docsOrigin,
        );
        const docs = docsVisits
          .flatMap(
            (v) => v.frames.find((f) => f.role === "docs")?.messages ?? [],
          )
          .filter((m) => m.fromParent && shellOrigins.includes(m.origin));
        return {
          verdict: INFO,
          detail: `docs to shell: ${shell.length} (${[...new Set(shell.map((m) => m.type))].join(", ")}); shell to docs: ${docs.length} (${[...new Set(docs.map((m) => m.type))].join(", ")})`,
        };
      },
    );
    await experiment(
      "frame-ancestors",
      "frame-ancestors from the custom-scheme response header",
      async () => {
        const header = await session.docs(async () => {
          const response = await fetch(location.href, {
            method: "HEAD",
            cache: "no-store",
          });
          return response.headers.get("content-security-policy");
        });
        const ancestors =
          /frame-ancestors ([^;]+)/.exec(header ?? "")?.[1]?.trim() ?? null;
        // A disallowed ancestor: a data: frame between the shell and the docs,
        // possible only while the shell's own policy is bypassed.
        const cdp = await session.cdp();
        let enforcement;
        try {
          await cdp.send("Page.setBypassCSP", { enabled: true });
          enforcement = await session.shell(async (src) => {
            const outer = document.createElement("iframe");
            outer.id = "s10-ancestors";
            outer.style.cssText =
              "position:fixed;width:10px;height:10px;opacity:0";
            outer.src = `data:text/html,<iframe src="${src}"></iframe>`;
            document.body.append(outer);
            await new Promise((done) => setTimeout(done, 4000));
            return "inserted";
          }, shown);
          const nested = page
            .frames()
            .filter((f) => f.parentFrame()?.parentFrame() === page.mainFrame());
          const loaded = [];
          for (const frame of nested)
            loaded.push(
              await frame
                .evaluate(() => document.title)
                .then(
                  (title) => `loaded "${title}"`,
                  (e) => `unreadable: ${String(e.message).slice(0, 80)}`,
                ),
            );
          enforcement = `${enforcement}; nested frames ${nested.map((f) => f.url()).join(", ") || "none"}: ${loaded.join(", ") || "none"}`;
        } catch (error) {
          enforcement = `could not construct a disallowed ancestor: ${error.message}`;
        } finally {
          await session
            .shell(() => document.getElementById("s10-ancestors")?.remove())
            .catch(() => undefined);
          await cdp
            .send("Page.setBypassCSP", { enabled: false })
            .catch(() => undefined);
        }
        const blocked = session.console
          .filter((entry) => /frame-ancestors/i.test(entry.text))
          .map((entry) => entry.text);
        return {
          verdict: INFO,
          detail: `header frame-ancestors ${ancestors}; enforcement: ${enforcement}; console: ${blocked.slice(-1)[0] ?? "no frame-ancestors report"}`,
        };
      },
    );

    // Refusal from inside the documentation frame -------------------------------
    const refusals = () => hostRefusals(session);
    const original = await session.call("shell_clipboard_read");
    if (original.ok) results.secret(original.value.text);
    const baseline = `S10-BASELINE-${randomBytes(6).toString("hex")}`;
    await session.call("shell_clipboard_write", { text: baseline });
    const probe = async (kind) => {
      const { result, ...verdict } = await refusalProbe(session, kind, {
        ipcOrigin: ipcPrefix.slice(0, -1),
        baseline,
      });
      evidence(`probe-${kind}.json`, result);
      return verdict;
    };
    await check(
      "docs-invoke-refused",
      "invoke from the docs frame is refused",
      () => probe("invoke"),
    );
    await check(
      "docs-fetch-refused",
      "a fetch to the IPC origin from the docs frame is blocked",
      () => probe("fetch"),
    );
    await check(
      "docs-ipc-postmessage-refused",
      "window.ipc.postMessage from the docs frame delivers nothing",
      () => probe("ipc-post-message"),
    );
    await check(
      "docs-webview-postmessage-refused",
      "chrome.webview.postMessage from the docs frame delivers nothing",
      () => probe("webview-post-message"),
    );

    // Flood: credit window, channel fetch from docs, every byte ---------------------
    const quiet = (kind, ms) =>
      waitFor(
        async () => {
          const a = await session.terminal(kind);
          await sleep(ms);
          const b = await session.terminal(kind);
          return a && b && a.dataBytes === b.dataBytes ? b : null;
        },
        { timeout: 240000, interval: 0, what: `${kind} output to settle` },
      );
    const flood = (lines, end) =>
      `_ = [print("S10-FLOOD %07d %s" % (i, "x" * 100)) for i in range(${lines})]; print("${end.slice(0, 4)}" + "${end.slice(4)}")`;
    await session.focusTerminal("python");
    await quiet("python", 1000);
    await session.shell(() => window.__s10.hold());
    await session.type("python", flood(40000, "S10-FLOOD-END"));
    const channelProbe = session.docs(docsProbe, {
      kind: "channel-fetch",
      ids: 512,
      timeoutMs: 3000,
    });
    const paused = await quiet("python", 2000);
    const plateau = paused.dataBytes - paused.acked;
    const fetched = await channelProbe;
    await check(
      "credit-backpressure",
      "with acknowledgements held the host pauses at the credit window",
      async () => creditVerdict({ plateau }),
    );
    await session.shell(() => window.__s10.release());
    const finished = await session
      .waitRows(
        "python",
        (rows) =>
          rows.includes("S10-FLOOD-END") &&
          /^>>>/m.test(rows.split("S10-FLOOD-END").pop()),
        { timeout: 300000 },
      )
      .then(() => quiet("python", 1500))
      .catch(() => session.terminal("python"));
    const channels = await session.shell(() => window.__s10.channels);
    const gaps = Object.values(channels).reduce(
      (sum, c) => sum + (c.maxIndex + 1 - c.seen),
      0,
    );
    const outOfOrder = Object.values(channels).reduce(
      (sum, c) => sum + c.outOfOrder,
      0,
    );
    evidence("channels.json", channels);
    evidence("probe-channel-fetch.json", fetched);
    await check(
      "docs-channel-fetch-refused",
      "channel fetch ids 0..511 from the docs frame during the flood return nothing",
      async () =>
        channelFetchVerdict({ outcomes: fetched.outcomes, gaps, outOfOrder }),
    );
    await check(
      "flood-every-byte",
      "the shell received every byte the host delivered",
      async () => {
        const received = finished.dataBytes;
        const atReceived = await session.call("terminal_ack", {
          session: finished.session,
          offset: received,
        });
        const pastReceived = await session.call("terminal_ack", {
          session: finished.session,
          offset: received + 1,
        });
        return everyByteVerdict({ received, atReceived, pastReceived, gaps });
      },
    );
    await results.screenshot(page, "05-flood");

    // Ctrl+C ------------------------------------------------------------------
    await check(
      "ctrl-c",
      "Ctrl+C reaches a Python child of the GUI host",
      async () => {
        await session.type("python", "import time; time.sleep(60)");
        await sleep(1500);
        await session.page.keyboard.press("Control+c");
        const rows = await session
          .waitRows("python", (text) => text.includes("KeyboardInterrupt"), {
            timeout: 15000,
          })
          .catch(() => session.rows("python"));
        return terminalVerdict(
          rows,
          ["KeyboardInterrupt"],
          "KeyboardInterrupt within 15 s",
        );
      },
    );
    await experiment(
      "ctrl-c-while-paused",
      "Ctrl+C delivery while the reader is paused",
      async () => {
        await quiet("python", 1000);
        await session.shell(() => window.__s10.hold());
        await session.type("python", flood(40000, "S10-FLOOD2-END"));
        await quiet("python", 2000);
        await session.page.keyboard.press("Control+c");
        await sleep(2000);
        await session.shell(() => window.__s10.release());
        const rows = await session
          .waitRows(
            "python",
            (text) =>
              text.includes("KeyboardInterrupt") ||
              text.includes("S10-FLOOD2-END"),
            { timeout: 300000 },
          )
          .catch(() => session.rows("python"));
        await quiet("python", 1500);
        const interrupted =
          rows?.includes("KeyboardInterrupt") &&
          !rows.includes("S10-FLOOD2-END");
        return {
          verdict: INFO,
          detail: interrupted
            ? "Ctrl+C sent while paused interrupted the flood once output resumed"
            : "the flood ran to its end: Ctrl+C sent while paused was not delivered",
        };
      },
    );

    // Restart, resize, paste ---------------------------------------------------
    await check(
      "restart-on-enter",
      "raise SystemExit then Enter restarts the Python session",
      async () => {
        const before = await session.terminal("python");
        await session.type("python", "raise SystemExit");
        const ended = await waitFor(
          async () => {
            const state = await session.terminal("python");
            return state?.exited ? state : null;
          },
          { timeout: 15000, what: "the exit frame" },
        );
        await session.focusTerminal("python");
        await session.page.keyboard.press("Enter");
        const after = await waitFor(
          async () => {
            const state = await session.terminal("python");
            return state && state.id !== before.id && state.started
              ? state
              : null;
          },
          { timeout: 30000, what: "a new Python session" },
        );
        const rows = await session
          .waitRows("python", (text) => text.includes(">>>"), {
            timeout: 30000,
          })
          .catch(() => null);
        return rows
          ? {
              verdict: PASS,
              detail: `session ${before.session} exited ${ended.exited.code ?? "?"}; session ${after.session} shows >>>`,
            }
          : { verdict: FAIL, detail: "the new session shows no prompt" };
      },
    );
    await check(
      "resize-propagates",
      "a panel resize reaches the Python child",
      async () => {
        await session.showTab("python");
        const separator = page.locator(".panel-separator");
        await separator.focus();
        for (let i = 0; i < 4; i += 1) await page.keyboard.press("ArrowUp");
        await sleep(1000);
        const state = await session.terminal("python");
        const resize = await session.shell(
          (id) =>
            window.__s10.ipc
              .filter(
                (e) =>
                  e.cmd === "terminal_resize" && e.args?.session === id && e.ok,
              )
              .pop() ?? null,
          state.session,
        );
        if (!resize)
          return {
            verdict: FAIL,
            detail: "no terminal_resize reached the host",
          };
        await session.type(
          "python",
          'import os; print("S10-SIZE", os.get_terminal_size())',
        );
        const rows = await session
          .waitRows(
            "python",
            (text) =>
              /S10-SIZE os\.terminal_size\(columns=\d+, lines=\d+\)/.test(text),
            { timeout: 15000 },
          )
          .catch(() => session.rows("python"));
        const size =
          /S10-SIZE os\.terminal_size\(columns=(\d+), lines=(\d+)\)/.exec(
            rows ?? "",
          );
        if (!size)
          return { verdict: FAIL, detail: "the child did not report its size" };
        const [cols, lines] = [Number(size[1]), Number(size[2])];
        return cols === resize.args.cols && lines === resize.args.rows
          ? {
              verdict: PASS,
              detail: `child sees ${cols}x${lines}, the last resize sent`,
            }
          : {
              verdict: FAIL,
              detail: `child sees ${cols}x${lines}; last resize ${resize.args.cols}x${resize.args.rows}`,
            };
      },
    );
    await check(
      "paste-200k",
      "a 200 KB paste reaches the child whole, with no write or ack error",
      async () => {
        const filler = "abcdefghijklmnopqrstuvwxyz0123456789".repeat(2);
        const lines = Array.from(
          { length: 2000 },
          (_, i) =>
            `# cadrumo paste probe ${String(i + 1).padStart(5, "0")} ${filler}`,
        );
        const text = `${lines.join("\n")}\n`;
        // xterm sends each line ending as CR; the console's line input returns CR LF.
        const expected = lines.map((line) => `${line}\r\n`).join("");
        await session.waitRows("console", (rows) => /PS .+>/.test(rows), {
          timeout: 30000,
        });
        await session.type(
          "console",
          `python.exe -c "import sys,hashlib;d=sys.stdin.buffer.read(${Buffer.byteLength(expected)});print('S10-PASTE',len(d),hashlib.sha256(d).hexdigest())"`,
        );
        await sleep(2500);
        const consoleState = await session.terminal("console");
        const firstSeq = await session.shell(() => window.__s10.ipc.length);
        await session.shell(pasteInto, { kind: "console", text });
        const rows = await session
          .waitRows(
            "console",
            (value) => /S10-PASTE \d+ [0-9a-f]{64}/.test(value),
            { timeout: 180000 },
          )
          .catch(() => session.rows("console"));
        const writes = await session.shell(
          ({ from, id }) =>
            window.__s10.ipc
              .slice(from)
              .filter(
                (e) =>
                  e.session === id &&
                  (e.cmd === "terminal_write" || e.cmd === "terminal_ack"),
              ),
          { from: firstSeq, id: consoleState.session },
        );
        const sent = writes
          .filter((e) => e.cmd === "terminal_write" && e.ok)
          .reduce((sum, e) => sum + e.bodyBytes, 0);
        const queueFull = writes.filter((e) => e.code === "queue_full").length;
        const errors = writes.filter(
          (e) => e.ok === false && e.code !== "queue_full",
        );
        const reported = /S10-PASTE (\d+) ([0-9a-f]{64})/.exec(rows ?? "");
        const detail = `${sent} bytes accepted in ${writes.filter((e) => e.cmd === "terminal_write" && e.ok).length} writes, ${queueFull} queue_full retries`;
        if (errors.length)
          return {
            verdict: FAIL,
            detail: `${detail}; errors ${JSON.stringify(errors.slice(0, 3))}`,
          };
        if (!reported)
          return {
            verdict: FAIL,
            detail: `${detail}; the child reported nothing`,
          };
        const ok =
          Number(reported[1]) === Buffer.byteLength(expected) &&
          reported[2] === sha256(expected);
        return {
          verdict: ok ? PASS : FAIL,
          detail: `${detail}; child read ${reported[1]} bytes${ok ? ", digest matches" : `, expected ${Buffer.byteLength(expected)} with ${sha256(expected).slice(0, 12)}`}`,
        };
      },
    );

    // Navigation and external links -------------------------------------------
    await check(
      "top-navigation-refused",
      "the top frame stays on the shell",
      async () => {
        const shellUrl = page.url();
        const before = await refusals();
        const markers = async () =>
          (await session.frames()).map((f) => f.marker).join("/");
        const start = await markers();
        await session
          .shell(() => {
            location.href = "https://example.invalid/cadrumo-s10-top";
          })
          .catch(() => undefined);
        await sleep(2500);
        const fromDocs = await session.docs(() => {
          try {
            window.top.location.href =
              "https://example.invalid/cadrumo-s10-docs";
            return "assigned";
          } catch (error) {
            return error.name;
          }
        });
        await sleep(2500);
        const after = await markers().catch(() => "unreadable");
        const delta = (await refusals()) - before;
        if (page.url() !== shellUrl || after !== start) {
          await page
            .goto(shellUrl, { waitUntil: "load" })
            .catch(() => undefined);
          await session.waitDocs(60000).catch(() => undefined);
          return {
            verdict: FAIL,
            detail: `the top frame left the shell (${page.url()})`,
          };
        }
        return {
          verdict: PASS,
          detail: `shell document kept; docs attempt ${fromDocs}; ${delta} host refusal record(s)`,
        };
      },
    );
    await check(
      "external-link",
      "an external docs link goes through open_external and nothing navigates",
      async () => {
        const frame = session.docsFrame();
        const docsUrl = frame.url();
        const target = "https://example.com/cadrumo-s10";
        await frame.evaluate((href) => {
          const link = document.createElement("a");
          link.id = "s10-external";
          link.href = href;
          link.textContent = "S10 external link";
          link.style.cssText =
            "position:fixed;left:8px;top:8px;z-index:2147483647;background:#ff0;padding:6px";
          document.body.append(link);
        }, target);
        const before = await session.shell(() => window.__s10.external.length);
        await frame.click("#s10-external");
        await sleep(2000);
        const external = await session.shell(
          (from) => window.__s10.external.slice(from),
          before,
        );
        await frame
          .evaluate(() => document.getElementById("s10-external")?.remove())
          .catch(() => undefined);
        const refused = await session.call("open_external", {
          url: "http://example.com/",
        });
        const problems = [];
        if (!external.some((e) => e.url === target))
          problems.push("the shell made no open_external request for the link");
        if (session.docsFrame()?.url() !== docsUrl)
          problems.push(
            `the docs frame navigated to ${session.docsFrame()?.url()}`,
          );
        if (refused.ok || refused.error.code !== "invalid_arguments")
          problems.push(
            `open_external with http: gave ${JSON.stringify(refused)}`,
          );
        return problems.length
          ? { verdict: FAIL, detail: problems.join("; ") }
          : {
              verdict: PASS,
              detail: `open_external(${target}) ${config.allowBrowser ? "sent to the host" : "intercepted before the host, so no browser opened"}; http: refused with invalid_arguments`,
            };
      },
    );
    await experiment(
      "opener-subframe-clicks",
      "whether the opener intercepts clicks in subframes",
      async () => ({
        verdict: INFO,
        detail:
          "see external-link: the click reached the bridge and the shell's open_external request, and the docs frame did not navigate",
      }),
    );

    // Native context menu -------------------------------------------------------
    await check(
      "context-menu-null",
      "a shell context menu opened and dismissed resolves null",
      async () => {
        const pending = session.call("shell_context_menu", {
          items: [{ id: "s10", label: "S10 probe & menu", enabled: true }],
          x: 40,
          y: 40,
        });
        const menu = await waitFor(
          async () =>
            (await input.windows([hostPid])).find((w) => w.class === "#32768"),
          { timeout: 5000, what: "the native menu" },
        ).catch(() => null);
        if (menu) {
          await input.post(hostPid, "cancelmode");
          const closed = await exited(
            pending.then(() => ({})),
            3000,
          );
          if (!closed) {
            await input.activate(hostPid).catch(() => undefined);
            await input.chord(hostPid, "escape").catch(() => undefined);
          }
        }
        const result = await Promise.race([
          pending,
          sleep(8000).then(() => ({ ok: false, error: { code: "no answer" } })),
        ]);
        if (!menu)
          return {
            verdict: FAIL,
            detail: `no native menu window appeared; result ${JSON.stringify(result)}`,
          };
        return result.ok && result.value.chosen === null
          ? {
              verdict: PASS,
              detail:
                "menu window #32768 appeared and the dismissal resolved null",
            }
          : { verdict: FAIL, detail: `result ${JSON.stringify(result)}` };
      },
    );

    // Accelerators and default context menus --------------------------------------
    const browserCdp = await session.browser.newBrowserCDPSession();
    const snapshot = async () =>
      session.effectState({
        windows: await input.windows([hostPid, ...webviewPids]),
        targets: (await browserCdp.send("Target.getTargets")).targetInfos
          .length,
      });
    const dismissNew = async (before) => {
      const known = new Set(before.windows.map((w) => w.hwnd));
      const opened = (await input.windows([hostPid, ...webviewPids])).filter(
        (w) => !known.has(w.hwnd),
      );
      for (const window of opened) {
        await input.activate(hostPid).catch(() => undefined);
        await input.chord(hostPid, "escape").catch(() => undefined);
        await input.post(hostPid, "close", window.hwnd).catch(() => undefined);
      }
    };
    const focusFrame = async (role) => {
      if (role === "shell")
        await page.locator(".pane-docs .pane-title").click();
      else
        await session
          .docsFrame()
          .locator("h1")
          .first()
          .click({ position: { x: 3, y: 3 } });
    };
    const suppress = (role, on) =>
      (role === "shell" ? page.mainFrame() : session.docsFrame()).evaluate(
        (value) => {
          window.__s10.suppressPageHandlers = value;
        },
        on,
      );
    const gestures = [
      { id: "f5", key: "f5", modifiers: [], cdp: "F5" },
      { id: "ctrl-r", key: "r", modifiers: ["control"], cdp: "Control+r" },
      { id: "ctrl-p", key: "p", modifiers: ["control"], cdp: "Control+p" },
      { id: "f12", key: "f12", modifiers: [], cdp: "F12" },
      {
        id: "ctrl-shift-i",
        key: "i",
        modifiers: ["control", "shift"],
        cdp: "Control+Shift+I",
      },
      { id: "ctrl-f", key: "f", modifiers: ["control"], cdp: "Control+f" },
      {
        id: "ctrl-plus",
        key: "plus",
        modifiers: ["control"],
        cdp: "Control+Equal",
      },
    ];
    const activated = await input
      .activate(hostPid)
      .then((r) => r.foreground === hostPid)
      .catch(() => false);
    for (const role of ["shell", "docs"]) {
      for (const via of ["os", "cdp"]) {
        const outcomes = [];
        let skipped = null;
        for (const gesture of gestures) {
          await focusFrame(role);
          await suppress(role, true);
          const before = await snapshot();
          try {
            if (via === "os") {
              if (!activated)
                throw new Error(
                  "the window could not be brought to the foreground",
                );
              await input.chord(hostPid, gesture.key, gesture.modifiers);
            } else await page.keyboard.press(gesture.cdp);
          } catch (error) {
            skipped = error.message;
            await suppress(role, false);
            break;
          }
          await sleep(1500);
          const after = await snapshot();
          await suppress(role, false);
          const verdict = noEffectVerdict(before, after);
          const reached = after.keys[role] > before.keys[role];
          outcomes.push({
            gesture: gesture.id,
            ...verdict,
            reachedPage: reached,
          });
          if (verdict.verdict === FAIL) {
            await dismissNew(before);
            if (after.markers.shell !== before.markers.shell)
              await session.waitDocs(60000).catch(() => undefined);
          }
        }
        evidence(`keys-${role}-${via}.json`, outcomes);
        await check(
          `keys-${role}-${via}`,
          `F5, Ctrl+R, Ctrl+P, F12, Ctrl+F and zoom change nothing in the ${role} frame (${via === "os" ? "real keyboard input" : "DevTools key events"})`,
          async () => {
            if (skipped && !outcomes.length)
              return { verdict: SKIP, detail: skipped };
            const failed = outcomes.filter((o) => o.verdict === FAIL);
            const unreached = outcomes
              .filter((o) => !o.reachedPage)
              .map((o) => o.gesture);
            return failed.length
              ? {
                  verdict: FAIL,
                  detail: failed
                    .map((o) => `${o.gesture}: ${o.detail}`)
                    .join("; "),
                }
              : {
                  verdict: PASS,
                  detail: `${outcomes.length} gestures, no effect; page handlers suppressed${unreached.length ? `; not seen by the page: ${unreached.join(", ")}` : ""}${skipped ? `; stopped: ${skipped}` : ""}`,
                };
          },
        );
      }
      // Right click with page handlers suppressed: only the webview's setting
      // can keep the default menu closed.
      const outcomes = [];
      for (const via of ["os", "cdp"]) {
        await suppress(role, true);
        const before = await snapshot();
        const box =
          role === "shell"
            ? await page.locator(".pane-docs .pane-title").boundingBox()
            : await page
                .locator("iframe.docs-frame")
                .boundingBox()
                .then(
                  (b) =>
                    b && {
                      ...b,
                      x: b.x + 40,
                      y: b.y + 60,
                      width: 1,
                      height: 1,
                    },
                );
        const x = box.x + Math.min(box.width / 2, 20);
        const y = box.y + Math.min(box.height / 2, 10);
        let note = null;
        try {
          if (via === "os") {
            if (!activated)
              throw new Error(
                "the window could not be brought to the foreground",
              );
            const client = await input.client(hostPid);
            const scale = await session.shell(() => devicePixelRatio);
            await input.click(
              hostPid,
              Math.round(client.x + x * scale),
              Math.round(client.y + y * scale),
              true,
            );
          } else await page.mouse.click(x, y, { button: "right" });
        } catch (error) {
          note = error.message;
        }
        await sleep(1500);
        const after = await snapshot();
        await suppress(role, false);
        const verdict = noEffectVerdict(before, after);
        if (verdict.verdict === FAIL) await dismissNew(before);
        outcomes.push({
          via,
          ...verdict,
          reachedPage: after.menus[role] > before.menus[role],
          note,
        });
      }
      evidence(`context-menu-${role}.json`, outcomes);
      await check(
        `default-menu-${role}`,
        `right click opens no default menu in the ${role} frame`,
        async () => {
          const failed = outcomes.filter((o) => o.verdict === FAIL);
          const ran = outcomes.filter((o) => !o.note);
          if (!ran.length)
            return {
              verdict: SKIP,
              detail: outcomes.map((o) => o.note).join("; "),
            };
          return failed.length
            ? {
                verdict: FAIL,
                detail: failed.map((o) => `${o.via}: ${o.detail}`).join("; "),
              }
            : {
                verdict: PASS,
                detail: ran
                  .map(
                    (o) =>
                      `${o.via}: no window${o.reachedPage ? ", contextmenu reached the page unprevented" : ", contextmenu not seen by the page"}`,
                  )
                  .join("; "),
              };
        },
      );
    }
    await experiment(
      "settings-timing",
      "accelerator and context-menu settings relative to the first navigation and in child frames",
      async () => ({
        verdict: INFO,
        detail: `measured after ${session.navigations} shell document load(s) seen by the harness; see the keys-* and default-menu-* checks for both frames`,
      }),
    );

    // Logs carry no terminal bytes ------------------------------------------------
    await check(
      "logs-no-pty",
      "no terminal byte reaches the Logs tab or host diagnostics",
      async () => {
        const leaked = await session.shell(
          () =>
            window.__s10.logs.records.filter((r) =>
              /S10-FLOOD|cadrumo paste probe|S10-PASTE/.test(r.message),
            ).length,
        );
        const snapshot = await session.call("diagnostics_snapshot", {
          after: 0,
        });
        evidence("diagnostics.json", snapshot);
        const output = snapshot.ok ? snapshot.value.output.length : -1;
        return leaked === 0 && output === 0
          ? {
              verdict: PASS,
              detail:
                "no flood, paste or probe text in any log record; diagnostics hold no output",
            }
          : {
              verdict: FAIL,
              detail: `${leaked} log record(s) with terminal text; ${output} diagnostics output chunk(s)`,
            };
      },
    );

    // Second instance ------------------------------------------------------------
    await check(
      "second-instance",
      "a second launch activates the window and exits 0",
      async () => {
        const second = launch(testHost.executable, ["--gui"], {
          env: hostEnv,
          cwd: config.run,
          out: resolve(config.results, "second-stdout.txt"),
          err: resolve(config.results, "second-stderr.txt"),
        });
        const started = Date.now();
        const done = await exited(second.exit, 30000);
        if (!done) {
          second.child.kill();
          return {
            verdict: FAIL,
            detail: "the second launch still ran after 30 s",
          };
        }
        const stderr = readFileSync(
          resolve(config.results, "second-stderr.txt"),
          "utf8",
        ).trim();
        const foreground = await input.windows([hostPid]);
        return done.code === 0
          ? {
              verdict: PASS,
              detail: `exit 0 after ${done.at - started} ms${stderr ? `; stderr ${stderr.slice(0, 120)}` : ""}; ${foreground.length} host window(s)`,
            }
          : {
              verdict: FAIL,
              detail: `exit ${done.code}; stderr ${stderr.slice(0, 200)}`,
            };
      },
    );

    // Evidence before the window closes ---------------------------------------------
    evidence("ipc-trace.json", await session.shell(() => window.__s10.ipc));
    evidence("frames.json", await session.frames());
    evidence("playwright-console.json", session.console);
    evidence(
      "log-records.json",
      await session.shell(() => window.__s10.logs.records.slice(-500)),
    );
    if (original.ok)
      await session.call("shell_clipboard_write", {
        text: original.value.text,
      });

    await check(
      "canonical-sign-out",
      "global sign-out uses the packaged CLI and preserves remaining access",
      () =>
        authenticated.verdict === PASS
          ? signIn.signOut(session)
          : { verdict: SKIP, detail: "canonical sign-in did not complete" },
    );
    await check(
      "sign-in-secret-isolation",
      "passwords stay out of arguments, logs, diagnostics and the docs frame",
      () =>
        authenticated.verdict === PASS
          ? signIn.isolation(session, input, projected)
          : {
              verdict: SKIP,
              detail:
                "complete secret-isolation acceptance depends on canonical sign-in",
            },
    );

    // Close with a paused session ------------------------------------------------
    await quiet("python", 1000);
    await session.shell(() => window.__s10.hold());
    await session.type("python", flood(40000, "S10-FLOOD3-END"));
    await quiet("python", 2000);
    const diagnostics = await session.call("diagnostics_snapshot", {
      after: 0,
    });
    const tracked = diagnostics.ok
      ? diagnostics.value.processes
          .filter((p) => p.phase === "running")
          .map((p) => ({ pid: p.pid, role: p.role }))
      : [];
    const all = await input.processes(PROCESS_NAMES);
    const tree = [...descendants(all, hostPid), ...(await webviewProcesses())];
    const watched = [...new Map(tree.map((p) => [p.pid, p])).values()];
    evidence("processes-before-close.json", {
      tracked,
      watched: watched.map(({ commandLine: _, ...p }) => p),
    });
    const closeStarted = Date.now();
    await input.post(hostPid, "close");
    const closed = await exited(host.exit, 15000);
    await sleep(5000);
    const now = await input.processes(PROCESS_NAMES);
    const left = survivors(watched, now).map((p) => ({
      pid: p.pid,
      name: p.name,
    }));
    const trackedLeft = tracked.filter((p) => now.some((q) => q.pid === p.pid));
    await check(
      "close-settles",
      "closing the window ends the host within 10 s and leaves no child process",
      async () =>
        closeVerdict({
          exitCode: closed ? closed.code : null,
          exitMs: closed ? closed.at - closeStarted : null,
          survivors: [
            ...left,
            ...trackedLeft.filter((p) => !left.some((q) => q.pid === p.pid)),
          ],
        }),
    );
    await experiment(
      "close-while-paused",
      "window close with a paused session (ClosePseudoConsole)",
      async () => ({
        verdict: INFO,
        detail: closed
          ? `host exited ${closed.code} ${closed.at - closeStarted} ms after the close request while the Python reader was paused`
          : "the host did not exit within 15 s",
      }),
    );
    if (closed) host = null;

    // Window state -------------------------------------------------------------
    await check(
      "window-state",
      "the window state is saved in the projected webview directory",
      async () => {
        const declared = resolve(projected.webview, "window-state.json");
        const strays = [];
        for (const root of [config.packageRoot, dirname(testHost.executable)])
          for (const entry of readdirSync(root, {
            recursive: root === config.packageRoot,
          }))
            if (String(entry).endsWith("window-state.json"))
              strays.push(resolve(root, String(entry)));
        if (!existsSync(declared))
          return {
            verdict: FAIL,
            detail: `no ${declared}${strays.length ? `; found ${strays.join(", ")}` : ""}`,
          };
        copyFileSync(
          declared,
          resolve(results.evidenceDirectory, "window-state.json"),
        );
        const keys = Object.keys(JSON.parse(readFileSync(declared, "utf8")));
        return strays.length
          ? { verdict: FAIL, detail: `also written to ${strays.join(", ")}` }
          : {
              verdict: PASS,
              detail: `${declared} (${statSync(declared).size} bytes, keys ${keys.join(", ")})`,
            };
      },
    );
    await experiment(
      "linux-scheme-order",
      "Linux selection order of custom schemes versus tauri://",
      async () => ({
        verdict: INFO,
        detail: "not applicable: this run is on Windows",
      }),
    );

    // Logs written under the fresh storage root.
    for (const file of [
      projected.logFile,
      resolve(projected.logs, "cadrumo-native.jsonl"),
    ])
      if (existsSync(file))
        copyFileSync(
          file,
          resolve(
            results.evidenceDirectory,
            `storage-${file.split(/[\\/]/).pop()}`,
          ),
        );
  } finally {
    if (host) {
      const done = await exited(host.exit, 1000);
      if (!done && hostPid) {
        await input.post(hostPid, "close").catch(() => undefined);
        if (!(await exited(host.exit, 15000))) host.child.kill();
      }
    }
    if (signIn)
      await check(
        "sign-in-fixture-cleanup",
        "test-owned runtime and exact-profile keychain entry are settled",
        async () => {
          return signIn.stop();
        },
      );
    input.close();
    const counts = results.finish({
      startedAt,
      endedAt: new Date().toISOString(),
      summary,
    });
    console.log(`Results: ${config.results}\n${JSON.stringify(counts)}`);
  }
});
