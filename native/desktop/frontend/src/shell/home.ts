import {
  useCallback,
  useEffect,
  useLayoutEffect,
  useMemo,
  useRef,
  useState,
} from "react";
import { failureCode } from "../errors";
import type { HomeServed } from "./homeContract";
import type { ProfileViews } from "./views";

/** What the Home page has to show: the read in flight, that the account
 * withholds it, why it failed, or Home as the product served it. A failed
 * read is never drawn as an empty Home. */
export type HomeState =
  | { kind: "loading" }
  | { kind: "withheld" }
  | { kind: "failed"; code: string }
  | { kind: "ready"; home: HomeServed };

type Read = Exclude<HomeState, { kind: "withheld" }>;

/** A Home read this recently is shown again as it is: on a real host a read
 * is a process, and putting the page away and back is not a question.
 * Refresh always asks. */
const FRESH_MS = 30_000;

/**
 * Home of a profile, read when its page is shown and again when it is shown
 * anew after a while. Nothing is read for a page nobody is looking at, and a
 * read that failed is not tried again until the person asks or shows the
 * page anew. `reader` names whose Home it is, and is null while the account
 * withholds the read: what was read is dropped whenever it changes, because
 * Home belongs to its profile and not to the window. A read that is refused
 * may mean the account has changed underneath, so it is reported.
 */
export function useHome(
  views: ProfileViews | undefined,
  reader: string | null,
  shown: boolean,
  onRefused: () => void,
  locale = "",
) {
  const identity = useMemo(() => ({ reader, views }), [reader, views]);
  const [stored, setStored] = useState<{
    identity: typeof identity;
    read: Read;
  }>({ identity, read: { kind: "loading" } });
  const [refreshing, setRefreshing] = useState(false);
  const [attempt, setAttempt] = useState(0);
  const request = useRef(0);
  // When the Home on screen was read; zero while there is none.
  const readAt = useRef(0);
  const refused = useRef(onRefused);
  refused.current = onRefused;

  const refresh = useCallback(() => {
    if (!views || reader === null) return;
    const mine = ++request.current;
    // What is on screen stays up while the newer read is in flight.
    setRefreshing(true);
    views
      .home(locale)
      .then(
        (home): Read => ({ kind: "ready", home }),
        (error: unknown): Read => ({
          kind: "failed",
          code: failureCode(error),
        }),
      )
      .then((next) => {
        // An answer to a question no longer being asked is not shown.
        if (mine !== request.current) return;
        setRefreshing(false);
        setAttempt((count) => count + 1);
        readAt.current = next.kind === "ready" ? Date.now() : 0;
        setStored({ identity, read: next });
        if (next.kind === "failed") refused.current();
      });
  }, [views, reader, identity, locale]);

  // Invalidate before the new profile is painted, including refusal callbacks.
  useLayoutEffect(() => {
    request.current += 1;
    return () => {
      request.current += 1;
    };
  }, [identity]);

  useEffect(() => {
    ++request.current;
    readAt.current = 0;
    setStored({ identity, read: { kind: "loading" } });
    setRefreshing(false);
  }, [identity]);

  useEffect(() => {
    // The language invalidates the sentences without dropping what is shown.
    readAt.current = 0;
    ++request.current;
  }, [locale]);

  useEffect(() => {
    if (reader !== null && shown && Date.now() - readAt.current >= FRESH_MS) {
      // Shown anew after a failure, it starts over: the old failure is not
      // said a second time ahead of the new answer.
      setStored((held) =>
        held.read.kind === "failed"
          ? { identity, read: { kind: "loading" } }
          : held,
      );
      refresh();
    }
  }, [reader, shown, refresh, locale, identity]);

  const state: HomeState =
    reader === null
      ? { kind: "withheld" }
      : stored.identity === identity
        ? stored.read
        : { kind: "loading" };
  return {
    state,
    refreshing: refreshing && state.kind !== "loading",
    /** How many reads have answered: tells one failure from the next. */
    attempt,
    refresh,
  };
}
