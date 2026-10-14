import { memo, type MouseEvent } from "react";
import { Button } from "@/components/ui/button";
import { cn } from "@/components/ui/cn";
import { Icon } from "@/components/ui/icon";
import type { LogLevel, LogRecord } from "@/ipc/contract";
import { recordContext, recordTime, shortLogger } from "@/shell/records";

const LEVEL_TONE: Partial<Record<LogLevel, string>> = {
  WARNING: "text-warning",
  ERROR: "text-destructive",
  CRITICAL: "text-destructive",
};

// One record. Memoized, so a new batch renders only its own rows: the list
// holds thousands, and a batch arrives up to ten times a second.
export const RecordRow = memo(function RecordRow({
  record,
  open,
  current,
  tabStop,
  sourceLabel,
  detailsLabel,
  onToggle,
  onCurrent,
  onMenu,
}: {
  record: LogRecord;
  open: boolean;
  /** The row the keyboard is on, or the one its menu was opened for. */
  current: boolean;
  /** The one row Tab lands on; the arrow keys reach the others. */
  tabStop: boolean;
  /** The name of the record's source, in the chrome language. */
  sourceLabel: string;
  detailsLabel: string;
  onToggle: (seq: number) => void;
  onCurrent: (seq: number) => void;
  onMenu: (event: MouseEvent<HTMLElement>, record: LogRecord) => void;
}) {
  const level = (record.level ?? "none").toLowerCase();
  const failed = record.level === "ERROR" || record.level === "CRITICAL";
  const context = recordContext(record);
  const hasContext = Object.keys(context).length > 0;
  const hasDetails = !!record.detail || hasContext;
  const summary = [
    context.stage,
    context.startup_phase,
    context.phase,
    context.outcome,
    context.reason_code,
    context.lifecycle_reason,
    context.service_reason,
    context.service_cause,
    context.service_scope,
    typeof context.total_ms === "number" ? `${context.total_ms} ms` : null,
    typeof context.restart_delay_ms === "number" ? `retry ${context.restart_delay_ms} ms` : null,
  ]
    .filter((value): value is string => typeof value === "string")
    .join(" · ");
  return (
    <div
      className={cn(
        `record level-${level} source-${record.source}`,
        // The current row carries an ink bar as well as the hover wash: its
        // faint text has no contrast to spare for a stronger surface.
        "border-l-(length:--selection-edge) hover:bg-accent focus-visible:-outline-offset-2 aria-[current=true]:border-ring aria-[current=true]:bg-accent",
        failed ? "border-destructive" : "border-transparent",
      )}
      data-seq={record.seq}
      aria-current={current || undefined}
      tabIndex={tabStop ? 0 : -1}
      onFocus={() => onCurrent(record.seq)}
      onContextMenu={(event) => {
        event.preventDefault();
        onMenu(event, record);
      }}
    >
      <div className="grid log-record-grid gap-x-3 px-3 py-px @max-xl:log-record-grid-compact">
        <time
          className="text-muted-foreground"
          dateTime={record.timestampMs === null ? undefined : record.timestamp}
          title={record.timestamp}
        >
          {recordTime(record)}
        </time>
        <span
          className={cn(
            "font-semibold tracking-wide",
            (record.level && LEVEL_TONE[record.level]) ||
              "text-muted-foreground",
          )}
        >
          {/* A level is said in words wherever there is one; a host line
              without one says where it came from instead. */}
          {record.level ?? (record.source === "host" ? sourceLabel : "—")}
        </span>
        <span
          className="truncate text-muted-foreground @max-xl:hidden"
          title={record.logger ?? undefined}
        >
          {record.logger
            ? shortLogger(record.logger)
            : record.level || record.source !== "host"
              ? sourceLabel
              : ""}
        </span>
        <span
          className={cn(
            "min-w-0 wrap-anywhere @max-xl:col-span-3",
            record.level === "DEBUG" && "text-muted-foreground",
          )}
        >
          {record.message}
          {hasDetails && (
            <Button
              variant="ghost"
              size="icon-xs"
              className="-my-1 ml-1 align-middle"
              // Reached from its row, by Enter: the log stays one tab stop.
              tabIndex={-1}
              aria-expanded={open}
              aria-label={detailsLabel}
              onClick={() => onToggle(record.seq)}
            >
              <Icon
                name="forward"
                size="xs"
                className={cn("transition-transform", open && "rotate-90")}
              />
            </Button>
          )}
          {(record.process ||
            summary ||
            typeof context.diagnostic_id === "string") && (
            <span className="ml-2 inline-flex flex-wrap gap-x-2 text-xs text-muted-foreground">
              {record.process && (
                <span className="record-process">
                  {record.process.role}:{record.process.pid}
                </span>
              )}
              {summary && (
                <span className="record-context-summary" title={summary}>
                  {summary}
                </span>
              )}
              {typeof context.diagnostic_id === "string" && (
                <span
                  className="record-correlation max-w-field truncate"
                  title={context.diagnostic_id}
                >
                  {context.diagnostic_id}
                </span>
              )}
            </span>
          )}
        </span>
      </div>
      {open && (
        <pre className="mx-3 mt-0.5 mb-1.5 overflow-x-auto rounded-md bg-accent px-2.5 py-1.5 text-xs whitespace-pre-wrap text-muted-foreground">
          {record.detail}
          {record.detail && hasContext && "\n\n"}
          {hasContext && JSON.stringify(context, null, 2)}
        </pre>
      )}
    </div>
  );
});
