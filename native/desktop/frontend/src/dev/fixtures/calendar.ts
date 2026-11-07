import type {
  CalendarEntry,
  CalendarEvent,
  CalendarObligationStatus,
  CalendarUserState,
  FilingCalendar,
  NotificationsSummary,
} from "../../shell/views";
import {
  fixtureDay,
  fixtureInstant,
  fixtureMonth,
  fixtureYear,
} from "@/dev/fixtureDates";

// A filing calendar in the shape the product reports, for the scenario host
// and the stories. The dates are fixed around `TODAY`, so a story looks the
// same on any day; nothing here is a real taxpayer's.

export const FIXTURE_TODAY = fixtureDay(10, 6);

/** The year of `FIXTURE_TODAY`, which its annual obligations belong to. */
const FIXTURE_YEAR = String(fixtureYear);

/** The deadline status a fixture row carries with each reading, unless the
 * row names its own. A reading the product could not place is reported as
 * not applicable; a close it could not work out is set row by row. */
export const FIXTURE_STATUS: Record<
  CalendarUserState,
  CalendarObligationStatus
> = {
  due: "UPCOMING",
  late: "OVERDUE",
  filed: "FILED",
  unknown: "NOT_APPLICABLE",
};

function entry(
  modelo: string,
  period: string,
  opens: string | null,
  closes: string,
  change: Partial<CalendarEntry> = {},
): CalendarEntry {
  return {
    modelo,
    period,
    opens_on: opens,
    closes_on: closes,
    adjusted_closes_on: closes,
    shift_reason: "none",
    payment_cutoff_on: null,
    evaluated_on: FIXTURE_TODAY,
    days_overdue: null,
    status: FIXTURE_STATUS[change.user_state ?? "due"],
    user_state: "due",
    local_filing_state: "not_ready_to_file",
    aeat_submission_state: "not_observed",
    justificante_verified: false,
    ...change,
  };
}

function observed(
  type: CalendarEvent["event_type"],
  on: string,
  summary: string,
  change: Partial<CalendarEvent> = {},
): CalendarEvent {
  return {
    event_type: type,
    event_date: on,
    source: type === "filing" ? "filed_declarations" : "notifications",
    summary,
    reference_id: `fixture-${type}-${on}`,
    status: null,
    aeat_submission_state: null,
    aeat_submitted_at: null,
    justificante_verified: null,
    ...change,
  };
}

export const FIXTURE_CALENDAR: FilingCalendar = {
  range: { from_date: fixtureDay(7, 1), to_date: fixtureDay(6, 30, 1) },
  generated_at: `${FIXTURE_TODAY}T09:14:05Z`,
  entries: [
    entry("303", `${FIXTURE_YEAR}-2T`, fixtureDay(7, 1), fixtureDay(7, 20), {
      user_state: "filed",
      local_filing_state: "ready_to_file",
      aeat_submission_state: "justificante_verified",
      justificante_verified: true,
    }),
    entry("130", `${FIXTURE_YEAR}-2T`, fixtureDay(7, 1), fixtureDay(7, 20), {
      user_state: "late",
      days_overdue: 78,
      local_filing_state: "ready_to_file",
    }),
    entry("303", `${FIXTURE_YEAR}-3T`, fixtureDay(10, 1), fixtureDay(10, 20), {
      payment_cutoff_on: fixtureDay(10, 15),
      local_filing_state: "ready_to_file",
    }),
    entry("130", `${FIXTURE_YEAR}-3T`, fixtureDay(10, 1), fixtureDay(10, 20)),
    entry("111", `${FIXTURE_YEAR}-3T`, fixtureDay(10, 1), fixtureDay(10, 20), {
      aeat_submission_state: "submitted_observed",
      user_state: "filed",
      local_filing_state: "external_baseline_imported",
    }),
    // A host that could not say when this window opens: only its close.
    entry("349", `${FIXTURE_YEAR}-3T`, null, fixtureDay(10, 20), {
      user_state: "unknown",
    }),
    entry(
      "303",
      `${FIXTURE_YEAR}-4T`,
      fixtureDay(1, 1, 1),
      fixtureDay(1, 30, 1),
      {
        adjusted_closes_on: fixtureDay(2, 1, 1),
        shift_reason: "weekend",
      },
    ),
    entry("390", FIXTURE_YEAR, fixtureDay(1, 1, 1), fixtureDay(1, 30, 1), {
      adjusted_closes_on: fixtureDay(2, 1, 1),
      shift_reason: "weekend",
    }),
    entry("100", FIXTURE_YEAR, fixtureDay(4, 7, 1), fixtureDay(6, 30, 1), {
      payment_cutoff_on: fixtureDay(6, 25, 1),
    }),
  ],
  events: [
    observed(
      "filing",
      fixtureDay(7, 17),
      `Modelo 303 ${FIXTURE_YEAR}-2T filed`,
      {
        status: "presentado",
        aeat_submission_state: "justificante_verified",
        aeat_submitted_at: fixtureInstant(7, 17, "10:42:00Z"),
        justificante_verified: true,
      },
    ),
    observed(
      "message",
      fixtureDay(9, 3),
      "Notification received from the agency",
    ),
    observed(
      "filing",
      fixtureDay(10, 2),
      `Modelo 111 ${FIXTURE_YEAR}-3T filed`,
      {
        status: "presentado",
        aeat_submission_state: "submitted_observed",
        aeat_submitted_at: fixtureInstant(10, 2, "08:15:00Z"),
        justificante_verified: false,
      },
    ),
  ],
  warnings: [
    {
      code: "profile_key_defaulted",
      message:
        "The foral territory is not set, so common-territory dates are used.",
      affected_modelos: ["303", "390"],
    },
  ],
  coverage: {
    surfaced: ["100", "111", "130", "303", "349", "390"],
    confidently_excluded: ["115", "180"],
    advised: [{ modelo: "347", reason: "applicability_undetermined" }],
    out_of_scope: ["720"],
  },
};

/** Counts from a capture earlier the same morning. */
export const FIXTURE_NOTIFICATIONS: NotificationsSummary = {
  captured_at: `${FIXTURE_TODAY}T07:02:11Z`,
  row_count: 7,
  unread: 3,
};

/** A profile whose notifications were never captured: not known to be none. */
export const NEVER_CAPTURED: NotificationsSummary = {
  captured_at: null,
  row_count: 0,
  unread: 0,
};

const without = (keep: (entry: CalendarEntry) => boolean): FilingCalendar => ({
  ...FIXTURE_CALENDAR,
  entries: FIXTURE_CALENDAR.entries.filter(keep),
  warnings: [],
});

/** Only what is behind today: the mark for today closes the list. */
export const BEHIND_CALENDAR = without(
  (item) => item.adjusted_closes_on < FIXTURE_TODAY,
);

/** Only what is ahead: the mark for today opens the list. */
export const AHEAD_CALENDAR = without(
  (item) => item.adjusted_closes_on >= FIXTURE_TODAY,
);

/** Today falls between two dates of one month: the month is split by it. */
export const STRADDLING_CALENDAR: FilingCalendar = {
  ...AHEAD_CALENDAR,
  entries: [
    entry("216", fixtureMonth(9), fixtureDay(9, 21), fixtureDay(10, 1), {
      user_state: "filed",
      local_filing_state: "ready_to_file",
      aeat_submission_state: "accepted",
    }),
    ...AHEAD_CALENDAR.entries,
  ],
};

/** Windows whose close the product could not work out, beside known ones:
 * one whose earliest close is still ahead of today, among the closes of its
 * month, and one whose earliest close has passed, which is not known to be
 * late. Their dates are only the earliest each can close. */
export const CLOSE_UNKNOWN_CALENDAR: FilingCalendar = {
  ...FIXTURE_CALENDAR,
  warnings: [],
  entries: [
    ...FIXTURE_CALENDAR.entries,
    entry("115", `${FIXTURE_YEAR}-2T`, fixtureDay(7, 1), fixtureDay(7, 20), {
      status: "UNKNOWN",
      user_state: "unknown",
    }),
    entry("123", `${FIXTURE_YEAR}-3T`, fixtureDay(10, 1), fixtureDay(10, 20), {
      status: "UNKNOWN",
      user_state: "unknown",
    }),
  ],
};

/** The same calendar with nothing due: an empty range is not a failed read. */
export const EMPTY_CALENDAR: FilingCalendar = {
  ...FIXTURE_CALENDAR,
  entries: [],
  events: [],
  warnings: [],
  coverage: { ...FIXTURE_CALENDAR.coverage, surfaced: [], advised: [] },
};

/** Each reason the local projection can leave a modelo without a window. */
export const ADVISED_CALENDAR: FilingCalendar = {
  ...FIXTURE_CALENDAR,
  coverage: {
    ...FIXTURE_CALENDAR.coverage,
    advised: [
      { modelo: "123", reason: "applicable_window_missing" },
      { modelo: "347", reason: "applicability_undetermined" },
      { modelo: "720", reason: "registry_unmodeled" },
      { modelo: "216", reason: "applicable_window_missing" },
    ],
    out_of_scope: [],
  },
};

/** No dated entries does not mean no possible obligations. */
export const ADVICE_ONLY_CALENDAR: FilingCalendar = {
  ...EMPTY_CALENDAR,
  coverage: { ...ADVISED_CALENDAR.coverage, surfaced: [] },
};
