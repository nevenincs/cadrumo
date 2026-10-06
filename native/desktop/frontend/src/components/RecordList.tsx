import {
  useCallback,
  memo,
  useEffect,
  useLayoutEffect,
  useMemo,
  useRef,
  useState,
  type KeyboardEvent,
  type MouseEvent,
} from "react";
import { Alert, AlertTitle } from "@/components/ui/alert";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { cn } from "@/components/ui/cn";
import { Empty, EmptyDescription, EmptyMedia } from "@/components/ui/empty";
import { Icon } from "@/components/ui/icon";
import { Input } from "@/components/ui/input";
import { NativeSelect } from "@/components/ui/native-select";
import { Spinner } from "@/components/ui/spinner";
import type { LogLevel, LogRecord, LogSourceState } from "../ipc/contract";
import { useMetric } from "../shell/metrics";
import { fromPointer } from "../shell/pointer";
import {
  DEFAULT_FILTERS,
  LEVELS,
  shortLogger,
  type RecordFilters,
} from "../shell/records";
import type { MenuAnchor } from "./ContextMenu";
import { useStrings } from "../shell/strings";

/** Where a record's menu opens, and whether a pointer asked for it. */
export type RecordMenuRequest = {
  at: MenuAnchor;
  pointer: boolean;
  record: LogRecord;
  /** Every record the filters let through, not only the ones drawn. */
  visible: LogRecord[];
};

const rank = (level: LogLevel | null) => (level ? LEVELS.indexOf(level) : 1);

// How many of the newest matching records are in the document at once. The
// log holds up to ten thousand; drawing them all costs every scroll and every
// keystroke in the filter. Reaching the top brings in the next span.
const WINDOW = 400;
// The most records drawn at once for a reader who has left the end. The span
// moves with them a window at a time, so it never becomes the whole log.
const MAX_SPAN = 5 * WINDOW;
// How many views from an edge of the drawn span the next span is brought in.
const SPAN_MARGIN = 3;

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
  return (
    <div
      className={cn(
        `record level-${level} source-${record.source}`,
        // The current row carries an ink bar as well as the hover wash: its
        // faint text has no contrast to spare for a stronger surface.
        "border-l-2 hover:bg-accent focus-visible:-outline-offset-2 aria-[current=true]:border-ring aria-[current=true]:bg-accent",
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
      <div className="grid grid-cols-[7.5em_5.5em_minmax(8em,16em)_1fr] gap-x-3 px-3 py-px @max-xl:grid-cols-[7.5em_5.5em_1fr]">
        <time className="text-muted-foreground">
          {record.timestamp.slice(11, 23) || record.timestamp}
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
          {record.detail && (
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
//
// The list is one tab stop. Inside it the arrow keys, Home and End move from
// record to record, Enter opens a record's detail, and the menu key opens the
// same menu a right-click does.
export const RecordList = memo(function RecordList({
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
  onMenu: (request: RecordMenuRequest) => void;
  shown: boolean;
}) {
  const t = useStrings();
  const followSlack = useMetric("--log-follow-slack", 24);
  const list = useRef<HTMLDivElement>(null);
  const [expanded, setExpanded] = useState<ReadonlySet<number>>(new Set());
  const [follow, setFollow] = useState(true);
  // While the log follows its end, the newest span is drawn. Once a reader
  // has left the end the span is pinned to its first record instead, so the
  // records that arrive do not slide it out from under them. It grows with
  // them up to a limit, and moves a window at a time as the reader nears
  // either end of it.
  const [first, setFirst] = useState<number | null>(null);
  const [current, setCurrent] = useState<number | null>(null);
  // The current record is out of view, however that came about: the reader
  // scrolled, the log moved on under them, or the record left what is drawn.
  // Tab into the list must not throw the view back to it.
  const [strayed, setStrayed] = useState(false);
  // The record at the top of a reader's view, and where it sits. Whenever
  // what is drawn changes, the view is put back on it: an earlier or later
  // span comes in, the oldest records are dropped from the ring, and not
  // every engine keeps the view anchored by itself.
  const anchor = useRef<{ seq: number; top: number } | null>(null);
  // End was pressed away from the end: the newest record takes focus once
  // the newest span is drawn. Home, likewise, for the oldest.
  const focusNewest = useRef(false);
  const focusOldest = useRef(false);
  const filterInput = useRef<HTMLInputElement>(null);
  // The record the keyboard is on, to notice when it leaves the drawn span.
  const focused = useRef<string | null>(null);
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

  // Other filters are another view. A reader who has left the end keeps
  // their place in it where the record at the top of their view is still
  // shown; otherwise it starts at its newest record again, and nothing of
  // the old view's place is carried into it.
  const [drawnFor, setDrawnFor] = useState(filters);
  if (drawnFor !== filters) {
    setDrawnFor(filters);
    const kept = follow ? null : anchor.current;
    let at =
      kept === null
        ? -1
        : visible.findIndex((record) => record.seq === kept.seq);
    if (at < 0 && !follow && current !== null) {
      // The record at the top is not in this view. The one the reader is
      // on may be: a filter chosen from a record's own menu keeps it. The
      // view stays on that record, where it is on screen.
      at = visible.findIndex((record) => record.seq === current);
      const el = list.current;
      const row = el
        ?.querySelector(`:scope > [data-seq="${current}"]`)
        ?.getBoundingClientRect();
      const box = el?.getBoundingClientRect();
      // Only where the reader can see it: a record above or below the view
      // is not where they are, and the view would jump to it.
      if (at >= 0 && row && box && row.bottom > box.top && row.top < box.bottom)
        anchor.current = { seq: current, top: Math.max(0, row.top - box.top) };
      else at = -1;
    }
    if (at >= 0) {
      setFirst(visible[Math.max(0, at - WINDOW)]?.seq ?? null);
    } else {
      anchor.current = null;
      setFirst(null);
      setFollow(true);
    }
  }

  const drawn = useMemo(() => {
    const newest = visible.length > WINDOW ? visible.slice(-WINDOW) : visible;
    if (first === null) return newest;
    // Records are in sequence order: find the first at or after the pin.
    let low = 0;
    let high = visible.length;
    while (low < high) {
      const middle = (low + high) >> 1;
      if ((visible[middle]?.seq ?? Infinity) < first) low = middle + 1;
      else high = middle;
    }
    // Never less than the newest span, whatever the pin.
    return low < visible.length - WINDOW
      ? visible.slice(low, low + MAX_SPAN)
      : newest;
  }, [visible, first]);

  useLayoutEffect(() => {
    const el = list.current;
    const keep = anchor.current;
    if (!el || !keep || follow) return;
    const row = el.querySelector(`:scope > [data-seq="${keep.seq}"]`);
    if (!row) return;
    if (focusOldest.current) return;
    const moved =
      row.getBoundingClientRect().top -
      el.getBoundingClientRect().top -
      keep.top;
    if (Math.abs(moved) >= 1) el.scrollTop += moved;
  }, [drawn, follow]);

  // Whether the current record is in view, asked whenever the view or what
  // is drawn has moved: wherever the keyboard is, and following or not.
  // It reads the current record from a ref and never changes itself: the
  // effect that keeps a following log at its end calls it, and must not run
  // again because the keyboard moved to another record, or it would take
  // the view back to the end from under the record just moved to.
  const currentNow = useRef(current);
  currentNow.current = current;
  const measureStray = useCallback(() => {
    const el = list.current;
    const seq = currentNow.current;
    if (!el || seq === null) return;
    const at = el
      .querySelector(`:scope > [data-seq="${seq}"]`)
      ?.getBoundingClientRect();
    const box = el.getBoundingClientRect();
    const away = !at || at.bottom <= box.top || at.top >= box.bottom;
    setStrayed((held) => (held === away ? held : away));
  }, []);

  // The focused record can leave the drawn span as newer ones arrive. Focus
  // then goes, once, to the list itself, without moving the view, rather
  // than out of the log; an arrow key takes it on to a record.
  useLayoutEffect(() => {
    const el = list.current;
    const seq = focused.current;
    if (!el || seq === null) return;
    if (el.querySelector(`:scope > [data-seq="${seq}"]`)) return;
    focused.current = null;
    if (document.activeElement === document.body)
      el.focus({ preventScroll: true });
  }, [drawn]);
  useEffect(() => {
    // A press outside the log has taken the keyboard elsewhere, even where
    // what was pressed cannot hold focus.
    const leave = (event: PointerEvent) => {
      if (!list.current?.contains(event.target as Node)) focused.current = null;
    };
    document.addEventListener("pointerdown", leave, true);
    return () => document.removeEventListener("pointerdown", leave, true);
  }, []);

  // Where the view was when it last scrolled: leaving the end means having
  // moved up from there, not merely being short of an end that has grown.
  const lastTop = useRef(0);

  // In the commit that draws new records or opens a record's detail, before
  // anything is painted or any scroll is reported: there is no moment at
  // which the end has moved on and the view has not.
  useLayoutEffect(() => {
    const el = list.current;
    if (!shown || !follow || !el) return;
    el.scrollTop = el.scrollHeight;
    lastTop.current = el.scrollTop;
    // The end has moved on, and what was in view may no longer be.
    measureStray();
    if (!focusNewest.current || first !== null) return;
    focusNewest.current = false;
    const newest = el.lastElementChild;
    if (newest instanceof HTMLElement && newest.classList.contains("record"))
      newest.focus({ preventScroll: true });
  }, [drawn, expanded, first, follow, shown, measureStray]);

  // The record at the top of the view and where it sits, to keep the view
  // on. Taken when the view moves, and at once after anything that moves
  // it by other means than a scroll the reader made: a batch that commits
  // before the scroll is reported must not put the view back.
  const captureAnchor = () => {
    const el = list.current;
    if (!el) return;
    const box = el.getBoundingClientRect();
    const hit = document
      .elementFromPoint(box.left + box.width / 2, box.top + 2)
      ?.closest<HTMLElement>(".record");
    const row =
      hit && el.contains(hit)
        ? hit
        : [...el.querySelectorAll<HTMLElement>(":scope > .record")].find(
            (candidate) => candidate.getBoundingClientRect().bottom > box.top,
          );
    anchor.current = row
      ? {
          seq: Number(row.dataset.seq),
          top: row.getBoundingClientRect().top - box.top,
        }
      : null;
    return row;
  };

  // Leaving the end, by whatever means: the span stays on what it shows.
  const leaveEnd = () => {
    if (!follow) return;
    captureAnchor();
    setFollow(false);
    setFirst(drawn[0]?.seq ?? null);
  };

  // Home, away from the oldest record: the oldest span is drawn, and its
  // first record takes focus at the top.
  useLayoutEffect(() => {
    const el = list.current;
    if (!el || !focusOldest.current || drawn[0] !== visible[0]) return;
    focusOldest.current = false;
    el.scrollTop = 0;
    lastTop.current = 0;
    const oldest = el.querySelector<HTMLElement>(":scope > .record");
    oldest?.focus({ preventScroll: true });
    captureAnchor();
  });
  const touchStart = useRef(0);

  // Following also holds when the list itself changes size: a narrower panel
  // wraps its rows, and the end moves without any new record.
  const following = useRef(follow);
  useEffect(() => {
    following.current = follow;
  }, [follow]);
  useEffect(() => {
    const el = list.current;
    if (!el) return;
    const observer = new ResizeObserver(() => {
      if (!following.current) return;
      el.scrollTop = el.scrollHeight;
      lastTop.current = el.scrollTop;
    });
    observer.observe(el);
    return () => observer.disconnect();
  }, []);

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
        setExpanded((held) => {
          const next = new Set(held);
          if (!next.delete(seq)) next.add(seq);
          return next;
        }),
      current: (seq: number) => {
        setCurrent(seq);
        setStrayed(false);
      },
      menu: (event: MouseEvent<HTMLElement>, record: LogRecord) => {
        setCurrent(record.seq);
        // A menu asked for by the menu key belongs at its row's edge, not
        // wherever the cursor was left.
        const pointer = fromPointer(event.nativeEvent);
        const row = event.currentTarget.getBoundingClientRect();
        const time = event.currentTarget
          .querySelector("time")
          ?.getBoundingClientRect();
        live.current.onMenu({
          at: pointer
            ? { x: event.clientX, y: event.clientY }
            : {
                x: time?.right ?? row.left,
                y: row.top,
                height: row.height,
              },
          pointer,
          record,
          visible: live.current.visible,
        });
      },
    }),
    [],
  );

  // Tab lands on the current row while it is drawn. Otherwise, while the
  // log follows its end, on the newest; and for a reader who has left the
  // end, on the list itself, which moves nothing: a row chosen for them
  // would scroll their place away.
  const tabStop =
    current !== null &&
    !strayed &&
    drawn.some((record) => record.seq === current)
      ? current
      : follow
        ? drawn.at(-1)?.seq
        : undefined;

  const key = (event: KeyboardEvent<HTMLDivElement>) => {
    const from = event.target;
    if (!(from instanceof HTMLElement)) return;
    const box = event.currentTarget;
    const moves = [
      "ArrowDown",
      "ArrowUp",
      "Home",
      "End",
      "PageUp",
      "PageDown",
    ].includes(event.key);
    // From the list itself, a movement key goes to a record without moving
    // the view: the one Tab would reach, or the one at the top of the view.
    if (from === box) {
      if (!moves) return;
      const stop =
        box.querySelector<HTMLElement>(':scope > .record[tabindex="0"]') ??
        captureAnchor();
      if (!stop) return;
      event.preventDefault();
      stop.focus({ preventScroll: true });
      return;
    }
    const row = from.closest<HTMLElement>(".record");
    if (!row) return;
    const rows = () => box.querySelectorAll<HTMLElement>(":scope > .record");
    // The record about a page away, in the direction asked for.
    const page = (step: 1 | -1) => {
      let at: Element = row;
      let far = 0;
      for (;;) {
        const next: Element | null =
          step > 0 ? at.nextElementSibling : at.previousElementSibling;
        if (!next?.classList.contains("record")) return at;
        far += next.getBoundingClientRect().height;
        at = next;
        if (far >= box.clientHeight * 0.8) return at;
      }
    };
    // End, away from the newest record, is the way back to it: the log
    // follows again, and the newest record takes focus when it is drawn.
    if (event.key === "End" && (!follow || first !== null)) {
      event.preventDefault();
      focusNewest.current = true;
      anchor.current = null;
      setFirst(null);
      setFollow(true);
      return;
    }
    // Home is the oldest record of the log, not of the span that is drawn.
    if (event.key === "Home" && drawn[0] !== visible[0]) {
      event.preventDefault();
      focusOldest.current = true;
      setFollow(false);
      setFirst(visible[0]?.seq ?? null);
      return;
    }
    // Movement keys work from a control inside a row as from the row.
    const target =
      event.key === "ArrowDown"
        ? row.nextElementSibling
        : event.key === "ArrowUp"
          ? row.previousElementSibling
          : event.key === "Home"
            ? rows()[0]
            : event.key === "End"
              ? rows()[rows().length - 1]
              : event.key === "PageDown"
                ? page(1)
                : event.key === "PageUp"
                  ? page(-1)
                  : null;
    if (target instanceof HTMLElement && target.classList.contains("record")) {
      event.preventDefault();
      // Moving up from the end is leaving it, whether or not the record
      // moved to is already in view. So is moving down to a record that is
      // not the newest, from one the log has gone past: leaving is decided
      // here, by the key, and not by the scroll that follows it, which a
      // batch of records can arrive ahead of.
      if (
        target !== row &&
        (["ArrowUp", "Home", "PageUp"].includes(event.key) ||
          Number(target.dataset.seq) !== visible.at(-1)?.seq)
      )
        leaveEnd();
      target.focus();
      if (
        !follow &&
        ["ArrowDown", "PageDown"].includes(event.key) &&
        Number(target.dataset.seq) === visible.at(-1)?.seq
      ) {
        // Back on the newest record of the log: following resumes, as it
        // does for a scroll that reaches the end.
        anchor.current = null;
        setFirst(null);
        setFollow(true);
        return;
      }
      // Where the view now is, before any batch can put it back.
      if (!follow || target !== row) captureAnchor();
    } else if (
      event.key === "ArrowDown" &&
      !follow &&
      Number(row.dataset.seq) === visible.at(-1)?.seq
    ) {
      // Already on the newest record, with nothing below to move to: asking
      // for more is asking to follow the end again.
      event.preventDefault();
      anchor.current = null;
      setFirst(null);
      setFollow(true);
    } else if (from === row && (event.key === "Enter" || event.key === " ")) {
      // Enter and Space on a control inside the row belong to that control.
      // On the row they open its detail; where it has none, Space still
      // does not scroll the list from under the keyboard.
      event.preventDefault();
      const toggle = row.querySelector<HTMLElement>("[aria-expanded]");
      if (!toggle) return;
      handlers.toggle(Number(row.dataset.seq));
    }
  };

  const loading = records === null && sourceState === null;
  const empty = state?.kind === "available" && visible.length === 0;
  const chip = "shrink-0 rounded-full";
  // Follow stands where each shape of the bar wants it: last in a wide bar,
  // after the level in a narrow one, and first in the one-row bar of a short
  // panel, where it also stays put while the rest scrolls sideways under it.
  // It is drawn once in each place and shown in one, so the keyboard reaches
  // it in the order the eye does.
  const followButton = (place: string) => (
    <Button
      variant="outline"
      size="sm"
      className={cn(chip, place)}
      data-follow=""
      aria-pressed={follow}
      title={t("desktop.logs.follow_hint")}
      // The bar has changed shape under the keyboard and this place is no
      // longer the one shown: focus goes to the one that is.
      onBlur={(event) => {
        const left = event.currentTarget;
        if (event.relatedTarget || left.getClientRects().length > 0) return;
        [
          ...(left
            .closest(".logview")
            ?.querySelectorAll<HTMLElement>("[data-follow]") ?? []),
        ]
          .find((place) => place.getClientRects().length > 0)
          ?.focus();
      }}
      onClick={() => {
        if (follow) leaveEnd();
        else {
          anchor.current = null;
          setFirst(null);
          setFollow(true);
        }
      }}
    >
      {t("desktop.logs.follow")}
    </Button>
  );

  return (
    <div
      className="logview @container flex min-h-0 flex-1 flex-col bg-background"
      hidden={!shown}
      role="tabpanel"
      id="panel-logs"
      aria-labelledby="tab-logs"
    >
      {/* One row where there is room. In a narrow panel: the filter, the
          level and Follow on a first row, and everything else on a second
          that scrolls sideways, so the bar is never taller than two rows.
          In a panel near its floor it is one row again, all of it scrolling
          sideways, so the records keep their room. */}
      <div className="flex shrink-0 flex-col gap-1.5 border-b px-2.5 py-1.5 @4xl:flex-row @4xl:items-center panel-short:flex-row panel-short:items-center panel-short:scroll-cue-x panel-short:overflow-x-auto panel-short:[scrollbar-width:none] panel-short:[&::-webkit-scrollbar]:hidden">
        <div className="flex min-w-0 items-center gap-1.5 @4xl:contents panel-short:contents panel-short:*:shrink-0">
          {followButton(
            "sticky left-0 z-(--layer-separator) hidden bg-background panel-short:inline-flex",
          )}
          <Input
            ref={filterInput}
            className="filter-text min-w-20 flex-1 @4xl:w-field @4xl:flex-none panel-short:w-field panel-short:flex-none"
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
            className="min-w-0 shrink panel-short:shrink-0"
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
          {followButton("@4xl:hidden panel-short:hidden")}
        </div>
        <div className="flex min-w-0 items-center gap-1.5 scroll-cue-x overflow-x-auto [scrollbar-width:none] [&::-webkit-scrollbar]:hidden @4xl:contents panel-short:contents">
          <div
            className="flex shrink-0 gap-1"
            role="group"
            aria-label={t("desktop.logs.sources")}
          >
            {sources.map((source) => (
              <Button
                key={source}
                variant="outline"
                size="sm"
                className={chip}
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
              className={chip}
              aria-pressed="true"
              aria-label={`${t("desktop.logs.clear_logger")}: ${shortLogger(filters.logger)}`}
              title={t("desktop.logs.clear_logger")}
              onClick={() => {
                setFilters({ ...filters, logger: null });
                // The chip goes with its filter: the keyboard goes to the
                // filter field, not to nothing.
                filterInput.current?.focus();
              }}
            >
              {shortLogger(filters.logger)}
              <Icon name="close" size="xs" />
            </Button>
          )}
          <span className="flex-1" />
          {state?.kind === "available" && (
            <span className="shrink-0 text-xs text-faint">
              {t("desktop.logs.state_available")}
            </span>
          )}
          {counts.errors > 0 && (
            <Badge variant="danger" className="shrink-0">
              {t("desktop.logs.errors", { count: counts.errors })}
            </Badge>
          )}
          {counts.warnings > 0 && (
            <Badge variant="warning" className="shrink-0">
              {t("desktop.logs.warnings", { count: counts.warnings })}
            </Badge>
          )}
          {followButton("hidden @4xl:inline-flex panel-short:hidden!")}
        </div>
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
        className="logview-list min-h-0 flex-1 overflow-auto pt-1 pb-2 font-mono text-sm leading-relaxed select-text focus-visible:-outline-offset-2"
        ref={list}
        role="log"
        aria-label={t("desktop.rail.logs")}
        aria-live="off"
        tabIndex={tabStop === undefined && drawn.length > 0 ? 0 : -1}
        onKeyDown={key}
        // A menu asked for off any record has no record to be about: none
        // is shown, the browser's own included.
        onContextMenu={(event) => {
          if (!(event.target as HTMLElement).closest(".record"))
            event.preventDefault();
        }}
        onFocus={(event) => {
          focused.current =
            (event.target as HTMLElement).closest<HTMLElement>(".record")
              ?.dataset.seq ?? null;
        }}
        onBlur={(event) => {
          // Focus went somewhere on purpose; a record that is removed gives
          // no such destination.
          if (event.relatedTarget) focused.current = null;
        }}
        // A wheel turned upward, or a finger drawn down, leaves the end at
        // once: under a busy log a slow movement would otherwise be undone
        // by the next records before it had gone anywhere.
        onWheel={(event) => {
          const el = event.currentTarget;
          // A sideways turn with a trace of upward in it is not a scroll up.
          if (
            event.deltaY < 0 &&
            Math.abs(event.deltaY) >= Math.abs(event.deltaX) &&
            el.scrollHeight > el.clientHeight
          )
            leaveEnd();
        }}
        onTouchStart={(event) => {
          touchStart.current = event.touches[0]?.clientY ?? 0;
        }}
        onTouchMove={(event) => {
          const el = event.currentTarget;
          if (
            (event.touches[0]?.clientY ?? 0) > touchStart.current + 4 &&
            el.scrollHeight > el.clientHeight
          )
            leaveEnd();
        }}
        onScroll={() => {
          const el = list.current;
          if (!el) return;
          measureStray();
          const top = drawn[0];
          const fromEnd = el.scrollHeight - el.scrollTop - el.clientHeight;
          // The end of the log, not merely of the span that is drawn.
          const newest = drawn.at(-1) === visible.at(-1);
          const atEnd = newest && fromEnd < followSlack;
          const movedUp = el.scrollTop < lastTop.current - 0.5;
          // While following, upward movement is measured from the end, so a
          // slow scroll adds up instead of never counting.
          if (atEnd || !follow) lastTop.current = el.scrollTop;
          if (follow) {
            // Still at the end, or the end has merely moved on: following
            // ends only when the reader has scrolled up from it.
            if (atEnd || !movedUp) return;
            setFollow(false);
          } else if (atEnd && !movedUp) {
            // Back down at the newest record: following resumes and the
            // earlier spans are let go.
            anchor.current = null;
            setFollow(true);
            if (first !== null) setFirst(null);
            return;
          }
          if (!top) return;
          captureAnchor();
          const at = visible.indexOf(top);
          // The next span comes in a few views before the edge of this one,
          // so a fast scroll does not run into the edge first.
          const margin = SPAN_MARGIN * el.clientHeight;
          if (el.scrollTop < margin && top.seq > (visible[0]?.seq ?? top.seq))
            // Near the top of what is drawn, with earlier records to show.
            setFirst(visible[Math.max(0, at - WINDOW)]?.seq ?? top.seq);
          else if (!newest && fromEnd < margin)
            // Near the bottom of a span that is not the newest: later
            // records come in and the earliest drawn are let go.
            setFirst(visible[at + WINDOW]?.seq ?? top.seq);
          else if (first === null)
            // Left the end: the span stays on the records it shows.
            setFirst(top.seq);
        }}
      >
        {loading && (
          <Empty role="status" className="min-h-full font-sans">
            <Spinner />
            <EmptyDescription>{t("desktop.logs.loading")}</EmptyDescription>
          </Empty>
        )}
        {dropped > 0 && drawn.length > 0 && drawn[0] === visible[0] && (
          <p className="px-3 py-2 font-sans text-faint">
            {t("desktop.logs.dropped", { count: dropped })}
          </p>
        )}
        {empty && (
          <Empty role="status" className="min-h-full font-sans">
            <EmptyMedia>
              <Icon name="logs" />
            </EmptyMedia>
            <EmptyDescription>
              {all.length
                ? t("desktop.logs.no_match")
                : t("desktop.logs.empty")}
            </EmptyDescription>
            {all.length > 0 && (
              <Button
                variant="outline"
                size="sm"
                onClick={() => {
                  setFilters(DEFAULT_FILTERS);
                  filterInput.current?.focus();
                }}
              >
                {t("desktop.action.logs_reset")}
              </Button>
            )}
          </Empty>
        )}
        {drawn.map((record) => (
          <Row
            key={record.seq}
            record={record}
            open={expanded.has(record.seq)}
            current={record.seq === current}
            tabStop={record.seq === tabStop}
            sourceLabel={sourceLabel(record.source)}
            detailsLabel={t("desktop.logs.details")}
            onToggle={handlers.toggle}
            onCurrent={handlers.current}
            onMenu={handlers.menu}
          />
        ))}
      </div>
    </div>
  );
});
