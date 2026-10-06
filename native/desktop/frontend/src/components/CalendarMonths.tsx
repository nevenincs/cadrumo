import { useId, useMemo, useRef, useState } from "react";
import { flushSync } from "react-dom";
import { Button } from "@/components/ui/button";
import { cn } from "@/components/ui/cn";
import { Icon } from "@/components/ui/icon";
import {
  calendarMonths,
  crowded,
  drawnWeeks,
  entryKey,
  entrySpan,
  LANES_SHOWN,
  weekStartOf,
  type DrawnWeek,
  type GridBar,
  type GridMonth,
  type GridWeek,
} from "../shell/calendarGrid";
import { evaluatedDay, evaluatedLabel, isoDay as day } from "../shell/calendar";
import { useStrings } from "../shell/strings";
import { EVENT_MARK, STATE_MARK } from "./calendarMarks";
import type { CalendarUserState, FilingCalendar } from "../shell/views";

// How a filing window is drawn for each of the product's readings: a wash
// and an edge in the reading's colour, with the words in ink, so the colour
// never carries the text. Colour is not the only teller: the edge is drawn
// differently for what is late and what is not known, and a window with
// room for it carries the reading's mark. What is filed is drawn hollow,
// what is still to do filled. Where the system forces its own colours the
// wash and the hue are gone: the edge and the mark remain, and what is
// filed takes a double edge in place of its hollow.
const BAR_TONE: Record<CalendarUserState, string> = {
  due: "border-muted-foreground bg-secondary",
  late: "border-dashed border-destructive bg-destructive/10",
  filed:
    "border-success bg-transparent forced-colors:border-y-[3px] forced-colors:border-double",
  unknown: "border-dotted border-warning bg-warning/10",
};

function Month({
  month,
  drawn,
  whole,
  locale,
  today,
  weekStart,
  selected,
  onSelect,
  onWhole,
}: {
  month: GridMonth;
  /** What of each of the month's weeks is drawn. */
  drawn: ReadonlyMap<GridWeek, DrawnWeek>;
  /** Whether a crowded month is drawn whole, for having been asked for;
   * null where the month is not crowded and there is nothing to ask. */
  whole: boolean | null;
  locale: string;
  /** The local day. */
  today: string;
  weekStart: number;
  selected: string | null;
  onSelect: (key: string) => void;
  onWhole: (whole: boolean) => void;
}) {
  const t = useStrings();
  const heading = useId();
  const wholeControl = useRef<HTMLButtonElement>(null);
  const formats = useMemo(
    () => ({
      title: new Intl.DateTimeFormat(locale, {
        month: "long",
        year: "numeric",
      }),
      weekday: new Intl.DateTimeFormat(locale, { weekday: "narrow" }),
      short: new Intl.DateTimeFormat(locale, {
        day: "numeric",
        month: "short",
      }),
      full: new Intl.DateTimeFormat(locale, { dateStyle: "full" }),
    }),
    [locale],
  );
  // The seven weekday letters, from the week's first day. 4 January 1970
  // was a Sunday.
  const weekdays = Array.from({ length: 7 }, (_, column) =>
    formats.weekday.format(new Date(1970, 0, 4 + weekStart + column)),
  );
  // What a window says for itself: its Modelo and period, the days it is
  // open, and where it stands.
  const describe = (bar: GridBar) => {
    const span = entrySpan(bar.entry);
    const days =
      bar.entry.opens_on === null
        ? `${formats.short.format(day(span.to))} (${t("desktop.calendar.window_unknown")})`
        : formats.short.formatRange(day(span.from), day(span.to));
    return `${t("desktop.calendar.modelo", { modelo: bar.entry.modelo })} ${bar.entry.period}, ${days}, ${t(`desktop.calendar.state.${bar.entry.user_state}`)}`;
  };
  const title = formats.title.format(new Date(month.year, month.month - 1, 1));
  const toggle = t(
    whole ? "desktop.calendar.show_fewer" : "desktop.calendar.show_all",
  );
  return (
    <div
      // A group, not a region: the list names its months as regions, and
      // the two stand side by side on a wide page.
      role="group"
      className="calendar-month min-w-0 scroll-mt-[calc(var(--calendar-head)+--spacing(3))]"
      aria-labelledby={heading}
      data-month={month.key}
    >
      <div className="flex items-end justify-between gap-2 px-1 pb-1.5">
        <h2
          id={heading}
          className="text-xs font-semibold tracking-wider text-muted-foreground uppercase"
        >
          {title}
        </h2>
        {/* A crowded month shows the nearest deadlines of each week and
            counts the rest. This is the way to all of it and back, and it
            stays where it is, so the keyboard is never left on nothing. */}
        {whole !== null && (
          <Button
            variant="ghost"
            size="xs"
            ref={wholeControl}
            className="calendar-whole -my-1"
            aria-expanded={whole}
            aria-label={`${toggle}: ${title}`}
            onClick={() => onWhole(!whole)}
          >
            {toggle}
          </Button>
        )}
      </div>
      <div className="overflow-hidden rounded-lg border bg-card">
        <div
          aria-hidden="true"
          className="grid grid-cols-7 border-b bg-chrome py-0.5 text-center text-2xs font-medium text-muted-foreground"
        >
          {weekdays.map((letter, column) => (
            <span key={column}>{letter}</span>
          ))}
        </div>
        {month.weeks.map((week, row) => (
          <div
            key={row}
            className="grid min-h-9 grid-cols-7 content-start gap-y-0.5 border-b pb-0.5 last:border-b-0"
          >
            {week.days.map((cell, column) => (
              <div
                key={column}
                // Explicit places: the windows below are placed the same way,
                // and nothing is left to the order things happen to come in.
                style={{ gridColumn: column + 1, gridRow: 1 }}
                data-day={cell?.iso}
                className="flex min-w-0 items-center justify-between gap-0.5 px-1 pt-0.5"
              >
                {cell && (
                  <>
                    <span
                      aria-hidden="true"
                      className={cn(
                        "grid size-5 place-items-center rounded-full text-xs tabular-nums",
                        // The day the product evaluated: filled where that
                        // day is today here, ringed where it is another.
                        !cell.today
                          ? "text-muted-foreground"
                          : cell.iso === today
                            ? "calendar-grid-today bg-primary font-semibold text-primary-foreground forced-colors:bg-[Highlight] forced-colors:text-[HighlightText]"
                            : "calendar-grid-today border border-primary font-semibold text-foreground",
                      )}
                      data-today={cell.today ? cell.iso === today : undefined}
                    >
                      {cell.day}
                    </span>
                    {cell.today && (
                      <span className="sr-only">
                        {evaluatedLabel(cell.iso, today, locale, true)}
                      </span>
                    )}
                    {cell.events.length > 0 && (
                      <span className="flex gap-0.5">
                        {cell.events.map((event) => {
                          const said = `${formats.full.format(day(cell.iso))}: ${t(`desktop.calendar.event.${event.event_type}`)}. ${event.summary}`;
                          return (
                            <span
                              key={event.reference_id}
                              role="img"
                              aria-label={said}
                              title={said}
                              data-event={event.event_type}
                              className={cn(
                                "calendar-event size-2 rounded-full",
                                EVENT_MARK[event.event_type],
                              )}
                            />
                          );
                        })}
                      </span>
                    )}
                  </>
                )}
              </div>
            ))}
            {(drawn.get(week)?.bars ?? []).map(({ bar, lane, stop }) => {
              const key = entryKey(bar.entry);
              const said = describe(bar);
              return (
                <button
                  key={key}
                  type="button"
                  data-entry={key}
                  data-state={bar.entry.user_state}
                  // An obligation crosses many weeks and is one thing: the
                  // first of it drawn is what the keyboard reaches and what
                  // is read aloud; the rest of it is there for the eye and
                  // the pointer.
                  aria-label={stop ? said : undefined}
                  aria-pressed={stop ? selected === key : undefined}
                  aria-hidden={stop ? undefined : true}
                  tabIndex={stop ? undefined : -1}
                  data-selected={selected === key || undefined}
                  title={said}
                  style={{
                    gridColumn: `${bar.from + 1} / ${bar.to + 2}`,
                    gridRow: lane + 2,
                  }}
                  className={cn(
                    "calendar-bar @container flex h-control-xs min-w-0 cursor-pointer items-center border-y px-1 text-xs font-medium text-foreground",
                    "scroll-mt-[calc(var(--calendar-head)+--spacing(8))] hover:brightness-95 focus-visible:z-(--layer-separator) data-selected:ring-2 data-selected:ring-ring data-selected:ring-inset",
                    // A ring is a shadow, which forced colours do not draw.
                    "forced-colors:data-selected:outline-2 forced-colors:data-selected:-outline-offset-2 forced-colors:data-selected:outline-[Highlight]",
                    BAR_TONE[bar.entry.user_state],
                    // A window is closed at the end it has inside this week,
                    // and runs to the edge where it goes on.
                    // The gap between one window's end and the next one's start is
                    // given up under a finger, where a day is barely a fingertip
                    // wide and a window of one day needs all of it.
                    bar.opens && "rounded-l-md border-l pointer-fine:ml-0.5",
                    bar.closes && "rounded-r-md border-r-4 pointer-fine:mr-0.5",
                  )}
                  onClick={(event) => {
                    onSelect(key);
                    // The rest of a window is for the eye and the pointer:
                    // pressed, the keyboard goes to the part that is the
                    // obligation's stop, without the view moving to it.
                    if (!stop)
                      event.currentTarget
                        .closest(".calendar-months")
                        ?.querySelector<HTMLElement>(
                          `.calendar-bar[data-entry="${CSS.escape(key)}"]:not([tabindex="-1"])`,
                        )
                        ?.focus({ preventScroll: true });
                  }}
                >
                  {STATE_MARK[bar.entry.user_state] && (
                    <Icon
                      name={STATE_MARK[bar.entry.user_state] ?? "info"}
                      size="xs"
                      className="mr-1 @max-[4.5rem]:hidden"
                    />
                  )}
                  {/* The Modelo is what a window too short for more keeps. */}
                  <span className="shrink-0">{bar.entry.modelo}</span>{" "}
                  <span className="ml-1 min-w-0 truncate font-normal text-muted-foreground @max-[4.5rem]:hidden">
                    {bar.entry.period}
                  </span>
                </button>
              );
            })}
            {(drawn.get(week)?.hidden.length ?? 0) > 0 && (
              // The week's last row says how many more windows cross it.
              // For the pointer it also opens the month; the keyboard and a
              // screen reader have the month's own control for that.
              <button
                type="button"
                tabIndex={-1}
                aria-hidden="true"
                className="calendar-more flex h-control-xs min-w-0 cursor-pointer items-center px-1.5 text-left text-xs text-muted-foreground hover:text-foreground hover:underline"
                style={{ gridColumn: "1 / -1", gridRow: LANES_SHOWN + 1 }}
                title={(drawn.get(week)?.hidden ?? [])
                  .map((bar) => `${bar.entry.modelo} ${bar.entry.period}`)
                  .join(", ")}
                onClick={(event) => {
                  // The month grows above and below this week. It is drawn
                  // at once and the week put back where it was pressed, so
                  // what was asked for opens under the pointer.
                  const row = event.currentTarget.parentElement;
                  const page = row?.closest<HTMLElement>(".calendar-page");
                  const was = row?.getBoundingClientRect().top ?? 0;
                  flushSync(() => onWhole(true));
                  if (row && page)
                    page.scrollTop += row.getBoundingClientRect().top - was;
                  // This row goes with what it counted: the keyboard goes to
                  // the control that brings it back, the view unmoved.
                  wholeControl.current?.focus({ preventScroll: true });
                }}
              >
                {t("desktop.calendar.more", {
                  count: drawn.get(week)?.hidden.length ?? 0,
                })}
              </button>
            )}
          </div>
        ))}
      </div>
    </div>
  );
}

/**
 * The filing calendar as months: each obligation drawn across the days its
 * filing window is open, ending on the day that binds, with what was
 * observed standing on its own day and today marked. It is the overview the
 * list beside it gives the detail of, and choosing a window in one shows it
 * in the other.
 */
export function CalendarMonths({
  calendar,
  locale,
  today,
  selected,
  onSelect,
  asked,
  onAsked,
}: {
  calendar: FilingCalendar;
  /** The chrome language: for names, and for the day a week begins on. */
  locale: string;
  /** The local day: the evaluated day is marked as today only where it is
   * this one. */
  today: string;
  /** The obligation chosen, by its Modelo and period. */
  selected: string | null;
  onSelect: (key: string) => void;
  /** The crowded months the person asked to see whole, by their keys. */
  asked: ReadonlySet<string>;
  onAsked: (month: string, whole: boolean) => void;
}) {
  const weekStart = useMemo(() => weekStartOf(locale), [locale]);
  const months = useMemo(
    () =>
      calendarMonths(
        calendar.range,
        calendar.entries,
        calendar.events,
        evaluatedDay(calendar),
        weekStart,
      ),
    [calendar, weekStart],
  );
  // A window deselected with the keyboard on it stays drawn until the
  // keyboard leaves it: what was only drawn for being chosen would otherwise
  // go from under the key that let it go.
  const [lingering, setLingering] = useState<string | null>(null);
  const kept = selected ?? lingering;
  const drawn = useMemo(
    () => drawnWeeks(months, (month) => asked.has(month.key), kept),
    [months, asked, kept],
  );
  return (
    <div
      className="calendar-months grid grid-cols-[repeat(auto-fill,minmax(16rem,1fr))] gap-x-4 gap-y-5 p-2 @md:p-4"
      onBlur={(event) => {
        if (
          lingering !== null &&
          event.relatedTarget?.getAttribute?.("data-entry") !== lingering
        )
          setLingering(null);
      }}
      // From one obligation the arrow keys go to the next and the one
      // before, and Home and End to the first and the last: each is one
      // stop, in the order of the days. Tab still goes through them all.
      onKeyDown={(event) => {
        const from =
          event.target instanceof HTMLElement
            ? event.target.closest<HTMLElement>(".calendar-bar")
            : null;
        if (!from) return;
        const stops = [
          ...event.currentTarget.querySelectorAll<HTMLElement>(
            '.calendar-bar:not([tabindex="-1"])',
          ),
        ];
        const at = stops.indexOf(from);
        const to =
          at < 0
            ? undefined
            : event.key === "ArrowRight" || event.key === "ArrowDown"
              ? stops[at + 1]
              : event.key === "ArrowLeft" || event.key === "ArrowUp"
                ? stops[at - 1]
                : event.key === "Home"
                  ? stops[0]
                  : event.key === "End"
                    ? stops.at(-1)
                    : undefined;
        if (!to || to === from) return;
        event.preventDefault();
        to.focus();
      }}
    >
      {months.map((month) => (
        <Month
          key={month.key}
          month={month}
          drawn={drawn}
          whole={crowded(month) ? asked.has(month.key) : null}
          onWhole={(whole) => onAsked(month.key, whole)}
          locale={locale}
          today={today}
          weekStart={weekStart}
          selected={selected}
          onSelect={(key) => {
            // Let go with the keyboard on it: it stays until that leaves.
            setLingering(
              selected === key &&
                document.activeElement?.getAttribute("data-entry") === key
                ? key
                : null,
            );
            onSelect(key);
          }}
        />
      ))}
    </div>
  );
}
