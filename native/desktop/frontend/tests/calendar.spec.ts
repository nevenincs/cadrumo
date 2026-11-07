import { expect, test } from "@playwright/test";
import { calendarRange, deadlineDistance } from "../src/shell/calendar";
import {
  calendarMonths,
  crowded,
  drawnWeeks,
  LANES_SHOWN,
  weekStartOf,
} from "../src/shell/calendarGrid";
import {
  closeUnknown,
  compareCalendarEntries,
  compareListedEntries,
  entrySpan,
  STATE_ORDER,
} from "../src/shell/calendarEntries";
import type { CalendarEntry } from "../src/shell/views";
import { fixtureDay, fixtureYear } from "../src/dev/fixtureDates";

// The calendar's pure rules, checked at their boundaries. No page is opened.

// Where a case depends on a weekday, its month is found by that shape from the
// fixtures' year on, never assumed: a fixed date does not keep its weekday
// from one year to the next.
type Month = { year: number; month: number };
const monthAfter = (from: Month, by = 1): Month => {
  const at = from.year * 12 + from.month - 1 + by;
  return { year: Math.floor(at / 12), month: (at % 12) + 1 };
};
const lengthOf = ({ year, month }: Month) =>
  new Date(Date.UTC(year, month, 0)).getUTCDate();
/** The weekday its first day falls on, 0 being Sunday. */
const startsOn = ({ year, month }: Month) =>
  new Date(Date.UTC(year, month - 1, 1)).getUTCDay();
const monthKey = ({ year, month }: Month) =>
  `${year}-${String(month).padStart(2, "0")}`;
/** ISO text of a day of the month; a day past its end falls in the months
 * after it, and one before its first in the months before. */
const isoDay = ({ year, month }: Month, day: number) =>
  new Date(Date.UTC(year, month - 1, day)).toISOString().slice(0, 10);
/** The first month from `from` on, every `step` months, of the shape. */
const monthLike = (
  accepts: (month: Month) => boolean,
  from: Month,
  step = 1,
): Month => {
  for (let tries = 0; tries < 400; tries += 1) {
    const month = monthAfter(from, tries * step);
    if (accepts(month)) return month;
  }
  throw new Error("no month of that shape");
};
const THURSDAY = 4;
const FRIDAY = 5;
const TUESDAY = 2;

/** A month of 31 days that begins on a Thursday, from October of the
 * fixtures' year on. */
const MONTH = monthLike(
  (month) => startsOn(month) === THURSDAY && lengthOf(month) === 31,
  { year: fixtureYear, month: 10 },
);
const NEXT = monthAfter(MONTH);
const PRIOR = monthAfter(MONTH, -1);
const day = (number: number) => isoDay(MONTH, number);
/** A December that begins on a Tuesday: its 28th is a Monday and the 1st of
 * the next January a Friday. */
const DECEMBER = monthLike(
  (month) => startsOn(month) === TUESDAY,
  { year: fixtureYear, month: 12 },
  12,
);
const YEAR_START = monthAfter(DECEMBER);
/** A month of 31 days that begins on a Friday, from the January after the
 * fixtures' year on: the first day of the month after it is a Monday. */
const CROWDED = monthLike(
  (month) => startsOn(month) === FRIDAY && lengthOf(month) === 31,
  { year: fixtureYear + 1, month: 1 },
);
const AFTER_CROWDED = monthAfter(CROWDED);
const PERIOD = `${fixtureYear}-3T`;

test("a deadline is said in days up to sixty, then in whole months never rounded up", () => {
  const cases: [number, boolean, number, "day" | "month"][] = [
    [0, false, 0, "day"],
    [1, false, 1, "day"],
    [59, false, 59, "day"],
    [60, false, 60, "day"],
    // Two months have fully to pass by day 61; three only by day 92.
    [61, false, 2, "month"],
    [91, false, 2, "month"],
    [92, false, 3, "month"],
    [118, false, 3, "month"],
    [365, false, 11, "month"],
    [366, false, 12, "month"],
  ];
  for (const [days, overdue, value, unit] of cases)
    expect(deadlineDistance(days, overdue), `${days} days`).toEqual({
      value,
      unit,
    });
});

test("lateness stays in days however long", () => {
  expect(deadlineDistance(-78, true)).toEqual({ value: -78, unit: "day" });
  expect(deadlineDistance(-400, true)).toEqual({ value: -400, unit: "day" });
  // A count the product gave is never turned into months, even at zero.
  expect(deadlineDistance(0, true)).toEqual({ value: 0, unit: "day" });
});

test("the range asked for is a year of whole months around today", () => {
  expect(calendarRange(new Date(fixtureYear, 9, 6))).toEqual({
    from: fixtureDay(7, 1),
    to: fixtureDay(6, 30, 1),
  });
  // Across a year's end, and into a leap February.
  const leap = monthLike(
    (month) => lengthOf(month) === 29,
    { year: fixtureYear + 1, month: 2 },
    12,
  );
  expect(calendarRange(new Date(leap.year - 1, 5, 15))).toEqual({
    from: isoDay({ year: leap.year - 1, month: 3 }, 1),
    to: isoDay(leap, 29),
  });
  expect(calendarRange(new Date(fixtureYear, 0, 31))).toEqual({
    from: fixtureDay(10, 1, -1),
    to: fixtureDay(9, 30),
  });
});

// The month grid's arithmetic: which column a day falls in, which weeks a
// filing window crosses, and which row of a week it takes.
const obligation = (
  modelo: string,
  opens: string | null,
  closes: string,
  adjusted = closes,
): CalendarEntry => ({
  modelo,
  period: PERIOD,
  opens_on: opens,
  closes_on: closes,
  adjusted_closes_on: adjusted,
  shift_reason: "none",
  payment_cutoff_on: null,
  evaluated_on: day(6),
  days_overdue: null,
  status: "UPCOMING",
  user_state: "due",
  local_filing_state: "not_ready_to_file",
  aeat_submission_state: "not_observed",
  justificante_verified: false,
});

/** A projected window whose close the product could not work out: its
 * closing dates are only the earliest it can close. */
const unknownClose = (
  modelo: string,
  opens: string | null,
  earliest: string,
): CalendarEntry => ({
  ...obligation(modelo, opens, earliest),
  status: "UNKNOWN",
  user_state: "unknown",
});

const RANGE = { from_date: day(1), to_date: day(31) };

test("only the product's unknown status makes a close unknown, never a reading or a date", () => {
  expect(closeUnknown(unknownClose("303", day(1), day(20)))).toBe(true);
  // A reading the product could not place is not a close it could not
  // work out.
  expect(
    closeUnknown({
      ...obligation("349", null, day(20)),
      status: "NOT_APPLICABLE",
      user_state: "unknown",
    }),
  ).toBe(false);
  expect(closeUnknown(obligation("130", day(1), day(20)))).toBe(false);
});

test("a close that is not known follows the known ones, in its reading and in its month", () => {
  const entries = [
    unknownClose("111", day(1), day(2)),
    {
      ...obligation("349", null, day(25)),
      status: "NOT_APPLICABLE" as const,
      user_state: "unknown" as const,
    },
    obligation("303", null, day(30)),
    unknownClose("123", isoDay(PRIOR, 1), isoDay(PRIOR, 20)),
    obligation("130", null, day(20)),
    obligation("202", null, isoDay(PRIOR, 25)),
  ];
  // Among what needs the person, by reading: the known closes of the
  // unknown reading first, by date; the closes not known after them.
  expect(
    [...entries].sort(compareCalendarEntries).map((entry) => entry.modelo),
  ).toEqual(["202", "130", "303", "349", "123", "111"]);
  // In the list, by month of the earliest close; within it the known
  // closes by date, then those not known, however early theirs is.
  expect(
    [...entries].sort(compareListedEntries).map((entry) => entry.modelo),
  ).toEqual(["202", "123", "130", "349", "303", "111"]);
});

test("a window whose close is not known runs to its earliest close and is never drawn closing", () => {
  const unknown = unknownClose("303", day(1), day(20));
  expect(entrySpan(unknown)).toEqual({ from: day(1), to: day(20) });
  const [month] = calendarMonths(
    RANGE,
    [unknown, obligation("130", day(1), day(20))],
    [],
    null,
    1,
  );
  const ends = month?.weeks
    .flatMap((week) => week.bars)
    .filter((bar) => bar.to === 1 && bar.entry.closes_on === day(20))
    .map((bar) => [bar.entry.modelo, bar.opens, bar.closes]);
  // The week of the 20th: the known window closes there, the other does not.
  expect(ends).toEqual([
    ["130", false, true],
    ["303", false, false],
  ]);
  // Where it opens it is still drawn opening.
  expect(
    month?.weeks[0]?.bars.map((bar) => [bar.entry.modelo, bar.opens]),
  ).toEqual([
    ["130", true],
    ["303", true],
  ]);
});

test("calendar faces share urgency ordering with deterministic date and identity ties", () => {
  const entries = [
    { ...obligation("303", null, day(20)), user_state: "filed" as const },
    {
      ...obligation("130", null, day(19)),
      user_state: "unknown" as const,
    },
    obligation("349", null, day(20)),
    obligation("303", null, day(20)),
    obligation("130", null, day(19)),
    { ...obligation("303", null, day(30)), user_state: "late" as const },
  ];
  expect(STATE_ORDER).toEqual(["late", "due", "unknown", "filed"]);
  expect(
    entries
      .sort(compareCalendarEntries)
      .map((entry) => `${entry.user_state}:${entry.modelo}`),
  ).toEqual([
    "late:303",
    "due:130",
    "due:303",
    "due:349",
    "unknown:130",
    "filed:303",
  ]);
});

test("a month is weeks from the locale's first day, blank outside the month", () => {
  // The month begins on a Thursday.
  const [monday] = calendarMonths(RANGE, [], [], day(6), 1);
  expect(monday?.key).toBe(monthKey(MONTH));
  expect(monday?.weeks).toHaveLength(5);
  expect(monday?.weeks[0]?.days.map((day) => day?.day ?? null)).toEqual([
    null,
    null,
    null,
    1,
    2,
    3,
    4,
  ]);
  expect(monday?.weeks[4]?.days.map((day) => day?.day ?? null)).toEqual([
    26,
    27,
    28,
    29,
    30,
    31,
    null,
  ]);
  // The day the product evaluated, and no other.
  const todays = monday?.weeks.flatMap((week) =>
    week.days.filter((day) => day?.today).map((day) => day?.iso),
  );
  expect(todays).toEqual([day(6)]);
  // From Sunday, the same month begins a column later.
  const [sunday] = calendarMonths(RANGE, [], [], null, 0);
  expect(sunday?.weeks[0]?.days.map((day) => day?.day ?? null)).toEqual([
    null,
    null,
    null,
    null,
    1,
    2,
    3,
  ]);
});

test("a filing window is drawn across every week it crosses", () => {
  const [month] = calendarMonths(
    RANGE,
    [obligation("303", day(1), day(20))],
    [],
    null,
    1,
  );
  const drawn = month?.weeks.map((week) =>
    week.bars.map((bar) => [bar.from, bar.to, bar.opens, bar.closes]),
  );
  expect(drawn).toEqual([
    [[3, 6, true, false]],
    [[0, 6, false, false]],
    [[0, 6, false, false]],
    [[0, 1, false, true]],
    [],
  ]);
});

test("the window ends on the day that binds, and an unknown opening is not guessed", () => {
  const [month] = calendarMonths(
    RANGE,
    [
      // Closes on a Saturday, moved to the Monday.
      obligation("130", day(1), day(17), day(19)),
      obligation("349", null, day(20)),
    ],
    [],
    null,
    1,
  );
  expect(entrySpan(obligation("130", day(1), day(17), day(19)))).toEqual({
    from: day(1),
    to: day(19),
  });
  expect(entrySpan(obligation("349", null, day(20)))).toEqual({
    from: day(20),
    to: day(20),
  });
  // Week of the 19th: the moved window ends on Monday, the other is one day.
  const week = month?.weeks[3];
  expect(
    week?.bars.map((bar) => [bar.entry.modelo, bar.from, bar.to, bar.lane]),
  ).toEqual([
    ["130", 0, 0, 0],
    ["349", 1, 1, 0],
  ]);
  expect(week?.lanes).toBe(1);
});

test("windows that overlap take rows of their own, the nearer deadline keeping the first", () => {
  const [month] = calendarMonths(
    RANGE,
    [
      obligation("111", day(1), day(20)),
      obligation("303", day(1), day(20)),
      obligation("100", day(1), day(30)),
      obligation("216", day(26), day(28)),
    ],
    [],
    null,
    1,
  );
  const first = month?.weeks[0];
  expect(first?.lanes).toBe(3);
  expect(first?.bars.map((bar) => [bar.entry.modelo, bar.lane])).toEqual([
    ["111", 0],
    ["303", 1],
    ["100", 2],
  ]);
  // No two in a week share a row where they share a day.
  for (const week of month?.weeks ?? [])
    for (const a of week.bars)
      for (const b of week.bars)
        if (a !== b && a.lane === b.lane)
          expect(a.to < b.from || b.to < a.from).toBe(true);
  // A row freed by a window that has closed is taken again.
  const last = month?.weeks[4];
  expect(last?.bars.map((bar) => [bar.entry.modelo, bar.lane])).toEqual([
    ["100", 0],
    ["216", 1],
  ]);
});

test("a window across months is drawn in each, open at the edge it continues from", () => {
  const months = calendarMonths(
    { from_date: isoDay(DECEMBER, 1), to_date: isoDay(YEAR_START, 31) },
    [obligation("390", isoDay(DECEMBER, 28), isoDay(YEAR_START, 5))],
    [],
    null,
    1,
  );
  expect(months.map((month) => month.key)).toEqual([
    monthKey(DECEMBER),
    monthKey(YEAR_START),
  ]);
  const bars = months.map((month) =>
    month.weeks.flatMap((week) =>
      week.bars.map((bar) => [bar.from, bar.to, bar.opens, bar.closes]),
    ),
  );
  expect(bars).toEqual([
    // Monday 28 to Thursday 31 December: it opens here and goes on.
    [[0, 3, true, false]],
    // Friday 1 to Sunday 3 January, then Monday 4 and Tuesday 5.
    [
      [4, 6, false, false],
      [0, 1, false, true],
    ],
  ]);
});

test("what was observed stands on its own day", () => {
  const event = {
    event_type: "filing" as const,
    event_date: day(2),
    source: "filed_declarations",
    summary: `Modelo 111 ${PERIOD} filed`,
    reference_id: "ref-1",
    status: "presentado",
    aeat_submission_state: "submitted_observed" as const,
    aeat_submitted_at: `${day(2)}T08:15:00Z`,
    justificante_verified: false,
  };
  const [month] = calendarMonths(RANGE, [], [event], null, 1);
  const withEvents = month?.weeks.flatMap((week) =>
    week.days.filter((day) => day && day.events.length > 0),
  );
  expect(withEvents?.map((day) => [day?.iso, day?.events.length])).toEqual([
    [day(2), 1],
  ]);
});

// The edges of the arithmetic: the ends of the range, of the year, and data
// that is not as it should be.
const bars = (months: ReturnType<typeof calendarMonths>) => {
  // Drawn whole: the first of each obligation is then its first anywhere.
  const drawn = drawnWeeks(months, () => true);
  return months.flatMap((month) =>
    month.weeks.flatMap((week) =>
      (drawn.get(week)?.bars ?? []).map(({ bar, stop }) => ({
        month: month.key,
        days: [
          week.days[bar.from]?.day ?? null,
          week.days[bar.to]?.day ?? null,
        ],
        lane: bar.lane,
        opens: bar.opens,
        closes: bar.closes,
        first: stop,
        modelo: bar.entry.modelo,
      })),
    ),
  );
};

test("a window that crosses the year's end is drawn in both years, and is first once", () => {
  const drawn = bars(
    calendarMonths(
      { from_date: isoDay(DECEMBER, 1), to_date: isoDay(YEAR_START, 31) },
      [obligation("303", isoDay(DECEMBER, 28), isoDay(YEAR_START, 5))],
      [],
      null,
      1,
    ),
  );
  // The 28th of December is a Monday; the 1st of January a Friday.
  expect(drawn).toEqual([
    {
      month: monthKey(DECEMBER),
      days: [28, 31],
      lane: 0,
      opens: true,
      closes: false,
      first: true,
      modelo: "303",
    },
    {
      month: monthKey(YEAR_START),
      days: [1, 3],
      lane: 0,
      opens: false,
      closes: false,
      first: false,
      modelo: "303",
    },
    {
      month: monthKey(YEAR_START),
      days: [4, 5],
      lane: 0,
      opens: false,
      closes: true,
      first: false,
      modelo: "303",
    },
  ]);
});

test("a window wider than the range is drawn through to its closing day, and no window stretches the months without bound", () => {
  const months = calendarMonths(
    RANGE,
    [
      obligation("100", isoDay(PRIOR, 15), isoDay(NEXT, 10)),
      // Closed before the range began.
      obligation(
        "111",
        isoDay(monthAfter(MONTH, -2), 1),
        isoDay(monthAfter(MONTH, -2), 20),
      ),
    ],
    [],
    null,
    1,
  );
  // The month the window closes in is drawn after the range's own: the
  // closing day is what the calendar is for.
  expect(months.map((month) => month.key)).toEqual([
    monthKey(MONTH),
    monthKey(NEXT),
  ]);
  const drawn = bars(months);
  // One segment for each week it crosses, from the first of October, where
  // it was already open, to the tenth of November, where it closes. The
  // first of the next month is a Sunday.
  expect(drawn.map((bar) => [bar.month, ...bar.days])).toEqual([
    [monthKey(MONTH), 1, 4],
    [monthKey(MONTH), 5, 11],
    [monthKey(MONTH), 12, 18],
    [monthKey(MONTH), 19, 25],
    [monthKey(MONTH), 26, 31],
    [monthKey(NEXT), 1, 1],
    [monthKey(NEXT), 2, 8],
    [monthKey(NEXT), 9, 10],
  ]);
  expect(drawn.every((bar) => bar.modelo === "100")).toBe(true);
  expect(drawn.some((bar) => bar.opens)).toBe(false);
  expect(drawn.map((bar) => bar.closes)).toEqual([
    false,
    false,
    false,
    false,
    false,
    false,
    false,
    true,
  ]);
  expect(drawn.filter((bar) => bar.first)).toHaveLength(1);
  expect(drawn[0]?.first).toBe(true);
  // A window that is not open in the range does not stretch it.
  expect(
    calendarMonths(
      RANGE,
      [obligation("115", isoDay(NEXT, 2), isoDay(monthAfter(MONTH, 2), 20))],
      [],
      null,
      1,
    ).map((month) => month.key),
  ).toEqual([monthKey(MONTH)]);
  // Nor does a closing date years away draw years of months: a year past
  // the range at most.
  const far = calendarMonths(
    RANGE,
    [obligation("100", day(1), isoDay(monthAfter(MONTH, 51), 1))],
    [],
    null,
    1,
  );
  // A year is at most 366 days past the range's last day.
  const latest = new Date(Date.parse(day(31)) + 366 * 24 * 60 * 60 * 1000);
  const lastMonth = {
    year: latest.getUTCFullYear(),
    month: latest.getUTCMonth() + 1,
  };
  expect(far).toHaveLength(
    (lastMonth.year - MONTH.year) * 12 + lastMonth.month - MONTH.month + 1,
  );
  expect(far.at(-1)?.key).toBe(monthKey(lastMonth));
});

test("an opening after its close is not believed: the closing day alone is drawn", () => {
  const entry = obligation("130", day(25), day(20));
  expect(entrySpan(entry)).toEqual({ from: day(20), to: day(20) });
  expect(bars(calendarMonths(RANGE, [entry], [], null, 1))).toEqual([
    {
      month: monthKey(MONTH),
      days: [20, 20],
      lane: 0,
      opens: true,
      closes: true,
      first: true,
      modelo: "130",
    },
  ]);
});

test("many windows over the same days each keep a row, and a row is taken again once free", () => {
  const months = calendarMonths(
    RANGE,
    [
      ...["111", "115", "123", "130", "303", "349"].map((modelo) =>
        obligation(modelo, day(5), day(7)),
      ),
      // After the six have closed, in the same week.
      obligation("216", day(9), day(11)),
    ],
    [],
    null,
    1,
  );
  const week = months[0]?.weeks[1];
  expect(week?.lanes).toBe(6);
  expect(week?.bars.map((bar) => [bar.entry.modelo, bar.lane])).toEqual([
    ["111", 0],
    ["115", 1],
    ["123", 2],
    ["130", 3],
    ["303", 4],
    ["349", 5],
    ["216", 0],
  ]);
  // No two windows of a row share a day.
  for (const lane of [0, 1, 2, 3, 4, 5]) {
    const taken = (week?.bars ?? [])
      .filter((bar) => bar.lane === lane)
      .flatMap((bar) =>
        Array.from(
          { length: bar.to - bar.from + 1 },
          (_, day) => bar.from + day,
        ),
      );
    expect(new Set(taken).size).toBe(taken.length);
  }
});

const LEAP_FEBRUARY = monthLike(
  (month) => lengthOf(month) === 29,
  { year: fixtureYear, month: 2 },
  12,
);

test("a leap February has its twenty-ninth day", () => {
  const [february] = calendarMonths(
    { from_date: isoDay(LEAP_FEBRUARY, 1), to_date: isoDay(LEAP_FEBRUARY, 29) },
    [],
    [],
    null,
    1,
  );
  const days = february?.weeks.flatMap((week) =>
    week.days.filter((day) => day !== null).map((day) => day.day),
  );
  expect(days).toHaveLength(29);
  expect(days?.at(-1)).toBe(29);
  // The 29th stands in the column of its weekday, the week beginning on Monday.
  const column =
    (new Date(Date.UTC(LEAP_FEBRUARY.year, 1, 29)).getUTCDay() + 6) % 7;
  expect(february?.weeks.at(-1)?.days[column]?.iso).toBe(
    isoDay(LEAP_FEBRUARY, 29),
  );
});

test("what was observed with a time of day stands on its date", () => {
  const event = {
    event_type: "filing" as const,
    event_date: `${day(2)}T08:15:00Z`,
    source: "filed_declarations",
    summary: "Filed",
    reference_id: "a",
    status: null,
    aeat_submission_state: null,
    aeat_submitted_at: null,
    justificante_verified: null,
  };
  const [october] = calendarMonths(RANGE, [], [event], null, 1);
  const on = october?.weeks.flatMap((week) =>
    week.days.filter((day) => (day?.events.length ?? 0) > 0),
  );
  expect(on?.map((day) => day?.iso)).toEqual([day(2)]);
});

test("the week begins on the day the language begins it, and on Monday where it cannot say", () => {
  expect(weekStartOf("en-US")).toBe(0);
  expect(weekStartOf("es")).toBe(1);
  expect(weekStartOf("ca")).toBe(1);
  expect(weekStartOf("hu")).toBe(1);
  expect(weekStartOf("ar-EG")).toBe(6);
  expect(weekStartOf("not a locale")).toBe(1);
});

// A crowded week shows its nearest deadlines and counts the rest.
const CROWD_RANGE = {
  from_date: isoDay(CROWDED, 1),
  to_date: isoDay(AFTER_CROWDED, lengthOf(AFTER_CROWDED)),
};
const crowd = () =>
  calendarMonths(
    CROWD_RANGE,
    [
      // Three that close on the twentieth, three on the first of February,
      // and one that opens in the month's second week.
      obligation("111", isoDay(CROWDED, 4), isoDay(CROWDED, 20)),
      obligation("115", isoDay(CROWDED, 4), isoDay(CROWDED, 20)),
      obligation("123", isoDay(CROWDED, 4), isoDay(CROWDED, 20)),
      obligation("130", isoDay(CROWDED, 4), isoDay(AFTER_CROWDED, 1)),
      obligation("303", isoDay(CROWDED, 4), isoDay(AFTER_CROWDED, 1)),
      obligation("390", isoDay(CROWDED, 4), isoDay(AFTER_CROWDED, 1)),
      obligation("349", isoDay(CROWDED, 11), isoDay(CROWDED, 13)),
    ],
    [],
    null,
    1,
  );

test("a week with more windows than it shows keeps the nearest deadlines and counts the rest", () => {
  const months = crowd();
  const [january, february] = months;
  expect(LANES_SHOWN).toBe(4);
  expect(crowded(january!)).toBe(true);
  // Three windows on its one day of February: nothing to leave out.
  expect(crowded(february!)).toBe(false);
  const drawn = drawnWeeks(months, () => false);
  // The week of the fourth: six windows. Three are drawn, the ones that
  // close soonest, and the fourth row is the count of the other three.
  const first = drawn.get(january!.weeks[1]!);
  expect(first?.bars.map(({ bar }) => bar.entry.modelo)).toEqual([
    "111",
    "115",
    "123",
  ]);
  expect(first?.hidden.map((bar) => bar.entry.modelo)).toEqual([
    "130",
    "303",
    "390",
  ]);
  expect(first?.bars.every(({ bar }) => bar.lane < LANES_SHOWN - 1)).toBe(true);
  // The last week of January: the three long ones alone, all drawn.
  const last = drawn.get(january!.weeks[4]!);
  expect(last?.bars.map(({ bar }) => bar.entry.modelo)).toEqual([
    "130",
    "303",
    "390",
  ]);
  expect(last?.hidden).toEqual([]);
});

test("an obligation's one stop is the first of it that is drawn, not the first that is counted", () => {
  const months = crowd();
  const stops = (open: boolean) => {
    const drawn = drawnWeeks(months, () => open);
    return months.flatMap((month) =>
      month.weeks.flatMap((week, index) =>
        (drawn.get(week)?.bars ?? [])
          .filter(({ stop }) => stop)
          .map(({ bar }) => [bar.entry.modelo, month.key, index]),
      ),
    );
  };
  // Left out of January's crowded weeks, the long windows are first drawn
  // where the short ones have closed: the week of the twenty-fifth. The
  // window of three days in the month's second week closes soonest of all
  // that cross it, and is drawn there.
  expect(stops(false)).toEqual([
    ["111", monthKey(CROWDED), 1],
    ["115", monthKey(CROWDED), 1],
    ["123", monthKey(CROWDED), 1],
    ["349", monthKey(CROWDED), 2],
    ["130", monthKey(CROWDED), 4],
    ["303", monthKey(CROWDED), 4],
    ["390", monthKey(CROWDED), 4],
  ]);
  // Drawn whole, every obligation stops where it opens.
  expect(stops(true)).toEqual([
    ["111", monthKey(CROWDED), 1],
    ["115", monthKey(CROWDED), 1],
    ["123", monthKey(CROWDED), 1],
    ["130", monthKey(CROWDED), 1],
    ["303", monthKey(CROWDED), 1],
    ["390", monthKey(CROWDED), 1],
    ["349", monthKey(CROWDED), 2],
  ]);
  // Every obligation has exactly one stop, counted or whole.
  for (const open of [false, true])
    expect(new Set(stops(open).map(([modelo]) => modelo)).size).toBe(7);
});

// What a crowded week keeps is what needs the person, whenever it opened.
const reading = (
  modelo: string,
  opens: string,
  closes: string,
  state: CalendarEntry["user_state"],
): CalendarEntry => ({
  ...obligation(modelo, opens, closes),
  user_state: state,
});
const staggered = () =>
  calendarMonths(
    { from_date: isoDay(CROWDED, 1), to_date: isoDay(CROWDED, 31) },
    [
      // Three that opened first and close last, one late that opened after
      // them, one due sooner than they are, and one already filed that
      // closes soonest of all.
      reading("180", isoDay(CROWDED, 1), isoDay(CROWDED, 30), "due"),
      reading("190", isoDay(CROWDED, 1), isoDay(CROWDED, 30), "due"),
      reading("390", isoDay(CROWDED, 1), isoDay(CROWDED, 30), "due"),
      reading("111", isoDay(CROWDED, 4), isoDay(CROWDED, 15), "late"),
      reading("303", isoDay(CROWDED, 4), isoDay(CROWDED, 20), "due"),
      reading("115", isoDay(CROWDED, 4), isoDay(CROWDED, 8), "filed"),
    ],
    [],
    null,
    1,
  );
const shownIn = (
  months: ReturnType<typeof calendarMonths>,
  week: number,
  chosen: string | null = null,
) => {
  const drawn = drawnWeeks(months, () => false, chosen).get(
    months[0]!.weeks[week]!,
  );
  return {
    shown: (drawn?.bars ?? []).map(({ bar, lane }) => [bar.entry.modelo, lane]),
    hidden: (drawn?.hidden ?? []).map((bar) => bar.entry.modelo),
    stops: (drawn?.bars ?? [])
      .filter(({ stop }) => stop)
      .map(({ bar }) => bar.entry.modelo),
  };
};

test("a crowded week keeps what is late, then what closes soonest, whenever each opened", () => {
  const months = staggered();
  // The week of the fourth has six windows. The late one and the one due
  // on the twentieth are kept though they opened after the three that are
  // due on the thirtieth, of which one keeps the last row; what is filed
  // is the first given up, though it closes soonest.
  expect(shownIn(months, 1)).toEqual({
    shown: [
      ["180", 0],
      ["111", 1],
      ["303", 2],
    ],
    hidden: ["190", "390", "115"],
    stops: ["111", "303"],
  });
  // No row of what is shown is the count's: three rows of four.
  expect(
    shownIn(months, 1).shown.every(
      ([, lane]) => Number(lane) < LANES_SHOWN - 1,
    ),
  ).toBe(true);
  // The week before has three windows and room for all of them.
  expect(shownIn(months, 0)).toEqual({
    shown: [
      ["180", 0],
      ["190", 1],
      ["390", 2],
    ],
    hidden: [],
    stops: ["180", "190", "390"],
  });
});

test("what is chosen is always drawn, in place of what the week would keep last, and keeps its stop", () => {
  const months = staggered();
  // Chosen, the obligation due on the thirtieth that the week left out is
  // drawn, and the one of its kind that was kept is counted instead. The
  // late one and the nearer deadline stay.
  const chosen = shownIn(months, 1, `390:${PERIOD}`);
  expect(chosen.shown.map(([modelo]) => modelo).sort()).toEqual([
    "111",
    "303",
    "390",
  ]);
  expect(chosen.hidden).toEqual(["180", "190", "115"]);
  // Its stop is still where it is drawn anyway, the week before: choosing
  // does not move the keyboard's place to a part drawn only for the choice.
  expect(chosen.stops).not.toContain("390");
  expect(shownIn(months, 0, `390:${PERIOD}`).stops).toContain("390");
  // One that is drawn nowhere unless chosen has its stop where it is
  // first drawn for the choice.
  expect(shownIn(months, 1).hidden).toContain("115");
  const filed = shownIn(months, 1, `115:${PERIOD}`);
  expect(filed.shown.map(([modelo]) => modelo)).toContain("115");
  expect(filed.stops).toContain("115");
  // A window kept before it was chosen stays in its row when it is.
  expect(shownIn(months, 1, `303:${PERIOD}`).shown).toEqual(
    shownIn(months, 1).shown,
  );
});

test("choosing a window a crowded week already keeps changes nothing of the week", () => {
  // Seven windows of every reading and length in one week: four begin on
  // its Monday, one in the middle, one on its last day.
  const months = calendarMonths(
    RANGE,
    [
      reading("112", day(5), day(10), "unknown"),
      reading("103", day(5), day(11), "unknown"),
      reading("104", day(5), day(11), "filed"),
      reading("100", day(5), day(5), "late"),
      reading("106", day(5), day(5), "filed"),
      reading("110", day(7), day(11), "due"),
      reading("101", day(11), day(11), "unknown"),
    ],
    [],
    null,
    1,
  );
  const plain = shownIn(months, 1);
  // Five of them fit in three rows when laid out from the left; the two
  // that are filed are what is counted.
  expect(plain.shown.map(([modelo]) => modelo).sort()).toEqual([
    "100",
    "101",
    "103",
    "110",
    "112",
  ]);
  expect([...plain.hidden].sort()).toEqual(["104", "106"]);
  // Choosing any window that is already drawn hides nothing more urgent
  // and moves no window to another row.
  for (const [modelo] of plain.shown)
    expect(shownIn(months, 1, `${modelo}:${PERIOD}`), String(modelo)).toEqual(
      plain,
    );
  // Choosing one that was counted draws it and counts one fewer of the
  // rest; what was late, due and nearest stays.
  const filed = shownIn(months, 1, `106:${PERIOD}`);
  expect(filed.shown.map(([modelo]) => modelo)).toContain("106");
  for (const urgent of ["100", "110", "112"])
    expect(filed.shown.map(([modelo]) => modelo)).toContain(urgent);
});

test("windows that do not share a day share a row of what a crowded week keeps", () => {
  const months = calendarMonths(
    RANGE,
    [
      obligation("111", day(5), day(6)),
      obligation("115", day(8), day(9)),
      ...["130", "303", "349", "390"].map((modelo) =>
        obligation(modelo, day(5), day(11)),
      ),
    ],
    [],
    null,
    1,
  );
  // Five rows to draw them all; three are shown. The two short ones close
  // first and take one row between them, so four windows are drawn.
  expect(months[0]!.weeks[1]!.lanes).toBe(5);
  expect(shownIn(months, 1)).toMatchObject({
    shown: [
      ["111", 0],
      ["130", 1],
      ["303", 2],
      ["115", 0],
    ],
    hidden: ["349", "390"],
  });
});

test("a window whose opening is not known and that closes after the range is drawn on its closing day", () => {
  const months = calendarMonths(
    { from_date: isoDay(CROWDED, 1), to_date: isoDay(CROWDED, 31) },
    [obligation("349", null, isoDay(monthAfter(CROWDED, 2), 28))],
    [],
    null,
    1,
  );
  expect(months.map((month) => month.key)).toEqual([
    monthKey(CROWDED),
    monthKey(AFTER_CROWDED),
    monthKey(monthAfter(CROWDED, 2)),
  ]);
  expect(bars(months)).toEqual([
    {
      month: monthKey(monthAfter(CROWDED, 2)),
      days: [28, 28],
      lane: 0,
      opens: true,
      closes: true,
      first: true,
      modelo: "349",
    },
  ]);
});

test("a week with exactly as many windows as it shows leaves none out", () => {
  const months = calendarMonths(
    RANGE,
    ["111", "115", "123", "130"].map((modelo) =>
      obligation(modelo, day(5), day(7)),
    ),
    [],
    null,
    1,
  );
  expect(crowded(months[0]!)).toBe(false);
  const week = drawnWeeks(months, () => false).get(months[0]!.weeks[1]!);
  expect(week?.bars).toHaveLength(4);
  expect(week?.hidden).toEqual([]);
});
