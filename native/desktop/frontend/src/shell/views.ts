// Read-only views of the signed-in profile that a host may offer the shell.
// The calendar is the product's own calendar read, served whole by the host
// under the product's names: its type is generated in calendarContract.ts,
// so nothing in it is computed, renamed or spelled by hand, and a state the
// product keeps apart stays apart on screen. The notifications are counts
// only, taken by the host, so that no row of them reaches the window. Home is
// the `home` state of the product's workbench generation, served by the host
// under the product's names with the rest of the generation left behind. Reference
// is the bundled corpus search, served as the product answers it.

import type { FilingCalendarServed } from "./calendarContract";
import type { HomeServed } from "./homeContract";
import type { ReferenceServed } from "./referenceContract";

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
  /** Home as the product served it, its sentences in `language`. Reads the
   * profile's local records only; it never asks the tax agency. Refused when
   * nobody is signed in. */
  home(language: string): Promise<HomeServed>;
  /** What the bundled reference corpus answers for the text typed, at most
   * `limit` passages, its words in `language`: orientation from bundled
   * sources, not verified current law. Reads no profile data and never asks
   * the tax agency; the host keeps nothing of the query. Refused when nobody
   * is signed in. */
  reference(
    query: string,
    limit: number,
    language: string,
  ): Promise<ReferenceServed>;
}
