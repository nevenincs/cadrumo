import type { CalendarEntry, CalendarUserState } from "./views";

/** The product's readings in the order they need the person. */
export const STATE_ORDER: readonly CalendarUserState[] = [
  "late",
  "due",
  "unknown",
  "filed",
];

/** The identity of an obligation: its Modelo and period. */
export const entryKey = (entry: CalendarEntry) =>
  `${entry.modelo}:${entry.period}`;

/** By reading, then binding date and identity, the sooner first. */
export const compareCalendarEntries = (a: CalendarEntry, b: CalendarEntry) =>
  STATE_ORDER.indexOf(a.user_state) - STATE_ORDER.indexOf(b.user_state) ||
  a.adjusted_closes_on.localeCompare(b.adjusted_closes_on) ||
  entryKey(a).localeCompare(entryKey(b));

/** Where an opening is unknown or after its close, draw only the closing
 * day; never invent a filing window. */
export function entrySpan(entry: CalendarEntry): { from: string; to: string } {
  const to = entry.adjusted_closes_on;
  const from =
    entry.opens_on !== null && entry.opens_on <= to ? entry.opens_on : to;
  return { from, to };
}
