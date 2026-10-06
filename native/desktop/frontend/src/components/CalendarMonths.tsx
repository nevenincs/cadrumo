import { useId, useMemo } from "react";
import { cn } from "@/components/ui/cn";
import {
  calendarMonths,
  entryKey,
  entrySpan,
  weekStartOf,
  type GridBar,
  type GridMonth,
} from "../shell/calendarGrid";
import { evaluatedDay } from "../shell/calendar";
import { useStrings } from "../shell/strings";
import type {
  CalendarEvent,
  CalendarUserState,
  FilingCalendar,
} from "../shell/views";

// How a filing window is drawn for each of the product's readings: a wash
// and an edge in the reading's colour, with the words in ink, so the colour
// tells the windows apart and never carries the text.
const BAR_TONE: Record<CalendarUserState, string> = {
  due: "border-border-strong bg-secondary",
  late: "border-destructive/60 bg-destructive/10",
  filed: "border-success/60 bg-success/10",
  unknown: "border-warning/60 bg-warning/10",
};

const EVENT_TONE: Record<CalendarEvent["event_type"], string> = {
  filing: "bg-success",
  message: "bg-muted-foreground",
};

/** An ISO date as a local calendar day: no time, so no zone can move it. */
function day(iso: string): Date {
  const [year = 1970, month = 1, date = 1] = iso.split("-").map(Number);
  return new Date(year, month - 1, date);
}

function Month({
  month,
  locale,
  weekStart,
  selected,
  onSelect,
}: {
  month: GridMonth;
  locale: string;
  weekStart: number;
  selected: string | null;
  onSelect: (key: string) => void;
}) {
  const t = useStrings();
  const heading = useId();
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
  return (
    <div
      // A group, not a region: the list names its months as regions, and
      // the two stand side by side on a wide page.
      role="group"
      className="calendar-month min-w-0 scroll-mt-[calc(var(--calendar-head)+--spacing(3))]"
      aria-labelledby={heading}
      data-month={month.key}
    >
      <h2
        id={heading}
        className="px-1 pb-1.5 text-xs font-semibold tracking-wider text-muted-foreground uppercase"
      >
        {formats.title.format(new Date(month.year, month.month - 1, 1))}
      </h2>
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
                        cell.today
                          ? "calendar-grid-today bg-primary font-semibold text-primary-foreground"
                          : "text-muted-foreground",
                      )}
                    >
                      {cell.day}
                    </span>
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
                                EVENT_TONE[event.event_type],
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
            {week.bars.map((bar) => {
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
                  aria-label={bar.first ? said : undefined}
                  aria-pressed={bar.first ? selected === key : undefined}
                  aria-hidden={bar.first ? undefined : true}
                  tabIndex={bar.first ? undefined : -1}
                  data-selected={selected === key || undefined}
                  title={said}
                  style={{
                    gridColumn: `${bar.from + 1} / ${bar.to + 2}`,
                    gridRow: bar.lane + 2,
                  }}
                  className={cn(
                    "calendar-bar @container flex h-control-xs min-w-0 cursor-pointer items-center border-y px-1 text-xs font-medium text-foreground",
                    "scroll-mt-[calc(var(--calendar-head)+--spacing(8))] hover:brightness-95 focus-visible:z-(--layer-separator) data-selected:ring-2 data-selected:ring-ring data-selected:ring-inset",
                    BAR_TONE[bar.entry.user_state],
                    // A window is closed at the end it has inside this week,
                    // and runs to the edge where it goes on.
                    // The gap between one window's end and the next one's start is
                    // given up under a finger, where a day is barely a fingertip
                    // wide and a window of one day needs all of it.
                    bar.opens && "rounded-l-md border-l pointer-fine:ml-0.5",
                    bar.closes && "rounded-r-md border-r-4 pointer-fine:mr-0.5",
                  )}
                  onClick={() => onSelect(key)}
                >
                  {/* The Modelo is what a window too short for both keeps. */}
                  <span className="shrink-0">{bar.entry.modelo}</span>{" "}
                  <span className="ml-1 min-w-0 truncate font-normal text-muted-foreground @max-[4.5rem]:hidden">
                    {bar.entry.period}
                  </span>
                </button>
              );
            })}
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
  selected,
  onSelect,
}: {
  calendar: FilingCalendar;
  /** The chrome language: for names, and for the day a week begins on. */
  locale: string;
  /** The obligation chosen, by its Modelo and period. */
  selected: string | null;
  onSelect: (key: string) => void;
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
  return (
    <div className="calendar-months grid grid-cols-[repeat(auto-fill,minmax(16rem,1fr))] gap-x-4 gap-y-5 p-2 @md:p-4">
      {months.map((month) => (
        <Month
          key={month.key}
          month={month}
          locale={locale}
          weekStart={weekStart}
          selected={selected}
          onSelect={onSelect}
        />
      ))}
    </div>
  );
}
