import type { CalendarEntry, FilingCalendar } from "../../shell/views";
import { FIXTURE_CALENDAR } from "./calendar";

// The turn of a year, when most of a small business's obligations fall due
// together: nine filing windows open over the same weeks of January, one
// behind and late, one moved past a weekend into the next month, and one
// that closes after the range ends. Synthetic data for the month view's
// layout under load; the dates are for the drawing and state nothing about
// any year's legal calendar.

export const BUSY_TODAY = "2027-01-12";

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
    user_state: "due",
    local_filing_state: "not_ready_to_file",
    aeat_submission_state: "not_observed",
    justificante_verified: false,
    ...change,
  };
}

// The thirtieth of January 2027 is a Saturday: what closes then binds on
// the Monday, the first of February.
const moved = { adjusted_closes_on: "2027-02-01", shift_reason: "weekend" };

export const BUSY_CALENDAR: FilingCalendar = {
  ...FIXTURE_CALENDAR,
  range: { from_date: "2026-11-01", to_date: "2027-04-30" },
  generated_at: `${BUSY_TODAY}T08:02:00Z`,
  warnings: [],
  entries: [
    entry("202", "2026-2P", "2026-12-01", "2026-12-21", {
      user_state: "late",
      days_overdue: 22,
    }),
    entry("111", "2026-4T", "2027-01-01", "2027-01-20"),
    entry("115", "2026-4T", "2027-01-01", "2027-01-20", {
      user_state: "filed",
      local_filing_state: "ready_to_file",
      aeat_submission_state: "justificante_verified",
      justificante_verified: true,
    }),
    entry("123", "2026-4T", "2027-01-01", "2027-01-20", {
      local_filing_state: "ready_to_file",
    }),
    entry("130", "2026-4T", "2027-01-01", "2027-01-30", moved),
    entry("303", "2026-4T", "2027-01-01", "2027-01-30", {
      ...moved,
      local_filing_state: "ready_to_file",
      payment_cutoff_on: "2027-01-27",
    }),
    entry("349", "2026-4T", null, "2027-01-30", {
      ...moved,
      user_state: "unknown",
    }),
    entry("180", "2026", "2027-01-01", "2027-01-30", moved),
    entry("190", "2026", "2027-01-01", "2027-01-30", moved),
    entry("390", "2026", "2027-01-01", "2027-01-30", moved),
    entry("347", "2026", "2027-02-01", "2027-03-01"),
    // Closes after the range that was asked for.
    entry("100", "2026", "2027-04-07", "2027-06-30"),
  ],
  events: [
    {
      event_type: "message",
      event_date: "2026-12-22",
      source: "notifications",
      summary: "Notification received from the agency",
      reference_id: "busy-message-2026-12-22",
      status: null,
      aeat_submission_state: null,
      aeat_submitted_at: null,
      justificante_verified: null,
    },
    {
      event_type: "filing",
      event_date: "2027-01-08",
      source: "filed_declarations",
      summary: "Modelo 115 2026-4T filed",
      reference_id: "busy-filing-2027-01-08",
      status: "presentado",
      aeat_submission_state: "justificante_verified",
      aeat_submitted_at: "2027-01-08T09:30:00Z",
      justificante_verified: true,
    },
    {
      event_type: "message",
      event_date: "2027-01-08",
      source: "notifications",
      summary: "Notification received from the agency",
      reference_id: "busy-message-2027-01-08",
      status: null,
      aeat_submission_state: null,
      aeat_submitted_at: null,
      justificante_verified: null,
    },
  ],
};
