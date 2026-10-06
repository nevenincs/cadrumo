import type { CalendarEntry, CalendarEvent } from "./views";

// The filing calendar laid out as months of weeks. This is arithmetic on the
// dates the product gave and nothing else: which day falls in which column,
// which week a filing window crosses, and which row of a week it takes so
// that two windows never share one. No date is derived that the product did
// not state.

/** One obligation's window as it crosses one week of one month. */
export type GridBar = {
  entry: CalendarEntry;
  /** First and last column it covers in this week, 0 to 6. */
  from: number;
  to: number;
  /** The row it takes among the week's windows, from 0. */
  lane: number;
  /** Whether the window opens, and closes, inside this segment. A segment
   * that does neither is the middle of a longer window. */
  opens: boolean;
  closes: boolean;
  /** Whether this is the first the calendar draws of the obligation. One
   * obligation crosses many weeks; it is one thing to reach and to hear. */
  first: boolean;
};

export type GridDay = {
  /** The day as an ISO date. */
  iso: string;
  day: number;
  today: boolean;
  /** What was observed on this day. */
  events: CalendarEvent[];
};

export type GridWeek = {
  /** Seven cells; null before the month's first day and after its last. */
  days: (GridDay | null)[];
  bars: GridBar[];
  /** How many rows the week's windows take. */
  lanes: number;
};

export type GridMonth = {
  /** `2026-10`. */
  key: string;
  year: number;
  /** 1 to 12. */
  month: number;
  weeks: GridWeek[];
};

const DAY_MS = 86_400_000;

/** An ISO date as a count of days, in UTC so that no zone or clock change
 * can make a day longer or shorter. */
const ordinal = (iso: string): number => {
  const [year = 1970, month = 1, day = 1] = iso.split("-").map(Number);
  return Math.round(Date.UTC(year, month - 1, day) / DAY_MS);
};

const isoOf = (year: number, month: number, day: number) =>
  `${year}-${String(month).padStart(2, "0")}-${String(day).padStart(2, "0")}`;

/** The identity of an obligation: its Modelo and period. */
export const entryKey = (entry: CalendarEntry) =>
  `${entry.modelo}:${entry.period}`;

/**
 * The days an obligation is drawn across: from the day its filing window
 * opens to the day it closes in effect. Where the opening is not known the
 * window is not guessed: only its closing day is drawn.
 */
export function entrySpan(entry: CalendarEntry): { from: string; to: string } {
  const to = entry.adjusted_closes_on;
  const from =
    entry.opens_on !== null && entry.opens_on <= to ? entry.opens_on : to;
  return { from, to };
}

/**
 * The months from the first to the last of the range, each as weeks that
 * begin on `weekStart` (0 Sunday to 6 Saturday), with the windows that cross
 * each week placed in rows and the day's observed events on their days.
 */
export function calendarMonths(
  range: { from_date: string; to_date: string },
  entries: readonly CalendarEntry[],
  events: readonly CalendarEvent[],
  today: string | null,
  weekStart: number,
): GridMonth[] {
  const spans = entries
    .map((entry) => {
      const span = entrySpan(entry);
      return { entry, from: ordinal(span.from), to: ordinal(span.to) };
    })
    // Earlier first, and of two that open together the longer first, so a
    // long window keeps one row and short ones fill in around it.
    .sort(
      (a, b) =>
        a.from - b.from ||
        b.to - a.to ||
        entryKey(a.entry).localeCompare(entryKey(b.entry)),
    );
  const observed = new Map<string, CalendarEvent[]>();
  for (const event of events) {
    const day = event.event_date.slice(0, 10);
    observed.set(day, [...(observed.get(day) ?? []), event]);
  }

  const [firstYear = 1970, firstMonth = 1] = range.from_date
    .split("-")
    .map(Number);
  const [lastYear = 1970, lastMonth = 1] = range.to_date.split("-").map(Number);
  const months: GridMonth[] = [];
  const drawn = new Set<CalendarEntry>();
  for (
    let year = firstYear, month = firstMonth;
    year < lastYear || (year === lastYear && month <= lastMonth);
    month === 12 ? ((month = 1), (year += 1)) : (month += 1)
  ) {
    const length = new Date(Date.UTC(year, month, 0)).getUTCDate();
    const first = ordinal(isoOf(year, month, 1));
    const last = first + length - 1;
    // The column of the month's first day.
    const lead =
      (new Date(Date.UTC(year, month - 1, 1)).getUTCDay() - weekStart + 7) % 7;
    const weeks: GridWeek[] = [];
    for (let start = first - lead; start <= last; start += 7) {
      const days = Array.from({ length: 7 }, (_, column): GridDay | null => {
        const at = start + column;
        if (at < first || at > last) return null;
        const day = at - first + 1;
        const iso = isoOf(year, month, day);
        return {
          iso,
          day,
          today: iso === today,
          events: observed.get(iso) ?? [],
        };
      });
      // What of each window lies in this week and in this month.
      const from = Math.max(start, first);
      const to = Math.min(start + 6, last);
      const taken: number[] = [];
      const bars: GridBar[] = [];
      for (const span of spans) {
        if (span.to < from || span.from > to) continue;
        const begin = Math.max(span.from, from);
        const end = Math.min(span.to, to);
        // The first row whose last window ended before this one begins.
        let lane = taken.findIndex((until) => until < begin);
        if (lane < 0) lane = taken.length;
        taken[lane] = end;
        bars.push({
          entry: span.entry,
          from: begin - start,
          to: end - start,
          lane,
          opens: span.from >= begin,
          closes: span.to <= end,
          first: !drawn.has(span.entry),
        });
        drawn.add(span.entry);
      }
      weeks.push({ days, bars, lanes: taken.length });
    }
    months.push({ key: isoOf(year, month, 1).slice(0, 7), year, month, weeks });
  }
  return months;
}

/** The first day of the week where `locale` is spoken, 0 Sunday to 6
 * Saturday. Monday where the platform cannot say. */
export function weekStartOf(locale: string): number {
  try {
    const described = new Intl.Locale(locale) as Intl.Locale & {
      getWeekInfo?: () => { firstDay?: number };
      weekInfo?: { firstDay?: number };
    };
    const first =
      described.getWeekInfo?.().firstDay ?? described.weekInfo?.firstDay;
    // The platform counts Monday as 1 and Sunday as 7.
    if (typeof first === "number") return first % 7;
  } catch {
    // An unknown locale has no week of its own.
  }
  return 1;
}
