import type { LogContext, LogLevel, LogRecord } from "../ipc/contract";

// What the log view and the shell both need to know about records, kept out
// of the component's module so that an edit to the view is a hot update and
// not a reload.

export const LEVELS: readonly LogLevel[] = [
  "DEBUG",
  "INFO",
  "WARNING",
  "ERROR",
  "CRITICAL",
];

export type RecordFilters = {
  text: string;
  minLevel: number;
  hiddenSources: string[];
  logger: string | null;
};

export const DEFAULT_FILTERS: RecordFilters = {
  text: "",
  minLevel: 1,
  hiddenSources: [],
  logger: null,
};

export const shortLogger = (logger: string | null) =>
  logger ? logger.split(".").slice(-2).join(".") : "";

export function recordLine(record: LogRecord): string {
  const context = recordContext(record);
  const suffix = Object.keys(context).length
    ? ` | ${JSON.stringify(context)}`
    : "";
  return `${record.timestamp} [${record.level ?? "-"}] ${record.logger ?? record.source}: ${record.message}${suffix}`;
}

export function recordContext(record: LogRecord): LogContext {
  const context = { ...record.context };
  if (record.process) {
    context.process_id = record.process.pid;
    context.process_role = record.process.role;
  }
  return Object.fromEntries(
    Object.entries(context).sort(([a], [b]) => (a < b ? -1 : a > b ? 1 : 0)),
  );
}

export function recordTime(record: LogRecord): string {
  if (record.timestampMs === null) return record.timestamp;
  const at = new Date(record.timestampMs);
  if (Number.isNaN(at.getTime())) return record.timestamp;
  const two = (value: number) => String(value).padStart(2, "0");
  return `${two(at.getHours())}:${two(at.getMinutes())}:${two(at.getSeconds())}.${String(at.getMilliseconds()).padStart(3, "0")}`;
}
