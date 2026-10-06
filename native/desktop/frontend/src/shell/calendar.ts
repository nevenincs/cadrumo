import { useCallback, useEffect, useRef, useState } from "react";
import { failureCode } from "../errors";
import type { FilingCalendar, ProfileViews } from "./views";

/** What the calendar page has to show: the read in flight, why there is
 * nothing to read, or the calendar. A failed read is never drawn as an empty
 * calendar. */
export type CalendarState =
  | { kind: "loading" }
  | { kind: "signed-out" }
  | { kind: "failed"; code: string }
  | { kind: "ready"; calendar: FilingCalendar };

type Read = Exclude<CalendarState, { kind: "signed-out" }>;

const iso = (day: Date) =>
  [
    day.getFullYear(),
    String(day.getMonth() + 1).padStart(2, "0"),
    String(day.getDate()).padStart(2, "0"),
  ].join("-");

/** The year the page asks for: the quarter behind today and the three ahead,
 * in whole months, so what was just due is still in view. */
export function calendarRange(today: Date): { from: string; to: string } {
  return {
    from: iso(new Date(today.getFullYear(), today.getMonth() - 3, 1)),
    to: iso(new Date(today.getFullYear(), today.getMonth() + 9, 0)),
  };
}

/**
 * The filing calendar of the signed-in profile, read when its page is shown
 * and again each time it is shown anew. Nothing is read for a page nobody is
 * looking at, and what was read is dropped when the sign-in ends: it belongs
 * to that profile, not to the window.
 */
export function useFilingCalendar(
  views: ProfileViews | undefined,
  signedIn: boolean,
  shown: boolean,
) {
  const [read, setRead] = useState<Read>({ kind: "loading" });
  const [refreshing, setRefreshing] = useState(false);
  const request = useRef(0);

  const refresh = useCallback(() => {
    if (!views) return;
    const mine = ++request.current;
    setRefreshing(true);
    // A read that failed starts over; one that answered stays up meanwhile.
    setRead((held) => (held.kind === "failed" ? { kind: "loading" } : held));
    views
      .filingCalendar(calendarRange(new Date()))
      .then(
        (calendar): Read => ({ kind: "ready", calendar }),
        (error: unknown): Read => ({
          kind: "failed",
          code: failureCode(error),
        }),
      )
      .then((next) => {
        // An answer to a question no longer being asked is not shown.
        if (mine !== request.current) return;
        setRead(next);
        setRefreshing(false);
      });
  }, [views]);

  useEffect(() => {
    if (signedIn && shown) refresh();
  }, [signedIn, shown, refresh]);

  useEffect(() => {
    if (signedIn) return;
    ++request.current;
    setRead({ kind: "loading" });
    setRefreshing(false);
  }, [signedIn]);

  const state: CalendarState = signedIn ? read : { kind: "signed-out" };
  return { state, refreshing: refreshing && read.kind === "ready", refresh };
}
