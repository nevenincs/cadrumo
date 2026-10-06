// Read-only views of the signed-in profile that a host may offer the shell.
// Each mirrors what the product's own command reports, field for field, for
// the fields the shell shows: nothing here is computed or renamed, so a state
// the product keeps apart stays apart on screen.

/** What the person still has to do about an obligation. */
export type CalendarUserState = "due" | "late" | "filed" | "unknown";

/** The local filing work. Never a statement about the tax agency. */
export type LocalFilingState =
  "not_ready_to_file" | "ready_to_file" | "external_baseline_imported";

/** What has been observed of the tax agency's side, from evidence already
 * captured. `not_observed` is not "not submitted". */
export type AeatSubmissionState =
  "not_observed" | "submitted_observed" | "accepted" | "justificante_verified";

/** One obligation of the calendar: a Modelo and its period. */
export type CalendarEntry = {
  modelo: string;
  period: string;
  /** The legal closing date, as an ISO date. */
  closes_on: string;
  /** The closing date after weekends and holidays; the one that binds. */
  adjusted_closes_on: string;
  /** Why the two differ; `none` when they do not. */
  shift_reason: string;
  /** The last day a direct debit can be ordered, where one applies. */
  payment_cutoff_on: string | null;
  /** The day the states below were worked out for. */
  evaluated_on: string;
  /** Days past the binding date; set only for a late obligation. */
  days_overdue: number | null;
  user_state: CalendarUserState;
  local_filing_state: LocalFilingState;
  aeat_submission_state: AeatSubmissionState;
  justificante_verified: boolean;
};

/** A profile detail the calendar had to assume, with the product's own
 * sentence about it in the output language. */
export type CalendarWarning = {
  code: string;
  message: string;
  affected_modelos: string[];
};

/** Every Modelo the calendar considered, in exactly one disposition. */
export type CalendarCoverage = {
  surfaced: string[];
  confidently_excluded: string[];
  /** Obligations that could not be positively scoped: not known to be absent. */
  advised: {
    modelo: string;
    reason:
      | "applicable_window_missing"
      | "applicability_undetermined"
      | "registry_unmodeled";
  }[];
  out_of_scope: string[];
};

/** The filing calendar of one profile over a range of dates, from local
 * records only. Reading it never asks the tax agency anything. */
export type FilingCalendar = {
  range: { from_date: string; to_date: string };
  entries: CalendarEntry[];
  warnings: CalendarWarning[];
  /** When the product worked this out. */
  generated_at: string | null;
  coverage: CalendarCoverage;
};

/** The views a host offers. A host without them offers none: the shell then
 * shows no way into them, rather than a way into something that cannot load. */
export interface ProfileViews {
  /** Dates are inclusive ISO dates. Refused when nobody is signed in. */
  filingCalendar(range: { from: string; to: string }): Promise<FilingCalendar>;
}
