// Deterministic log records for the scenario host: every level, both known
// sources, one source the shell does not name, a record with continuation
// lines and one long message. All values are synthetic.

import type { LogLevel, LogRecord, LogSourceState } from "../../ipc/contract";

export const FIXTURE_LOG_FILE = "<storage>/logs/cadrumo.log";

export const AVAILABLE: LogSourceState = {
  kind: "available",
  detail: FIXTURE_LOG_FILE,
  failure: null,
};

export const MISSING: LogSourceState = {
  kind: "missing",
  detail: FIXTURE_LOG_FILE,
  failure: null,
};

export const UNREADABLE: LogSourceState = {
  kind: "unreadable",
  detail: FIXTURE_LOG_FILE,
  failure: {
    code: "read_failed",
    operation: "logging",
    message: "The log file could not be read.",
  },
};

const START_MS = Date.UTC(2026, 2, 2, 9, 14, 5, 120);

function python(
  seq: number,
  offsetMs: number,
  level: LogLevel,
  logger: string,
  message: string,
  detail: string | null = null,
): LogRecord {
  const at = new Date(START_MS + offsetMs);
  const two = (value: number) => String(value).padStart(2, "0");
  const timestamp =
    `${at.getUTCFullYear()}-${two(at.getUTCMonth() + 1)}-${two(at.getUTCDate())} ` +
    `${two(at.getUTCHours())}:${two(at.getUTCMinutes())}:${two(at.getUTCSeconds())},` +
    String(at.getUTCMilliseconds()).padStart(3, "0");
  return {
    seq,
    source: "python",
    timestamp,
    timestampMs: null,
    level,
    logger,
    message,
    detail,
    process: null,
  };
}

function host(
  seq: number,
  offsetMs: number,
  level: LogLevel,
  message: string,
  role: "tui" | "repl" | "console",
  pid: number,
): LogRecord {
  const timestampMs = START_MS + offsetMs;
  return {
    seq,
    source: "host",
    timestamp: new Date(timestampMs).toISOString(),
    timestampMs,
    level,
    logger: null,
    message,
    detail: null,
    process: { role, pid },
  };
}

const TRACEBACK = [
  "Traceback (most recent call last):",
  '  File "cadrumo/application/example.py", line 42, in run',
  "    result = step(value)",
  '  File "cadrumo/application/example.py", line 17, in step',
  '    raise ValueError("fixture failure")',
  "ValueError: fixture failure",
].join("\n");

export const FIXTURE_RECORDS: readonly LogRecord[] = [
  host(1, 0, "INFO", "host_started", "console", 4120),
  host(2, 40, "INFO", "child_started", "console", 4188),
  host(3, 95, "INFO", "child_started", "repl", 4204),
  python(4, 1300, "INFO", "cadrumo.entrypoints.tui.app", "Workbench ready"),
  python(
    5,
    1420,
    "DEBUG",
    "cadrumo.application.state_projection",
    "Projection refreshed in 18 ms",
  ),
  python(
    6,
    2210,
    "INFO",
    "cadrumo.application.overview.calendar",
    "Calendar projection admitted 6 obligations",
  ),
  python(
    7,
    3050,
    "WARNING",
    "cadrumo.application.aeat_sync.workspace_reader",
    "Remote observations were never captured for this profile",
  ),
  {
    seq: 8,
    source: "manager",
    timestamp: new Date(START_MS + 3400).toISOString(),
    timestampMs: START_MS + 3400,
    level: "INFO",
    logger: null,
    message: "A source this shell does not name still renders by its name",
    detail: null,
    process: null,
  },
  python(
    9,
    4125,
    "ERROR",
    "cadrumo.application.example",
    "Step failed and was not retried",
    TRACEBACK,
  ),
  python(
    10,
    4630,
    "INFO",
    "cadrumo.core.logging",
    "A long message wraps inside its column instead of widening the list: " +
      "identifier-with-no-break-opportunity-".repeat(4) +
      "end",
  ),
  host(11, 5200, "WARNING", "child_exited", "repl", 4204),
  python(
    12,
    6010,
    "CRITICAL",
    "cadrumo.application.operations",
    "Operation settled as UNKNOWN after an ambiguous interruption",
  ),
  python(13, 6900, "INFO", "cadrumo.entrypoints.tui.app", "Idle"),
  {
    seq: 14,
    source: "python",
    timestamp: "",
    timestampMs: null,
    level: null,
    logger: null,
    message: "A line the format did not match: no timestamp, level or logger",
    detail: null,
    process: null,
  },
];

/** Records the fixture reports as lost to ring overflow before delivery. */
export const FIXTURE_DROPPED = 3;

const BATCH_LIMIT = 5000;
const GENERATED_LEVELS: readonly LogLevel[] = [
  "INFO",
  "INFO",
  "DEBUG",
  "INFO",
  "WARNING",
  "INFO",
  "ERROR",
];

/**
 * A log of `count` generated records, in batches no larger than the host
 * sends, for measuring the log view under the load the contract allows.
 */
export function generatedBatches(
  count: number,
): { records: LogRecord[]; dropped: number; state: LogSourceState }[] {
  const batches = [];
  for (let start = 0; start < count; start += BATCH_LIMIT) {
    const records: LogRecord[] = [];
    for (let at = start; at < Math.min(count, start + BATCH_LIMIT); at++) {
      const level = GENERATED_LEVELS[at % GENERATED_LEVELS.length] ?? "INFO";
      records.push(
        python(
          at + 1,
          at * 37,
          level,
          `cadrumo.generated.module_${at % 23}`,
          `Generated record ${at + 1} of ${count} for the log view measurement`,
          level === "ERROR" ? TRACEBACK : null,
        ),
      );
    }
    batches.push({ records, dropped: 0, state: AVAILABLE });
  }
  return batches;
}
