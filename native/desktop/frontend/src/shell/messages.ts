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
 * The counts of the signed-in profile's notifications, read at sign-in and
 * again when the window is returned to. Reading asks the tax agency nothing:
 * the counts are of the last capture. They are dropped when the sign-in
 * ends.
 */
export function useMessages(
  views: ProfileViews | undefined,
  signedIn: boolean,
): MessagesState {
  const [state, setState] = useState<MessagesState>({ kind: "unknown" });
  const request = useRef(0);
  const readAt = useRef(0);

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
        if (mine === request.current) setState(next);
      });
  }, [views]);

  useEffect(() => {
    if (!signedIn) {
      ++request.current;
      setState({ kind: "unknown" });
      return;
    }
    read();
    const focus = () => {
      if (Date.now() - readAt.current >= REREAD_MS) read();
    };
    window.addEventListener("focus", focus);
    return () => window.removeEventListener("focus", focus);
  }, [signedIn, read]);

  return state;
}
