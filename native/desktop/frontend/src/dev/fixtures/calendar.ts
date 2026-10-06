import type {
  CalendarEntry,
  FilingCalendar,
  NotificationsSummary,
} from "../../shell/views";

// A filing calendar in the shape the product reports, for the scenario host
// and the stories. The dates are fixed around `TODAY`, so a story looks the
// same on any day; nothing here is a real taxpayer's.

export const FIXTURE_TODAY = "2026-10-06";

function entry(
  modelo: string,
  period: string,
  closes: string,
  change: Partial<CalendarEntry> = {},
): CalendarEntry {
  return {
    modelo,
    period,
    closes_on: closes,
    adjusted_closes_on: closes,
    shift_reason: "none",
    payment_cutoff_on: null,
    evaluated_on: FIXTURE_TODAY,
    days_overdue: null,
    user_state: "due",
    local_filing_state: "not_ready_to_file",
    aeat_submission_state: "not_observed",
    justificante_verified: false,
    ...change,
  };
}

export const FIXTURE_CALENDAR: FilingCalendar = {
  range: { from_date: "2026-07-01", to_date: "2027-06-30" },
  generated_at: `${FIXTURE_TODAY}T09:14:05Z`,
  entries: [
    entry("303", "2026-2T", "2026-07-20", {
      user_state: "filed",
      local_filing_state: "ready_to_file",
      aeat_submission_state: "justificante_verified",
      justificante_verified: true,
    }),
    entry("130", "2026-2T", "2026-07-20", {
      user_state: "late",
      days_overdue: 78,
      local_filing_state: "ready_to_file",
    }),
    entry("303", "2026-3T", "2026-10-20", {
      payment_cutoff_on: "2026-10-15",
      local_filing_state: "ready_to_file",
    }),
    entry("130", "2026-3T", "2026-10-20"),
    entry("111", "2026-3T", "2026-10-20", {
      aeat_submission_state: "submitted_observed",
      user_state: "filed",
      local_filing_state: "external_baseline_imported",
    }),
    entry("349", "2026-3T", "2026-10-20", { user_state: "unknown" }),
    entry("303", "2026-4T", "2027-01-30", {
      adjusted_closes_on: "2027-02-01",
      shift_reason: "weekend",
    }),
    entry("390", "2026", "2027-01-30", {
      adjusted_closes_on: "2027-02-01",
      shift_reason: "weekend",
    }),
    entry("100", "2026", "2027-06-30", { payment_cutoff_on: "2027-06-25" }),
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
    entry("216", "2026-09", "2026-10-01", {
      user_state: "filed",
      local_filing_state: "ready_to_file",
      aeat_submission_state: "accepted",
    }),
    ...AHEAD_CALENDAR.entries,
  ],
};

/** The same calendar with nothing due: an empty range is not a failed read. */
export const EMPTY_CALENDAR: FilingCalendar = {
  ...FIXTURE_CALENDAR,
  entries: [],
  warnings: [],
  coverage: { ...FIXTURE_CALENDAR.coverage, surfaced: [], advised: [] },
};
