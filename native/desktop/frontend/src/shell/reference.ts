import {
  useCallback,
  useEffect,
  useLayoutEffect,
  useMemo,
  useRef,
  useState,
} from "react";
import { failureCode } from "../errors";
import type { ReferenceServed } from "./referenceContract";
import type { ProfileViews } from "./views";

/** The longest text the product's corpus search takes, and how many passages
 * the page asks for. The host refuses a query or a count outside the
 * product's bounds as well; these only keep the field from offering more. */
export const REFERENCE_QUERY_MAX = 200;
export const REFERENCE_LIMIT = 8;

/** What the Reference page has to show: that the account withholds it, that
 * nothing has been searched, the search in flight, why it failed, or what the
 * bundled corpus answered. `query` is the text the answer is to. A search is
 * only ever made because the person asked for it, and a failed one is never
 * drawn as an answer that found nothing. */
export type ReferenceState =
  | { kind: "withheld" }
  | { kind: "idle" }
  | { kind: "searching"; query: string }
  | { kind: "failed"; query: string; code: string }
  | { kind: "ready"; query: string; served: ReferenceServed };

type Held = Exclude<ReferenceState, { kind: "withheld" }>;

/**
 * Searches of the bundled reference corpus, made only when `search` is
 * called. `reader` names whose page it is, and is null while the account
 * withholds the read: what was found is dropped whenever it changes, because
 * an answer belongs to the profile that asked and not to the window. A
 * search that is refused may mean the account has changed underneath, so it
 * is reported. Only the newest search is answered: a slower, older one is
 * dropped.
 */
export function useReference(
  views: ProfileViews | undefined,
  reader: string | null,
  onRefused: () => void,
  locale = "",
) {
  const identity = useMemo(() => ({ reader, views }), [reader, views]);
  const [stored, setStored] = useState<{
    identity: typeof identity;
    held: Held;
  }>({ identity, held: { kind: "idle" } });
  const [attempt, setAttempt] = useState(0);
  const request = useRef(0);
  const refused = useRef(onRefused);
  refused.current = onRefused;

  // Invalidate before the new profile is painted, including refusal callbacks.
  useLayoutEffect(() => {
    request.current += 1;
    return () => {
      request.current += 1;
    };
  }, [identity]);

  useEffect(() => {
    setStored({ identity, held: { kind: "idle" } });
  }, [identity]);

  const search = useCallback(
    (text: string) => {
      const query = text.trim();
      if (!views || reader === null || query === "") return;
      const mine = ++request.current;
      setStored({ identity, held: { kind: "searching", query } });
      views
        .reference(query, REFERENCE_LIMIT, locale)
        .then(
          (served): Held => ({ kind: "ready", query, served }),
          (error: unknown): Held => ({
            kind: "failed",
            query,
            code: failureCode(error),
          }),
        )
        .then((next) => {
          // An answer to a question no longer being asked is not shown.
          if (mine !== request.current) return;
          setAttempt((count) => count + 1);
          setStored({ identity, held: next });
          if (next.kind === "failed") refused.current();
        });
    },
    [views, reader, identity, locale],
  );

  const state: ReferenceState =
    reader === null
      ? { kind: "withheld" }
      : stored.identity === identity
        ? stored.held
        : { kind: "idle" };
  return {
    state,
    /** How many searches have answered: tells one failure from the next. */
    attempt,
    search,
  };
}
