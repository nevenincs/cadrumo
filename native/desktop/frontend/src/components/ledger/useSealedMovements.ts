// Which movements a finalized declaration seals, as far as the page has
// read. The product answers it for many movements in one read,
// `ledger.sealed.read`, with the same guard a batch edit refuses a sealed
// row by. The page reads the movements it acts on, the selected and the
// staged ones, a bounded number per read of the window, and the review
// reads every staged one it is about to save that the page has not, asking
// again what failed, and says how far it has got. A movement whose state
// could not be read, or was left unread past a budget, is unread: never
// counted as sealed or as not sealed.

import {
  startTransition,
  useCallback,
  useEffect,
  useMemo,
  useRef,
  useState,
} from "react";
import type { LedgerPort } from "../../shell/ledger";
import { isTransactionPrefix } from "../../shell/ledgerGrammar";
import { BATCH_ROW_LIMIT } from "../../shell/ledgerPlan";
import { readAnswer } from "../../shell/ledgerWindow";

/** The most movements the page reads for one read of the window, for the
 * selection and the staged movements it acts on: one sealed read's worth. */
export const SEALED_READS = BATCH_ROW_LIMIT;
/** The most movements one sealed read names, the product's batch bound. */
const PER_READ = BATCH_ROW_LIMIT;
const NO_RESULTS: ReadonlyMap<string, boolean | null> = new Map();
const EMPTY_READ: SealedRead = { sealed: new Set(), unread: new Set() };

// Page reads may cover hundreds of movements. Give input and paint work
// priority before them; explicit review reads do not wait.
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

/** Whether each movement is sealed, as the product served it; null where
 * it could not be read or names no movement. */
export async function readSealed(
  port: LedgerPort,
  ids: readonly string[],
): Promise<ReadonlyMap<string, boolean | null>> {
  const out = new Map<string, boolean | null>(ids.map((id) => [id, null]));
  // A draft's key names no stored movement and never reaches the product.
  const stored = ids.filter(isTransactionPrefix);
  if (stored.length === 0) return out;
  try {
    const answer = readAnswer(
      await port.submit("ledger.sealed.read", { transaction_ids: stored }),
    );
    if (answer.kind !== "answer") return out;
    for (const row of answer.result.rows)
      if (out.has(row.transaction_id))
        out.set(
          row.transaction_id,
          row.state === "sealed" ? true : row.state === "open" ? false : null,
        );
  } catch {
    // Unread: neither sealed nor not sealed.
  }
  return out;
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
      const total = ids.length;
      let done = 0;
      progress?.(done, total);
      if (!review) {
        await yieldPageRead();
        if (signal?.aborted || map !== known.current) return EMPTY_READ;
      }
      // Wait for existing reads; a review asks again only what failed.
      const fresh: string[] = [];
      const waiting: Promise<unknown>[] = [];
      for (const id of new Set(ids)) {
        const existing = map.get(id);
        if (existing) {
          waiting.push(
            existing.then(async (value) => {
              if (review && value === null && map.get(id) === existing)
                fresh.push(id);
              else {
                if (review && value === null) await map.get(id);
                done += 1;
                progress?.(done, total);
              }
            }),
          );
          continue;
        }
        if (!review) {
          // Past the page's budget a movement stays unread.
          if (spent.current >= SEALED_READS) {
            done += 1;
            continue;
          }
          spent.current += 1;
        }
        fresh.push(id);
      }
      await Promise.all(waiting);
      for (let at = 0; at < fresh.length; at += PER_READ) {
        if (!review && (signal?.aborted || map !== known.current)) break;
        const chunk = fresh.slice(at, at + PER_READ);
        const found = readSealed(port, chunk);
        for (const id of chunk)
          map.set(
            id,
            found.then((values) => values.get(id) ?? null),
          );
        await found;
        done += chunk.length;
        progress?.(done, total);
      }
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
