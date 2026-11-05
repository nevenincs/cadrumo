// The product-log gate of the packaged runs: after the product has run, the
// logs it wrote under its storage root are read and any ERROR, CRITICAL, gated
// WARNING, malformed line or stall dump that no authored fault test explains
// fails the run. Nothing here launches or mocks the product.
import { createHash } from "node:crypto";
import { existsSync, readFileSync, readdirSync, statSync } from "node:fs";
import { basename, resolve } from "node:path";

import { FAIL, PASS } from "./verdicts.mjs";

export const LEVELS = ["DEBUG", "INFO", "WARNING", "ERROR", "CRITICAL"];

/** Loggers whose WARNING records fail the run; widen one logger at a time. */
export const GATED_WARNING_PREFIXES = [
  "cadrumo_agent.control.",
  "cadrumo_agent_service.",
  "cadrumo_runtime.host.",
  "cadrumo.adapters.persistence.storage.custody.",
  "cadrumo.core.logging",
  "cadrumo.core.log_file_handler",
  "cadrumo.application.cli_provisioning",
];

const AGENT_SCHEMA = "cadrumo-agent.log/1";
const STARTUP_OUTCOMES_LOG = "cadrumo-startup-outcomes.jsonl";
const MANAGER_LOG = "cadrumo-manager.log";
const NATIVE_LOG = "cadrumo-native.jsonl";
const STALL_DUMP = /^profile-worker-stall-.+\.txt$/;
// These two sets mirror the host's startup Outcome enum (startup_outcome.rs).
export const STARTUP_NORMAL_OUTCOMES = ["handed_off", "open_in_other_session"];
export const STARTUP_FAILURE_OUTCOMES = ["timed_out", "refused"];
const WINDOW_GRACE_MS = 2000;
const GROUP_LIMIT = 200;
const DETAIL_GROUPS = 5;
const TOKEN = {
  asctime: String.raw`(\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}\.\d{3}Z)`,
  levelname: `(${LEVELS.join("|")})`,
  name: String.raw`([A-Za-z_][\w.\-]*)`,
};

const escapeLiteral = (text) => text.replace(/[.*+?^${}()|[\]\\]/g, "\\$&");

/**
 * Turns the contract's `desktop_defaults.log_format` into a header matcher and
 * the separator that precedes the diagnostic context.
 */
export function compileLineFormat(format) {
  const tokens = [...String(format).matchAll(/%\((\w+)\)s/g)];
  const names = tokens.map((token) => token[1]);
  const expected = [
    "asctime",
    "levelname",
    "name",
    "message",
    "diagnostic_context",
  ];
  if (names.join() !== expected.join())
    throw new Error(`unsupported log format: ${format}`);
  const messageAt = tokens[3].index;
  const contextAt = tokens[4].index;
  const separator = format.slice(messageAt + tokens[3][0].length, contextAt);
  if (format.slice(contextAt + tokens[4][0].length) !== "" || !separator)
    throw new Error(`unsupported log format: ${format}`);
  let pattern = "^";
  let cursor = 0;
  for (const token of tokens.slice(0, 3)) {
    pattern +=
      escapeLiteral(format.slice(cursor, token.index)) + TOKEN[token[1]];
    cursor = token.index + token[0].length;
  }
  pattern += escapeLiteral(format.slice(cursor, messageAt)) + "(.*)$";
  return { header: new RegExp(pattern), separator };
}

function splitContext(rest, separator) {
  let at = rest.lastIndexOf(separator);
  while (at >= 0) {
    try {
      const context = JSON.parse(rest.slice(at + separator.length));
      if (context && typeof context === "object" && !Array.isArray(context))
        return { message: rest.slice(0, at), context };
    } catch {
      // Not the context; an earlier separator may be.
    }
    if (at === 0) break;
    at = rest.lastIndexOf(separator, at - 1);
  }
  return { message: rest, context: null };
}

/**
 * Parses one diagnostic log. A header line starts a record; every other line
 * continues it, and a continuation before any header is an orphan.
 */
export function parseDiagnosticLog(text, compiled) {
  const records = [];
  const orphans = [];
  let current = null;
  const lines = String(text).split(/\r?\n/);
  lines.forEach((line, index) => {
    const header = compiled.header.exec(line);
    if (header) {
      const { message, context } = splitContext(header[4], compiled.separator);
      current = {
        level: header[2],
        logger: header[3],
        timeMs: Date.parse(header[1]),
        timeText: header[1],
        message,
        context,
        line: index + 1,
        continuation: [],
      };
      records.push(current);
    } else if (line.trim() === "") {
      // Blank lines carry nothing.
    } else if (current) current.continuation.push(line);
    else orphans.push({ line: index + 1 });
  });
  return { records, orphans };
}

/** Digits, hex runs, sha256 tokens and Windows paths become placeholders. */
export function normalizeMessage(text) {
  return String(text)
    .replace(/sha256:[0-9a-f]+(?:-sha256:[0-9a-f]+)*/gi, "<n>")
    .replace(/[A-Za-z]:\\[^\s|;,)]*/g, "<path>")
    .replace(/<storage>[^\s|;,)]*/g, "<path>")
    .replace(/\b[0-9a-f]{8,}\b/gi, "<n>")
    .replace(/\d+(?:\.\d+)?/g, "<n>");
}

const digest = (text) =>
  createHash("sha256").update(String(text)).digest("hex").slice(0, 16);

function readText(path) {
  return readFileSync(path, "utf8");
}

function listFiles(directory, accept) {
  try {
    return readdirSync(directory)
      .filter(accept)
      .sort()
      .map((name) => resolve(directory, name));
  } catch {
    return [];
  }
}

/** Rotated siblings of a base log, `<base>.1` … `<base>.N`. */
function rotations(directory, base) {
  const pattern = new RegExp(`^${escapeLiteral(base)}(\\.\\d+)?$`);
  return listFiles(directory, (name) => pattern.test(name));
}

/**
 * Every concrete file of the storage root's log directory that the gate reads
 * outside the agent tree: the primary log, the startup outcomes and the
 * manager log with their rotations, the native record and the stall dumps.
 * The gate and the evidence capture share this one listing.
 */
export function gatedLogFiles(storage, defaults) {
  const logs = resolve(storage, defaults.logs);
  const native = resolve(logs, NATIVE_LOG);
  return [
    ...rotations(logs, basename(defaults.log_file)),
    ...rotations(logs, STARTUP_OUTCOMES_LOG),
    ...rotations(logs, MANAGER_LOG),
    ...(existsSync(native) ? [native] : []),
    ...listFiles(logs, (name) => STALL_DUMP.test(name)),
  ];
}

function agentRecord(source, line) {
  let value;
  try {
    value = JSON.parse(line);
  } catch {
    return null;
  }
  if (!value || value.schema !== AGENT_SCHEMA) return null;
  if (!LEVELS.includes(value.level)) return null;
  return {
    level: value.level,
    logger: String(value.name ?? ""),
    timeMs: Date.parse(value.timestamp),
    pid: value.pid,
    messageHash: digest(value.message),
    hasException: Boolean(value.exception),
    source,
  };
}

export const AGENT_STRUCTURED_LOGS = ["gateway.log", "worker.log"];
export const AGENT_STDERR_LOG =
  /^(conversation-worker-.+|worker-autospawn-.+)\.stderr\.log$/;

/**
 * The agent logs under `<storage>/agent/<hash>/home/runtime/`, grouped by
 * agent root. The gate and the evidence capture share this one discovery.
 */
export function agentLogGroups(storage) {
  return listFiles(resolve(storage, "agent"), () => true).map((root) => {
    const runtime = resolve(root, "home", "runtime");
    return {
      root,
      runtime,
      structured: listFiles(runtime, (name) =>
        AGENT_STRUCTURED_LOGS.includes(name),
      ),
      stderr: listFiles(runtime, (name) => AGENT_STDERR_LOG.test(name)),
    };
  });
}

const RAW_STDERR_ERROR = /^(ERROR|CRITICAL) cadrumo_agent[\w.]*:/;
const RAW_TRACEBACK = /^Traceback \(most recent call last\)/;

/**
 * Reads the storage root's logs into findings candidates. A missing primary
 * log is itself a finding: a blind gate cannot report clean.
 */
export function readProductLogs({ storage, defaults }) {
  const compiled = compileLineFormat(defaults.log_format);
  const logs = resolve(storage, defaults.logs);
  const primary = basename(defaults.log_file);
  const records = [];
  const problems = [];
  const sources = [];
  const relayed = new Set();

  const pythonFiles = [
    ...rotations(logs, primary),
    ...rotations(logs, MANAGER_LOG),
  ];
  if (!existsSync(resolve(logs, primary)))
    problems.push({
      level: "ERROR",
      source: "python",
      logger: "product-log.sources",
      template: `missing ${primary}`,
      timeMs: null,
    });
  for (const file of pythonFiles) {
    sources.push(basename(file));
    const { records: parsed, orphans } = parseDiagnosticLog(
      readText(file),
      compiled,
    );
    for (const record of parsed) {
      records.push({ ...record, source: "python" });
      if (record.context && record.context.process_id !== undefined)
        relayed.add(
          [
            record.level,
            record.logger,
            record.context.process_id,
            record.timeMs,
          ].join("|"),
        );
    }
    for (const orphan of orphans)
      problems.push({
        level: "ERROR",
        source: "python",
        logger: "product-log.unparsed",
        template: `unparsed continuation line before any header in ${basename(file)}`,
        timeMs: null,
        line: orphan.line,
      });
  }

  for (const { structured, stderr } of agentLogGroups(storage)) {
    for (const file of [...structured, ...stderr]) {
      sources.push(`agent/${basename(file)}`);
      const strict = structured.includes(file);
      let malformed = 0;
      for (const line of readText(file).split(/\r?\n/)) {
        if (line.trim() === "") continue;
        const record = agentRecord("agent", line);
        if (record) {
          const key = [
            record.level,
            record.logger,
            record.pid,
            record.timeMs,
          ].join("|");
          if (!relayed.has(key)) records.push(record);
        } else if (strict) malformed += 1;
        else if (RAW_STDERR_ERROR.test(line) || RAW_TRACEBACK.test(line))
          problems.push({
            level: "ERROR",
            source: "agent",
            logger: "agent.stderr",
            template: RAW_TRACEBACK.test(line)
              ? "traceback in worker stderr"
              : `error line in worker stderr sha256:${digest(normalizeMessage(line))}`,
            timeMs: null,
          });
      }
      if (malformed)
        problems.push({
          level: "ERROR",
          source: "agent",
          logger: "product-log.malformed",
          template: `${malformed} line(s) of ${basename(file)} are not ${AGENT_SCHEMA} records`,
          timeMs: null,
        });
    }
  }

  for (const file of rotations(logs, STARTUP_OUTCOMES_LOG)) {
    sources.push(basename(file));
    let malformed = 0;
    for (const line of readText(file).split(/\r?\n/)) {
      if (line.trim() === "") continue;
      let value;
      try {
        value = JSON.parse(line);
      } catch {
        malformed += 1;
        continue;
      }
      const known = [...STARTUP_NORMAL_OUTCOMES, ...STARTUP_FAILURE_OUTCOMES];
      if (
        !value ||
        value.schema !== 1 ||
        value.event !== "startup_outcome" ||
        !known.includes(value.outcome)
      ) {
        malformed += 1;
        continue;
      }
      if (STARTUP_FAILURE_OUTCOMES.includes(value.outcome))
        problems.push({
          level: "ERROR",
          source: "native",
          logger: "desktop.startup_outcome",
          template: `startup outcome=${value.outcome} reason=${value.reason ?? "-"} stage=${value.stage}`,
          timeMs: value.timestampMs,
        });
    }
    if (malformed)
      problems.push({
        level: "ERROR",
        source: "native",
        logger: "product-log.malformed",
        template: `${malformed} line(s) of ${basename(file)} are not startup_outcome records`,
        timeMs: null,
      });
  }

  const native = resolve(logs, NATIVE_LOG);
  if (existsSync(native)) {
    sources.push(basename(native));
    let malformed = 0;
    for (const line of readText(native).split(/\r?\n/)) {
      if (line.trim() === "") continue;
      let value;
      try {
        value = JSON.parse(line);
      } catch {
        malformed += 1;
        continue;
      }
      if (value.kind === "failure") {
        const causes = (value.failure?.causes ?? [])
          .map((cause) => cause?.reason ?? cause?.code)
          .filter(Boolean);
        problems.push({
          level: "ERROR",
          source: "native",
          logger: "desktop.failure",
          template: `failure code=${value.failure?.code} reason=${value.failure?.reason} causes=${causes.join(",")}`,
          native: {
            kind: "failure",
            code: String(value.failure?.code),
            reason: String(value.failure?.reason),
            cause_reason: causes.join(","),
          },
          timeMs: value.timestampMs,
        });
      } else if (value.desktopDiagnostic?.level === "ERROR") {
        const d = value.desktopDiagnostic;
        problems.push({
          level: "ERROR",
          source: "native",
          logger: `desktop.${d.origin}`,
          template: `${d.event} command=${d.command ?? "-"} code=${d.code ?? "-"}`,
          timeMs: value.timestampMs,
        });
      }
    }
    if (malformed)
      problems.push({
        level: "ERROR",
        source: "native",
        logger: "product-log.malformed",
        template: `${malformed} line(s) of ${basename(native)} are not JSON`,
        timeMs: null,
      });
  }

  for (const dump of listFiles(logs, (name) => STALL_DUMP.test(name))) {
    sources.push(basename(dump));
    if (statSync(dump).size > 0)
      problems.push({
        level: "ERROR",
        source: "python",
        logger: "profile_worker.stall",
        template: "non-empty profile worker stall dump",
        timeMs: null,
      });
  }
  return { records, problems, sources };
}

function gatedWarning(logger) {
  return GATED_WARNING_PREFIXES.some((prefix) =>
    prefix.endsWith(".")
      ? logger.startsWith(prefix)
      : logger === prefix || logger.startsWith(`${prefix}.`),
  );
}

const ENTRY_FIELDS = [
  "id",
  "source",
  "level",
  "logger",
  "message",
  "native",
  "context_fields",
  "context_patterns",
  "fault_test",
  "runs",
  "max_count",
  "justification",
];

/**
 * Structural problems of an allow-list; an empty array means it is valid.
 * An entry can excuse only a named WARNING of one logger inside one fault
 * test. Errors and native records are never excusable.
 */
export function allowlistProblems(entries) {
  if (!Array.isArray(entries)) return ["the allow-list is not an array"];
  const problems = [];
  const ids = new Set();
  entries.forEach((entry, index) => {
    const at = `entry ${entry?.id ?? index}`;
    if (!entry || typeof entry !== "object")
      return problems.push(`${at} is not an object`);
    for (const key of Object.keys(entry))
      if (!ENTRY_FIELDS.includes(key))
        problems.push(`${at} has unknown field ${key}`);
    if (typeof entry.id !== "string" || !/^[a-z0-9-]+$/.test(entry.id))
      problems.push(`${at} needs a kebab-case id`);
    else if (ids.has(entry.id)) problems.push(`${at} repeats an id`);
    else ids.add(entry.id);
    const native = entry.source === "native";
    if (!["python", "agent", "native"].includes(entry.source))
      problems.push(`${at} source must be python, agent or native`);
    if (native) {
      if (entry.level !== "ERROR")
        problems.push(`${at} a native entry must be level ERROR`);
      if (entry.logger !== "desktop.failure")
        problems.push(
          `${at} a native entry covers only desktop.failure records`,
        );
      const tuple = entry.native;
      const keys = ["kind", "code", "reason", "cause_reason"];
      if (
        !tuple ||
        typeof tuple !== "object" ||
        Object.keys(tuple).sort().join() !== [...keys].sort().join() ||
        keys.some((key) => typeof tuple[key] !== "string" || tuple[key] === "")
      )
        problems.push(
          `${at} a native entry needs the full tuple {kind, code, reason, cause_reason}`,
        );
      if (entry.message !== undefined)
        problems.push(
          `${at} a native entry is keyed on its tuple, not a message`,
        );
      if (JSON.stringify(entry.runs) !== '["setup"]')
        problems.push(`${at} a native entry runs in setup only`);
      if (entry.max_count !== 1)
        problems.push(`${at} a native entry allows exactly one record`);
      if (entry.fault_test?.require_verdict !== "PASS")
        problems.push(
          `${at} a native entry needs its fault test to have passed`,
        );
    } else {
      if (entry.level !== "WARNING")
        problems.push(
          `${at} level must be WARNING; ERROR and CRITICAL are never allow-listed`,
        );
      if (entry.native !== undefined)
        problems.push(`${at} only a native entry carries a native tuple`);
      if (
        typeof entry.message !== "string" ||
        !entry.message.startsWith("^") ||
        !entry.message.endsWith("$")
      )
        problems.push(`${at} message must be an anchored regex`);
      else {
        if (/(^|[^\\])\.[*+]/.test(entry.message))
          problems.push(`${at} message must not use a wildcard run`);
        try {
          new RegExp(entry.message);
        } catch {
          problems.push(`${at} message is not a valid regex`);
        }
      }
    }
    if (
      typeof entry.logger !== "string" ||
      !/^[A-Za-z_][\w.]*$/.test(entry.logger)
    )
      problems.push(`${at} needs an exact logger name`);
    for (const field of ["context_fields", "context_patterns"])
      if (
        entry[field] !== undefined &&
        (!entry[field] ||
          typeof entry[field] !== "object" ||
          Array.isArray(entry[field]))
      )
        problems.push(`${at} ${field} must be an object`);
    for (const [key, pattern] of Object.entries(entry.context_patterns ?? {}))
      if (
        typeof pattern !== "string" ||
        !pattern.startsWith("^") ||
        !pattern.endsWith("$")
      )
        problems.push(`${at} context pattern ${key} must be anchored`);
    const fault = entry.fault_test;
    if (
      !fault ||
      typeof fault.check !== "string" ||
      typeof fault.source !== "string" ||
      (fault.phase !== undefined && typeof fault.phase !== "string") ||
      (fault.require_verdict !== undefined && fault.require_verdict !== "PASS")
    )
      problems.push(`${at} needs fault_test {check, source, phase?}`);
    if (
      !Array.isArray(entry.runs) ||
      entry.runs.length === 0 ||
      entry.runs.some((run) => !["setup", "window"].includes(run))
    )
      problems.push(`${at} runs must list setup and/or window`);
    if (!Number.isInteger(entry.max_count) || entry.max_count < 1)
      problems.push(`${at} max_count must be a positive integer`);
    if (
      typeof entry.justification !== "string" ||
      entry.justification.length < 40
    )
      problems.push(`${at} needs a justification of at least 40 characters`);
  });
  return problems;
}

export function loadAllowlist(path) {
  const entries = JSON.parse(readFileSync(path, "utf8"));
  const problems = allowlistProblems(entries);
  if (problems.length)
    throw new Error(`invalid allow-list: ${problems.join("; ")}`);
  return entries;
}

/** The time window an entry's fault test recorded, or null when it did not run. */
function faultWindow(entry, checks) {
  const check = checks.find(
    (candidate) => candidate.id === entry.fault_test.check,
  );
  if (!check) return null;
  if (
    entry.fault_test.require_verdict &&
    check.verdict !== entry.fault_test.require_verdict
  )
    return null;
  const span = entry.fault_test.phase
    ? check.phases?.find((phase) => phase.phase === entry.fault_test.phase)
    : check;
  if (!span) return null;
  const start = Date.parse(span.startedAt);
  if (!Number.isFinite(start) || !Number.isFinite(span.elapsedMs)) return null;
  return [start - WINDOW_GRACE_MS, start + span.elapsedMs + WINDOW_GRACE_MS];
}

function entryMatches(entry, record, normalized, window) {
  if (entry.source !== record.source || entry.level !== record.level)
    return false;
  if (entry.logger !== record.logger) return false;
  if (!window || !Number.isFinite(record.timeMs)) return false;
  if (record.timeMs < window[0] || record.timeMs > window[1]) return false;
  if (entry.source === "native") {
    for (const [key, value] of Object.entries(entry.native))
      if (record.native?.[key] !== value) return false;
    return true;
  }
  if (!new RegExp(entry.message).test(normalized)) return false;
  const context = record.context ?? {};
  for (const [key, value] of Object.entries(entry.context_fields ?? {}))
    if (String(context[key]) !== String(value)) return false;
  for (const [key, pattern] of Object.entries(entry.context_patterns ?? {}))
    if (
      context[key] === undefined ||
      !new RegExp(pattern).test(normalizeMessage(String(context[key])))
    )
      return false;
  return true;
}

function iso(timeMs) {
  return Number.isFinite(timeMs) ? new Date(timeMs).toISOString() : null;
}

/**
 * The gate: reads the storage root's logs, classifies each record and fails
 * when any group is unexpected. `checks` are the run's recorded checks as
 * `{id, startedAt, elapsedMs, phases?: [{phase, startedAt, elapsedMs}]}`.
 */
export function productLogVerdict({
  storage,
  defaults,
  checks,
  allowlist,
  run = "setup",
}) {
  let read;
  try {
    read = readProductLogs({ storage, defaults });
  } catch (error) {
    return {
      verdict: FAIL,
      detail: `the product logs could not be read: ${error.message}`,
    };
  }
  const entries = allowlist.filter((entry) => entry.runs.includes(run));
  const windows = new Map(
    entries.map((entry) => [entry.id, faultWindow(entry, checks)]),
  );
  const used = new Map(entries.map((entry) => [entry.id, 0]));
  const groups = new Map();
  const add = (disposition, item, template, entryId) => {
    const key = [
      disposition,
      item.source,
      item.level,
      item.logger,
      template,
      entryId ?? "",
    ].join("\u0000");
    const group = groups.get(key) ?? {
      disposition,
      source: item.source,
      level: item.level,
      logger: item.logger,
      template,
      ...(entryId && { entry: entryId }),
      count: 0,
      first: null,
      last: null,
    };
    group.count += 1;
    const at = iso(item.timeMs);
    if (at && (!group.first || at < group.first)) group.first = at;
    if (at && (!group.last || at > group.last)) group.last = at;
    groups.set(key, group);
  };

  for (const problem of read.problems) {
    const match = problem.native
      ? entries.find(
          (entry) =>
            used.get(entry.id) < entry.max_count &&
            entryMatches(
              entry,
              problem,
              problem.template,
              windows.get(entry.id),
            ),
        )
      : undefined;
    if (match) {
      used.set(match.id, used.get(match.id) + 1);
      add("allowed", problem, problem.template, match.id);
    } else add("unexpected", problem, problem.template);
  }
  for (const record of read.records) {
    const gated =
      record.level === "ERROR" ||
      record.level === "CRITICAL" ||
      (record.level === "WARNING" && gatedWarning(record.logger));
    const python = record.source === "python";
    const template = python
      ? normalizeMessage(record.message)
      : `sha256:${record.messageHash}`;
    if (!gated) {
      if (record.level === "WARNING") add("observed", record, template);
      continue;
    }
    const match = python
      ? entries.find(
          (entry) =>
            used.get(entry.id) < entry.max_count &&
            entryMatches(entry, record, template, windows.get(entry.id)),
        )
      : undefined;
    if (match) {
      used.set(match.id, used.get(match.id) + 1);
      add("allowed", record, template, match.id);
    } else add("unexpected", record, template);
  }

  const ordered = [...groups.values()].sort(
    (a, b) =>
      (a.disposition === "unexpected" ? 0 : 1) -
        (b.disposition === "unexpected" ? 0 : 1) ||
      b.count - a.count ||
      a.template.localeCompare(b.template),
  );
  const unexpected = ordered.filter(
    (group) => group.disposition === "unexpected",
  );
  const data = {
    run,
    sources: read.sources,
    groups: ordered.slice(0, GROUP_LIMIT),
    groupsDropped: Math.max(0, ordered.length - GROUP_LIMIT),
    inactiveEntries: entries
      .filter((entry) => windows.get(entry.id) === null)
      .map((entry) => entry.id),
  };
  if (unexpected.length) {
    const named = unexpected
      .slice(0, DETAIL_GROUPS)
      .map(
        (group) =>
          `${group.level} ${group.logger} x${group.count} "${group.template.slice(0, 120)}"`,
      )
      .join("; ");
    return {
      verdict: FAIL,
      detail: `${unexpected.length} unexplained product-log group(s): ${named}${unexpected.length > DETAIL_GROUPS ? "; …" : ""}`,
      data,
    };
  }
  const observed = ordered.filter(
    (group) => group.disposition === "observed",
  ).length;
  const allowed = ordered.filter(
    (group) => group.disposition === "allowed",
  ).length;
  return {
    verdict: PASS,
    detail: `${read.sources.length} log file(s) read, no unexplained ERROR, CRITICAL or gated WARNING; ${allowed} allowed group(s), ${observed} observed warning group(s)`,
    data,
  };
}

/** The checks a gate needs from a run: ids, windows and the sign-in phase windows. */
export function recordedChecks(checks, phaseWindows = {}) {
  return checks
    .filter(
      (check) => check.startedAt !== undefined && check.elapsedMs !== undefined,
    )
    .map((check) => ({
      id: check.id,
      verdict: check.verdict,
      startedAt: check.startedAt,
      elapsedMs: check.elapsedMs,
      ...(phaseWindows[check.id] && { phases: phaseWindows[check.id] }),
    }));
}

/** Absolute phase windows from the sign-in fixture's relative timings. */
export function phaseWindowsOf(timings) {
  const origin = Date.parse(timings?.originAt);
  if (!Number.isFinite(origin)) return [];
  return (timings.phases ?? []).map((phase) => ({
    phase: phase.phase,
    startedAt: new Date(origin + phase.startedMs).toISOString(),
    elapsedMs: phase.elapsedMs,
  }));
}
