import { useEffect, useMemo, useRef, useState, type MouseEvent } from "react";
import type { LogLevel, LogRecord, LogSourceState } from "../ipc/contract";
import { useMetric } from "../shell/metrics";
import { useStrings } from "../shell/strings";
import { Icon } from "@/components/ui/icon";

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

const rank = (level: LogLevel | null) => (level ? LEVELS.indexOf(level) : 1);
export const shortLogger = (logger: string | null) =>
  logger ? logger.split(".").slice(-2).join(".") : "";

export function recordLine(record: LogRecord): string {
  return `${record.timestamp} [${record.level ?? "-"}] ${record.logger ?? record.source}: ${record.message}`;
}

// Read-only view of the host's log batches. A missing or unreadable source is
// never presented as an empty log, and an unknown source renders by name.
export function RecordList({
  records,
  sourceState,
  dropped,
  filters,
  setFilters,
  onMenu,
  shown,
}: {
  /** null until the host's subscription answers. */
  records: LogRecord[] | null;
  sourceState: LogSourceState | "unavailable" | null;
  dropped: number;
  filters: RecordFilters;
  setFilters: (filters: RecordFilters) => void;
  onMenu: (event: MouseEvent, record: LogRecord, visible: LogRecord[]) => void;
  shown: boolean;
}) {
  const t = useStrings();
  // How close to the end still counts as following the newest record.
  const followSlack = useMetric("--log-follow-slack", 24);
  const list = useRef<HTMLDivElement>(null);
  const [expanded, setExpanded] = useState<ReadonlySet<number>>(new Set());
  const [follow, setFollow] = useState(true);
  const all = useMemo(() => records ?? [], [records]);

  const sources = useMemo(() => {
    const seen = new Set(["python", "host"]);
    for (const record of all) seen.add(record.source);
    return [...seen];
  }, [all]);

  const visible = useMemo(() => {
    const text = filters.text.trim().toLowerCase();
    return all.filter(
      (record) =>
        !filters.hiddenSources.includes(record.source) &&
        rank(record.level) >= filters.minLevel &&
        (!filters.logger || record.logger === filters.logger) &&
        (!text ||
          `${record.logger ?? ""} ${record.message} ${record.detail ?? ""}`
            .toLowerCase()
            .includes(text)),
    );
  }, [all, filters]);

  useEffect(() => {
    if (shown && follow && list.current)
      list.current.scrollTop = list.current.scrollHeight;
  }, [visible, follow, shown]);

  const counts = useMemo(() => {
    let warnings = 0;
    let errors = 0;
    for (const record of all) {
      if (record.level === "WARNING") warnings += 1;
      else if (record.level === "ERROR" || record.level === "CRITICAL")
        errors += 1;
    }
    return { warnings, errors };
  }, [all]);

  const sourceLabel = (source: string) =>
    source === "python"
      ? t("desktop.logs.source_python")
      : source === "host"
        ? t("desktop.logs.source_host")
        : source;
  const state =
    sourceState && sourceState !== "unavailable" ? sourceState : null;

  return (
    <div
      className="logview"
      hidden={!shown}
      role="tabpanel"
      id="panel-logs"
      aria-labelledby="tab-logs"
    >
      <div className="logview-tools">
        <input
          className="filter-text"
          type="search"
          placeholder={t("desktop.logs.filter")}
          aria-label={t("desktop.logs.filter")}
          value={filters.text}
          onChange={(event) =>
            setFilters({ ...filters, text: event.target.value })
          }
        />
        <select
          aria-label={t("desktop.logs.minimum_level")}
          value={filters.minLevel}
          onChange={(event) =>
            setFilters({ ...filters, minLevel: Number(event.target.value) })
          }
        >
          <option value={0}>{t("desktop.logs.level_all")}</option>
          <option value={1}>{t("desktop.logs.level_info")}</option>
          <option value={2}>{t("desktop.logs.level_warning")}</option>
          <option value={3}>{t("desktop.logs.level_error")}</option>
        </select>
        <div
          className="source-toggles"
          role="group"
          aria-label={t("desktop.logs.sources")}
        >
          {sources.map((source) => (
            <button
              key={source}
              className="chip"
              aria-pressed={!filters.hiddenSources.includes(source)}
              onClick={() =>
                setFilters({
                  ...filters,
                  hiddenSources: filters.hiddenSources.includes(source)
                    ? filters.hiddenSources.filter((s) => s !== source)
                    : [...filters.hiddenSources, source],
                })
              }
            >
              {sourceLabel(source)}
            </button>
          ))}
        </div>
        {filters.logger && (
          <button
            className="chip chip-active"
            title={t("desktop.logs.clear_logger")}
            aria-label={t("desktop.logs.clear_logger")}
            onClick={() => setFilters({ ...filters, logger: null })}
          >
            {shortLogger(filters.logger)} <Icon name="close" size="xs" />
          </button>
        )}
        <span className="tools-spacer" />
        {state && (
          <span className={`source-state state-${state.kind}`}>
            {state.kind === "available"
              ? t("desktop.logs.state_available")
              : state.kind === "missing"
                ? t("desktop.logs.state_missing")
                : t("desktop.logs.state_unreadable")}
          </span>
        )}
        {counts.errors > 0 && (
          <span className="count count-error">
            {t("desktop.logs.errors", { count: counts.errors })}
          </span>
        )}
        {counts.warnings > 0 && (
          <span className="count count-warning">
            {t("desktop.logs.warnings", { count: counts.warnings })}
          </span>
        )}
        <button
          className={`chip ${follow ? "chip-active" : ""}`}
          aria-pressed={follow}
          title={t("desktop.logs.follow_hint")}
          onClick={() => {
            setFollow(!follow);
            if (!follow && list.current)
              list.current.scrollTop = list.current.scrollHeight;
          }}
        >
          {t("desktop.logs.follow")}
        </button>
      </div>
      {sourceState === "unavailable" && (
        <div className="source-banner state-unavailable" role="status">
          {t("desktop.host.unavailable")}
        </div>
      )}
      {state?.kind === "missing" && (
        <div className="source-banner state-missing" role="status">
          {t("desktop.logs.state_missing_detail")}
        </div>
      )}
      {state?.kind === "unreadable" && (
        <div className="source-banner state-unreadable" role="status">
          {state.detail
            ? `${t("desktop.logs.state_unreadable")}: ${state.detail}`
            : t("desktop.logs.state_unreadable")}
        </div>
      )}
      <div
        className="logview-list"
        ref={list}
        role="log"
        aria-live="off"
        onScroll={() => {
          const el = list.current;
          if (!el) return;
          const atEnd =
            el.scrollHeight - el.scrollTop - el.clientHeight < followSlack;
          if (atEnd !== follow) setFollow(atEnd);
        }}
      >
        {dropped > 0 && (
          <div className="logview-note">
            {t("desktop.logs.dropped", { count: dropped })}
          </div>
        )}
        {state?.kind === "available" && visible.length === 0 && (
          <div className="logview-note">
            {all.length ? t("desktop.logs.no_match") : t("desktop.logs.empty")}
          </div>
        )}
        {visible.map((record) => {
          const open = expanded.has(record.seq);
          return (
            <div
              key={record.seq}
              className={`record level-${(record.level ?? "none").toLowerCase()} source-${record.source}`}
              onContextMenu={(event) => {
                event.preventDefault();
                onMenu(event, record, visible);
              }}
            >
              <div
                className="record-line"
                onClick={() => {
                  if (!record.detail) return;
                  const next = new Set(expanded);
                  if (open) next.delete(record.seq);
                  else next.add(record.seq);
                  setExpanded(next);
                }}
              >
                <time>
                  {record.timestamp.slice(11, 23) || record.timestamp}
                </time>
                <span className="level">
                  {record.source === "host"
                    ? sourceLabel("host")
                    : (record.level ?? "—")}
                </span>
                <span className="logger" title={record.logger ?? ""}>
                  {record.logger
                    ? shortLogger(record.logger)
                    : sourceLabel(record.source)}
                </span>
                <span className="message">
                  {record.message}
                  {record.detail && (
                    <span className="detail-toggle">{open ? " ▾" : " ▸"}</span>
                  )}
                </span>
              </div>
              {open && <pre className="detail">{record.detail}</pre>}
            </div>
          );
        })}
      </div>
    </div>
  );
}
