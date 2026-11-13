// Read-only views of the signed-in profile that a host may offer the shell.
// The calendar is the product's own calendar read, field for field, for the
// fields the shell shows: every type here takes its fields from the wire
// types generated in calendarContract.ts, so nothing in it is computed,
// renamed or spelled by hand, and a state the product keeps apart stays
// apart on screen. The
// notifications are counts only, taken by the host, so that no row of them
// reaches the window.

import type {
  ObligationCoverageReport,
  OverviewCalendarEntrySnapshot,
  OverviewCalendarEventSnapshot,
  OverviewCalendarRange,
  OverviewCalendarWarningSnapshot,
  OverviewFilingEvidenceSnapshot,
  OverviewSuppressedEntrySnapshot,
} from "./calendarContract";

/** One obligation of the calendar: a Modelo and its period. The host takes
 * these fields from the served calendar row and flattens the three filing
 * states out of the row's filing evidence; none is computed or renamed. */
export type CalendarEntry = Pick<
  OverviewCalendarEntrySnapshot,
  | "modelo"
  | "period"
  | "closes_on"
  | "adjusted_closes_on"
  | "shift_reason"
  | "payment_cutoff_on"
  | "evaluated_on"
  | "days_overdue"
  | "status"
  | "user_state"
> &
  Pick<
    OverviewFilingEvidenceSnapshot,
    "local_filing_state" | "aeat_submission_state" | "justificante_verified"
  > & {
    /** The day the filing window opens, as an ISO date; null where a host
     * has no source for it. The window is then not drawn, only its close:
     * an opening is never guessed. */
    opens_on: OverviewCalendarEntrySnapshot["opens_on"] | null;
  };

/** Something observed beside the legal calendar: a filing that was made, or
 * a message from the agency. It is a record of what was seen and when, and
 * never by itself a statement that an obligation is met. */
export type CalendarEvent = Pick<
  OverviewCalendarEventSnapshot,
  | "event_type"
  | "event_date"
  | "source"
  | "summary"
  | "reference_id"
  | "status"
  | "aeat_submission_state"
  | "aeat_submitted_at"
  | "justificante_verified"
>;

/** A profile detail the calendar had to assume, with the product's own
 * sentence about it in the output language: the served warning's `text`
 * arrives here as `message`. */
export type CalendarWarning = Pick<
  OverviewCalendarWarningSnapshot,
  "code" | "affected_modelos"
> & { message: string };

/** One obligation the calendar holds off its schedule, as served: its
 * verdict and the worker's own sentence for it in `verdict_words_language`,
 * shown as it came. The doors that move it on are not part of it. */
export type CalendarSuppressedEntry = Omit<
  OverviewSuppressedEntrySnapshot,
  "actions"
>;

/** The filing calendar of one profile over a range of dates, from local
 * records only. Reading it never asks the tax agency anything. */
export type FilingCalendar = {
  range: OverviewCalendarRange;
  entries: CalendarEntry[];
  /** What was observed in the range: the profile's own filing history and
   * the agency's messages, as the product recorded them. */
  events: CalendarEvent[];
  warnings: CalendarWarning[];
  /** When the product worked this out. */
  generated_at: string | null;
  /** Every Modelo the calendar considered, in exactly one disposition. */
  coverage: ObligationCoverageReport;
  /** The obligations the read served as held off the schedule. Left out
   * where the host did not ask for them or pass them on; an empty list is
   * the read saying there are none. */
  suppressed_entries?: CalendarSuppressedEntry[];
};

/** What the last capture of the tax agency's notifications held, as counts.
 * The rows carry names and tax numbers, and the window has no use for them:
 * the host counts and passes on only this. */
export type NotificationsSummary = {
  /** When the notifications were last captured from the agency; null when
   * they never were, which is not "no notifications". */
  captured_at: string | null;
  /** Rows in that capture. */
  row_count: number;
  /** Rows the agency had not marked as read when they were captured. */
  unread: number;
};

/** The views a host offers. A host without them offers none: the shell then
 * shows no way into them, rather than a way into something that cannot load. */
export interface ProfileViews {
  /** Counts from the last capture. Refused when nobody is signed in. */
  notifications(): Promise<NotificationsSummary>;
  /** Dates are inclusive ISO dates; the product's sentences come in
   * `language`. Refused when nobody is signed in. */
  filingCalendar(
    range: { from: string; to: string },
    language: string,
  ): Promise<FilingCalendar>;
}
