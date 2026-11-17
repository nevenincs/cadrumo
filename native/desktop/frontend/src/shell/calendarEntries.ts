import type { OverviewPeriodState } from "./calendarContract";
import type { FilingCalendarServed } from "./calendarContract";

/** The identity of an obligation: its Modelo and period. */
export const entryKey = (entry: FilingCalendarServed["entries"][number]) =>
  `${entry.modelo}:${entry.period}`;

/** Whether the product could not work out when the obligation's window
 * closes. Its closing dates are then the earliest it can close, never a
 * deadline: nothing is counted down to them or late from them. */
export const closeUnknown = (entry: FilingCalendarServed["entries"][number]) =>
  entry.status === "UNKNOWN";

/** The calendar's entries in the order the product serves them as needing
 * the person: its attention order, read over its entries. */
export const inAttentionOrder = (
  calendar: Pick<FilingCalendarServed, "entries" | "attention_order">,
): FilingCalendarServed["entries"][number][] =>
  calendar.attention_order.flatMap((index) => {
    const entry = calendar.entries[index];
    return entry === undefined ? [] : [entry];
  });

/** The readings the calendar holds, in the order its attention order first
 * reaches each. */
export const attentionStates = (
  calendar: Pick<FilingCalendarServed, "entries" | "attention_order">,
): OverviewPeriodState[] => [
  ...new Set(inAttentionOrder(calendar).map((entry) => entry.user_state)),
];

/** The list's months, each with its obligations in the order the product
 * serves them and what was observed in it, and how many of its obligations
 * the product serves as past and as ahead of the day it evaluated: the mark
 * for that day stands between them. A close the product could not work out
 * whose earliest has passed is neither. */
export function listedMonths(
  calendar: Pick<FilingCalendarServed, "entries" | "events">,
  title: (iso: string) => string,
) {
  const groups = new Map<
    string,
    {
      title: string;
      entries: FilingCalendarServed["entries"][number][];
      events: FilingCalendarServed["events"][number][];
      ahead: number;
      behind: number;
    }
  >();
  for (const entry of calendar.entries) {
    const key = entry.adjusted_closes_on.slice(0, 7);
    const group = groups.get(key) ?? {
      title: title(entry.adjusted_closes_on),
      entries: [],
      events: [],
      ahead: 0,
      behind: 0,
    };
    if (entry.scopes.includes("ahead")) group.ahead += 1;
    else if (entry.scopes.includes("past")) group.behind += 1;
    group.entries.push(entry);
    groups.set(key, group);
  }
  // What was observed, in the month it happened, whether or not anything
  // falls due in that month.
  for (const event of [...calendar.events].sort((a, b) =>
    a.event_date.localeCompare(b.event_date),
  )) {
    const key = event.event_date.slice(0, 7);
    const group = groups.get(key) ?? {
      title: title(event.event_date),
      entries: [],
      events: [],
      ahead: 0,
      behind: 0,
    };
    group.events.push(event);
    groups.set(key, group);
  }
  return [...groups].sort(([a], [b]) => a.localeCompare(b));
}

/** Where an opening is after its close, draw only the closing day; never
 * invent a filing window. Where the close is unknown the span ends on the
 * earliest close: the days it is known to be open. */
export function entrySpan(entry: FilingCalendarServed["entries"][number]): { from: string; to: string } {
  const to = entry.adjusted_closes_on;
  const from = entry.opens_on <= to ? entry.opens_on : to;
  return { from, to };
}
