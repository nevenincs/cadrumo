// Sweep every persona@horizon case of a persona-table rows file through the
// packaged native window and collect the window's acceptance lines.
//
// For each case (one persona under one horizon) the runner
//   1. materialises a world with `python -m dev.desktop_persona_world` into a
//      fresh root <temp>/cadrumo-e2e-<run>-<case>/world,
//   2. runs window-persona.test.mjs for that world with the results written to
//      the root, and
//   3. validates every line the spec wrote, then removes the root.
// A persona's lines are appended to the output file as soon as its last case
// finishes, and only for cases whose lines all validate. A case that fails to
// validate contributes nothing and is reported; a case that times out
// contributes the lines the spec wrote, and each row it did not reach is
// reported as not run, with its cause, in <out>.not-run.txt (one JSON object
// per line, never written as a window result and never dropped; not .jsonl,
// because the table's render reads every .jsonl beside the output as results).
// A persona-level line (modelo null) is kept once per persona, from its first
// case. The spec's logs are copied to --logs and each line's `log` points at
// the copy.
//
// Usage:
//   node native/desktop/tests/personas/run-sweep.mjs --tree <sha> \
//     --build <CMake binary dir of the packaged host> [--rows <rows-<sha>.jsonl>] \
//     [--config Release] [--jobs 1] [--persona <id>[@<horizon>][,...]] [--out <file>] \
//     [--case-timeout-min 30] [--durations <dir>[,<dir>...]] [--logs <dir>]
//     [--fresh] [--no-stop-on-load-failure]
//     [--loads-only] [--world-tree <dir>] [--staged-package <dir>] [--dry-run]
//
//   --rows       default: the newest rows-*.jsonl in the table directory; the
//                tree defaults to the sha in that file name.
//   --jobs       personas run concurrently up to this cap; the cases of one
//                persona run one after another. Default 1.
//   --fresh      truncate the output file first; otherwise lines are appended.
//   --logs       where the per-case logs are kept.
//   --durations  spec logs of earlier sweeps (default: --logs). Each case's
//                timeout is sized from its own rows: the longest recorded
//                start-up plus, per row, the longest recorded duration of
//                that modelo (a default where none is recorded), times a
//                margin; --case-timeout-min is only the floor.
//   By default no further case starts once a case's window did not load the
//   profile (loads false) or its world was not prepared;
//   --no-stop-on-load-failure runs on.
//   --world-tree materialise worlds from this source tree (src and dev) instead
//                of the repository, so a world matches an older packaged build.
//   --staged-package reuse an automation package mirror an earlier run staged
//                (its app directory) instead of staging, when the build records
//                have since moved past the package under test.
//   --loads-only plan one case per persona (the newest horizon of the rows
//                file) and only sign in and wait for the declarations list
//                (CADRUMO_PERSONA_LOADS_ONLY=1); a load failure does not stop
//                the sweep, and each persona's line is appended as it ends.
//                A final line per persona reads `<persona> loads=<yes|no> <reason>`.
//   A case that fails with a WebView2 ExecuteScript error, a timeout or
//   `Access is denied` is a harness failure: its lines carry the reason prefix
//   `cause harness: ` and the sweep goes on; only a real sign-in or version
//   refusal stops it.
//   --only-listed open only the declarations the rows file lists for each case,
//                each with its year's earlier ones (CADRUMO_PERSONA_ONLY), so a
//                rerun of moved rows re-measures those rows and what they
//                read, not every return of the persona's world.
//   --dry-run    print the planned cases and exit; nothing is launched.
//
// The packaged host is staged once at the start and shared by every window;
// the spec is told so through CADRUMO_PERSONA_HOST and stages nothing itself.
// Ports and nonces: the spec picks a free loopback port and a fresh random
// nonce for each window it launches, so concurrent cases do not share them.
// Processes: only the spec processes this runner started are stopped (their
// process tree, by PID), on a case timeout or when the runner is interrupted.
// Python needs CADRUMO_DEV_AGENT_CHECKOUT in the environment, as the world
// tests do.
import { spawn, spawnSync } from "node:child_process";
import {
  appendFileSync,
  copyFileSync,
  existsSync,
  mkdirSync,
  readdirSync,
  readFileSync,
  rmSync,
  statSync,
  writeFileSync,
} from "node:fs";
import { tmpdir } from "node:os";
import { basename, delimiter, dirname, join, resolve, sep } from "node:path";
import { fileURLToPath } from "node:url";
import {
  removeLeftSessionKeys,
  sessionKeyTargets,
  storageProfileIds,
} from "../automation/session-keys.mjs";

const repository = fileURLToPath(new URL("../../../../", import.meta.url));
const spec = fileURLToPath(
  new URL("./window-persona.test.mjs", import.meta.url),
);
const TABLE_DIR = "X:/code/cadrumo/.tmp/2026-11-11-prime/table";
const KEYS = [
  "surface",
  "tree",
  "persona",
  "modelo",
  "year",
  "period",
  "loads",
  "calculate",
  "verify",
  "export",
  "refusal_code",
  "figures",
  "reason",
  "log",
];
// Row keys the spec states only when they apply: export_served says whether a
// return whose verification did not pass was served an export door, and file
// is the stage of the local filing the window recorded (the acceptance
// intake's stage words plus not-shown); blocking_findings are the ids of the
// blocking findings the form served once a check did not pass.
const OPTIONAL_ROW_KEYS = ["export_served", "file", "blocking_findings"];
const FILE_WORDS = [
  "pass",
  "incomplete",
  "refused",
  "not-owed",
  "not-reached",
  "error",
  "not-shown",
];
const optionalProblem = {
  export_served: (value) =>
    typeof value === "boolean" ? null : "export_served is not a boolean",
  file: (value) =>
    FILE_WORDS.includes(value) ? null : `file ${value} is not a stage word`,
  blocking_findings: (value) =>
    Array.isArray(value) &&
    value.every((id) => typeof id === "string" && id.trim() !== "")
      ? null
      : "blocking_findings is not an array of non-empty finding ids",
};
const PERSONA_KEYS = KEYS.filter(
  (key) => !["calculate", "verify", "export"].includes(key),
);

function parseArguments(argv) {
  const flags = new Set([
    "dry-run",
    "fresh",
    "loads-only",
    "no-stop-on-load-failure",
    "only-listed",
  ]);
  const values = {};
  for (let index = 0; index < argv.length; index += 1) {
    const name = argv[index];
    if (!name.startsWith("--")) throw new Error(`unexpected argument ${name}`);
    const key = name.slice(2);
    if (flags.has(key)) values[key] = true;
    else {
      const value = argv[(index += 1)];
      if (value === undefined) throw new Error(`${name} needs a value`);
      values[key] = value;
    }
  }
  return values;
}

function newestRows() {
  const found = readdirSync(TABLE_DIR)
    .filter((name) => /^rows-.+\.jsonl$/.test(name))
    .map((name) => join(TABLE_DIR, name));
  if (found.length === 0) throw new Error(`no rows-*.jsonl in ${TABLE_DIR}`);
  const mtime = (path) => statSync(path).mtimeMs;
  return found.sort((a, b) => mtime(b) - mtime(a))[0];
}

/** Every persona@horizon of the rows file, in first-seen order, with its row count. */
export function plannedCases(rowsPath) {
  const cases = new Map();
  const lines = readFileSync(rowsPath, "utf8").split(/\r?\n/);
  lines.forEach((line, index) => {
    if (!line.trim()) return;
    const row = JSON.parse(line);
    if (typeof row.persona !== "string" || !Number.isInteger(row.horizon))
      throw new Error(`${rowsPath}:${index + 1} has no persona and horizon`);
    const id = `${row.persona}@${row.horizon}`;
    const found = cases.get(id) ?? {
      id,
      persona: row.persona,
      horizon: row.horizon,
      rows: 0,
      listed: [],
    };
    found.rows += 1;
    if (row.modelo != null)
      found.listed.push(`${row.modelo}/${row.year}/${row.period}`);
    cases.set(id, found);
  });
  return [...cases.values()];
}

/** One case per persona: its newest horizon. */
export function newestHorizonCases(cases) {
  const newest = new Map();
  for (const item of cases) {
    const have = newest.get(item.persona);
    if (!have || item.horizon > have.horizon) newest.set(item.persona, item);
  }
  return [...newest.values()];
}

/** Whether a failure is the harness's (WebView2 script error, timeout, access denied), not the window's. */
export function isHarnessFailure(text) {
  return /0x8007139F|ExecuteScript|timeout|timed out|Access is denied/i.test(
    String(text),
  );
}

function byPersona(cases) {
  const groups = new Map();
  for (const item of cases)
    groups.set(item.persona, [...(groups.get(item.persona) ?? []), item]);
  return [...groups.values()];
}

// ---------------------------------------------------------------------------
// Processes the runner started
// ---------------------------------------------------------------------------

const started = new Set();

function stopTree(pid) {
  if (process.platform === "win32")
    spawnSync("taskkill", ["/PID", String(pid), "/T", "/F"], {
      stdio: "ignore",
    });
  else {
    try {
      process.kill(pid, "SIGTERM");
    } catch {
      // already gone
    }
  }
}

function stopStarted() {
  for (const pid of started) stopTree(pid);
  started.clear();
}

for (const signal of ["SIGINT", "SIGTERM"])
  process.on(signal, () => {
    stopStarted();
    process.exit(130);
  });

/** Run a child to its end; stop its tree on timeout. Resolves with status and captured output. */
function run(command, args, options, timeoutMs) {
  return new Promise((done) => {
    const child = spawn(command, args, { ...options, windowsHide: true });
    started.add(child.pid);
    let stdout = "";
    let stderr = "";
    child.stdout.on("data", (chunk) => (stdout += chunk));
    child.stderr.on("data", (chunk) => (stderr += chunk));
    let timedOut = false;
    const timer = setTimeout(() => {
      timedOut = true;
      stopTree(child.pid);
    }, timeoutMs);
    child.on("close", (status) => {
      clearTimeout(timer);
      started.delete(child.pid);
      done({ status, stdout, stderr, timedOut });
    });
    child.on("error", (error) => {
      clearTimeout(timer);
      started.delete(child.pid);
      done({ status: -1, stdout, stderr: String(error), timedOut });
    });
  });
}

// ---------------------------------------------------------------------------
// One case
// ---------------------------------------------------------------------------

function windowsTemp() {
  return process.env.LOCALAPPDATA
    ? join(process.env.LOCALAPPDATA, "Temp")
    : tmpdir();
}

function removeRoot(root, parent) {
  const resolved = resolve(root);
  const inside = resolved.startsWith(resolve(parent) + sep);
  if (!inside || !basename(resolved).startsWith("cadrumo-e2e-")) {
    throw new Error(`refusing to remove ${resolved}`);
  }
  rmSync(resolved, {
    recursive: true,
    force: true,
    maxRetries: 5,
    retryDelay: 500,
  });
  if (existsSync(resolved)) throw new Error(`${resolved} was not removed`);
}

/** Refusals a person can act on, which the host says below error. */
const ACTIONABLE_REFUSALS = new Set([
  "agent_signed_out",
  "agent_provider_credential_missing",
]);

/**
 * Why a run root must be kept for diagnosis, or null: its host recorded a
 * failure or refused the agent, or its runtime logged an error. A sign-in or
 * agent failure is diagnosed from these logs, which a removed root takes with it.
 */
export function keepReason(runRoot) {
  const host = join(runRoot, "storage", "logs", "cadrumo-native.jsonl");
  if (existsSync(host)) {
    for (const line of readFileSync(host, "utf8").split(/\r?\n/)) {
      if (!line.trim()) continue;
      let record;
      try {
        record = JSON.parse(line);
      } catch {
        return "the host log has an unreadable record";
      }
      if (record.failure) return "the host recorded a failure";
      const service = record.service;
      if (
        service?.event === "agent_refused" &&
        !ACTIONABLE_REFUSALS.has(service.reason)
      )
        return `the host refused the agent: ${service.reason}`;
    }
  }
  const runtime = join(runRoot, "storage", "logs", "cadrumo.log");
  if (
    existsSync(runtime) &&
    /\[ERROR\]|\[CRITICAL\]/.test(readFileSync(runtime, "utf8"))
  )
    return "the runtime logged an error";
  return null;
}

/** Why the case's lines do not meet the acceptance contract, or null. */
export function lineProblem(lines, world, tree, persona) {
  const seen = new Set();
  let personaLines = 0;
  for (const line of lines) {
    const optional = line.modelo === null ? [] : OPTIONAL_ROW_KEYS;
    const keys = Object.keys(line)
      .filter((key) => !optional.includes(key))
      .sort();
    const expected = (line.modelo === null ? PERSONA_KEYS : KEYS)
      .slice()
      .sort();
    if (JSON.stringify(keys) !== JSON.stringify(expected))
      return `line keys differ: ${Object.keys(line).sort().join(",")}`;
    for (const key of optional) {
      const problem = key in line ? optionalProblem[key](line[key]) : null;
      if (problem) return problem;
    }
    if (line.surface !== "window") return "surface is not window";
    if (line.tree !== tree) return `tree ${line.tree} is not ${tree}`;
    if (line.persona !== persona) return `persona ${line.persona}`;
    if (line.modelo === null) {
      personaLines += 1;
      continue;
    }
    const key = `${line.modelo}|${line.year}|${line.period}`;
    if (seen.has(key)) return `row ${key} appears twice`;
    seen.add(key);
  }
  if (personaLines !== 1) return `${personaLines} persona lines`;
  for (const row of world.rows) {
    if (!seen.delete(`${row.modelo}|${row.year}|${row.period}`))
      return `no line for row ${row.modelo} ${row.year} ${row.period}`;
  }
  if (seen.size !== 0) return `lines for rows the world lacks: ${[...seen]}`;
  return null;
}

const rowKey = (row) => `${row.modelo}/${row.year}/${row.period}`;

/** The listed rows, each with the rows of its year the world orders before it. */
export function listedWithTheirYear(rows, listed) {
  const last = new Map();
  rows.forEach((row, index) => {
    if (listed.includes(rowKey(row))) last.set(String(row.year), index);
  });
  return rows.filter(
    (row, index) => index <= (last.get(String(row.year)) ?? -1),
  );
}

/** The world rows a timed-out case's spec wrote no line for. */
export function unreachedRows(lines, world) {
  const have = new Set(
    lines.map((line) => `${line.modelo}|${line.year}|${line.period}`),
  );
  return world.rows.filter(
    (row) => !have.has(`${row.modelo}|${Number(row.year)}|${row.period}`),
  );
}

const MODELO_OF_HEADER = /^Declaraciones(\d{3})/;

/**
 * The longest recorded start-up and per-modelo row durations (ms) in the spec
 * logs (`<persona>-<horizon>.log`, one JSON event per line) under `dirs`. A row
 * runs from its `workspace` event to the next one, the last to the log's last
 * event; start-up runs from `launched` to the first `workspace`.
 */
export function recordedDurations(dirs) {
  const rows = new Map();
  let startup = 0;
  for (const dir of dirs) {
    let names = [];
    try {
      names = readdirSync(dir).filter((name) => /-\d{4}\.log$/.test(name));
    } catch {
      continue;
    }
    for (const name of names) {
      const events = [];
      for (const text of readFileSync(join(dir, name), "utf8").split(/\r?\n/)) {
        if (!text.trim()) continue;
        try {
          const event = JSON.parse(text);
          const at = Date.parse(event.at);
          if (Number.isFinite(at)) events.push({ ...event, at });
        } catch {
          // a torn last line of a killed spec
        }
      }
      if (events.length === 0) continue;
      const opened = events.filter((event) => event.event === "workspace");
      const launched = events.find((event) => event.event === "launched");
      if (launched && opened.length)
        startup = Math.max(startup, opened[0].at - launched.at);
      const last = events[events.length - 1].at;
      opened.forEach((event, index) => {
        const modelo = MODELO_OF_HEADER.exec(event.header ?? "")?.[1];
        if (!modelo) return;
        const end = index + 1 < opened.length ? opened[index + 1].at : last;
        rows.set(modelo, Math.max(rows.get(modelo) ?? 0, end - event.at));
      });
    }
  }
  return { startup, rows };
}

export const BUDGET = {
  defaultStartupMs: 5 * 60_000,
  defaultRowMs: 5 * 60_000,
  margin: 1.5,
};

/** A case's timeout: recorded start-up and row durations for its rows, with a margin, never below `floorMs`. */
export function caseBudgetMs(worldRows, recorded, floorMs, budget = BUDGET) {
  const startup = recorded.startup || budget.defaultStartupMs;
  const rows = worldRows.reduce(
    (sum, row) =>
      sum + (recorded.rows.get(String(row.modelo)) ?? budget.defaultRowMs),
    0,
  );
  return Math.max(floorMs, Math.ceil((startup + rows) * budget.margin));
}

async function runCase(item, context) {
  const {
    tree,
    build,
    config,
    runId,
    parent,
    logsDir,
    timeoutMs,
    ordinal,
    host,
  } = context;
  const root = join(parent, `cadrumo-e2e-${runId}-${ordinal}`);
  const result = { id: item.id, ok: false, lines: [], note: "" };
  try {
    mkdirSync(root, { recursive: true });
    const python = resolve(
      repository,
      process.platform === "win32"
        ? ".venv/Scripts/python.exe"
        : ".venv/bin/python",
    );
    const world = await run(
      python,
      [
        "-m",
        "dev.desktop_persona_world",
        "--persona",
        item.persona,
        "--horizon",
        String(item.horizon),
        "--storage-root",
        join(root, "world"),
      ],
      {
        cwd: context.worldTree,
        env: {
          ...process.env,
          PYTHONPATH: [join(context.worldTree, "src"), context.worldTree].join(
            delimiter,
          ),
        },
      },
      timeoutMs,
    );
    if (world.status !== 0) {
      result.note = `world not prepared (exit ${world.status}${world.timedOut ? ", timed out" : ""}): ${world.stderr.trim().split(/\r?\n/).slice(-3).join(" | ")}`;
      return result;
    }
    const worldPath = join(root, "world.json");
    writeFileSync(worldPath, world.stdout);
    const built = JSON.parse(world.stdout);
    // Under --only-listed the spec opens each listed declaration and the ones
    // of its year the world files before it, because a return reads those
    // (a Modelo 100 its year's Modelo 130 instalments); the case is sized and
    // checked against those rows, not the whole world.
    const worldJson = context.onlyListed
      ? { ...built, rows: listedWithTheirYear(built.rows, item.listed) }
      : built;
    const results = join(root, "results", "window.jsonl");
    mkdirSync(dirname(results), { recursive: true });
    // A spec killed at the case timeout never reaches its own sign-out and
    // credential guard, so the sweep removes the keys the case added itself.
    const profileIds = storageProfileIds(worldJson.storage_root);
    const keysBefore = sessionKeyTargets(profileIds);
    const caseMs = context.loadsOnly
      ? timeoutMs
      : caseBudgetMs(
          worldJson.rows,
          recordedDurations(context.durationDirs ?? [logsDir]),
          timeoutMs,
        );
    result.budgetMin = Math.round(caseMs / 60_000);
    const window = await run(
      process.execPath,
      ["--test", spec],
      {
        cwd: repository,
        env: {
          ...process.env,
          CADRUMO_PERSONA_WORLD: worldPath,
          CADRUMO_PERSONA_RESULTS: results,
          CADRUMO_PERSONA_RUN: join(root, "run"),
          CADRUMO_TREE: tree,
          CADRUMO_CMAKE_BINARY_DIR: build,
          CADRUMO_BUILD_CONFIG: config,
          CADRUMO_PERSONA_HOST: host,
          ...(context.loadsOnly ? { CADRUMO_PERSONA_LOADS_ONLY: "1" } : {}),
          ...(context.onlyListed
            ? { CADRUMO_PERSONA_ONLY: worldJson.rows.map(rowKey).join(",") }
            : {}),
          PYTHONDONTWRITEBYTECODE: "1",
        },
      },
      caseMs,
    );
    let lines = existsSync(results)
      ? readFileSync(results, "utf8")
          .split(/\r?\n/)
          .filter((text) => text.trim())
          .map((text) => JSON.parse(text))
      : [];
    // A timed-out case keeps what the window measured; every row it did not
    // reach is not run, with the cause, and is never written as a result.
    const unreached =
      window.timedOut && !context.loadsOnly
        ? unreachedRows(lines, worldJson)
        : [];
    const cause = `case timeout after ${result.budgetMin} min (sized from ${worldJson.rows.length} rows and recorded durations)`;
    result.notRun = unreached.map((row) => ({
      surface: "window",
      tree,
      persona: item.persona,
      horizon: item.horizon,
      modelo: row.modelo,
      year: Number(row.year),
      period: row.period,
      cause,
    }));
    const keys = removeLeftSessionKeys(profileIds, keysBefore);
    const keyNote =
      keys.left.length > 0
        ? `the case left ${keys.left.length} profile-session key(s)${window.timedOut ? " (timed out before its sign-out)" : ""}; removed ${keys.left.length - keys.failed.length}${keys.failed.length ? `, could not remove ${keys.failed.length}` : ""}`
        : "";
    // Keep the spec's log and test output under --logs before any refusal,
    // because the root is removed and a failed case is the one to diagnose.
    const caseName = item.id.replace("@", "-");
    const kept = join(logsDir, `${caseName}.log`);
    const logSource = join(dirname(results), `window-${item.persona}.log`);
    if (existsSync(logSource)) copyFileSync(logSource, kept);
    // The window's host output and the runtime log, which the removed root
    // would otherwise take with it: a WebView refusing scripts is diagnosed there.
    const runRoot = join(dirname(dirname(results)), "run");
    for (const [from, suffix] of [
      [join(runRoot, "host.stderr.log"), "host-stderr.log"],
      [join(runRoot, "host.stdout.log"), "host-stdout.log"],
      [join(runRoot, "storage", "logs", "cadrumo.log"), "runtime.log"],
    ])
      if (existsSync(from))
        copyFileSync(from, join(logsDir, `${caseName}.${suffix}`));
    writeFileSync(
      join(logsDir, `${caseName}.test.txt`),
      `${window.stdout}\n--- stderr ---\n${window.stderr}`,
    );
    if (lines.length === 0) {
      result.note = [
        window.timedOut
          ? `${cause}; the spec wrote no lines`
          : `the spec wrote no lines (exit ${window.status})`,
        keyNote,
      ]
        .filter(Boolean)
        .join("; ");
      return result;
    }
    const problem = lineProblem(
      lines,
      context.loadsOnly
        ? { rows: [] }
        : {
            ...worldJson,
            rows: worldJson.rows.filter((row) => !unreached.includes(row)),
          },
      tree,
      item.persona,
    );
    if (problem) {
      result.note = [problem, keyNote].filter(Boolean).join("; ");
      return result;
    }
    result.lines = lines.map((line) => ({ ...line, log: kept }));
    result.ok = true;
    result.note = [
      window.timedOut
        ? `${cause}: ${unreached.length} of ${worldJson.rows.length} rows not run`
        : window.status === 0
          ? ""
          : `spec exit ${window.status}`,
      keyNote,
    ]
      .filter(Boolean)
      .join("; ");
    return result;
  } catch (error) {
    result.note = String(error?.message ?? error);
    return result;
  } finally {
    // A failed case, or one whose window logged a failure, keeps its root
    // for diagnosis; every other root is removed.
    let kept = null;
    try {
      kept = result.ok ? keepReason(join(root, "run")) : "the case failed";
    } catch (error) {
      kept = `its logs could not be read: ${error.message}`;
    }
    if (kept) {
      result.note += ` | root kept (${kept}): ${root}`;
    } else {
      try {
        removeRoot(root, parent);
      } catch (error) {
        result.note += ` | cleanup: ${error.message}`;
      }
    }
  }
}

// ---------------------------------------------------------------------------
// Main
// ---------------------------------------------------------------------------

/**
 * The cases named by --persona (`<id>` or `<id>@<horizon>`, comma separated),
 * or every case when it is absent. A name that matches no case of the rows
 * file is refused, so a mistyped persona cannot silently shrink a sweep.
 */
export function selectCases(planned, persona) {
  if (!persona) return planned;
  const wanted = persona
    .split(",")
    .map((name) => name.trim())
    .filter(Boolean);
  const matches = (name, item) =>
    name === item.persona || name === `${item.persona}@${item.horizon}`;
  const unknown = wanted.filter(
    (name) => !planned.some((item) => matches(name, item)),
  );
  if (unknown.length > 0)
    throw new Error(
      `--persona names no case of the rows file: ${unknown.join(", ")}`,
    );
  return planned.filter((item) => wanted.some((name) => matches(name, item)));
}

async function main() {
  const args = parseArguments(process.argv.slice(2));
  const rowsPath = resolve(args.rows ?? newestRows());
  const tree = args.tree ?? basename(rowsPath).match(/^rows-(.+)\.jsonl$/)?.[1];
  if (!tree) throw new Error("--tree is required");
  const loadsOnly = args["loads-only"] === true;
  const filtered = selectCases(plannedCases(rowsPath), args.persona);
  const cases = loadsOnly ? newestHorizonCases(filtered) : filtered;
  const groups = byPersona(cases);
  if (args["dry-run"]) {
    console.log(`rows ${rowsPath}`);
    console.log(`tree ${tree}`);
    for (const group of groups)
      console.log(
        `${group[0].persona}: ${group.length} cases (${group.map((item) => `${item.horizon}:${item.rows} rows`).join(", ")})`,
      );
    console.log(
      `total: ${groups.length} personas, ${cases.length} cases, ${cases.reduce((sum, item) => sum + item.rows, 0)} table rows`,
    );
    return 0;
  }
  if (!args.build) throw new Error("--build is required");
  const jobs = Math.max(1, Number(args.jobs ?? 1));
  const out = resolve(
    args.out ??
      `X:/code/cadrumo/.tmp/2026-11-11-prime/table/frontend/window-${tree}.jsonl`,
  );
  const logsDir = resolve(
    args.logs ?? join(repository, ".tmp/2026-11-13-desktop-sweep"),
  );
  mkdirSync(dirname(out), { recursive: true });
  mkdirSync(logsDir, { recursive: true });
  const notRunOut = out.replace(/\.jsonl$/, "") + ".not-run.txt";
  if (args.fresh) {
    writeFileSync(out, "");
    writeFileSync(notRunOut, "");
  }
  // Stage the packaged host once, before any window runs: staging mirrors the
  // package over the previous one, which a running host holds open. Every
  // window then starts from the same staged package.
  const python = resolve(
    repository,
    process.platform === "win32"
      ? ".venv/Scripts/python.exe"
      : ".venv/bin/python",
  );
  const config = args.config ?? process.env.CADRUMO_BUILD_CONFIG ?? "Release";
  const staged = args["staged-package"]
    ? {
        status: 0,
        stdout: JSON.stringify({
          package: resolve(args["staged-package"]),
          executable: join(resolve(args["staged-package"]), "cadrumo.exe"),
        }),
      }
    : await run(
        python,
        [
          "-m",
          "dev.desktop_automation_stage",
          "--build",
          resolve(args.build),
          "--config",
          config,
        ],
        {
          cwd: repository,
          env: {
            ...process.env,
            PYTHONPATH: [join(repository, "src"), repository].join(delimiter),
          },
        },
        10 * 60_000,
      );
  if (staged.status !== 0)
    throw new Error(
      `staging the packaged host failed: ${(staged.stdout || staged.stderr).trim().slice(-400)}`,
    );
  const context = {
    host: staged.stdout.trim(),
    tree,
    build: resolve(args.build),
    config,
    runId: `${Date.now().toString(36)}`,
    parent: windowsTemp(),
    logsDir,
    timeoutMs: Number(args["case-timeout-min"] ?? 30) * 60_000,
    durationDirs: args.durations
      ? String(args.durations)
          .split(",")
          .filter(Boolean)
          .map((dir) => resolve(dir))
      : [logsDir],
    loadsOnly,
    onlyListed: args["only-listed"] === true,
    worldTree: args["world-tree"] ? resolve(args["world-tree"]) : repository,
  };
  const ordinals = new Map(cases.map((item, index) => [item.id, index + 1]));
  const results = new Map();
  const queue = [...groups];
  let halted = false;
  const harness = [];
  const worker = async () => {
    for (let group = queue.shift(); group && !halted; group = queue.shift()) {
      let personaLine = false;
      for (const item of group) {
        if (halted) break;
        console.error(`case ${item.id} start`);
        const done = await runCase(item, {
          ...context,
          ordinal: ordinals.get(item.id),
        });
        console.error(
          `case ${item.id} ${done.ok ? "ok" : "FAILED"} ${done.note}`,
        );
        results.set(item.id, done);
        if (done.notRun?.length)
          appendFileSync(
            notRunOut,
            done.notRun
              .map(
                (row) => `${JSON.stringify(row)}
`,
              )
              .join(""),
          );
        let unloaded = done.lines.find(
          (line) => line.modelo === null && line.loads === false,
        );
        const harnessLines = done.lines.filter((line) =>
          isHarnessFailure(line.reason),
        );
        if (harnessLines.length || (!done.ok && isHarnessFailure(done.note))) {
          // The harness failed, not the window: mark the lines and go on.
          harness.push(item.id);
          done.lines = done.lines.map((line) =>
            !harnessLines.includes(line) ||
            line.reason.includes("cause harness: ")
              ? line
              : {
                  ...line,
                  reason: line.reason.replace(
                    /^(\S+?: )?/,
                    (head) => `${head}cause harness: `,
                  ),
                },
          );
          if (unloaded && harnessLines.includes(unloaded)) unloaded = undefined;
        }
        // Append this case's validated lines now, so an interrupted run keeps
        // every case that finished; the persona-level line goes in once.
        if (done.ok) {
          const lines = done.lines.filter(
            (line) => line.modelo !== null || !personaLine,
          );
          personaLine ||= lines.some((line) => line.modelo === null);
          if (lines.length)
            appendFileSync(
              out,
              lines.map((line) => `${JSON.stringify(line)}\n`).join(""),
            );
        }
        if (
          !loadsOnly &&
          !args["no-stop-on-load-failure"] &&
          (unloaded || /world not prepared/.test(done.note))
        ) {
          halted = true;
          console.error(
            `stopping: ${item.id} did not load: ${unloaded?.reason ?? done.note}`,
          );
        }
      }
    }
  };
  await Promise.all(
    Array.from({ length: Math.min(jobs, groups.length) }, worker),
  );
  const output = cases.flatMap((item) => results.get(item.id)?.lines ?? []);
  const failed = cases.filter((item) => !results.get(item.id)?.ok);
  console.log(
    `${cases.length - failed.length}/${cases.length} cases validated; ${output.length} lines appended to ${out}`,
  );
  for (const item of failed)
    console.log(
      `FAILED ${item.id}: ${results.get(item.id)?.note ?? "not run"}`,
    );
  if (harness.length)
    console.log(`${harness.length} harness failures: ${harness.join(", ")}`);
  if (loadsOnly)
    for (const item of cases) {
      const line = results
        .get(item.id)
        ?.lines.find((have) => have.modelo === null);
      const reason = line?.reason ?? results.get(item.id)?.note ?? "not run";
      console.log(
        `${item.persona} loads=${line?.loads ? "yes" : "no"} ${reason}`,
      );
    }
  return failed.length === 0 ? 0 : 1;
}

if (
  process.argv[1] &&
  resolve(process.argv[1]) === fileURLToPath(import.meta.url)
) {
  main().then(
    (code) => process.exit(code),
    (error) => {
      stopStarted();
      console.error(error.message);
      process.exit(2);
    },
  );
}
