// Read-only views of the signed-in profile that a host may offer the shell.
// The calendar is the product's own calendar read, served whole by the host
// under the product's names: its type is generated in calendarContract.ts,
// so nothing in it is computed, renamed or spelled by hand, and a state the
// product keeps apart stays apart on screen. The notifications are counts
// only, taken by the host, so that no row of them reaches the window.

import type { FilingCalendarServed } from "./calendarContract";

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
  ): Promise<FilingCalendarServed>;
}
