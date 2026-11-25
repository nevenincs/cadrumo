import {
  useCallback,
  useEffect,
  useLayoutEffect,
  useMemo,
  useRef,
  useState,
} from "react";
import { failureCode } from "../errors";
import type {
  OperationHistoryCursorV1,
  OperationHistoryRowV1,
  OperationsServed,
} from "./operationsContract";
import { tokensOf } from "./strings";
import type { ProfileViews } from "./views";

/** How many runs a page of the history asks for. The host refuses a count
 * outside the product's bounds as well. */
export const OPERATIONS_PAGE_SIZE = 25;

/** What the pages read so far hold: the runs newest first, as served, and
 * what the last page read says of the journal. `next` is the continuation
 * the last page served, or null when it was the last. */
export type OperationsListing = {
  runs: OperationHistoryRowV1[];
  total: number;
  unreadable: number;
  unverifiable: number;
  observedAt: string;
  next: OperationHistoryCursorV1 | null;
};

/** The standing of a request for more runs: none made, one in flight, or
 * one that failed, by its code. The runs already listed stay on screen. */
export type OperationsMore =
  { kind: "idle" } | { kind: "loading" } | { kind: "failed"; code: string };

/** What the Operations page has to show: the read in flight, that the account
 * withholds it, why it failed, or the runs as the product served them. A
 * failed read is never drawn as an empty history. */
export type OperationsState =
  | { kind: "loading" }
  | { kind: "withheld" }
  | { kind: "failed"; code: string }
  | { kind: "ready"; listing: OperationsListing; more: OperationsMore };

type Read = Exclude<OperationsState, { kind: "withheld" }>;

/** A history read this recently is shown again as it is when the page is
 * shown anew. Refresh always asks. */
const FRESH_MS = 30_000;

/** The code of a page that holds a value outside the closed vocabularies the
 * window has words for: such a page is refused, not drawn. It is the code the
 * host gives a read it cannot pass on. */
const UNRECOGNISED = "unavailable";

/** Whether every run of a page names a lifecycle, an effect and a receipt
 * outcome the window has a word for. Those words are generated from the
 * product's own enums, so the members are the served vocabularies. */
function recognised(served: OperationsServed): boolean {
  const lifecycle = new Set(tokensOf("desktop.operations.lifecycle."));
  const effect = new Set(tokensOf("desktop.operations.effect."));
  const outcome = new Set(tokensOf("desktop.operations.outcome."));
  return served.runs.every(
    (run) =>
      lifecycle.has(run.lifecycle) &&
      effect.has(run.effect) &&
      (run.receipt === null ||
        (outcome.has(run.receipt.condition) && effect.has(run.receipt.effect))),
  );
}

function listing(
  served: OperationsServed,
  runs: OperationHistoryRowV1[],
): OperationsListing {
  return {
    runs,
    total: served.run_count,
    unreadable: served.unreadable_records,
    unverifiable: served.unverifiable_records,
    observedAt: served.observed_at,
    next: served.next_cursor,
  };
}

/**
 * The operation history of a profile, read when its page is shown and again
 * only when the person asks: nothing polls. More runs are read only when asked
 * for, after the continuation the last page served. `reader` names whose
 * history it is, and is null while the account withholds the read: what was
 * read is dropped whenever it changes, because a history belongs to its
 * profile and not to the window. A read that is refused may mean the account
 * has changed underneath, so it is reported.
 */
export function useOperations(
  views: ProfileViews | undefined,
  reader: string | null,
  shown: boolean,
  onRefused: () => void,
) {
  const identity = useMemo(() => ({ reader, views }), [reader, views]);
  const [stored, setStored] = useState<{
    identity: typeof identity;
    read: Read;
  }>({ identity, read: { kind: "loading" } });
  const [refreshing, setRefreshing] = useState(false);
  const [attempt, setAttempt] = useState(0);
  const request = useRef(0);
  // When the history on screen was read; zero while there is none.
  const readAt = useRef(0);
  const refused = useRef(onRefused);
  refused.current = onRefused;

  const refresh = useCallback(() => {
    if (!views || reader === null) return;
    const mine = ++request.current;
    // What is on screen stays up while the newer read is in flight.
    setRefreshing(true);
    views
      .operations(OPERATIONS_PAGE_SIZE, null)
      .then(
        (served): Read =>
          recognised(served)
            ? {
                kind: "ready",
                listing: listing(served, served.runs),
                more: { kind: "idle" },
              }
            : { kind: "failed", code: UNRECOGNISED },
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
  }, [views, reader, identity]);

  const more = useCallback(() => {
    if (!views || reader === null) return;
    const held = stored.identity === identity ? stored.read : null;
    if (held?.kind !== "ready" || held.listing.next === null) return;
    if (held.more.kind === "loading") return;
    const { listing: before } = held;
    const after = before.next;
    const mine = ++request.current;
    setStored({
      identity,
      read: { kind: "ready", listing: before, more: { kind: "loading" } },
    });
    views
      .operations(OPERATIONS_PAGE_SIZE, after)
      .then(
        (served): Read =>
          recognised(served)
            ? {
                kind: "ready",
                listing: listing(served, [...before.runs, ...served.runs]),
                more: { kind: "idle" },
              }
            : {
                kind: "ready",
                listing: before,
                more: { kind: "failed", code: UNRECOGNISED },
              },
        (error: unknown): Read => ({
          kind: "ready",
          listing: before,
          more: { kind: "failed", code: failureCode(error) },
        }),
      )
      .then((next) => {
        if (mine !== request.current) return;
        setAttempt((count) => count + 1);
        setStored({ identity, read: next });
        if (next.kind === "ready" && next.more.kind === "failed")
          refused.current();
      });
  }, [views, reader, identity, stored]);

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
  }, [reader, shown, refresh, identity]);

  const state: OperationsState =
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
    more,
  };
}
