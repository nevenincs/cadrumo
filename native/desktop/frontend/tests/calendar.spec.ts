import { expect, test } from "@playwright/test";
import { calendarRange, deadlineDistance } from "../src/shell/calendar";
import {
  calendarMonths,
  crowded,
  drawnWeeks,
  entrySpan,
  LANES_SHOWN,
  weekStartOf,
} from "../src/shell/calendarGrid";
import type { CalendarEntry } from "../src/shell/views";

// The calendar's pure rules, checked at their boundaries. No page is opened.

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
  expect(calendarRange(new Date(2026, 9, 6))).toEqual({
    from: "2026-07-01",
    to: "2027-06-30",
  });
  // Across a year's end, and into a leap February.
  expect(calendarRange(new Date(2027, 5, 15))).toEqual({
    from: "2027-03-01",
    to: "2028-02-29",
  });
  expect(calendarRange(new Date(2026, 0, 31))).toEqual({
    from: "2025-10-01",
    to: "2026-09-30",
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
  period: "2026-3T",
  opens_on: opens,
  closes_on: closes,
  adjusted_closes_on: adjusted,
  shift_reason: "none",
  payment_cutoff_on: null,
  evaluated_on: "2026-10-06",
  days_overdue: null,
  user_state: "due",
  local_filing_state: "not_ready_to_file",
  aeat_submission_state: "not_observed",
  justificante_verified: false,
});

const OCTOBER = { from_date: "2026-10-01", to_date: "2026-10-31" };

test("a month is weeks from the locale's first day, blank outside the month", () => {
  // 1 October 2026 is a Thursday.
  const [monday] = calendarMonths(OCTOBER, [], [], "2026-10-06", 1);
  expect(monday?.key).toBe("2026-10");
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
  expect(todays).toEqual(["2026-10-06"]);
  // From Sunday, the same month begins a column later.
  const [sunday] = calendarMonths(OCTOBER, [], [], null, 0);
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
    OCTOBER,
    [obligation("303", "2026-10-01", "2026-10-20")],
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
    OCTOBER,
    [
      // Closes on a Saturday, moved to the Monday.
      obligation("130", "2026-10-01", "2026-10-17", "2026-10-19"),
      obligation("349", null, "2026-10-20"),
    ],
    [],
    null,
    1,
  );
  expect(
    entrySpan(obligation("130", "2026-10-01", "2026-10-17", "2026-10-19")),
  ).toEqual({ from: "2026-10-01", to: "2026-10-19" });
  expect(entrySpan(obligation("349", null, "2026-10-20"))).toEqual({
    from: "2026-10-20",
    to: "2026-10-20",
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
    OCTOBER,
    [
      obligation("111", "2026-10-01", "2026-10-20"),
      obligation("303", "2026-10-01", "2026-10-20"),
      obligation("100", "2026-10-01", "2026-10-30"),
      obligation("216", "2026-10-26", "2026-10-28"),
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
    { from_date: "2026-12-01", to_date: "2027-01-31" },
    [obligation("390", "2026-12-28", "2027-01-05")],
    [],
    null,
    1,
  );
  expect(months.map((month) => month.key)).toEqual(["2026-12", "2027-01"]);
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
    event_date: "2026-10-02",
    source: "filed_declarations",
    summary: "Modelo 111 2026-3T filed",
    reference_id: "ref-1",
    status: "presentado",
    aeat_submission_state: "submitted_observed" as const,
    aeat_submitted_at: "2026-10-02T08:15:00Z",
    justificante_verified: false,
  };
  const [month] = calendarMonths(OCTOBER, [], [event], null, 1);
  const withEvents = month?.weeks.flatMap((week) =>
    week.days.filter((day) => day && day.events.length > 0),
  );
  expect(withEvents?.map((day) => [day?.iso, day?.events.length])).toEqual([
    ["2026-10-02", 1],
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
      { from_date: "2026-12-01", to_date: "2027-01-31" },
      [obligation("303", "2026-12-28", "2027-01-05")],
      [],
      null,
      1,
    ),
  );
  // 28 December 2026 is a Monday; 1 January 2027 a Friday.
  expect(drawn).toEqual([
    {
      month: "2026-12",
      days: [28, 31],
      lane: 0,
      opens: true,
      closes: false,
      first: true,
      modelo: "303",
    },
    {
      month: "2027-01",
      days: [1, 3],
      lane: 0,
      opens: false,
      closes: false,
      first: false,
      modelo: "303",
    },
    {
      month: "2027-01",
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
    OCTOBER,
    [
      obligation("100", "2026-09-15", "2026-11-10"),
      // Closed before the range began.
      obligation("111", "2026-08-01", "2026-08-20"),
    ],
    [],
    null,
    1,
  );
  // The month the window closes in is drawn after the range's own: the
  // closing day is what the calendar is for.
  expect(months.map((month) => month.key)).toEqual(["2026-10", "2026-11"]);
  const drawn = bars(months);
  // One segment for each week it crosses, from the first of October, where
  // it was already open, to the tenth of November, where it closes. The
  // first of November 2026 is a Sunday.
  expect(drawn.map((bar) => [bar.month, ...bar.days])).toEqual([
    ["2026-10", 1, 4],
    ["2026-10", 5, 11],
    ["2026-10", 12, 18],
    ["2026-10", 19, 25],
    ["2026-10", 26, 31],
    ["2026-11", 1, 1],
    ["2026-11", 2, 8],
    ["2026-11", 9, 10],
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
      OCTOBER,
      [obligation("115", "2026-11-02", "2026-12-20")],
      [],
      null,
      1,
    ).map((month) => month.key),
  ).toEqual(["2026-10"]);
  // Nor does a closing date years away draw years of months: a year past
  // the range at most.
  const far = calendarMonths(
    OCTOBER,
    [obligation("100", "2026-10-01", "2031-01-01")],
    [],
    null,
    1,
  );
  expect(far).toHaveLength(14);
  expect(far.at(-1)?.key).toBe("2027-11");
});

test("an opening after its close is not believed: the closing day alone is drawn", () => {
  const entry = obligation("130", "2026-10-25", "2026-10-20");
  expect(entrySpan(entry)).toEqual({ from: "2026-10-20", to: "2026-10-20" });
  expect(bars(calendarMonths(OCTOBER, [entry], [], null, 1))).toEqual([
    {
      month: "2026-10",
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
    OCTOBER,
    [
      ...["111", "115", "123", "130", "303", "349"].map((modelo) =>
        obligation(modelo, "2026-10-05", "2026-10-07"),
      ),
      // After the six have closed, in the same week.
      obligation("216", "2026-10-09", "2026-10-11"),
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

test("a leap February has its twenty-ninth day", () => {
  const [february] = calendarMonths(
    { from_date: "2028-02-01", to_date: "2028-02-29" },
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
  // 29 February 2028 is a Tuesday.
  expect(february?.weeks.at(-1)?.days[1]?.iso).toBe("2028-02-29");
});

test("what was observed with a time of day stands on its date", () => {
  const event = {
    event_type: "filing" as const,
    event_date: "2026-10-02T08:15:00Z",
    source: "filed_declarations",
    summary: "Filed",
    reference_id: "a",
    status: null,
    aeat_submission_state: null,
    aeat_submitted_at: null,
    justificante_verified: null,
  };
  const [october] = calendarMonths(OCTOBER, [], [event], null, 1);
  const on = october?.weeks.flatMap((week) =>
    week.days.filter((day) => (day?.events.length ?? 0) > 0),
  );
  expect(on?.map((day) => day?.iso)).toEqual(["2026-10-02"]);
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
const JANUARY = { from_date: "2027-01-01", to_date: "2027-02-28" };
const crowd = () =>
  calendarMonths(
    JANUARY,
    [
      // Three that close on the twentieth, three on the first of February,
      // and one that opens in the month's second week.
      obligation("111", "2027-01-04", "2027-01-20"),
      obligation("115", "2027-01-04", "2027-01-20"),
      obligation("123", "2027-01-04", "2027-01-20"),
      obligation("130", "2027-01-04", "2027-02-01"),
      obligation("303", "2027-01-04", "2027-02-01"),
      obligation("390", "2027-01-04", "2027-02-01"),
      obligation("349", "2027-01-11", "2027-01-13"),
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
  const january = months[0]!;
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
  // where the short ones have closed: the week of the twenty-fifth.
  expect(stops(false)).toEqual([
    ["111", "2027-01", 1],
    ["115", "2027-01", 1],
    ["123", "2027-01", 1],
    ["130", "2027-01", 4],
    ["303", "2027-01", 4],
    ["390", "2027-01", 4],
  ]);
  // A window that is never drawn has no stop among the months: the count
  // in its week and the list are where it is found.
  expect(stops(false).some(([modelo]) => modelo === "349")).toBe(false);
  expect(
    drawnWeeks(months, () => false)
      .get(january.weeks[2]!)
      ?.hidden.map((bar) => bar.entry.modelo),
  ).toContain("349");
  // Drawn whole, every obligation stops where it opens.
  expect(stops(true)).toEqual([
    ["111", "2027-01", 1],
    ["115", "2027-01", 1],
    ["123", "2027-01", 1],
    ["130", "2027-01", 1],
    ["303", "2027-01", 1],
    ["390", "2027-01", 1],
    ["349", "2027-01", 2],
  ]);
  // Every obligation has exactly one stop when all of it is drawn.
  expect(new Set(stops(true).map(([modelo]) => modelo)).size).toBe(7);
});

test("a week with exactly as many windows as it shows leaves none out", () => {
  const months = calendarMonths(
    OCTOBER,
    ["111", "115", "123", "130"].map((modelo) =>
      obligation(modelo, "2026-10-05", "2026-10-07"),
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
