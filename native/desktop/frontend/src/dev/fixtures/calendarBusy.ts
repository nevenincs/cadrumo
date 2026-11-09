import type { CalendarEntry, FilingCalendar } from "../../shell/views";
import { FIXTURE_CALENDAR, FIXTURE_STATUS } from "./calendar";
import { fixtureDay, fixtureInstant, fixtureYear } from "@/dev/fixtureDates";

// The turn of a year, when most of a small business's obligations fall due
// together: nine filing windows open over the same weeks of January, one
// behind and late, one moved past a weekend into the next month, and one
// that closes after the range ends. Synthetic data for the month view's
// layout under load; the dates are for the drawing and state nothing about
// any year's legal calendar.

export const BUSY_TODAY = fixtureDay(1, 12, 1);

/** The year the obligations here belong to: the one before the year of
 * `BUSY_TODAY`, in which they close. */
const ANNUAL_YEAR = String(fixtureYear);

/** A period of `ANNUAL_YEAR`, written as the backend writes it. */
const periodOf = (code: string): string => `${ANNUAL_YEAR}-${code}`;

const base = FIXTURE_CALENDAR.entries[0];
if (!base) throw new Error("the calendar fixture has no entry to shape from");

function entry(
  modelo: string,
  period: string,
  opens: string | null,
  closes: string,
  change: Partial<CalendarEntry> = {},
): CalendarEntry {
  return {
    ...base,
    modelo,
    period,
    opens_on: opens,
    closes_on: closes,
    adjusted_closes_on: closes,
    shift_reason: "none",
    payment_cutoff_on: null,
    evaluated_on: BUSY_TODAY,
    days_overdue: null,
    status: FIXTURE_STATUS[change.user_state ?? "due"],
    user_state: "due",
    local_filing_state: "not_ready_to_file",
    aeat_submission_state: "not_observed",
    justificante_verified: false,
    ...change,
  };
}

// What closes on the thirtieth of January is drawn as moved past a weekend
// to the first of February; the weekday is the drawing's, not the calendar's.
const moved = {
  adjusted_closes_on: fixtureDay(2, 1, 1),
  shift_reason: "weekend",
};

export const BUSY_CALENDAR: FilingCalendar = {
  ...FIXTURE_CALENDAR,
  range: { from_date: fixtureDay(11, 1), to_date: fixtureDay(4, 30, 1) },
  generated_at: `${BUSY_TODAY}T08:02:00Z`,
  warnings: [],
  entries: [
    entry("202", periodOf("2P"), fixtureDay(12, 1), fixtureDay(12, 21), {
      user_state: "late",
      days_overdue: 22,
    }),
    entry("111", periodOf("4T"), fixtureDay(1, 1, 1), fixtureDay(1, 20, 1)),
    entry("115", periodOf("4T"), fixtureDay(1, 1, 1), fixtureDay(1, 20, 1), {
      user_state: "filed",
      local_filing_state: "ready_to_file",
      aeat_submission_state: "justificante_verified",
      justificante_verified: true,
    }),
    entry("123", periodOf("4T"), fixtureDay(1, 1, 1), fixtureDay(1, 20, 1), {
      local_filing_state: "ready_to_file",
    }),
    entry(
      "130",
      periodOf("4T"),
      fixtureDay(1, 1, 1),
      fixtureDay(1, 30, 1),
      moved,
    ),
    entry("303", periodOf("4T"), fixtureDay(1, 1, 1), fixtureDay(1, 30, 1), {
      ...moved,
      local_filing_state: "ready_to_file",
      payment_cutoff_on: fixtureDay(1, 27, 1),
    }),
    entry("349", periodOf("4T"), null, fixtureDay(1, 30, 1), {
      ...moved,
      user_state: "unknown",
    }),
    entry("180", ANNUAL_YEAR, fixtureDay(1, 1, 1), fixtureDay(1, 30, 1), moved),
    entry("190", ANNUAL_YEAR, fixtureDay(1, 1, 1), fixtureDay(1, 30, 1), moved),
    entry("390", ANNUAL_YEAR, fixtureDay(1, 1, 1), fixtureDay(1, 30, 1), moved),
    entry("347", ANNUAL_YEAR, fixtureDay(2, 1, 1), fixtureDay(3, 1, 1)),
    // Closes after the range that was asked for.
    entry("100", ANNUAL_YEAR, fixtureDay(4, 7, 1), fixtureDay(6, 30, 1)),
  ],
  events: [
    {
      event_type: "message",
      event_date: fixtureDay(12, 22),
      source: "notifications",
      summary: "Notification received from the agency",
      reference_id: `busy-message-${fixtureDay(12, 22)}`,
      status: null,
      aeat_submission_state: null,
      aeat_submitted_at: null,
      justificante_verified: null,
    },
    {
      event_type: "filing",
      event_date: fixtureDay(1, 8, 1),
      source: "filed_declarations",
      summary: `Modelo 115 ${periodOf("4T")} filed`,
      reference_id: `busy-filing-${fixtureDay(1, 8, 1)}`,
      status: "presentado",
      aeat_submission_state: "justificante_verified",
      aeat_submitted_at: fixtureInstant(1, 8, "09:30:00Z", 1),
      justificante_verified: true,
    },
    {
      event_type: "message",
      event_date: fixtureDay(1, 8, 1),
      source: "notifications",
      summary: "Notification received from the agency",
      reference_id: `busy-message-${fixtureDay(1, 8, 1)}`,
      status: null,
      aeat_submission_state: null,
      aeat_submitted_at: null,
      justificante_verified: null,
    },
  ],
};
