// The desktop console takes its environment from the agent service, proved on
// the packaged window: the console runs with the provider homes the service
// names for the signed-in profile (never the person's own), starts in the
// profile's agent workspace, finds the cadrumo-mcp tool server registered
// there in each provider's own form, and takes a new environment after a
// sign-out and a sign-in. One window serves the whole file.
//
// Environment: as ./window-ux-audit.test.mjs (CADRUMO_PERSONA_WORLD,
// CADRUMO_PERSONA_HOST, CADRUMO_CMAKE_BINARY_DIR, CADRUMO_BUILD_CONFIG,
// CADRUMO_UX_RUN, optional CADRUMO_UX_STAGED_SHA256), plus
//   CADRUMO_CONSOLE_OTHER_PROFILE  (optional) the value of another profile the
//                    sign-in form offers, which accepts the same credential as
//                    the run's profile; the refresh case then signs in to it.
//                    Without it the case signs out and in again as the same
//                    profile and its profile-switch part is reported
//                    not-requested, never faked
//
// What is read, and why a wrong environment cannot pass:
//   - The console is asked for its own working directory and provider home
//     variables by typing into its terminal (the window draws it with WebGL,
//     so no text is in the DOM). The shell writes each answer to a fresh file
//     named by a random marker under the run's storage root; the spec polls
//     that file from disk and deletes it. Nothing but the shell itself can
//     write it. With no file the case says whether the console was not open
//     or accepted no input. Each location is reported relative to the run's storage root
//     inside the shell itself (a location outside it reads OUTSIDE, an unset
//     variable UNSET), so no absolute path, user name or value is recorded.
//   - The layout the answers must have is read from the agent service's own
//     source (agent_programs.py), never restated here, and the files named
//     are read from the run's storage on disk.
//   - A secret is never read or printed: only relative paths, names and
//     booleans reach the record, and the profile credential is searched for in
//     the run's logs by a boolean.
//
// Every case writes one JSON line through t.diagnostic. A part the packaged
// build cannot show fails with "UNMEASURED: <why>" and is never passed.
import assert from "node:assert/strict";
import { spawnSync } from "node:child_process";
import { randomBytes } from "node:crypto";
import {
  existsSync,
  mkdirSync,
  mkdtempSync,
  readFileSync,
  readdirSync,
  realpathSync,
  rmSync,
  statSync,
} from "node:fs";
import { tmpdir } from "node:os";
import { basename, isAbsolute, join, relative, resolve } from "node:path";
import { after, before, test } from "node:test";
import {
  pageChooseSignOut,
  pageOpenAccountMenu,
  pageSignedOut,
} from "../automation/session-keys.mjs";
import {
  clickSelector,
  exec,
  label,
  profileCredential,
  runIdentity,
  signIn,
  sleep,
  start,
  teardown,
  waitFor,
  win,
} from "./ux-driver.mjs";
import { dismissSetup } from "./ux-nav.mjs";

const STAGED_SHA256 = (process.env.CADRUMO_UX_STAGED_SHA256 ?? "")
  .trim()
  .toLowerCase();
const OTHER_PROFILE = (process.env.CADRUMO_CONSOLE_OTHER_PROFILE ?? "").trim();
const PROFILE = process.env.CADRUMO_PERSONA_PROFILE || "persona";

// ---------------------------------------------------------------------------
// The layout the service promises, read from its own source.
// ---------------------------------------------------------------------------

const AGENT_PROGRAMS = readFileSync(
  new URL(
    "../../../../src/cadrumo_agent_service/adapters/agent_programs.py",
    import.meta.url,
  ),
  "utf8",
);

/** A string constant of agent_programs.py, by name. */
function pythonConstant(name) {
  const match = new RegExp(`^${name}: Final = "([^"]+)"`, "m").exec(
    AGENT_PROGRAMS,
  );
  if (!match) throw new Error(`agent_programs.py declares no ${name}`);
  return match[1];
}

const AGENT_DIRECTORY = pythonConstant("AGENT_DIRECTORY");
const WORKSPACE_PARTS = [
  pythonConstant("_HOSTED_HOME"),
  pythonConstant("_HOSTED_WORKSPACES"),
  pythonConstant("_HOSTED_WORKSPACE"),
];

// The provider homes the console variables name, and the files a provider
// reads its tool servers from.
const TOOL_SERVER = /cadrumo[-_]?mcp/i;
const PROVIDERS = {
  claude: { variable: "CLAUDE_CONFIG_DIR" },
  codex: { variable: "CODEX_HOME" },
};

// ---------------------------------------------------------------------------
// The run
// ---------------------------------------------------------------------------

let runDir;
let storage;
let packageRoot;
let credentialsBefore = null;
let credentialError = null;

const host = JSON.parse(process.env.CADRUMO_PERSONA_HOST ?? "{}");

/** The path in its resolved form, or as given when it does not exist. */
const resolved = (path) => {
  try {
    return realpathSync.native(path);
  } catch {
    return path;
  }
};

/** Whether `path` lies strictly inside the directory `base`. */
function inside(base, path) {
  if (!isAbsolute(path)) return false;
  const rel = relative(base, path);
  return rel !== "" && !rel.startsWith("..") && !isAbsolute(rel);
}

before(async () => {
  runDir =
    process.env.CADRUMO_UX_RUN ??
    join(mkdtempSync(join(tmpdir(), "cadrumo-e2e-console-")), "run");
  try {
    credentialsBefore = credentialCounts();
  } catch (error) {
    credentialError = error.message;
  }
  await start(runDir);
  storage = resolved(resolve(runDir, "storage"));
  packageRoot = host.package ? resolved(host.package) : null;
});
after(teardown);

/** One structured line per case. */
function record(t, line) {
  t.diagnostic(JSON.stringify({ probe: "console-environment", ...line }));
}

/** A case: its line is written whatever the outcome. */
/** The case being run, for the diagnostics a silent console leaves. */
const diagnosis = { line: null, kind: "run", shots: 0 };

/** Where the run's diagnostics are kept: the log directory when one is named. */
const logDirectory = () => process.env.CADRUMO_UX_LOG_DIR || runDir;

/** Save a window screenshot for the case in hand; answers its file name or null. */
async function saveShot() {
  diagnosis.shots += 1;
  const name = `console-${diagnosis.kind}-${diagnosis.shots}.png`;
  try {
    mkdirSync(logDirectory(), { recursive: true });
    await win.browser.saveScreenshot(join(logDirectory(), name));
  } catch {
    return null;
  }
  if (diagnosis.line) (diagnosis.line.screenshots ??= []).push(name);
  return name;
}

const conCase = (name, kind, fn, timeout = 420_000) =>
  test(name, { timeout }, async (t) => {
    const line = { case: kind, verdict: "fail", durations_ms: {} };
    const began = Date.now();
    diagnosis.line = line;
    diagnosis.kind = kind;
    diagnosis.shots = 0;
    try {
      line.verdict = (await fn(t, line)) ?? "pass";
    } catch (error) {
      line.reason = error instanceof Error ? error.message : String(error);
      throw error;
    } finally {
      line.durations_ms.total = Date.now() - began;
      record(t, line);
    }
  });

/** Parts of a case that are measured one by one: a failure of one does not
 * hide the others, and a part that cannot be seen is not a pass. */
function checklist(line) {
  const items = [];
  const publish = () => {
    line.checks = Object.fromEntries(
      items.map(({ id, status }) => [id, status]),
    );
  };
  const add = (id, status, why) => {
    items.push({ id, status, why });
    publish();
  };
  return {
    pass: (id) => add(id, "pass"),
    ok: (id, condition, why) => add(id, condition ? "pass" : "fail", why),
    unmeasured: (id, why) => add(id, "unmeasured", why),
    finish() {
      const failed = items.filter((item) => item.status === "fail");
      const unmeasured = items.filter((item) => item.status === "unmeasured");
      if (failed.length > 0)
        assert.fail(
          [...failed, ...unmeasured]
            .map(
              (item) =>
                `${item.status === "fail" ? "" : "UNMEASURED: "}${item.id}: ${item.why}`,
            )
            .join(" | "),
        );
      if (unmeasured.length > 0)
        assert.fail(
          `UNMEASURED: ${unmeasured.map((item) => `${item.id}: ${item.why}`).join(" | ")}`,
        );
    },
  };
}

// ---------------------------------------------------------------------------
// The credential store: targets counted by class, never printed.
// ---------------------------------------------------------------------------

const SESSION_SUFFIX = "@cadrumo:profile-session:v2";

/** Counts of the credential-store targets by class; null off Windows. */
function credentialCounts() {
  if (process.platform !== "win32") return null;
  const listed = spawnSync("cmdkey", ["/list"], { encoding: "utf8" });
  if (listed.status !== 0)
    throw new Error(`cmdkey /list failed with status ${listed.status}`);
  const counts = { profileSession: 0, cadrumo: 0, provider: 0, total: 0 };
  for (const line of listed.stdout.split(/\r?\n/)) {
    const match = /Target:\s*(\S+)/.exec(line);
    if (!match) continue;
    const target = match[1];
    counts.total += 1;
    if (target.endsWith(SESSION_SUFFIX)) counts.profileSession += 1;
    if (/cadrumo/i.test(target)) counts.cadrumo += 1;
    if (/claude|anthropic|codex|openai/i.test(target)) counts.provider += 1;
  }
  return counts;
}

// ---------------------------------------------------------------------------
// Logs under the run: counts only, never a line.
// ---------------------------------------------------------------------------

/** Walk the log-like files under `dir`; `wanted(line)` is counted per file. */
function scanLogs(dir, wanted) {
  const result = { files: 0, lines: 0, in_files: [] };
  const walk = (path, depth) => {
    if (depth > 10 || result.files > 4000) return;
    let entries;
    try {
      entries = readdirSync(path, { withFileTypes: true });
    } catch {
      return;
    }
    for (const entry of entries) {
      const full = join(path, entry.name);
      if (entry.isSymbolicLink()) continue;
      if (entry.isDirectory()) {
        walk(full, depth + 1);
        continue;
      }
      if (!/\.(log|jsonl|txt)$/i.test(entry.name)) continue;
      result.files += 1;
      try {
        if (statSync(full).size > 32 * 1024 * 1024) continue;
        let hits = 0;
        for (const text of readFileSync(full, "utf8").split(/\r?\n/))
          if (wanted(text)) hits += 1;
        if (hits > 0) {
          result.lines += hits;
          result.in_files.push(basename(full));
        }
      } catch {
        // An unreadable file is not evidence either way.
      }
    }
  };
  walk(dir, 0);
  return result;
}

// ---------------------------------------------------------------------------
// The console terminal
// ---------------------------------------------------------------------------

const CONSOLE = '[data-terminal="console"]';

/** The console terminal as the page draws it. The window renders it with
 * WebGL, so its text is not in the DOM: only its presence, its input element
 * and the tab's own words are read. */
function pageConsole() {
  const terminal = document.querySelector('[data-terminal="console"]');
  const screen = terminal?.querySelector(".xterm-screen");
  const tab = document.querySelector("#tab-console");
  return {
    present: !!terminal,
    shown: !!terminal && terminal.getClientRects().length > 0,
    screen: !!screen && screen.getClientRects().length > 0,
    input: !!terminal?.querySelector(".xterm-helper-textarea"),
    tab: !!tab,
    notice: !!document.querySelector(
      '[data-slot="console-environment-notice"]',
    ),
    tabDescription: tab?.getAttribute("aria-description") ?? null,
  };
}

/** Show the console terminal; answers its state, or null when it cannot be shown. */
async function showConsole() {
  await dismissSetup();
  const drawn = async () => {
    const now = await exec(pageConsole);
    return now.shown && now.screen ? now : null;
  };
  if (await drawn()) return drawn();
  try {
    const pressed = await exec(
      () =>
        document
          .querySelector('[data-rail="panel"]')
          ?.getAttribute("aria-pressed") ?? null,
    );
    if (pressed === "false") {
      await clickSelector('[data-rail="panel"]');
      await sleep(1000);
    }
    if (await exec(() => !!document.querySelector("#tab-console"))) {
      await clickSelector("#tab-console");
      await sleep(800);
    }
  } catch {
    // Whether the console is drawn decides.
  }
  return waitFor(drawn, {
    timeout: 30_000,
    what: "the console terminal",
    soft: true,
  });
}

const ENTER = String.fromCharCode(0xe007);

/** Focus the console's input element, as a click on its screen does. */
async function focusConsole() {
  await clickSelector(`${CONSOLE} .xterm-screen`);
  await exec(() =>
    document
      .querySelector('[data-terminal="console"] .xterm-helper-textarea')
      ?.focus(),
  );
}

/** Deliver `text` as one paste on the focused input element. */
async function pasteText(text) {
  return exec((text) => {
    const input = document.querySelector(
      '[data-terminal="console"] .xterm-helper-textarea',
    );
    if (!input) return false;
    input.focus();
    const data = new DataTransfer();
    data.setData("text/plain", text);
    input.dispatchEvent(
      new ClipboardEvent("paste", {
        clipboardData: data,
        bubbles: true,
        cancelable: true,
      }),
    );
    return true;
  }, text);
}

/** Enter a line into the console: one paste of the whole command, then Enter
 * as a key action of its own. */
async function typeLine(text) {
  await focusConsole();
  assert(
    await pasteText(text),
    "the console has no input element to paste into",
  );
  await sleep(300);
  await win.browser.keys(ENTER);
}

/** Why the last probe drew no answer: the console was not open, or it took no input. */
let lastSilence = null;

/**
 * Ask the console shell for `expression`: the shell writes the answer to a
 * fresh file named by a random marker under the run's storage root, and the
 * spec polls that file from disk and deletes it. The file holds one relative
 * path, word or boolean, never another variable's value. Answers the text, or
 * null when no file appeared (lastSilence says why).
 */
async function probe(expression, timeout = 25_000) {
  const nonce = randomBytes(6).toString("hex");
  const file = join(storage, `console-probe-${nonce}.txt`);
  const state = await exec(pageConsole);
  if (!state.shown || !state.screen || !state.input) {
    lastSilence = `console not open (terminal ${state.present ? "present" : "absent"}, tab ${state.tab ? "present" : "absent"}, input element ${state.input ? "present" : "absent"})`;
    return null;
  }
  const target = file.replaceAll("'", "''");
  if (diagnosis.line && !diagnosis.line.probe_target)
    diagnosis.line.probe_target = {
      typed_form:
        "<storage>/console-probe-<marker>.txt, single-quoted, -LiteralPath",
      drive_absolute: /^[A-Za-z]:[\\/]/.test(file),
      backslashes: file.includes("\\"),
      forward_slashes: file.includes("/"),
      unix_style_root: file.startsWith("/"),
      storage_from:
        "the storage root the driver gives the app as CADRUMO_STORAGE_ROOT: path.resolve(<CADRUMO_UX_RUN>, 'storage'), resolved with realpath.native",
    };
  await typeLine(
    `Set-Content -LiteralPath '${target}' -Value (${expression}) -Encoding ascii`,
  );
  const answer = await waitFor(
    async () => {
      const text = readText(file);
      if (text === null || !/\n$/.test(text)) return null;
      return { text: text.trim() };
    },
    { timeout, what: "the console's answer file", soft: true },
  );
  try {
    rmSync(file, { force: true });
  } catch {
    // A file that cannot be removed is reported by the next probe's search.
  }
  if (!answer) {
    lastSilence =
      "console accepted no input (it is open, and wrote no answer file)";
    await saveShot();
    return null;
  }
  return answer.text;
}

/** A location of the console, relative to the run's storage root, in the shell. */
const relativeTo = (expression) =>
  `& { $s='${storage.replaceAll("'", "''")}'; $v=${expression}; ` +
  `if ($v -and $v.StartsWith($s,[StringComparison]::OrdinalIgnoreCase)) { $v.Substring($s.Length) } ` +
  `elseif ($v) { 'OUTSIDE' } else { 'UNSET' } }`;

/** A boolean the shell answers about a path. */
const pathExists = (expression) => `Test-Path -LiteralPath (${expression})`;

/**
 * The console ready for input, bounded at 30 s: a constant is probed, and a
 * silent attempt is typed once more before the next.
 */
async function consoleReady(timeoutMs = 30_000) {
  const end = Date.now() + timeoutMs;
  while (Date.now() < end) {
    if ((await probe("'ready'", 10_000)) === "ready") return true;
    await sleep(1000);
  }
  return false;
}

/** The parts of a probed location: inside the storage, outside it, unset or unread. */
function placeOf(text) {
  if (text === null) return { state: "unread", parts: [] };
  if (text === "OUTSIDE" || text === "UNSET")
    return { state: text.toLowerCase(), parts: [] };
  return { state: "inside", parts: text.split(/[\\/]+/).filter(Boolean) };
}

/** What the console reports about its environment now. */
async function snapshot() {
  const cwd = placeOf(await probe(relativeTo("(Get-Location).ProviderPath")));
  const homes = {};
  for (const [provider, { variable }] of Object.entries(PROVIDERS))
    homes[provider] = placeOf(await probe(relativeTo(`$env:${variable}`)));
  const files = {
    claudeRegistration: await probe(
      pathExists("Join-Path (Get-Location).ProviderPath '.mcp.json'"),
    ),
    codexRegistration: await probe(
      pathExists("Join-Path $env:CODEX_HOME 'config.toml'"),
    ),
  };
  return { cwd, homes, files };
}

/** The profile's agent directory name a placed location lies in, or null. */
const profileDirectory = (place) =>
  place.state === "inside" &&
  place.parts.length >= 2 &&
  place.parts[0] === AGENT_DIRECTORY
    ? place.parts[1]
    : null;

/** Disk path under the run's storage for a placed location. */
const onDisk = (place) => join(storage, ...place.parts);

/** Names (never contents) of a directory's entries, bounded. */
function namesIn(path) {
  try {
    return readdirSync(path).slice(0, 20);
  } catch {
    return null;
  }
}

// ---------------------------------------------------------------------------
// The tool server registration, per provider
// ---------------------------------------------------------------------------

/** Where a registered launcher lives: booleans only. */
function launcherFacts(command, args) {
  const text = [command, ...args].join(" ");
  return {
    names_cadrumo_mcp: TOOL_SERVER.test(text),
    command_absolute: isAbsolute(command ?? ""),
    command_exists: !!command && isAbsolute(command) && existsSync(command),
    command_in_package:
      !!packageRoot && !!command && inside(packageRoot, resolved(command)),
  };
}

/** A basic or literal TOML string's value from `text` at `index`. */
function tomlStrings(text) {
  const out = [];
  for (const match of text.matchAll(/"((?:[^"\\]|\\.)*)"|'([^']*)'/g))
    out.push(
      match[2] !== undefined ? match[2] : match[1].replace(/\\(["\\])/g, "$1"),
    );
  return out;
}

/** The [mcp_servers.<name>] tables of a Codex config.toml: name, command, args. */
function codexServers(text) {
  const heads = [
    ...text.matchAll(/^\[mcp_servers\.(?:"([^"]+)"|([A-Za-z0-9_-]+))\]\s*$/gm),
  ];
  return heads.map((head, index) => {
    const from = head.index + head[0].length;
    const next = text.slice(from).search(/^\[/m);
    const body = next < 0 ? text.slice(from) : text.slice(from, from + next);
    const command = /^\s*command\s*=\s*("(?:[^"\\]|\\.)*"|'[^']*')/m.exec(body);
    const args = /^\s*args\s*=\s*\[([^\]]*)\]/m.exec(body);
    return {
      name: head[1] ?? head[2],
      command: command ? (tomlStrings(command[1])[0] ?? null) : null,
      args: args ? tomlStrings(args[1]) : [],
    };
  });
}

function readText(path) {
  try {
    return readFileSync(path, "utf8");
  } catch {
    return null;
  }
}

/** The facts of Claude's registration in `workspace` (.mcp.json and settings). */
function claudeRegistration(workspace) {
  const facts = { mcp_json: false, settings_local: false, server: null };
  const mcp = readText(join(workspace, ".mcp.json"));
  facts.mcp_json = mcp !== null;
  let servers = {};
  try {
    servers = mcp ? (JSON.parse(mcp).mcpServers ?? {}) : {};
  } catch {
    facts.mcp_json_invalid = true;
  }
  const found = Object.entries(servers).find(([name, entry]) =>
    TOOL_SERVER.test(
      [name, entry?.command, ...(entry?.args ?? [])].filter(Boolean).join(" "),
    ),
  );
  if (found) {
    const [name, entry] = found;
    facts.server = {
      name,
      ...launcherFacts(entry?.command ?? null, entry?.args ?? []),
    };
  }
  const settings = readText(join(workspace, ".claude", "settings.local.json"));
  facts.settings_local = settings !== null;
  try {
    const enabled = settings
      ? (JSON.parse(settings).enabledMcpjsonServers ?? [])
      : [];
    facts.enabled = !!facts.server && enabled.includes(facts.server.name);
  } catch {
    facts.settings_invalid = true;
    facts.enabled = false;
  }
  return facts;
}

/** The facts of Codex's registration in `home` (config.toml). */
function codexRegistrationOf(home) {
  const facts = { config_toml: false, server: null };
  const config = readText(join(home, "config.toml"));
  facts.config_toml = config !== null;
  const found = (config ? codexServers(config) : []).find((entry) =>
    TOOL_SERVER.test([entry.name, entry.command, ...entry.args].join(" ")),
  );
  if (found)
    facts.server = {
      name: found.name,
      ...launcherFacts(found.command, found.args),
    };
  return facts;
}

/** The launcher of a registration must be the packaged cadrumo-mcp. */
function judgeLauncher(checks, id, server) {
  checks.ok(
    `${id}.registered`,
    !!server,
    "no tool server naming cadrumo-mcp is registered",
  );
  if (!server) return;
  checks.ok(
    `${id}.is_cadrumo_mcp`,
    server.names_cadrumo_mcp,
    "the registered launcher is not cadrumo-mcp",
  );
  checks.ok(
    `${id}.packaged`,
    server.command_absolute &&
      server.command_exists &&
      server.command_in_package,
    "the registered launcher is not an existing program of the packaged build " +
      `(absolute: ${server.command_absolute}, exists: ${server.command_exists}, in package: ${server.command_in_package})`,
  );
}

// ---------------------------------------------------------------------------
// The shared first measurement
// ---------------------------------------------------------------------------

let current = null;

/** The console shown and ready, and what it reports; UNMEASURED when it cannot. */
async function measuredConsole(fresh = false) {
  await prelude(diagnosis.line ?? {});
  if (fresh || !current) current = await snapshot();
  return current;
}

/** The shown dialogs' titles, and the console restart notice, as the page has them. */
function pageDialogs() {
  const shown = (el) => !!el && el.getClientRects().length > 0;
  return [...document.querySelectorAll('[role="dialog"]')]
    .filter(shown)
    .map((dialog) =>
      (
        dialog.querySelector('[data-slot="dialog-title"], h1, h2, h3')
          ?.textContent ?? ""
      )
        .replace(/\s+/g, " ")
        .trim(),
    );
}

/**
 * The agent column's service up, bounded at 120 s: its own "starting" words
 * are gone and its settings door (the signal the provider sign-in spec waits
 * for) is offered and not held.
 */
async function agentReady() {
  const starting = (label("desktop.agent.service_starting") ?? "")
    .replace(/\s+/g, " ")
    .trim();
  const settings = label("desktop.agent.settings");
  const read = () =>
    exec(
      (starting, settings) => {
        const norm = (text) => (text ?? "").replace(/\s+/g, " ").trim();
        const rail = document.querySelector('[data-rail="agent"]');
        const startingShown = [...document.querySelectorAll("body *")].some(
          (el) =>
            el.getClientRects().length > 0 &&
            el.children.length === 0 &&
            norm(el.textContent) === starting,
        );
        const door = [
          ...document.querySelectorAll('button[data-slot="icon-button"]'),
        ].find(
          (el) =>
            el.getClientRects().length > 0 &&
            (el.getAttribute("aria-label") ?? "").startsWith(settings),
        );
        return {
          rail: !!rail,
          pressed: rail?.getAttribute("aria-pressed") === "true",
          startingShown,
          door: !!door,
          held: door?.getAttribute("aria-disabled") === "true",
        };
      },
      starting,
      settings,
    );
  let now = await read();
  if (now.rail && !now.pressed) {
    await clickSelector('[data-rail="agent"]');
    await sleep(1200);
  }
  const ready = await waitFor(
    async () => {
      now = await read();
      return now.door && !now.held && !now.startingShown ? now : null;
    },
    { timeout: 120_000, what: "the agent to be ready", soft: true },
  );
  return { ready: !!ready, last: now };
}

/** Close any first-run dialog, as its own "not now" does; answers their titles. */
async function dismissDialogs() {
  const titles = [];
  for (let round = 0; round < 3; round += 1) {
    const shown = await exec(pageDialogs);
    if (shown.length === 0) break;
    titles.push(...shown);
    await dismissSetup();
    await sleep(500);
  }
  return { titles, left: await exec(pageDialogs) };
}

/** Press the notice's own button and wait for it to go. */
async function restartConsole() {
  await exec(() => {
    document
      .querySelector('[data-slot="console-environment-notice"] button')
      ?.click();
  });
  await waitFor(async () => !(await exec(pageConsole)).notice, {
    timeout: 20_000,
    what: "the restart notice to go",
    soft: true,
  });
  await sleep(1500);
}

/**
 * What every measuring case begins with: the agent ready (so the console starts
 * with the profile's environment), the setup dialog closed, a console started
 * before that restarted when it says so, and the console ready for input.
 * Records what it found in `line`.
 */
async function prelude(line) {
  const agent = await agentReady();
  line.agent_ready = agent.ready;
  if (!agent.ready)
    assert.fail(
      `UNMEASURED: the agent was not ready within 120 s (service starting words shown: ${agent.last.startingShown}, settings door offered: ${agent.last.door}, held: ${agent.last.held})`,
    );
  const first = await dismissDialogs();
  line.dialog_dismissed = first.titles.length > 0;
  if (first.titles.length > 0) line.dialog_titles = first.titles;
  if (!(await showConsole()))
    assert.fail(
      "UNMEASURED: the window shows no console terminal (no rail panel or console tab to open it)",
    );
  // A console opened before the agent was ready is told so once the agent is.
  const noticed = await waitFor(async () => (await exec(pageConsole)).notice, {
    timeout: 10_000,
    what: "the console restart notice",
    soft: true,
  });
  line.restart_notice_at_open = !!noticed;
  line.console_restarted = false;
  const second = await dismissDialogs();
  if (second.titles.length > 0) {
    line.dialog_dismissed = true;
    line.dialog_titles = [...(line.dialog_titles ?? []), ...second.titles];
  }
  if (second.left.length > 0)
    assert.fail(
      `UNMEASURED: a dialog stays open over the console (${JSON.stringify(second.left)})`,
    );
  if (noticed) {
    await restartConsole();
    line.console_restarted = true;
  }
  if (!(await consoleReady()))
    assert.fail(`UNMEASURED: ${lastSilence ?? "the console wrote no answer"}`);
}

// ---------------------------------------------------------------------------
// Cases
// ---------------------------------------------------------------------------

test("CON-00 the run records the live bundle and the host executable", (t) => {
  record(t, {
    case: "run-identity",
    bundle: runIdentity.bundle,
    exe: runIdentity.exe,
    exeSha256: runIdentity.exeSha256,
    packaged_host: !!host.package,
    other_profile_requested: OTHER_PROFILE !== "",
  });
  assert.equal(runIdentity.error, null, `run identity: ${runIdentity.error}`);
  assert(host.package, "CADRUMO_PERSONA_HOST names no package");
  if (STAGED_SHA256)
    assert.equal(
      runIdentity.exeSha256?.toLowerCase(),
      STAGED_SHA256,
      "the window ran another executable than the freshly staged host",
    );
});

/** The measurements every provider case shares, then its own registration. */
async function providerCase(provider, line, registration) {
  const { variable } = PROVIDERS[provider];
  const checks = checklist(line);
  const seen = await measuredConsole(true);
  const home = seen.homes[provider];
  const other = seen.homes[provider === "claude" ? "codex" : "claude"];
  line.variable = variable;
  line.home_state = home.state;
  line.cwd_state = seen.cwd.state;

  // (a) The provider's own home, beneath the profile's agent directory.
  const owner = profileDirectory(home);
  checks.ok(
    "a.home_set",
    home.state !== "unset" && home.state !== "unread",
    `${variable} is ${home.state} in the console`,
  );
  checks.ok(
    "a.home_outside_person",
    home.state !== "outside",
    `${variable} points outside the run's storage root, so it is not the profile's provider home`,
  );
  checks.ok(
    "a.home_in_profile_agent_directory",
    owner !== null && home.parts.length > 2,
    `${variable} is not a location inside <storage>/${AGENT_DIRECTORY}/<profile directory>/...`,
  );
  checks.ok(
    "a.home_distinct_from_other_provider",
    home.state === "inside" && home.parts.join("/") !== other.parts.join("/"),
    "both providers name one home",
  );

  // (b) The working directory is the profile's harness workspace.
  const wanted = [AGENT_DIRECTORY, null, ...WORKSPACE_PARTS];
  const layout =
    seen.cwd.state === "inside" &&
    seen.cwd.parts.length === wanted.length &&
    wanted.every(
      (part, index) => part === null || seen.cwd.parts[index] === part,
    );
  checks.ok(
    "b.cwd_is_agent_workspace",
    layout,
    `the console's working directory is ${seen.cwd.state}` +
      (seen.cwd.state === "inside"
        ? `, not <storage>/${wanted.map((p) => p ?? "<profile directory>").join("/")}`
        : ""),
  );
  checks.ok(
    "b.same_profile_as_home",
    layout && owner === profileDirectory(seen.cwd),
    "the provider home and the working directory belong to different profile directories",
  );
  let workspace = null;
  if (layout) {
    workspace = onDisk(seen.cwd);
    checks.ok(
      "b.workspace_on_disk",
      existsSync(workspace) && statSync(workspace).isDirectory(),
      "the working directory the console reports is not a directory in the run's storage",
    );
    line.workspace_entries = namesIn(workspace)?.length ?? null;
  }

  // (b)(c) The registration the workspace or the home holds.
  const where = registration === "claude" ? "workspace" : "home";
  const base =
    registration === "claude"
      ? workspace
      : home.state === "inside"
        ? onDisk(home)
        : null;
  if (base === null) {
    checks.unmeasured(
      `${registration}.registration`,
      `no ${where} location was resolved to read the registration from`,
    );
    return checks.finish();
  }
  const facts =
    registration === "claude"
      ? claudeRegistration(base)
      : codexRegistrationOf(base);
  line.registration = facts;
  const file = registration === "claude" ? ".mcp.json" : "config.toml";
  const seenInConsole =
    registration === "claude"
      ? seen.files.claudeRegistration
      : seen.files.codexRegistration;
  line.console_sees_registration_file = seenInConsole;
  const present =
    registration === "claude" ? facts.mcp_json : facts.config_toml;
  if (!present) {
    checks.unmeasured(
      `${registration}.registration_file`,
      `${file} is absent from the ${where} the console runs in (${namesIn(base)?.length ?? "no"} entries there). ` +
        "The service's console_environment read names provider homes and the agent workspace and creates the workspace empty; " +
        "it writes no tool server registration, so it is the bundled cadrumo-agent that must prepare it. " +
        "Either its pin has no console prepare yet or the prepare has not run for this profile",
    );
    return checks.finish();
  }
  checks.ok(
    `${registration}.console_sees_registration_file`,
    seenInConsole === "True",
    `the console's own shell does not see the ${file} the disk holds (${seenInConsole})`,
  );
  judgeLauncher(checks, `${registration}.c`, facts.server);
  if (registration === "claude") {
    checks.ok(
      "claude.settings_local_present",
      facts.settings_local,
      ".claude/settings.local.json is absent from the workspace",
    );
    checks.ok(
      "claude.enabledMcpjsonServers_names_it",
      !!facts.enabled,
      "enabledMcpjsonServers does not list the registered cadrumo-mcp server",
    );
  }
  return checks.finish();
}

/** The characters of `expected` a received text lacks, in order: [{at, char}]. */
function droppedFrom(expected, received) {
  const dropped = [];
  let next = 0;
  for (let at = 0; at < expected.length; at += 1) {
    const found = received.indexOf(expected[at], next);
    if (found < 0) dropped.push({ at, char: expected[at] });
    else next = found + 1;
  }
  return dropped;
}

const HUMAN_KEY_MS = 60;
const TYPED = "Set-Content Abc-Xyz_09 stRUp C:\\Dir-9\\x";

conCase(
  "CON-typing a person's keys at a human pace reach the console unchanged",
  "typing",
  async (t, line) => {
    await prelude(line);
    const nonce = randomBytes(6).toString("hex");
    const file = join(storage, `console-probe-${nonce}.txt`);
    // The command is typed by keys, one every HUMAN_KEY_MS, around the pasted
    // file name: the shell writes what it received for the typed string.
    await focusConsole();
    for (const key of `'${TYPED}' | Set-Content -LiteralPath `) {
      await win.browser.keys(key);
      await sleep(HUMAN_KEY_MS);
    }
    assert(await pasteText(`'${file.replaceAll("'", "''")}'`));
    await sleep(300);
    await win.browser.keys(ENTER);
    const interrupting = await exec(pageDialogs);
    if (interrupting.length > 0) {
      line.dialog_interrupted = true;
      line.dialog_interrupted_titles = interrupting;
    }
    const answer = await waitFor(
      async () => {
        const text = readText(file);
        return text !== null && /\n$/.test(text) ? { text: text.trim() } : null;
      },
      { timeout: 20_000, what: "the typed line's answer file", soft: true },
    );
    try {
      rmSync(file, { force: true });
    } catch {
      // Reported by the case's own result.
    }
    line.key_interval_ms = HUMAN_KEY_MS;
    line.typed_length = TYPED.length;
    if (!answer) {
      line.received = null;
      await saveShot();
      assert.fail(
        `keys at a human pace left the console's command unrunnable: no answer file for the ${TYPED.length}-character string`,
      );
    }
    line.received_length = answer.text.length;
    line.dropped = droppedFrom(TYPED, answer.text);
    assert.deepEqual(
      line.dropped,
      [],
      `characters typed at ${HUMAN_KEY_MS} ms intervals that the console dropped (received: ${JSON.stringify(answer.text)})`,
    );
    assert.equal(
      answer.text,
      TYPED,
      "the console received other text than was typed",
    );
  },
  180_000,
);

conCase(
  "CON-claude the console takes the profile's Claude home, workspace and tool server",
  "claude",
  (t, line) => providerCase("claude", line, "claude"),
);

conCase(
  "CON-codex the console takes the profile's Codex home and tool server",
  "codex",
  (t, line) => providerCase("codex", line, "codex"),
);

// --- refresh ---------------------------------------------------------------

/** Choose a profile in the sign-in form; answers whether it was chosen. */
function pageChooseProfile(value) {
  const node = document.querySelector("#profile-choice");
  if (!node) return false;
  const option = [...node.options].find((item) => item.value === value);
  if (!option || option.disabled) return false;
  Object.getOwnPropertyDescriptor(
    HTMLSelectElement.prototype,
    "value",
  ).set.call(node, value);
  node.dispatchEvent(new Event("input", { bubbles: true }));
  node.dispatchEvent(new Event("change", { bubbles: true }));
  return node.value === value;
}

/** The shell reached again after a sign-in, or the form's own refusal words. */
function pageAfterSignIn() {
  const shown = (el) => !!el && el.getClientRects().length > 0;
  return {
    rail: shown(document.querySelector('[data-rail="declarations"]')),
    password: shown(document.querySelector("#profile-password")),
    words: [
      ...document.querySelectorAll(
        '.sign-in [role="alert"], .sign-in [data-slot="alert"], .sign-in [data-slot="field-error"]',
      ),
    ]
      .map((el) => (el.textContent ?? "").replace(/\s+/g, " ").trim())
      .filter(Boolean),
  };
}

/** Sign in to another profile with the run's credential; answers { ok, words }. */
async function signInOther(profile) {
  const field = await waitFor(
    async () =>
      (await exec(pageAfterSignIn)).password
        ? await win.browser.$("#profile-password")
        : null,
    { timeout: 120_000, what: "the sign-in form" },
  );
  if (!(await exec(pageChooseProfile, profile)))
    return { ok: false, words: ["the form does not offer that profile"] };
  await field.setValue(profileCredential());
  await clickSelector(".sign-in button[type=submit]");
  const answer = await waitFor(
    async () => {
      const now = await exec(pageAfterSignIn);
      if (now.rail && !now.password) return { ok: true, words: [] };
      if (now.words.length > 0) return { ok: false, words: now.words };
      return null;
    },
    { timeout: 300_000, what: "the sign-in answer", soft: true },
  );
  return answer ?? { ok: false, words: ["no sign-in answer"] };
}

/** Sign out through the account menu, as teardown does; answers whether the form is back. */
async function signOut() {
  assert(await exec(pageOpenAccountMenu), "the account menu cannot be opened");
  await sleep(500);
  assert(
    await exec(pageChooseSignOut, label("desktop.account.sign_out")),
    "the account menu offers no sign-out",
  );
  return waitFor(() => exec(pageSignedOut), {
    timeout: 60_000,
    what: "the sign-in form after signing out",
    soft: true,
  });
}

conCase(
  "CON-refresh a sign-out and a sign-in give the console the new environment",
  "refresh",
  async (t, line) => {
    const checks = checklist(line);
    const earlier = await measuredConsole(true);
    const beforeOwner = profileDirectory(earlier.cwd);
    if (!beforeOwner)
      assert.fail(
        "UNMEASURED: the console reported no agent workspace before the change, so a change cannot be told from it (the claude and codex cases say why)",
      );

    // The console process is told apart from the next one by a variable only it holds.
    const mark = randomBytes(6).toString("hex");
    await typeLine(`$global:CadrumoConsoleMark='${mark}'`);
    line.marker_set = (await probe("$global:CadrumoConsoleMark")) === mark;
    assert(line.marker_set, "UNMEASURED: the console kept no marker variable");

    // What the code promises: the profile signing out and in again is read
    // afresh; a running console is not stopped, it is asked to restart; a
    // console that has no process is opened again. The next console holds the
    // profile's new environment and none of the previous one's values.
    assert(await signOut(), "the window did not return to its sign-in form");
    line.signed_out = true;
    let switched = "not-requested";
    if (OTHER_PROFILE !== "" && OTHER_PROFILE !== PROFILE) {
      const other = await signInOther(OTHER_PROFILE);
      if (other.ok) switched = "switched";
      else {
        switched = "refused";
        await signIn(profileCredential());
        assert.fail(
          `UNMEASURED: the other profile refused the run's credential (${other.words.join(" | ").slice(0, 120)})`,
        );
      }
    } else {
      await signIn(profileCredential());
    }
    line.profile_switch = switched;
    await dismissSetup();

    const shown = await showConsole();
    checks.ok(
      "console_drawn_again",
      !!shown,
      "the window shows no console after the sign-in",
    );
    if (!shown) return checks.finish();

    // The running console is either asked to restart (its process is still the
    // old one) or was already opened again (its process is new).
    const state = await waitFor(
      async () => {
        const now = await exec(pageConsole);
        return now.notice ? { kind: "asks" } : null;
      },
      { timeout: 20_000, what: "the restart notice", soft: true },
    );
    let handled = state?.kind ?? "no-notice";
    if (state) {
      await win.browser.execute(() => {
        document
          .querySelector('[data-slot="console-environment-notice"] button')
          ?.click();
      });
      await sleep(1500);
    }
    line.notice = handled;
    assert(
      await consoleReady(),
      "UNMEASURED: the console shell answered no input after the change",
    );
    const alive = (await probe("$global:CadrumoConsoleMark")) === mark;
    line.old_process_still_running = alive;
    if (alive)
      checks.unmeasured(
        "console_refreshed",
        "the console kept its old process and offered no restart notice, so a refresh cannot be told from a missed one",
      );
    else checks.pass("console_refreshed");

    const later = await snapshot();
    current = later;
    const afterOwner = profileDirectory(later.cwd);
    const afterHomes = Object.fromEntries(
      Object.entries(later.homes).map(([name, place]) => [
        name,
        profileDirectory(place),
      ]),
    );
    checks.ok(
      "cwd_is_agent_workspace_again",
      afterOwner !== null &&
        later.cwd.parts.slice(2).join("/") === WORKSPACE_PARTS.join("/"),
      `the new console's working directory is ${later.cwd.state}, not an agent workspace`,
    );
    checks.ok(
      "homes_belong_to_the_same_profile_as_the_cwd",
      afterOwner !== null &&
        Object.values(afterHomes).every((owner) => owner === afterOwner),
      "the new console mixes the homes of one profile with the workspace of another",
    );
    if (switched === "switched") {
      checks.ok(
        "workspace_changed_with_the_profile",
        afterOwner !== null && afterOwner !== beforeOwner,
        "the other profile's console still runs in the previous profile's agent directory",
      );
      checks.ok(
        "no_previous_profile_value_remains",
        ![later.cwd, ...Object.values(later.homes)].some(
          (place) => profileDirectory(place) === beforeOwner,
        ),
        "a location of the previous profile is still named by the new console",
      );
    } else {
      checks.ok(
        "same_profile_same_directory",
        afterOwner === beforeOwner,
        "the same profile signed in again and its agent directory changed",
      );
      checks.unmeasured(
        "profile_switch",
        "no second profile was requested (CADRUMO_CONSOLE_OTHER_PROFILE), so a different profile's directory is not shown; only the sign-out and sign-in trigger is",
      );
    }
    return checks.finish();
  },
  900_000,
);

// --- teardown --------------------------------------------------------------

test("CON-99 the console is closed, the profile signed out, and no credential left", async (t) => {
  let exited = null;
  let teardownError = null;
  try {
    if ((await showConsole()) && (await consoleReady(15_000))) {
      await typeLine("exit");
      exited = !!(await waitFor(
        async () => {
          const now = await exec(pageConsole);
          return (now.tabDescription ?? "").length > 0 ? now : null;
        },
        { timeout: 20_000, what: "the console to report it ended", soft: true },
      ));
    }
  } catch (error) {
    exited = `close-failed: ${error.message}`;
  }
  const consoleLogs = scanLogs(runDir, (text) => /console/i.test(text));
  let password = null;
  try {
    password = profileCredential();
  } catch {
    password = null;
  }
  const leaked = password
    ? scanLogs(runDir, (text) => text.includes(password))
    : null;
  try {
    await teardown();
  } catch (error) {
    teardownError = error.message;
  }
  let counts = null;
  try {
    counts = credentialCounts();
  } catch (error) {
    credentialError = credentialError ?? error.message;
  }
  record(t, {
    case: "teardown",
    console_ended: exited,
    console_log_lines: consoleLogs.lines,
    console_log_files: consoleLogs.in_files,
    credential_in_logs: leaked ? leaked.lines > 0 : "unsearched",
    credential_store: { before: credentialsBefore, after: counts },
    teardown_error: teardownError,
    signed_out: win.closed,
  });
  if (leaked)
    assert.equal(
      leaked.lines,
      0,
      "the profile credential appears in a log under the run",
    );
  if (process.platform !== "win32") {
    t.skip("the credential store is counted on Windows only");
    return;
  }
  assert.equal(credentialError, null, `cmdkey: ${credentialError}`);
  assert.equal(teardownError, null, `teardown: ${teardownError}`);
  for (const kind of ["profileSession", "cadrumo", "provider"])
    assert(
      counts[kind] <= credentialsBefore[kind],
      `the run left ${counts[kind] - credentialsBefore[kind]} more ${kind} credential-store target(s)`,
    );
});
