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

/** A calendar read this recently is shown again as it is: on a real host a
 * read is a process, and putting the page away and back is not a question.
 * Refresh always asks. */
const FRESH_MS = 30_000;

/**
 * The filing calendar of a profile, read when its page is shown and again
 * when it is shown anew after a while. Nothing is read for a page nobody is looking
 * at. `reader` names whose calendar it is, and is null while the account
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
        setRead(next);
        setRefreshing(false);
        setAttempt((count) => count + 1);
        if (next.kind === "failed") refused.current();
      });
  }, [views]);

  useEffect(() => {
    ++request.current;
    readAt.current = 0;
    setRead({ kind: "loading" });
    setRefreshing(false);
  }, [reader]);

  useEffect(() => {
    if (reader !== null && shown && Date.now() - readAt.current >= FRESH_MS)
      refresh();
  }, [reader, shown, refresh]);

  const state: CalendarState = reader === null ? { kind: "withheld" } : read;
  return {
    state,
    refreshing: refreshing && state.kind !== "loading",
    /** How many reads have answered: tells one failure from the next. */
    attempt,
    refresh,
  };
}
