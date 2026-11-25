// The packaged window at rest on a fresh profile, where the local AI has its
// bundled program but no model yet. Asking for model lists is never an error:
// a local AI that is not set up, has no model downloaded or is not running is
// a state the window shows with its next step, and nothing reads the lists
// again on a timer.
//
// MLI-01 signs in and finds the setup summary naming the local AI's state and
// its next step (the program ready and a model to download).
// MLI-02 puts the setup panel away and waits until the window has made no
// agent call for QUIET_MS (the panels' own opening reads, at most SETTLE_MS),
// then leaves the window alone for the idle window and asserts that the host
// logged no WARNING or ERROR line in it and that the window did not ask for
// the local model list again.
//
// Environment: as ./silent-controls.test.mjs (CADRUMO_PERSONA_WORLD,
// CADRUMO_PERSONA_HOST, CADRUMO_CMAKE_BINARY_DIR, CADRUMO_BUILD_CONFIG,
// CADRUMO_UX_RUN), plus
//   CADRUMO_MODEL_LIST_IDLE_MS  (optional) the idle window; default 300000
//
// Results are appended, one JSON object per line, to
// <run>/model-list-idle.jsonl, with every WARNING or ERROR line in full.
import assert from "node:assert/strict";
import {
  appendFileSync,
  closeSync,
  existsSync,
  mkdtempSync,
  openSync,
  readdirSync,
  readSync,
  statSync,
} from "node:fs";
import { tmpdir } from "node:os";
import { join, resolve } from "node:path";
import { after, before, test } from "node:test";
import {
  exec,
  label,
  sleep,
  start,
  teardown,
  waitFor,
  win,
} from "./ux-driver.mjs";
import { callsSince, pageTimeInvokes } from "./ux-calls.mjs";
import { dismissSetup } from "./ux-nav.mjs";

const IDLE_MS = Number(process.env.CADRUMO_MODEL_LIST_IDLE_MS ?? 300_000);
const QUIET_MS = 20_000;
const SETTLE_MS = 120_000;
const LOG_READ_LIMIT = 4 << 20;
/** A log line at WARNING or above, in the host's text or JSON records. */
const RAISED =
  /"(?:level|levelname)"\s*:\s*"(?:WARN|WARNING|ERROR|CRITICAL)"|\b(?:WARN|WARNING|ERROR|CRITICAL)\b/;
const LOCAL_MODELS = "agent_local_models";

let runDir;
let results;

function record(line) {
  appendFileSync(results, `${JSON.stringify(line)}\n`);
  console.info(JSON.stringify(line));
}

/** The sizes of the host's log files under the run's storage, by path. */
function logSizes() {
  const sizes = new Map();
  const walk = (dir, depth) => {
    if (depth > 6 || !existsSync(dir)) return;
    for (const entry of readdirSync(dir, { withFileTypes: true })) {
      const path = join(dir, entry.name);
      // The WebView's profile (LevelDB *.log files) holds page storage, not
      // the host's logs.
      if (entry.isDirectory()) {
        if (!/^(webview|EBWebView)$/i.test(entry.name)) walk(path, depth + 1);
      } else if (/\.(log|jsonl)$/i.test(entry.name)) {
        try {
          sizes.set(path, statSync(path).size);
        } catch {
          // A log rotated away between the listing and the stat is not counted.
        }
      }
    }
  };
  walk(resolve(runDir, "storage"), 0);
  return sizes;
}

/** The lines the host's logs gained since `from`; a file that shrank was
 * rotated and is read from its start. */
function logLinesSince(from) {
  const lines = [];
  for (const [path, size] of logSizes()) {
    const begin = (from.get(path) ?? 0) > size ? 0 : (from.get(path) ?? 0);
    if (size <= begin) continue;
    let fd;
    try {
      fd = openSync(path, "r");
      const buffer = Buffer.alloc(Math.min(size - begin, LOG_READ_LIMIT));
      const read = readSync(fd, buffer, 0, buffer.length, begin);
      lines.push(
        ...buffer
          .subarray(0, read)
          .toString("utf8")
          .split(/\r?\n/)
          .filter((line) => line.trim()),
      );
    } catch {
      // A log rotated away while it was read adds no lines.
    } finally {
      if (fd !== undefined) closeSync(fd);
    }
  }
  return lines;
}

/** The local AI row of the setup panel, as its text reads. */
function pageLocalAiSummary() {
  const row =
    document.querySelector('[data-setup-element="local_ai"]') ??
    document.querySelector('[data-setup-row="local_ai"]');
  return row ? (row.textContent ?? "").replace(/\s+/g, " ").trim() : null;
}

before(async () => {
  runDir =
    process.env.CADRUMO_UX_RUN ??
    join(mkdtempSync(join(tmpdir(), "cadrumo-e2e-model-list-idle-")), "run");
  results = join(runDir, "model-list-idle.jsonl");
  await start(runDir);
  assert(await exec(pageTimeInvokes), "the window's host calls are not timed");
});
after(async () => {
  if (!win.closed) await teardown();
});

test("MLI-01 the setup summary names the local AI's state and its next step", async () => {
  const awaited = label("desktop.setup.awaits_model");
  const summary = await waitFor(
    async () => {
      const text = await exec(pageLocalAiSummary);
      return text && text.includes(awaited) ? text : null;
    },
    {
      timeout: 30_000,
      what: "the local AI summary to name its next step",
      soft: true,
    },
  );
  const seen = summary ?? (await exec(pageLocalAiSummary));
  record({ case: "MLI-01", summary: seen, expected: awaited });
  assert.ok(
    seen?.includes(awaited),
    `the local AI summary reads ${JSON.stringify(seen)}, not its next step ${JSON.stringify(awaited)}`,
  );
});

/** The agent calls made since `since`, with when each started. */
async function agentCalls(since) {
  return (await callsSince(since))
    .filter((call) => call.cmd.startsWith("agent_"))
    .map((call) => `${call.cmd}@${call.startMs}`);
}

test("MLI-02 the idle window logs no WARNING or ERROR and reads no model list again", async () => {
  await dismissSetup();
  const closed = Date.now();
  let settled = null;
  while (Date.now() - closed < SETTLE_MS) {
    await sleep(1_000);
    const last = (await callsSince(closed))
      .filter((call) => call.cmd.startsWith("agent_"))
      .reduce(
        (latest, call) => Math.max(latest, closed + call.startMs),
        closed,
      );
    if (Date.now() - last >= QUIET_MS) {
      settled = Date.now();
      break;
    }
  }
  const opening = await agentCalls(closed);
  assert.ok(
    settled,
    `the window kept asking for agent data for ${SETTLE_MS} ms after the setup panel closed: ${opening.join(", ")}`,
  );
  const visibility = await exec(() => document.visibilityState);
  const fromLogs = logSizes();
  const since = Date.now();
  await sleep(IDLE_MS);
  const raised = logLinesSince(fromLogs).filter((line) => RAISED.test(line));
  const calls = await callsSince(since);
  const localModels = calls.filter((call) => call.cmd === LOCAL_MODELS);
  const sinceLaunch = logLinesSince(new Map()).filter((line) =>
    RAISED.test(line),
  );
  record({
    case: "MLI-02",
    idle_ms: IDLE_MS,
    raised,
    raised_since_launch: sinceLaunch,
    local_model_reads: localModels.length,
    model_list_starts: await agentCalls(since),
    opening_agent_calls: opening,
    visibility,
    calls_by_command: Object.fromEntries(
      [...new Set(calls.map((call) => call.cmd))].map((command) => [
        command,
        calls.filter((call) => call.cmd === command).length,
      ]),
    ),
  });
  assert.deepEqual(
    raised,
    [],
    `${raised.length} WARNING/ERROR line(s) while idle`,
  );
  assert.equal(
    localModels.length,
    0,
    `the local model list was read ${localModels.length} times while idle`,
  );
});
