// Which movements a finalized declaration cites, as far as the page has
// read. The product reports it per movement only: the participation index
// answers one movement at a time, through `ledger.track`, and nothing reads
// it for a period. So the page reads the movements it acts on, the selected
// and the staged ones, a bounded number per read of the window, and the
// review reads the staged ones it is about to save, on a budget of its own
// and asking again what failed. A movement whose participation could not be
// read, or was left unread past a budget, is unread: never counted as
// sealed or as not sealed. One whose index was never built is not known to
// be sealed; the product refuses a change to a sealed one regardless.

import { useCallback, useEffect, useRef, useState } from "react";
import type { LedgerPort } from "../../shell/ledger";
import { readAnswer } from "../../shell/ledgerWindow";
import { seals } from "./inspector/inspectorWords";

/** The most movements read for one read of the window, for the selection
 * and the staged movements the page acts on. */
export const SEALED_READS = 400;
/** The most movements the review reads each time it opens or reads again,
 * apart from the page's own budget. */
export const REVIEW_SEALED_READS = 400;
/** Reads in flight at once. */
const AT_ONCE = 4;

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
  sealedOf: (ids: readonly string[]) => Promise<SealedRead>;
} {
  const [sealed, setSealed] = useState<ReadonlySet<string>>(new Set());
  const [unread, setUnread] = useState<ReadonlySet<string>>(new Set());
  // What was read, or is being read, for this window and profile.
  const known = useRef(new Map<string, Promise<boolean | null>>());
  const scope = useRef({ reader, generation });
  if (
    scope.current.reader !== reader ||
    scope.current.generation !== generation
  ) {
    scope.current = { reader, generation };
    known.current = new Map();
  }
  useEffect(() => {
    setSealed(new Set());
    setUnread(new Set());
  }, [reader, generation]);

  const read = useCallback(
    async (ids: readonly string[], review: boolean): Promise<SealedRead> => {
      const map = known.current;
      // The review asks again what failed; the page asks once.
      const settled = await Promise.all(
        ids.map(
          async (id) =>
            [id, map.has(id) ? await map.get(id)! : undefined] as const,
        ),
      );
      const asking = settled
        .filter(
          ([, value]) => value === undefined || (review && value === null),
        )
        .map(([id]) => id);
      const room = review
        ? REVIEW_SEALED_READS
        : Math.max(0, SEALED_READS - map.size);
      const queue = asking.slice(0, room);
      const run = async () => {
        for (let id = queue.shift(); id !== undefined; id = queue.shift()) {
          // Another read may have started it since this one looked.
          if (!review && map.has(id)) continue;
          const found = readSealed(port, id);
          map.set(id, found);
          await found;
        }
      };
      await Promise.all(Array.from({ length: AT_ONCE }, run));
      const out = new Set<string>();
      const missed = new Set<string>();
      for (const id of ids) {
        const value = map.has(id) ? await map.get(id) : null;
        if (value === true) out.add(id);
        else if (value !== false) missed.add(id);
      }
      if (known.current === map) {
        if (out.size > 0)
          setSealed((before) => {
            const missing = [...out].some((id) => !before.has(id));
            return missing ? new Set([...before, ...out]) : before;
          });
        setUnread((before) => {
          const next = new Set(before);
          for (const id of ids)
            if (missed.has(id)) next.add(id);
            else next.delete(id);
          const same =
            next.size === before.size &&
            [...next].every((id) => before.has(id));
          return same ? before : next;
        });
      }
      return { sealed: out, unread: missed };
    },
    [port],
  );
  const sealedOf = useCallback(
    (ids: readonly string[]) => read(ids, true),
    [read],
  );

  const key = wanted.join(" ");
  useEffect(() => {
    if (reader === null || generation === null || key === "") return;
    void read(key.split(" "), false);
  }, [read, reader, generation, key]);

  return { sealed, unread, sealedOf };
}
