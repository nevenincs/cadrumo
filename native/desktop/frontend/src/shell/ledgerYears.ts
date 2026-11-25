// The years a ledger holds records in, for the period selector's long jumps.
// They are the backend's: the years of the movements' filing dates and of the
// invoices' issue dates, served by one `ledger.known-values` read. The window
// derives none of them from the rows it has drawn.

import { useCallback, useEffect, useState } from "react";
import type { LedgerPort } from "./ledger";
import { readAnswer } from "./ledgerWindow";

/** The years with a movement or an invoice, oldest first, or null where they
 * could not be read. */
export async function readLedgerYears(
  port: LedgerPort,
  stillWanted: () => boolean = () => true,
): Promise<number[] | null> {
  if (!stillWanted()) return null;
  try {
    const answer = readAnswer(
      await port.submit("ledger.known-values", { kinds: ["ledger_year"] }),
    );
    return answer.kind === "answer" && stillWanted()
      ? [...answer.result.ledger_years]
      : null;
  } catch {
    return null;
  }
}

/**
 * The years with records of one profile's ledger, read the first time
 * `wanted` is true and kept for as long as the reader stays the same. They
 * are dropped when the reader changes and read again on `refresh`.
 */
export function useLedgerYears(
  port: LedgerPort | undefined,
  reader: string | null,
  wanted: boolean,
) {
  const [round, setRound] = useState(0);
  const [held, setHeld] = useState<{
    reader: string | null;
    round: number;
    years: number[] | null;
  } | null>(null);
  const current = held?.reader === reader && held.round === round;

  useEffect(() => {
    if (!port || reader === null || !wanted || current) return;
    let active = true;
    void readLedgerYears(port, () => active).then((years) => {
      if (active) setHeld({ reader, round, years });
    });
    return () => {
      active = false;
    };
  }, [port, reader, wanted, round, current]);

  const refresh = useCallback(() => setRound((value) => value + 1), []);
  return { years: current ? (held?.years ?? null) : null, refresh };
}
