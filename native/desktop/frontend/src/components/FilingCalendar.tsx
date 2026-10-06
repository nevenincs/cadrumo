import {
  Fragment,
  memo,
  useCallback,
  useEffect,
  useId,
  useLayoutEffect,
  useMemo,
  useRef,
  useState,
  type ReactNode,
  type RefObject,
} from "react";
import { flushSync } from "react-dom";
import { Alert } from "@/components/ui/alert";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { cn } from "@/components/ui/cn";
import {
  Empty,
  EmptyDescription,
  EmptyMedia,
  EmptyTitle,
} from "@/components/ui/empty";
import { Icon } from "@/components/ui/icon";
import { IconButton } from "@/components/ui/icon-button";
import {
  SegmentedControl,
  SegmentedControlItem,
} from "@/components/ui/segmented-control";
import { Spinner } from "@/components/ui/spinner";
import {
  deadlineDistance,
  evaluatedDay,
  evaluatedLabel,
  isoDay as day,
  localDay,
  type CalendarState,
} from "../shell/calendar";
import { entryKey } from "../shell/calendarGrid";
import { useMetric } from "../shell/metrics";
import { useStrings } from "../shell/strings";
import type {
  CalendarEntry,
  CalendarEvent,
  CalendarUserState,
} from "../shell/views";
import { CalendarMonths } from "./CalendarMonths";

const STATE_TONE: Record<
  CalendarUserState,
  "neutral" | "danger" | "success" | "warning"
> = { due: "neutral", late: "danger", filed: "success", unknown: "warning" };

// What needs the person first comes first.
const STATE_ORDER: readonly CalendarUserState[] = [
  "late",
  "due",
  "unknown",
  "filed",
];

const DAY_MS = 86_400_000;

// The formats of a language, made once: a row needs four and there are
// many rows.
const FORMATS = new Map<string, ReturnType<typeof makeFormats>>();
const makeFormats = (locale: string) => ({
  short: new Intl.DateTimeFormat(locale, { day: "numeric", month: "short" }),
  full: new Intl.DateTimeFormat(locale, { dateStyle: "full" }),
  weekday: new Intl.DateTimeFormat(locale, { weekday: "short" }),
  relative: new Intl.RelativeTimeFormat(locale, { numeric: "auto" }),
});
function formatsFor(locale: string) {
  let formats = FORMATS.get(locale);
  if (!formats) FORMATS.set(locale, (formats = makeFormats(locale)));
  return formats;
}

// A row is drawn again only when it changes: choosing one obligation does
// not redraw the others.
const Entry = memo(function Entry({
  entry,
  locale,
  selected,
  onSelect,
  onOpen,
}: {
  entry: CalendarEntry;
  locale: string;
  /** Chosen, here or in the months beside the list. */
  selected: boolean;
  onSelect: (key: string) => void;
  onOpen?: (entry: CalendarEntry) => void;
}) {
  const t = useStrings();
  const closes = day(entry.adjusted_closes_on);
  const { short, full, weekday, relative: distance } = formatsFor(locale);
  // How far the binding date is from the day the product evaluated: the
  // product's own count where it gives one.
  const away =
    entry.days_overdue !== null
      ? -entry.days_overdue
      : Math.round(
          (closes.getTime() - day(entry.evaluated_on).getTime()) / DAY_MS,
        );
  // A filed obligation has no distance left to say.
  const { value, unit } = deadlineDistance(away, entry.days_overdue !== null);
  const relative =
    entry.user_state === "filed" ? null : distance.format(value, unit);
  const name = t("desktop.calendar.modelo", { modelo: entry.modelo });
  const notes = [
    t(`desktop.calendar.local.${entry.local_filing_state}`),
    t(`desktop.calendar.aeat.${entry.aeat_submission_state}`),
    entry.adjusted_closes_on !== entry.closes_on
      ? t("desktop.calendar.moved", {
          date: short.format(day(entry.closes_on)),
        })
      : null,
    entry.payment_cutoff_on
      ? t("desktop.calendar.payment_cutoff", {
          date: short.format(day(entry.payment_cutoff_on)),
        })
      : null,
  ].filter((note): note is string => note !== null);
  return (
    <li
      data-entry={entryKey(entry)}
      aria-current={selected || undefined}
      // The chosen row carries a bar as well as a surface, as a chosen item
      // does everywhere in the window.
      className="grid scroll-mt-[calc(var(--calendar-head)+--spacing(8))] grid-cols-[auto_minmax(0,1fr)_auto] items-center gap-x-3 border-b border-l-2 border-l-transparent px-4 py-2 hover:bg-accent aria-[current=true]:border-l-ring aria-[current=true]:bg-selected forced-colors:border-l-[Canvas] forced-colors:aria-[current=true]:border-l-[Highlight]"
    >
      <time
        dateTime={entry.adjusted_closes_on}
        className="grid w-10 justify-items-center"
      >
        {/* The eye has the month in the heading above; read aloud, a day
            and a weekday alone are not a date, so the whole date is said. */}
        <span className="sr-only">{full.format(closes)}</span>
        <span
          aria-hidden="true"
          className="text-md leading-tight font-semibold tabular-nums"
        >
          {closes.getDate()}
        </span>
        <span aria-hidden="true" className="text-xs text-muted-foreground">
          {weekday.format(closes)}
        </span>
      </time>
      <div className="grid min-w-0 gap-0.5">
        {/* The row's name is what chooses it: the same obligation is then
            shown among the months. */}
        <button
          type="button"
          aria-pressed={selected}
          className="flex min-h-control-xs cursor-pointer flex-wrap items-center gap-x-2 justify-self-start rounded-sm text-left hover:underline"
          onClick={() => onSelect(entryKey(entry))}
        >
          <span className="font-medium">{name}</span>
          <span className="text-muted-foreground">{entry.period}</span>
        </button>
        <span className="text-sm text-muted-foreground">
          {notes.join(" · ")}
        </span>
        {/* In a narrow pane the distance moves under the notes: it is what
            the person came for, and is never the thing left out. */}
        {relative && (
          <span className="calendar-distance text-sm text-muted-foreground @md:hidden">
            {relative}
          </span>
        )}
      </div>
      <div className="flex items-center gap-2">
        <span className="grid justify-items-end gap-0.5">
          <Badge variant={STATE_TONE[entry.user_state]}>
            {t(`desktop.calendar.state.${entry.user_state}`)}
          </Badge>
          {relative && (
            <span className="calendar-distance text-xs text-muted-foreground @max-md:hidden">
              {relative}
            </span>
          )}
        </span>
        {onOpen && (
          <IconButton
            label={t("desktop.calendar.open_tui")}
            accessibleName={`${t("desktop.calendar.open_tui")}: ${name} ${entry.period}`}
            side="left"
            onClick={() => onOpen(entry)}
          >
            <Icon name="arrow" />
          </IconButton>
        )}
      </div>
    </li>
  );
});

/**
 * Where the past ends: a line across the list at the day the product worked
 * the states out for, so what is behind and what is ahead are told apart at
 * a glance. It is said in the language's own word for today where that day
 * is today here; a calendar worked out for another day says the day alone.
 */
function TodayMark({
  on,
  today,
  locale,
}: {
  on: string;
  /** The local day. */
  today: string;
  locale: string;
}) {
  const label = evaluatedLabel(on, today, locale);
  return (
    <div
      role="separator"
      aria-label={label}
      className="calendar-today flex items-center gap-2 px-4 py-1.5 text-xs font-semibold text-brand"
    >
      <span aria-hidden="true">{label}</span>
      <span aria-hidden="true" className="h-px flex-1 bg-current opacity-40" />
    </div>
  );
}

/**
 * The filing calendar: every obligation in a range of dates, by month, with
 * the product's own reading of where each stands. It keeps apart what the
 * product keeps apart: the local filing work, what has been seen of the tax
 * agency, and what could not be determined at all.
 *
 * The page is one region that scrolls and can hold focus, so the keyboard
 * scrolls it from wherever focus is inside. A control that held focus and
 * has gone, because the read it asked for answered or the sign-in ended,
 * leaves focus on the page rather than on nothing.
 */
export function FilingCalendarView({
  state,
  withheld,
  attempt = 0,
  locale,
  today: localToday,
  defaultView = "months",
  refreshing = false,
  page,
  onRefresh,
  onOpen,
}: {
  state: CalendarState;
  /** What stands in the page while the account withholds the calendar: the
   * account's own account of why, and the ways on. */
  withheld?: ReactNode;
  /** Which read this is. A failure is announced again when a new read
   * fails the same way. */
  attempt?: number;
  /** The chrome language, for dates. */
  locale: string;
  /** The local day, as an ISO date, from whoever keeps it current. The
   * calendar's mark is called today only where its day is this one. */
  today?: string;
  /** The face a page too narrow for both shows first. */
  defaultView?: "months" | "list";
  /** A newer read is in flight over what is shown. */
  refreshing?: boolean;
  /** The page's own element, for whoever sends focus to it. */
  page?: RefObject<HTMLElement | null>;
  onRefresh: () => void;
  /** Take the person to where this obligation is worked on. Left out where
   * the window cannot: no row then offers a way it does not have. */
  onOpen?: (entry: CalendarEntry) => void;
}) {
  const t = useStrings();
  const heading = useId();
  const own = useRef<HTMLElement>(null);
  const root = page ?? own;
  const calendar = state.kind === "ready" ? state.calendar : null;

  // The calendar has two faces that complete each other: the months, where
  // each obligation is drawn across the days its window is open, and the
  // list, which says where each stands. A wide page shows both side by
  // side; a narrower one shows one, the months first, with a switch.
  const [view, setView] = useState<"months" | "list">(defaultView);
  const splitAt = useMetric("--calendar-split", 896);
  const tallAt = useMetric("--calendar-tall", 352);
  // Only what changes the drawing is state: whether there is room for both
  // faces, and whether the page is tall enough for its whole head to stay.
  // The sizes themselves go to the page's styles as they are measured, and
  // draw nothing again.
  const [room, setRoom] = useState({ wide: false, tall: true });
  // The month at the top of the reader's view, and where it sits: the
  // place the months are put back on whenever they are laid out anew.
  const anchor = useRef<{ key: string; top: number } | null>(null);
  const widthWas = useRef<number | null>(null);
  // The row of controls stays at the top while the page scrolls under it.
  const head = useRef<HTMLDivElement>(null);
  const bar = useRef<HTMLDivElement>(null);
  // How much of the page's top the head keeps: all of it, or its controls.
  const kept = () =>
    head.current?.offsetHeight || bar.current?.offsetHeight || 0;
  const shown = calendar !== null;
  useLayoutEffect(() => {
    const el = root.current;
    if (!el) return;
    const fit = () =>
      setRoom((held) => {
        const next = {
          wide: el.clientWidth >= splitAt,
          tall: el.clientHeight >= tallAt,
        };
        return held.wide === next.wide && held.tall === next.tall ? held : next;
      });
    const measure = () => {
      el.style.setProperty("--calendar-head", `${kept()}px`);
      el.style.setProperty("--calendar-height", `${el.clientHeight}px`);
    };
    const resized = () => {
      // A page made wider or narrower lays its months out in other rows.
      // The month the reader was on is put back where it was, here, before
      // the browser reports the scroll that the new layout caused.
      const width = el.clientWidth;
      const left = anchor.current;
      if (left && widthWas.current !== null && width !== widthWas.current) {
        const month = el.querySelector(`[data-month="${left.key}"]`);
        if (month)
          el.scrollTop +=
            month.getBoundingClientRect().top -
            el.getBoundingClientRect().top -
            left.top;
      }
      widthWas.current = width;
      // What the new size changes in the drawing is drawn now, before the
      // browser paints: a page that has just become wide enough for both
      // faces is never shown for a moment with one, laid out for the other.
      // A face that comes to be shown by it is then placed by its own rule,
      // which has the last word: on what is chosen, or on that same month.
      flushSync(fit);
      measure();
    };
    measure();
    fit();
    widthWas.current = el.clientWidth;
    const observer = new ResizeObserver(resized);
    observer.observe(el);
    if (head.current) observer.observe(head.current);
    if (bar.current) observer.observe(bar.current);
    return () => observer.disconnect();
  }, [root, splitAt, tallAt, shown]);
  const wide = room.wide;

  // The obligation chosen, by Modelo and period, and which face it was
  // chosen in: the other face brings it into view.
  const [selected, setSelected] = useState<string | null>(null);
  const chosenIn = useRef<"months" | "list">("months");
  const select = useCallback((key: string, from: "months" | "list") => {
    chosenIn.current = from;
    setSelected((held) => (held === key ? null : key));
  }, []);
  const selectInList = useCallback(
    (key: string) => select(key, "list"),
    [select],
  );
  const selectInMonths = useCallback(
    (key: string) => select(key, "months"),
    [select],
  );

  // A face opens on where the person is: on the obligation they chose, or
  // else the months on the month of the day the product evaluated and the
  // list on its mark for today. Once for each time a face comes to be
  // shown; after that the place is theirs: the months come back to the month
  // that was at the top when they were last scrolled, where it was, in a
  // pane or beside the list alike.
  const aside = useRef<HTMLDivElement>(null);
  const placed = useRef<string | null>(null);
  const evaluatedOn = calendar ? evaluatedDay(calendar) : null;
  const here = localToday ?? localDay();
  useLayoutEffect(() => {
    const el = root.current;
    if (!el) return;
    if (evaluatedOn === null) {
      // Nothing is shown: a calendar read anew opens as a first one does.
      placed.current = null;
      anchor.current = null;
      return;
    }
    const face = wide ? "both" : view;
    if (placed.current === face) return;
    if (
      !el.querySelector(face === "list" ? ".calendar-list" : ".calendar-months")
    )
      return;
    placed.current = face;
    // Its top to just under what stays at the top, with some air.
    const bring = (scroller: HTMLElement, to: Element | null, air: number) => {
      if (to)
        scroller.scrollTop +=
          to.getBoundingClientRect().top -
          scroller.getBoundingClientRect().top -
          air;
    };
    const chosen = (within: string) =>
      selected === null
        ? null
        : el.querySelector(`${within} [data-entry="${CSS.escape(selected)}"]`);
    if (face !== "list") {
      const bar = chosen(".calendar-months");
      const left = anchor.current;
      if (bar) bring(el, bar, kept() + 48);
      else if (left)
        bring(el, el.querySelector(`[data-month="${left.key}"]`), left.top);
      else
        bring(
          el,
          el.querySelector(`[data-month="${evaluatedOn.slice(0, 7)}"]`),
          kept() + 12,
        );
    }
    // The list keeps a month's name above its rows: exactly its room is
    // left, so no sliver of the row before shows under it.
    const list = wide ? aside.current : el;
    const name =
      el.querySelector<HTMLElement>(".calendar-list h2")?.offsetHeight ?? 0;
    if (face !== "months" && list)
      bring(
        list,
        chosen(".calendar-list") ??
          el.querySelector(".calendar-list .calendar-today"),
        (wide ? 0 : kept()) + name,
      );
  }, [evaluatedOn, root, room, view, wide, selected]);
  useEffect(() => {
    if (selected === null) return;
    const other = chosenIn.current === "months" ? "list" : "months";
    root.current
      ?.querySelector(
        `.calendar-${other} [data-entry="${CSS.escape(selected)}"]`,
      )
      ?.scrollIntoView({ block: "nearest" });
  }, [selected, view, wide, root]);

  // Whether the last thing focused or pressed was in the page. Removing a
  // focused control reports nothing, so this is how its loss is known.
  const within = useRef(false);
  useEffect(() => {
    const track = (event: Event) => {
      within.current =
        event.target instanceof Node &&
        (root.current?.contains(event.target) ?? false);
    };
    document.addEventListener("focusin", track);
    document.addEventListener("pointerdown", track);
    return () => {
      document.removeEventListener("focusin", track);
      document.removeEventListener("pointerdown", track);
    };
  }, [root]);
  useEffect(() => {
    if (within.current && document.activeElement === document.body)
      root.current?.focus();
  });

  const months = useMemo(() => {
    const month = new Intl.DateTimeFormat(locale, {
      month: "long",
      year: "numeric",
    });
    const groups = new Map<
      string,
      {
        title: string;
        entries: CalendarEntry[];
        events: CalendarEvent[];
        ahead: number;
      }
    >();
    for (const entry of [...(calendar?.entries ?? [])].sort(
      (a, b) =>
        a.adjusted_closes_on.localeCompare(b.adjusted_closes_on) ||
        a.modelo.localeCompare(b.modelo),
    )) {
      const key = entry.adjusted_closes_on.slice(0, 7);
      const group = groups.get(key) ?? {
        title: month.format(day(entry.adjusted_closes_on)),
        entries: [],
        events: [],
        ahead: 0,
      };
      // How many of the month's obligations bind on or after the day the
      // product evaluated: they are listed last, being sorted by date.
      if (evaluatedOn !== null && entry.adjusted_closes_on >= evaluatedOn)
        group.ahead += 1;
      group.entries.push(entry);
      groups.set(key, group);
    }
    // What was observed, in the month it happened, whether or not anything
    // falls due in that month.
    for (const event of [...(calendar?.events ?? [])].sort((a, b) =>
      a.event_date.localeCompare(b.event_date),
    )) {
      const key = event.event_date.slice(0, 7);
      const group = groups.get(key) ?? {
        title: month.format(day(event.event_date)),
        entries: [],
        events: [],
        ahead: 0,
      };
      group.events.push(event);
      groups.set(key, group);
    }
    return [...groups].sort(([a], [b]) => a.localeCompare(b));
  }, [calendar, locale, evaluatedOn]);
  // The day the product worked the states out for, and the month in which
  // the first obligation still ahead falls: the mark for today stands just
  // before that obligation, or after the last one when none is ahead.
  const today = evaluatedOn;
  const turning = months.find(([, month]) => month.ahead > 0)?.[0] ?? null;

  let body: ReactNode;
  if (state.kind === "loading") {
    body = (
      <Empty role="status">
        <Spinner />
        <EmptyDescription>{t("desktop.calendar.loading")}</EmptyDescription>
      </Empty>
    );
  } else if (state.kind === "withheld") {
    body = withheld ?? (
      <Empty>
        <EmptyMedia>
          <Icon name="lock" />
        </EmptyMedia>
        <div className="grid gap-1">
          <EmptyTitle>{t("desktop.account.signed_out")}</EmptyTitle>
          <EmptyDescription>
            {t("desktop.calendar.signed_out")}
          </EmptyDescription>
        </div>
      </Empty>
    );
  } else if (state.kind === "failed") {
    body = (
      <Empty>
        <EmptyMedia>
          <Icon name="alert" />
        </EmptyMedia>
        {/* The sentence is the alert, made anew for each read that fails,
            so a second failure is heard. The button beside it stays as it
            is, and keeps the keyboard. */}
        <EmptyDescription key={attempt} role="alert">
          {t("desktop.calendar.failed", { code: state.code })}
        </EmptyDescription>
        <Button variant="outline" pending={refreshing} onClick={onRefresh}>
          {t("desktop.calendar.refresh")}
        </Button>
      </Empty>
    );
  } else {
    const { warnings, coverage, generated_at } = state.calendar;
    const asOf = generated_at
      ? new Intl.DateTimeFormat(locale, {
          dateStyle: "medium",
          timeStyle: "short",
        }).format(new Date(generated_at))
      : "—";
    // How the range stands, in the product's own four readings: counted,
    // never combined into a verdict.
    const standing = STATE_ORDER.map(
      (kind) =>
        [
          kind,
          state.calendar.entries.filter((entry) => entry.user_state === kind)
            .length,
        ] as const,
    ).filter(([, count]) => count > 0);
    const short = new Intl.DateTimeFormat(locale, {
      day: "numeric",
      month: "short",
    });
    const nothing = months.length === 0;
    // What the page is made from, and what it is not.
    const provenance = (
      <p className="text-sm text-muted-foreground">
        {t("desktop.calendar.as_of", { date: asOf })}
      </p>
    );
    const list = (
      <div className="calendar-list @container">
        {months.map(([key, month]) => (
          <section key={key} aria-labelledby={`${heading}-${key}`}>
            {/* Before the month's heading where the whole month is ahead. */}
            {today &&
              key === turning &&
              month.ahead === month.entries.length && (
                <TodayMark on={today} today={here} locale={locale} />
              )}
            <h2
              id={`${heading}-${key}`}
              className={cn(
                "sticky top-(--calendar-head) z-(--layer-separator) border-b bg-background px-4 pt-3 pb-1.5",
                "text-xs font-semibold tracking-wider text-muted-foreground uppercase",
              )}
            >
              {month.title}
            </h2>
            {/* Within the month where today falls between its dates: the
                month is then two lists with the mark between them. */}
            {(today && key === turning && month.ahead < month.entries.length
              ? [
                  month.entries.slice(0, month.entries.length - month.ahead),
                  month.entries.slice(month.entries.length - month.ahead),
                ]
              : [month.entries]
            ).map((entries, part) => (
              <Fragment key={part}>
                {part === 1 && today && (
                  <TodayMark on={today} today={here} locale={locale} />
                )}
                {entries.length > 0 && (
                  <ul>
                    {entries.map((entry) => (
                      <Entry
                        key={entryKey(entry)}
                        entry={entry}
                        locale={locale}
                        selected={selected === entryKey(entry)}
                        onSelect={selectInList}
                        onOpen={onOpen}
                      />
                    ))}
                  </ul>
                )}
              </Fragment>
            ))}
            {/* What was observed that month: the profile's own filing
                history and the agency's messages, each on its day. */}
            {month.events.length > 0 && (
              <ul
                className="calendar-observed"
                aria-label={t("desktop.calendar.observed")}
              >
                {month.events.map((event) => (
                  <li
                    key={event.reference_id}
                    data-event={event.event_type}
                    className="grid grid-cols-[auto_minmax(0,1fr)] items-center gap-x-3 border-b px-4 py-1.5 pl-[calc(--spacing(4)+2px)] text-sm text-muted-foreground"
                  >
                    <span className="grid w-10 justify-items-center">
                      <Icon
                        name={event.event_type === "filing" ? "check" : "mail"}
                        size="sm"
                      />
                    </span>
                    <span className="min-w-0">
                      <time dateTime={event.event_date}>
                        {short.format(day(event.event_date))}
                      </time>
                      {" · "}
                      {t(`desktop.calendar.event.${event.event_type}`)}
                      {" · "}
                      <span className="text-foreground">{event.summary}</span>
                    </span>
                  </li>
                ))}
              </ul>
            )}
          </section>
        ))}
        {today && turning === null && (
          <TodayMark on={today} today={here} locale={locale} />
        )}
      </div>
    );
    const note = coverage.advised.length > 0 && (
      <p className="px-4 py-3 text-sm text-muted-foreground">
        {t("desktop.calendar.undetermined", {
          modelos: coverage.advised.map((item) => item.modelo).join(", "),
        })}
      </p>
    );
    body = (
      <div
        className={cn(
          "calendar-layout",
          wide &&
            !nothing &&
            "grid grid-cols-[minmax(0,1fr)_minmax(20rem,26rem)] items-start",
        )}
      >
        <div className="min-w-0">
          {/* The head stays while the page scrolls under it: the calendar
              opens on the current month, which is seldom the first. Where
              the page is narrow or short only the controls stay, and the
              counts and the sentence scroll with the rest. */}
          <div
            ref={head}
            className="calendar-head contents @md:group-data-[head=whole]/calendar:sticky @md:group-data-[head=whole]/calendar:top-0 @md:group-data-[head=whole]/calendar:z-(--layer-pinned) @md:group-data-[head=whole]/calendar:block @md:group-data-[head=whole]/calendar:border-b @md:group-data-[head=whole]/calendar:bg-background"
          >
            <div className="contents @md:group-data-[head=whole]/calendar:grid @md:group-data-[head=whole]/calendar:grid-cols-[minmax(0,1fr)_auto] @md:group-data-[head=whole]/calendar:items-center @md:group-data-[head=whole]/calendar:gap-x-3 @md:group-data-[head=whole]/calendar:px-4 @md:group-data-[head=whole]/calendar:py-1.5">
              {/* The counts are also the key to the months' colours. With
                  nothing to count, the sentence takes their place. */}
              {standing.length > 0 ? (
                <ul className="calendar-standing flex flex-wrap gap-1.5 px-4 pt-2.5 @md:group-data-[head=whole]/calendar:p-0">
                  {standing.map(([kind, count]) => (
                    <li key={kind} className="flex">
                      <Badge variant={STATE_TONE[kind]}>
                        {t(`desktop.calendar.state.${kind}`)}{" "}
                        <span className="font-semibold tabular-nums">
                          {count}
                        </span>
                      </Badge>
                    </li>
                  ))}
                </ul>
              ) : (
                <div className="px-4 pt-2.5 @md:group-data-[head=whole]/calendar:p-0">
                  {provenance}
                </div>
              )}
              <div
                ref={bar}
                className="calendar-controls sticky top-0 z-(--layer-pinned) flex items-center justify-end gap-2 border-b bg-background px-4 py-1 @md:group-data-[head=whole]/calendar:static @md:group-data-[head=whole]/calendar:border-b-0 @md:group-data-[head=whole]/calendar:p-0"
              >
                {/* One face at a time where there is no room for both. */}
                {!wide && !nothing && (
                  <SegmentedControl
                    className="calendar-view"
                    aria-label={t("desktop.calendar.view")}
                    value={view}
                    onValueChange={(next) =>
                      setView(next === "list" ? "list" : "months")
                    }
                  >
                    <SegmentedControlItem value="months">
                      {t("desktop.calendar.view_months")}
                    </SegmentedControlItem>
                    <SegmentedControlItem value="list">
                      {t("desktop.calendar.view_list")}
                    </SegmentedControlItem>
                  </SegmentedControl>
                )}
                <IconButton
                  label={t("desktop.calendar.refresh")}
                  pending={refreshing}
                  onClick={onRefresh}
                >
                  {!refreshing && <Icon name="reset" />}
                </IconButton>
              </div>
            </div>
            {standing.length > 0 && (
              <div className="border-b px-4 py-1.5 @md:group-data-[head=whole]/calendar:border-b-0 @md:group-data-[head=whole]/calendar:pt-0 @md:group-data-[head=whole]/calendar:pb-2">
                {provenance}
              </div>
            )}
          </div>
          {warnings.length > 0 && (
            <Alert
              tone="warning"
              className="mx-4 mt-3 w-auto"
              icon={<Icon name="alert" />}
            >
              <p>{t("desktop.calendar.warnings")}</p>
              <ul className="mt-1 grid gap-0.5 text-sm">
                {warnings.map((warning) => (
                  <li key={warning.code + warning.affected_modelos.join()}>
                    {warning.message}
                  </li>
                ))}
              </ul>
            </Alert>
          )}
          {nothing ? (
            <Empty role="status">
              <EmptyMedia>
                <Icon name="calendar" />
              </EmptyMedia>
              <EmptyDescription>{t("desktop.calendar.empty")}</EmptyDescription>
            </Empty>
          ) : wide || view === "months" ? (
            <CalendarMonths
              calendar={state.calendar}
              locale={locale}
              today={here}
              selected={selected}
              onSelect={selectInMonths}
            />
          ) : (
            list
          )}
          {note}
        </div>
        {/* Beside the months where the page is wide: the list keeps its own
            place and scrolls by itself, as tall as the page. */}
        {wide && !nothing && (
          <div
            ref={aside}
            className="calendar-aside sticky top-0 h-(--calendar-height) overflow-y-auto border-l bg-background [--calendar-head:0px]"
          >
            {list}
          </div>
        )}
      </div>
    );
  }

  return (
    <section
      ref={root}
      tabIndex={-1}
      aria-label={t("desktop.calendar.title")}
      aria-busy={refreshing || undefined}
      data-head={room.tall ? "whole" : "controls"}
      // The month the reader is on, for when the months are laid out anew:
      // the first whose name is in view under the head, or else the last
      // that begins above it. A month that begins in view is still the
      // first to do so when it is put back where it was, so what is kept
      // does not drift from one layout to the next.
      onScroll={(event) => {
        const el = event.currentTarget;
        // A scroll reported while the page is a width the months have not
        // yet been put back for is the new layout's doing, not the
        // reader's: where it left the view is not their place.
        if (el.clientWidth !== widthWas.current) return;
        const edge = el.getBoundingClientRect().top;
        const under = edge + kept() - 1;
        let on: { key: string; top: number } | null = null;
        for (const month of el.querySelectorAll<HTMLElement>(
          ".calendar-month",
        )) {
          const top = month.getBoundingClientRect().top;
          on = { key: month.dataset.month ?? "", top: top - edge };
          if (top >= under) break;
        }
        if (on) anchor.current = on;
      }}
      className="group/calendar calendar-page @container flex min-h-0 flex-1 flex-col overflow-y-auto bg-background focus-visible:-outline-offset-2"
    >
      {body}
    </section>
  );
}
