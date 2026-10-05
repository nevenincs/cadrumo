import {
  memo,
  useEffect,
  useMemo,
  useRef,
  useState,
  type MouseEvent,
} from "react";
import { Alert, AlertTitle } from "@/components/ui/alert";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { cn } from "@/components/ui/cn";
import { Icon } from "@/components/ui/icon";
import { Input } from "@/components/ui/input";
import { NativeSelect } from "@/components/ui/native-select";
import type { LogLevel, LogRecord, LogSourceState } from "../ipc/contract";
import { useMetric } from "../shell/metrics";
import { useStrings } from "../shell/strings";

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

// How many of the newest matching records are in the document at once. The
// log holds up to ten thousand; drawing them all costs every scroll and every
// keystroke in the filter. Reaching the top brings in the next span.
const WINDOW = 400;

const LEVEL_TONE: Partial<Record<LogLevel, string>> = {
  WARNING: "text-warning",
  ERROR: "text-destructive",
  CRITICAL: "text-destructive",
};

// One record. Memoized, so a new batch renders only its own rows: the list
// holds thousands, and a batch arrives up to ten times a second.
const Row = memo(function Row({
  record,
  open,
  sourceLabel,
  detailsLabel,
  onToggle,
  onMenu,
}: {
  record: LogRecord;
  open: boolean;
  /** The name of the record's source, in the chrome language. */
  sourceLabel: string;
  detailsLabel: string;
  onToggle: (seq: number) => void;
  onMenu: (event: MouseEvent, record: LogRecord) => void;
}) {
  const level = (record.level ?? "none").toLowerCase();
  const failed = record.level === "ERROR" || record.level === "CRITICAL";
  return (
    <div
      className={cn(
        `record level-${level} source-${record.source}`,
        "border-l-2 hover:bg-accent",
        failed ? "border-destructive" : "border-transparent",
      )}
      onContextMenu={(event) => {
        event.preventDefault();
        onMenu(event, record);
      }}
    >
      <div className="grid grid-cols-[7.5em_5.5em_minmax(8em,16em)_1fr] gap-x-3 px-3 py-px @max-xl:grid-cols-[7.5em_5.5em_1fr]">
        <time className="text-faint">
          {record.timestamp.slice(11, 23) || record.timestamp}
        </time>
        <span
          className={cn(
            "font-semibold tracking-wide",
            record.source === "host"
              ? "text-brand"
              : (record.level && LEVEL_TONE[record.level]) || "text-faint",
          )}
        >
          {record.source === "host" ? sourceLabel : (record.level ?? "—")}
        </span>
        <span
          className="truncate text-muted-foreground @max-xl:hidden"
          title={record.logger ?? undefined}
        >
          {record.logger ? shortLogger(record.logger) : sourceLabel}
        </span>
        <span
          className={cn(
            "min-w-0 wrap-anywhere @max-xl:col-span-3",
            record.level === "DEBUG" && "text-muted-foreground",
          )}
        >
          {record.message}
          {record.detail && (
            <button
              type="button"
              className="ml-1 inline-flex cursor-pointer align-middle text-faint hover:text-foreground"
              aria-expanded={open}
              aria-label={detailsLabel}
              onClick={() => onToggle(record.seq)}
            >
              <Icon
                name="forward"
                size="xs"
                className={cn("transition-transform", open && "rotate-90")}
              />
            </button>
          )}
        </span>
      </div>
      {open && (
        <pre className="mx-3 mt-0.5 mb-1.5 overflow-x-auto rounded-md bg-accent px-2.5 py-1.5 text-xs whitespace-pre-wrap text-muted-foreground">
          {record.detail}
        </pre>
      )}
    </div>
  );
});

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
  const followSlack = useMetric("--log-follow-slack", 24);
  const list = useRef<HTMLDivElement>(null);
  const [expanded, setExpanded] = useState<ReadonlySet<number>>(new Set());
  const [follow, setFollow] = useState(true);
  const [extent, setExtent] = useState(WINDOW);
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

  // The newest `extent` of what matches; the browser's own scroll anchoring
  // keeps the view still when an earlier span is brought in above it.
  const drawn = useMemo(
    () => (visible.length > extent ? visible.slice(-extent) : visible),
    [visible, extent],
  );

  useEffect(() => {
    if (shown && follow && list.current)
      list.current.scrollTop = list.current.scrollHeight;
  }, [drawn, follow, shown]);

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

  // Stable across batches, so memoized rows are not re-rendered by them.
  const live = useRef({ onMenu, visible });
  live.current = { onMenu, visible };
  const handlers = useMemo(
    () => ({
      toggle: (seq: number) =>
        setExpanded((current) => {
          const next = new Set(current);
          if (!next.delete(seq)) next.add(seq);
          return next;
        }),
      menu: (event: MouseEvent, record: LogRecord) =>
        live.current.onMenu(event, record, live.current.visible),
    }),
    [],
  );

  return (
    <div
      className="logview @container flex min-h-0 flex-1 flex-col bg-background"
      hidden={!shown}
      role="tabpanel"
      id="panel-logs"
      aria-labelledby="tab-logs"
    >
      <div className="flex shrink-0 flex-wrap items-center gap-1.5 border-b px-2.5 py-1.5">
        <Input
          className="filter-text w-field max-w-full"
          controlSize="sm"
          type="search"
          placeholder={t("desktop.logs.filter")}
          aria-label={t("desktop.logs.filter")}
          value={filters.text}
          onChange={(event) =>
            setFilters({ ...filters, text: event.target.value })
          }
        />
        <NativeSelect
          controlSize="sm"
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
        </NativeSelect>
        <div
          className="flex gap-1"
          role="group"
          aria-label={t("desktop.logs.sources")}
        >
          {sources.map((source) => (
            <Button
              key={source}
              variant="outline"
              size="sm"
              className="rounded-full"
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
            </Button>
          ))}
        </div>
        {filters.logger && (
          <Button
            variant="outline"
            size="sm"
            className="rounded-full"
            aria-pressed="true"
            aria-label={t("desktop.logs.clear_logger")}
            title={t("desktop.logs.clear_logger")}
            onClick={() => setFilters({ ...filters, logger: null })}
          >
            {shortLogger(filters.logger)}
            <Icon name="close" size="xs" />
          </Button>
        )}
        <span className="flex-1" />
        {state && (
          <span
            className={cn(
              "source-state text-xs",
              `state-${state.kind}`,
              state.kind === "available" ? "text-faint" : "text-warning",
            )}
          >
            {state.kind === "available"
              ? t("desktop.logs.state_available")
              : state.kind === "missing"
                ? t("desktop.logs.state_missing")
                : t("desktop.logs.state_unreadable")}
          </span>
        )}
        {counts.errors > 0 && (
          <Badge variant="danger">
            {t("desktop.logs.errors", { count: counts.errors })}
          </Badge>
        )}
        {counts.warnings > 0 && (
          <Badge variant="warning">
            {t("desktop.logs.warnings", { count: counts.warnings })}
          </Badge>
        )}
        <Button
          variant="outline"
          size="sm"
          className="rounded-full"
          aria-pressed={follow}
          title={t("desktop.logs.follow_hint")}
          onClick={() => {
            setFollow(!follow);
            if (!follow && list.current)
              list.current.scrollTop = list.current.scrollHeight;
          }}
        >
          {t("desktop.logs.follow")}
        </Button>
      </div>
      {sourceState === "unavailable" && (
        <Alert
          className="source-banner state-unavailable mx-2.5 mt-2 w-auto"
          icon={<Icon name="unplug" />}
        >
          <AlertTitle className="font-normal">
            {t("desktop.host.unavailable")}
          </AlertTitle>
        </Alert>
      )}
      {state?.kind === "missing" && (
        <Alert
          tone="warning"
          className="source-banner state-missing mx-2.5 mt-2 w-auto"
          icon={<Icon name="alert" />}
        >
          <AlertTitle className="font-normal">
            {t("desktop.logs.state_missing_detail")}
          </AlertTitle>
        </Alert>
      )}
      {state?.kind === "unreadable" && (
        <Alert
          tone="danger"
          className="source-banner state-unreadable mx-2.5 mt-2 w-auto"
          icon={<Icon name="alert" />}
        >
          <AlertTitle className="font-normal">
            {state.detail
              ? `${t("desktop.logs.state_unreadable")}: ${state.detail}`
              : t("desktop.logs.state_unreadable")}
          </AlertTitle>
        </Alert>
      )}
      <div
        className="logview-list min-h-0 flex-1 overflow-auto pt-1 pb-2 font-mono text-sm leading-relaxed select-text"
        ref={list}
        role="log"
        aria-live="off"
        tabIndex={0}
        onScroll={() => {
          const el = list.current;
          if (!el) return;
          const atEnd =
            el.scrollHeight - el.scrollTop - el.clientHeight < followSlack;
          if (atEnd !== follow) setFollow(atEnd);
          if (el.scrollTop < el.clientHeight && extent < visible.length)
            setExtent(extent + WINDOW);
        }}
      >
        {dropped > 0 && (
          <p className="px-3 py-2 font-sans text-faint">
            {t("desktop.logs.dropped", { count: dropped })}
          </p>
        )}
        {state?.kind === "available" && visible.length === 0 && (
          <p className="px-3 py-2 font-sans text-faint">
            {all.length ? t("desktop.logs.no_match") : t("desktop.logs.empty")}
          </p>
        )}
        {drawn.map((record) => (
          <Row
            key={record.seq}
            record={record}
            open={expanded.has(record.seq)}
            sourceLabel={sourceLabel(record.source)}
            detailsLabel={t("desktop.logs.details")}
            onToggle={handlers.toggle}
            onMenu={handlers.menu}
          />
        ))}
      </div>
    </div>
  );
}
