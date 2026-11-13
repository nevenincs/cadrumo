import type { OverviewPeriodState } from "./calendarContract";
import type { CalendarEntry } from "./views";

/** The product's readings in the order they need the person. */
export const STATE_ORDER: readonly OverviewPeriodState[] = [
  "late",
  "due",
  "unknown",
  "filed",
];

/** The identity of an obligation: its Modelo and period. */
export const entryKey = (entry: CalendarEntry) =>
  `${entry.modelo}:${entry.period}`;

/** Whether the product could not work out when the obligation's window
 * closes. Its closing dates are then the earliest it can close, never a
 * deadline: nothing is counted down to them or late from them. */
export const closeUnknown = (entry: CalendarEntry) =>
  entry.status === "UNKNOWN";

/** Of two obligations, the one with a known close first. */
const datedFirst = (a: CalendarEntry, b: CalendarEntry) =>
  Number(closeUnknown(a)) - Number(closeUnknown(b));

/** By reading, then binding date and identity, the sooner first. A close
 * that is not known comes after the known ones of its reading, and among
 * its kind keeps its earliest close only as a steady order. */
export const compareCalendarEntries = (a: CalendarEntry, b: CalendarEntry) =>
  STATE_ORDER.indexOf(a.user_state) - STATE_ORDER.indexOf(b.user_state) ||
  datedFirst(a, b) ||
  a.adjusted_closes_on.localeCompare(b.adjusted_closes_on) ||
  entryKey(a).localeCompare(entryKey(b));

/** The list's order: by the month a window closes in, or at the earliest
 * closes in where that is all that is known; within a month the known
 * closes by date, then those not known. */
export const compareListedEntries = (a: CalendarEntry, b: CalendarEntry) =>
  a.adjusted_closes_on
    .slice(0, 7)
    .localeCompare(b.adjusted_closes_on.slice(0, 7)) ||
  datedFirst(a, b) ||
  a.adjusted_closes_on.localeCompare(b.adjusted_closes_on) ||
  a.modelo.localeCompare(b.modelo);

/** Where an opening is unknown or after its close, draw only the closing
 * day; never invent a filing window. Where the close is unknown the span
 * ends on the earliest close: the days it is known to be open. */
export function entrySpan(entry: CalendarEntry): { from: string; to: string } {
  const to = entry.adjusted_closes_on;
  const from =
    entry.opens_on !== null && entry.opens_on <= to ? entry.opens_on : to;
  return { from, to };
}
