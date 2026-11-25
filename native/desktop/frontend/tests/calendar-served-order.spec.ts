import { expect, test } from "@playwright/test";
import { calendarMonths } from "../src/shell/calendarGrid";
import { listedMonths } from "../src/shell/calendarEntries";
import type { FilingCalendarServed } from "../src/shell/calendarContract";
import { calendarEntry } from "../src/dev/fixtures/calendar";
import { fixtureDay, fixtureYear } from "../src/dev/fixtureDates";

// The calendar's order and its mark for the evaluated day, as the product
// serves them. Each case serves an order or a membership that the rows'
// own dates, states and names would not give, so a window that ordered or
// placed rows itself would draw something else.

const PERIOD = `${fixtureYear}-3T`;
const title = (iso: string) => iso.slice(0, 7);

/** The list's months as keys of their rows, with how many of each month's
 * rows stand behind the mark for the evaluated day and how many ahead. */
const listed = (entries: FilingCalendarServed["entries"][number][]) =>
  listedMonths({ entries, events: [] }, title).map(([key, month]) => ({
    key,
    rows: month.entries.map((entry) => entry.modelo),
    behind: month.behind,
    ahead: month.ahead,
  }));

test("the list keeps the entries in the order the product serves them", () => {
  // Same month, same close: by name the 130 would come first; the product
  // serves the 303 first.
  const month = fixtureDay(10, 20).slice(0, 7);
  expect(
    listed([
      calendarEntry("303", PERIOD, fixtureDay(10, 1), fixtureDay(10, 20)),
      calendarEntry("130", PERIOD, fixtureDay(10, 1), fixtureDay(10, 20)),
    ]),
  ).toEqual([{ key: month, rows: ["303", "130"], behind: 0, ahead: 2 }]);
});

test("the months give the first row of a week to what the product's attention order puts first", () => {
  // Opening together, the due 130 would need the person before the filed
  // 303 by its reading; the product serves the 303 first.
  const entries = [
    calendarEntry("130", PERIOD, fixtureDay(10, 1), fixtureDay(10, 20)),
    calendarEntry("303", PERIOD, fixtureDay(10, 1), fixtureDay(10, 20), {
      user_state: "filed",
    }),
  ];
  const [month] = calendarMonths(
    { from_date: fixtureDay(10, 1), to_date: fixtureDay(10, 31) },
    entries,
    [],
    null,
    1,
    [1, 0],
  );
  const first = month?.weeks.find((week) => week.bars.length > 0);
  expect(first?.bars.map((bar) => [bar.entry.modelo, bar.lane])).toEqual([
    ["303", 0],
    ["130", 1],
  ]);
});

test("what stands behind the mark is what the product serves as past, and ahead of it what it serves as ahead", () => {
  // Both close after the evaluated day by their dates; the product serves
  // the first as past and the second as ahead.
  const month = fixtureDay(10, 20).slice(0, 7);
  expect(
    listed([
      calendarEntry("130", PERIOD, fixtureDay(10, 1), fixtureDay(10, 20), {
        scopes: ["past"],
      }),
      calendarEntry("303", PERIOD, fixtureDay(10, 1), fixtureDay(10, 21), {
        scopes: ["ahead", "upcoming"],
      }),
    ]),
  ).toEqual([{ key: month, rows: ["130", "303"], behind: 1, ahead: 1 }]);
});

test("a row served as neither past nor ahead stands on neither side, whatever its date", () => {
  // Dated after the evaluated day, but a close the product could not work
  // out whose earliest it serves as passed.
  const month = fixtureDay(10, 20).slice(0, 7);
  expect(
    listed([
      calendarEntry("130", PERIOD, fixtureDay(10, 1), fixtureDay(10, 20), {
        scopes: ["past"],
      }),
      calendarEntry("123", PERIOD, fixtureDay(10, 1), fixtureDay(10, 22), {
        status: "UNKNOWN",
        user_state: "unknown",
        scopes: [],
      }),
    ]),
  ).toEqual([{ key: month, rows: ["130", "123"], behind: 1, ahead: 0 }]);
});
