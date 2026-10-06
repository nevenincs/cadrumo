import type { LogLevel, LogRecord } from "../ipc/contract";

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
  return `${record.timestamp} [${record.level ?? "-"}] ${record.logger ?? record.source}: ${record.message}`;
}
