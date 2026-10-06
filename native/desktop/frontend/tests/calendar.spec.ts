import { expect, test } from "@playwright/test";
import { calendarRange, deadlineDistance } from "../src/shell/calendar";

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
