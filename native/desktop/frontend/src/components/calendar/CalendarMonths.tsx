import { memo, useEffect, useMemo, useRef, useState } from "react";
import {
  calendarMonths,
  crowded,
  drawnWeeks,
  weekStartOf,
} from "@/shell/calendarGrid";
import { evaluatedDay } from "@/shell/calendar";
import type { FilingCalendar } from "@/shell/views";
import { CalendarMonth } from "./CalendarMonth";

/**
 * The filing calendar as months: each obligation drawn across the days its
 * filing window is open, ending on the day that binds, with what was
 * observed standing on its own day and today marked. It is the overview the
 * list beside it gives the detail of, and choosing a window in one shows it
 * in the other.
 *
 * It is drawn again only when what it shows changes: a page that gains or
 * loses the list beside it, at a change of width, draws the months as they
 * are.
 */
export const CalendarMonths = memo(function CalendarMonths({
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
  // A choice, or a month drawn whole, can move an obligation's stop to
  // another of its weeks. Where the keyboard was on the part that is no
  // longer the stop, it goes to the part that is: it is never left on a
  // part hidden from assistive technology.
  const all = useRef<HTMLDivElement>(null);
  useEffect(() => {
    const held = document.activeElement;
    if (
      !(held instanceof HTMLElement) ||
      !all.current?.contains(held) ||
      held.getAttribute("aria-hidden") !== "true"
    )
      return;
    const entry = held.getAttribute("data-entry");
    if (entry === null) return;
    // The keyboard goes where it can be seen. A pointer chose what it was
    // on, which stays under it: the view is not taken from the hand.
    const byKeyboard = held.matches(":focus-visible");
    all.current
      .querySelector<HTMLElement>(
        `.calendar-bar[data-entry="${CSS.escape(entry)}"]:not([tabindex="-1"])`,
      )
      ?.focus({ preventScroll: !byKeyboard });
  }, [drawn]);
  return (
    <div
      ref={all}
      className="calendar-months grid calendar-month-grid gap-x-4 gap-y-5 p-2 @md:p-4"
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
        <CalendarMonth
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
});
