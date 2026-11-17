import { expect, test } from "@playwright/test";
import type { FilingCalendarServed } from "../src/shell/calendarContract";
import { calendarEntry, FIXTURE_TODAY } from "../src/dev/fixtures/calendar";
import { fixtureDay, fixtureYear } from "../src/dev/fixtureDates";
import { markupOf } from "./support/markup";

// How far a calendar row's deadline is, said in the product's own count of
// days to its close. The served count here disagrees with the row's dates
// on purpose: a row that measured its dates itself would say the dates'
// distance.

const drawRow = () =>
  markupOf<{
    entry: FilingCalendarServed["entries"][number];
    locale: string;
    selected: boolean;
    onSelect: (key: string) => void;
  }>("components/calendar/CalendarEntryRow.tsx", "CalendarEntryRow");
const row = async (entry: FilingCalendarServed["entries"][number]) =>
  (await drawRow())({
    entry,
    locale: "en",
    selected: false,
    onSelect: () => {},
  });

const distance = new Intl.RelativeTimeFormat("en", { numeric: "auto" });
const PERIOD = `${fixtureYear}-3T`;

test("a row ahead of its close says the product's count of days, not its dates' distance", async () => {
  // The dates put the close fourteen days after the evaluated day; the
  // product counts three.
  const entry = calendarEntry(
    "303",
    PERIOD,
    fixtureDay(10, 1),
    fixtureDay(10, 20),
    { evaluated_on: fixtureDay(10, 6), days_until_close: 3 },
  );
  expect(entry.evaluated_on).toBe(FIXTURE_TODAY);
  const markup = await row(entry);
  expect(markup).toContain(distance.format(3, "day"));
  expect(markup).not.toContain(distance.format(14, "day"));
});

test("a row past its close says the product's signed count, however its dates fall", async () => {
  // Late by the product's count of five days; the dates alone would say
  // seventy-eight.
  const entry = calendarEntry(
    "130",
    PERIOD,
    fixtureDay(7, 1),
    fixtureDay(7, 20),
    { user_state: "late", days_overdue: 5, days_until_close: -5 },
  );
  const markup = await row(entry);
  expect(markup).toContain(distance.format(-5, "day"));
  expect(markup).not.toContain(distance.format(-78, "day"));
});

test("a row the product gives no count for says no distance, though its dates would give one", async () => {
  const entry = calendarEntry(
    "123",
    PERIOD,
    fixtureDay(10, 1),
    fixtureDay(10, 20),
    {
      status: "UNKNOWN",
      user_state: "unknown",
      holiday_coverage: "calendar_unavailable",
      days_until_close: null,
    },
  );
  const markup = await row(entry);
  expect(markup).not.toContain("calendar-distance");
  expect(markup).not.toContain(distance.format(14, "day"));
});
