import { expect, test } from "@playwright/test";
import { calendarRange, deadlineDistance } from "../src/shell/calendar";
import { calendarMonths, entrySpan } from "../src/shell/calendarGrid";
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

test("windows that overlap take rows of their own, the longer keeping the first", () => {
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
    ["100", 0],
    ["111", 1],
    ["303", 2],
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
