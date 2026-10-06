import type { CalendarEntry, CalendarEvent, CalendarUserState } from "./views";

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

/** The product's readings in the order they need the person: what is late
 * first, what is filed last. */
export const STATE_ORDER: readonly CalendarUserState[] = [
  "late",
  "due",
  "unknown",
  "filed",
];

/** Which of two obligations needs the person first: by its reading, then by
 * the day it binds, the sooner first. */
const urgency = (a: CalendarEntry, b: CalendarEntry) =>
  STATE_ORDER.indexOf(a.user_state) - STATE_ORDER.indexOf(b.user_state) ||
  a.adjusted_closes_on.localeCompare(b.adjusted_closes_on) ||
  entryKey(a).localeCompare(entryKey(b));

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
 * The months from the first of the range to its last, or to the month the
 * last window open in it closes, each as weeks that
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
    // Earlier first, and of two that open together the one that needs the
    // person first: what is late, then the nearest deadline, takes the
    // first row.
    .sort((a, b) => a.from - b.from || urgency(a.entry, b.entry));
  const observed = new Map<string, CalendarEvent[]>();
  for (const event of events) {
    const day = event.event_date.slice(0, 10);
    observed.set(day, [...(observed.get(day) ?? []), event]);
  }

  const [firstYear = 1970, firstMonth = 1] = range.from_date
    .split("-")
    .map(Number);
  // The months run to the range's last, and on to the month in which the
  // last window open in the range closes: its closing day is what the
  // calendar is for, and the list names that month. Never more than a year
  // past the range, whatever a date says.
  const rangeEnd = ordinal(range.to_date);
  // A window whose opening is not known was returned for the range too:
  // its closing day is all there is of it to draw.
  const latest = spans.reduce(
    (far, span) =>
      (span.from <= rangeEnd || span.entry.opens_on === null) && span.to > far
        ? span.to
        : far,
    rangeEnd,
  );
  const until = new Date(Math.min(latest, rangeEnd + 366) * DAY_MS);
  const lastYear = until.getUTCFullYear();
  const lastMonth = until.getUTCMonth() + 1;
  const months: GridMonth[] = [];
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
        });
      }
      weeks.push({ days, bars, lanes: taken.length });
    }
    months.push({ key: isoOf(year, month, 1).slice(0, 7), year, month, weeks });
  }
  return months;
}

/** How many rows of windows a week shows before it says how many more
 * there are. The last of them is the row that says so. */
export const LANES_SHOWN = 4;

/** Whether any week of a month has more windows than it shows at once. */
export const crowded = (month: GridMonth, cap: number = LANES_SHOWN) =>
  month.weeks.some((week) => week.lanes > cap);

/** A week as it is drawn. */
export type DrawnWeek = {
  /** The windows drawn, each in its row. `stop` marks the one part of its
   * obligation that the keyboard reaches and that is read aloud: one
   * obligation crosses many weeks, and is one thing to reach and to hear. */
  bars: { bar: GridBar; lane: number; stop: boolean }[];
  /** The windows left out, for the row that counts them. */
  hidden: GridBar[];
};

const overlap = (a: GridBar, b: GridBar) => a.from <= b.to && b.from <= a.to;

/** The windows of `bars` in rows, none sharing a day with another of its
 * row, as few rows as there can be: in the order they are given. */
function rows(bars: readonly GridBar[]): { bar: GridBar; lane: number }[] {
  const placed: { bar: GridBar; lane: number }[] = [];
  for (const bar of bars) {
    let lane = 0;
    while (placed.some((at) => at.lane === lane && overlap(at.bar, bar)))
      lane += 1;
    placed.push({ bar, lane });
  }
  return placed;
}

/**
 * What of a week with more windows than `cap` rows is drawn: as many as
 * fit in one row fewer, the last being the count's. What needs the person
 * most is kept first, and of those what closes soonest; what is `chosen`
 * is kept before any of them.
 */
function kept(
  week: GridWeek,
  cap: number,
  chosen: string | null,
): { shown: { bar: GridBar; lane: number }[]; hidden: GridBar[] } {
  const ranked = [...week.bars].sort(
    (a, b) =>
      Number(entryKey(b.entry) === chosen) -
        Number(entryKey(a.entry) === chosen) || urgency(a.entry, b.entry),
  );
  const order = new Map(week.bars.map((bar, index) => [bar, index]));
  const byOrder = (a: GridBar, b: GridBar) =>
    (order.get(a) ?? 0) - (order.get(b) ?? 0);
  // Laid out from the left, a set of windows takes the fewest rows it can:
  // that is the measure of whether one more fits, and the layout drawn.
  // Whatever was kept first, a window drawn before it was chosen is then in
  // the row it was in.
  const laid = (bars: readonly GridBar[]) =>
    rows([...bars].sort((a, b) => a.from - b.from || byOrder(a, b)));
  const shown: GridBar[] = [];
  const hidden: GridBar[] = [];
  for (const bar of ranked) {
    const room = laid([...shown, bar]).every((at) => at.lane < cap - 1);
    (room ? shown : hidden).push(bar);
  }
  return { shown: laid(shown), hidden: hidden.sort(byOrder) };
}

/**
 * What of each week is drawn when a week shows at most `cap` rows. A week
 * with more keeps what needs the person most and gives its last row to the
 * count of the rest; a month that is `open` is drawn whole. The obligation
 * that is `chosen`, by its key, is never among what is only counted.
 */
export function drawnWeeks(
  months: readonly GridMonth[],
  open: (month: GridMonth) => boolean,
  chosen: string | null = null,
  cap: number = LANES_SHOWN,
): Map<GridWeek, DrawnWeek> {
  const all = (week: GridWeek) => ({
    shown: week.bars.map((bar) => ({ bar, lane: bar.lane })),
    hidden: [] as GridBar[],
  });
  const take = (month: GridMonth, week: GridWeek, key: string | null) =>
    open(month) || week.lanes <= cap ? all(week) : kept(week, cap, key);
  // The parts of the chosen obligation that are drawn whether or not it is
  // chosen. Where it has any, the first of them is its stop, so choosing it
  // does not move the keyboard's place to a part drawn only for the choice.
  const anyway = new Set<GridBar>();
  if (chosen !== null)
    for (const month of months)
      for (const week of month.weeks)
        for (const { bar } of take(month, week, null).shown)
          if (entryKey(bar.entry) === chosen) anyway.add(bar);
  const reached = new Set<CalendarEntry>();
  const drawn = new Map<GridWeek, DrawnWeek>();
  for (const month of months)
    for (const week of month.weeks) {
      const { shown, hidden } = take(month, week, chosen);
      drawn.set(week, {
        bars: shown.map(({ bar, lane }) => {
          const stop =
            !reached.has(bar.entry) &&
            (entryKey(bar.entry) !== chosen ||
              anyway.size === 0 ||
              anyway.has(bar));
          if (stop) reached.add(bar.entry);
          return { bar, lane, stop };
        }),
        hidden,
      });
    }
  return drawn;
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
