import { useCallback, useEffect, useRef, useState } from "react";
import { failureCode } from "../errors";
import type { NotificationsSummary, ProfileViews } from "./views";

/** What is known of the agency's notifications. Not known is its own state:
 * it is never shown as none unread. */
export type MessagesState =
  | { kind: "unknown" }
  | { kind: "failed"; code: string }
  | { kind: "ready"; summary: NotificationsSummary };

/** A read on window focus at most this often: the answer changes only when
 * the product next syncs with the agency. */
const REREAD_MS = 60_000;

/**
 * The counts of a profile's notifications, read when the profile becomes
 * readable and again when the window is returned to. Reading asks the tax
 * agency nothing: the counts are of the last capture. `reader` names whose
 * they are, and is null while the account withholds the read; the counts are
 * dropped whenever it changes. A read that is refused may mean the account
 * has changed underneath, so it is reported.
 */
export function useMessages(
  views: ProfileViews | undefined,
  reader: string | null,
  onRefused: () => void,
): MessagesState {
  const [state, setState] = useState<MessagesState>({ kind: "unknown" });
  const request = useRef(0);
  const readAt = useRef(0);
  const refused = useRef(onRefused);
  refused.current = onRefused;

  const read = useCallback(() => {
    if (!views) return;
    const mine = ++request.current;
    readAt.current = Date.now();
    views
      .notifications()
      .then(
        (summary): MessagesState => ({ kind: "ready", summary }),
        (error: unknown): MessagesState => ({
          kind: "failed",
          code: failureCode(error),
        }),
      )
      .then((next) => {
        // An answer to a question no longer being asked is not shown.
        if (mine !== request.current) return;
        setState(next);
        if (next.kind === "failed") refused.current();
      });
  }, [views]);

  useEffect(() => {
    ++request.current;
    setState({ kind: "unknown" });
    if (reader === null) return;
    read();
    const focus = () => {
      if (Date.now() - readAt.current >= REREAD_MS) read();
    };
    window.addEventListener("focus", focus);
    return () => window.removeEventListener("focus", focus);
  }, [reader, read]);

  return state;
}
