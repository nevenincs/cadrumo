// Which movements a finalized declaration cites, as far as the page has
// read. The product reports it per movement only: the participation index
// answers one movement at a time, through `ledger.track`, and nothing reads
// it for a period. So the page reads the movements it acts on, the selected
// and the staged ones, a bounded number per read of the window, and the
// review reads every staged one it is about to save that the page has not,
// asking again what failed, and says how far it has got. A movement whose participation could not be
// read, or was left unread past a budget, is unread: never counted as
// sealed or as not sealed. One whose index was never built is not known to
// be sealed; the product refuses a change to a sealed one regardless.

import {
  startTransition,
  useCallback,
  useEffect,
  useMemo,
  useRef,
  useState,
} from "react";
import type { LedgerPort } from "../../shell/ledger";
import { readAnswer } from "../../shell/ledgerWindow";
import { seals } from "./inspector/inspectorWords";

/** The most movements read for one read of the window, for the selection
 * and the staged movements the page acts on. */
export const SEALED_READS = 400;
/** Reads in flight at once. */
const AT_ONCE = 4;
const NO_RESULTS: ReadonlyMap<string, boolean | null> = new Map();

// Page reads may cover hundreds of movements. Give input and paint work
// priority between them; explicit review reads do not use this queue.
function yieldPageRead(): Promise<void> {
  const scheduler = (
    globalThis as typeof globalThis & {
      scheduler?: {
        postTask(
          callback: () => void,
          options: { priority: "background" },
        ): Promise<void>;
      };
    }
  ).scheduler;
  return scheduler
    ? scheduler.postTask(() => {}, { priority: "background" })
    : new Promise((resolve) => window.setTimeout(resolve, 0));
}

/** Whether one movement is sealed; null where it could not be read. */
async function readSealed(
  port: LedgerPort,
  id: string,
): Promise<boolean | null> {
  try {
    const answer = readAnswer(
      await port.submit("ledger.track", { transaction_prefix: id }),
    );
    if (answer.kind !== "answer") return null;
    return (answer.result.participated_in ?? []).some(seals);
  } catch {
    return null;
  }
}

/** Hears how many of the movements a read was asked about it has read. */
export type SealedProgress = (done: number, total: number) => void;

/** Which of the asked movements a finalized declaration seals, and which
 * were not read: failed, or past the budget. */
export type SealedRead = {
  sealed: ReadonlySet<string>;
  unread: ReadonlySet<string>;
};

/**
 * The sealed movements among `wanted`, read as they are wanted and kept
 * until the window is read again (`generation`) or the profile changes,
 * with those of `wanted` that could not be read. `sealedOf` is the
 * review's: it reads what it is asked now, failed reads included, on its
 * own budget, and answers once it has.
 */
export function useSealedMovements(
  port: LedgerPort,
  reader: string | null,
  generation: number | string | null,
  wanted: readonly string[],
): {
  sealed: ReadonlySet<string>;
  /** Of the movements wanted, those whose sealed state was not read. */
  unread: ReadonlySet<string>;
  sealedOf: (
    ids: readonly string[],
    progress?: SealedProgress,
  ) => Promise<SealedRead>;
} {
  const [projection, setProjection] = useState<{
    reader: string | null;
    generation: number | string | null;
    values: ReadonlyMap<string, boolean | null>;
  }>(() => ({ reader, generation, values: NO_RESULTS }));
  // Only completed reads establish either sealed or unsealed. Pending,
  // failed, and unrequested movements must be treated as unread immediately.
  const resolved = useRef(new Map<string, boolean | null>());
  // What was read, or is being read, for this window and profile.
  const known = useRef(new Map<string, Promise<boolean | null>>());
  // How much of the page's budget has actually started. Overlapping reads
  // share the same map and spend once per newly started page read.
  const spent = useRef(0);
  const scope = useRef({ reader, generation });
  if (
    scope.current.reader !== reader ||
    scope.current.generation !== generation
  ) {
    scope.current = { reader, generation };
    known.current = new Map();
    resolved.current = new Map();
    spent.current = 0;
  }
  const values =
    projection.reader === reader && projection.generation === generation
      ? projection.values
      : NO_RESULTS;
  const { sealed, unread } = useMemo(() => {
    const sealed = new Set<string>();
    const unread = new Set<string>();
    for (const id of wanted) {
      const value = values.get(id);
      if (value === true) sealed.add(id);
      else if (value !== false) unread.add(id);
    }
    return { sealed, unread };
  }, [wanted, values]);

  const read = useCallback(
    async (
      ids: readonly string[],
      review: boolean,
      progress?: SealedProgress,
      signal?: AbortSignal,
    ): Promise<SealedRead> => {
      const map = known.current;
      // Admission and budget are checked immediately before a host read.
      // Queues for an old selection can stop without reserving the budget
      // for reads they never started.
      const queue = [...ids];
      const total = ids.length;
      let done = 0;
      progress?.(done, total);
      const run = async () => {
        for (let id = queue.shift(); id !== undefined; id = queue.shift()) {
          if (!review) {
            if (
              signal?.aborted ||
              map !== known.current ||
              spent.current >= SEALED_READS
            )
              return;
            await yieldPageRead();
            if (signal?.aborted || map !== known.current) return;
          }
          // Wait for an existing read; a review retries only failed reads.
          const existing = map.get(id);
          if (existing) {
            const value = await existing;
            if (!review || value !== null) {
              done += 1;
              progress?.(done, total);
              continue;
            }
            // Another caller may already have retried this failed read.
            if (map.get(id) !== existing) {
              await map.get(id);
              done += 1;
              progress?.(done, total);
              continue;
            }
          }
          if (!review) {
            if (signal?.aborted || map !== known.current) return;
            if (spent.current >= SEALED_READS) {
              done += 1;
              continue;
            }
            spent.current += 1;
          }
          const found = readSealed(port, id);
          map.set(id, found);
          await found;
          done += 1;
          progress?.(done, total);
        }
      };
      await Promise.all(Array.from({ length: AT_ONCE }, run));
      const out = new Set<string>();
      const missed = new Set<string>();
      let changed = false;
      for (const id of ids) {
        const entry = map.get(id);
        const value = entry ? await entry : null;
        if (value === true) out.add(id);
        else if (value !== false) missed.add(id);
        // Never publish an older answer over a newer review, or treat an
        // unstarted read as a settled result.
        if (
          entry &&
          known.current === map &&
          map.get(id) === entry &&
          (!resolved.current.has(id) || resolved.current.get(id) !== value)
        ) {
          resolved.current.set(id, value);
          changed = true;
        }
      }
      if (changed && known.current === map) {
        const next = {
          reader: scope.current.reader,
          generation: scope.current.generation,
          values: new Map(resolved.current),
        };
        // Background results may wait behind input; review answers may not.
        if (review) setProjection(next);
        else startTransition(() => setProjection(next));
      }
      return { sealed: out, unread: missed };
    },
    [port],
  );
  const sealedOf = useCallback(
    (ids: readonly string[], progress?: SealedProgress) =>
      read(ids, true, progress),
    [read],
  );

  const key = wanted.join(" ");
  useEffect(() => {
    if (reader === null || generation === null || key === "") return;
    // Pending movements are already unread. Let the selection paint before
    // starting the page's background reads; review reads remain immediate.
    let task: number | undefined;
    const controller = new AbortController();
    const frame = window.requestAnimationFrame(() => {
      task = window.setTimeout(
        () => void read(key.split(" "), false, undefined, controller.signal),
        0,
      );
    });
    return () => {
      controller.abort();
      window.cancelAnimationFrame(frame);
      if (task !== undefined) window.clearTimeout(task);
    };
  }, [read, reader, generation, key]);

  return { sealed, unread, sealedOf };
}
