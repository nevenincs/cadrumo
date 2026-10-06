import { useCallback, useEffect, useRef, useState } from "react";
import { failureCode } from "../errors";
import type { FilingCalendar, ProfileViews } from "./views";

/** What the calendar page has to show: the read in flight, that the account
 * withholds it, why it failed, or the calendar. A failed read is never drawn
 * as an empty calendar. */
export type CalendarState =
  | { kind: "loading" }
  | { kind: "withheld" }
  | { kind: "failed"; code: string }
  | { kind: "ready"; calendar: FilingCalendar };

type Read = Exclude<CalendarState, { kind: "withheld" }>;

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

/** The local calendar day, as an ISO date. */
export const localDay = (now: Date = new Date()): string => iso(now);

/**
 * The day the product worked a calendar's states out for: one day for the
 * whole read, the latest that any of its entries names. Null where no entry
 * says.
 */
export function evaluatedDay(calendar: FilingCalendar): string | null {
  let latest: string | null = null;
  for (const entry of calendar.entries)
    if (latest === null || entry.evaluated_on > latest)
      latest = entry.evaluated_on;
  return latest;
}

/**
 * The local day, kept current: looked at again just after each midnight, and
 * whenever the window is returned to, since a machine that slept through
 * midnight ran no timer.
 */
function useLocalDay(): string {
  const [day, setDay] = useState(() => localDay());
  useEffect(() => {
    const look = () => setDay(localDay());
    const midnight = new Date();
    midnight.setHours(24, 0, 1, 0);
    const timer = window.setTimeout(look, midnight.getTime() - Date.now());
    window.addEventListener("focus", look);
    document.addEventListener("visibilitychange", look);
    return () => {
      window.clearTimeout(timer);
      window.removeEventListener("focus", look);
      document.removeEventListener("visibilitychange", look);
    };
  }, [day]);
  return day;
}

/** Beyond this many days ahead, a distance is said in months. */
const FAR_DAYS = 60;
const MONTH_DAYS = 365.25 / 12;

/**
 * How far a deadline is, in the unit it is read in. Lateness is the
 * product's own count of days and stays in days. A date far ahead is said in
 * whole months that have fully to pass, never rounded up: a deadline must
 * not read as further off than it is.
 */
export function deadlineDistance(
  days: number,
  overdue: boolean,
): { value: number; unit: "day" | "month" } {
  return !overdue && days > FAR_DAYS
    ? { value: Math.floor(days / MONTH_DAYS), unit: "month" }
    : { value: days, unit: "day" };
}

/** A calendar read this recently is shown again as it is: on a real host a
 * read is a process, and putting the page away and back is not a question.
 * Refresh always asks. */
const FRESH_MS = 30_000;

/**
 * The filing calendar of a profile, read when its page is shown, again when
 * it is shown anew after a while, and again when the day changes under a
 * page that is shown: every distance on it is counted from the day it was
 * read. Nothing is read for a page nobody is looking at. `reader` names whose calendar it is, and is null while the account
 * withholds the read: what was read is dropped whenever it changes, because
 * a calendar belongs to its profile and not to the window. A read that is
 * refused may mean the account has changed underneath, so it is reported.
 */
export function useFilingCalendar(
  views: ProfileViews | undefined,
  reader: string | null,
  shown: boolean,
  onRefused: () => void,
) {
  const [read, setRead] = useState<Read>({ kind: "loading" });
  const [refreshing, setRefreshing] = useState(false);
  const [attempt, setAttempt] = useState(0);
  const request = useRef(0);
  // When the calendar on screen was read; zero while there is none.
  const readAt = useRef(0);
  // The local day it was read on; empty while there is none.
  const readOn = useRef("");
  const today = useLocalDay();
  const refused = useRef(onRefused);
  refused.current = onRefused;

  const refresh = useCallback(() => {
    if (!views) return;
    const mine = ++request.current;
    // What is on screen stays up, and so does whatever was pressed to ask.
    setRefreshing(true);
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
        readAt.current = next.kind === "ready" ? Date.now() : 0;
        readOn.current = next.kind === "ready" ? localDay() : "";
        setRead(next);
        setRefreshing(false);
        setAttempt((count) => count + 1);
        if (next.kind === "failed") refused.current();
      });
  }, [views]);

  useEffect(() => {
    ++request.current;
    readAt.current = 0;
    readOn.current = "";
    setRead({ kind: "loading" });
    setRefreshing(false);
  }, [reader]);

  useEffect(() => {
    const stale =
      Date.now() - readAt.current >= FRESH_MS ||
      (readOn.current !== "" && readOn.current !== today);
    if (reader !== null && shown && stale) {
      // Shown anew after a failure, it starts over: the old failure is not
      // said a second time ahead of the new answer.
      setRead((held) => (held.kind === "failed" ? { kind: "loading" } : held));
      refresh();
    }
  }, [reader, shown, refresh, today]);

  const state: CalendarState = reader === null ? { kind: "withheld" } : read;
  return {
    state,
    refreshing: refreshing && state.kind !== "loading",
    /** How many reads have answered: tells one failure from the next. */
    attempt,
    /** The local day, kept current while the window is open. */
    today,
    refresh,
  };
}
