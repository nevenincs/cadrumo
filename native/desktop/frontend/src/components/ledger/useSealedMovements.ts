// Which movements a finalized declaration cites, as far as the page has
// read. The product reports it per movement only: the participation index
// answers one movement at a time, through `ledger.track`, and nothing reads
// it for a period. So the page reads the movements it acts on, the selected
// and the staged ones, a bounded number per read of the window, and the
// review reads the staged ones it is about to save. A movement whose
// participation was not read, or whose index was never built, is not known
// to be sealed; the product refuses a change to a sealed one regardless.

import { useCallback, useEffect, useRef, useState } from "react";
import type { LedgerPort } from "../../shell/ledger";
import { readAnswer } from "../../shell/ledgerWindow";
import { seals } from "./inspector/inspectorWords";

/** The most movements read for one read of the window. */
export const SEALED_READS = 400;
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

/**
 * The sealed movements among `wanted`, read as they are wanted and kept
 * until the window is read again (`generation`) or the profile changes.
 * `sealedOf` reads what it is asked now and answers once it has.
 */
export function useSealedMovements(
  port: LedgerPort,
  reader: string | null,
  generation: number | string | null,
  wanted: readonly string[],
): {
  sealed: ReadonlySet<string>;
  sealedOf: (ids: readonly string[]) => Promise<ReadonlySet<string>>;
} {
  const [sealed, setSealed] = useState<ReadonlySet<string>>(new Set());
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
  useEffect(() => setSealed(new Set()), [reader, generation]);

  const read = useCallback(
    async (ids: readonly string[]): Promise<ReadonlySet<string>> => {
      const map = known.current;
      const asking = ids.filter((id) => !map.has(id));
      const room = Math.max(0, SEALED_READS - map.size);
      const queue = asking.slice(0, room);
      const run = async () => {
        for (let id = queue.shift(); id !== undefined; id = queue.shift()) {
          const found = readSealed(port, id);
          map.set(id, found);
          await found;
        }
      };
      await Promise.all(Array.from({ length: AT_ONCE }, run));
      const out = new Set<string>();
      for (const id of ids) if ((await map.get(id)) === true) out.add(id);
      if (known.current === map && out.size > 0)
        setSealed((before) => {
          const missing = [...out].some((id) => !before.has(id));
          return missing ? new Set([...before, ...out]) : before;
        });
      return out;
    },
    [port],
  );

  const key = wanted.join(" ");
  useEffect(() => {
    if (reader === null || generation === null || key === "") return;
    void read(key.split(" "));
  }, [read, reader, generation, key]);

  return { sealed, sealedOf: read };
}
