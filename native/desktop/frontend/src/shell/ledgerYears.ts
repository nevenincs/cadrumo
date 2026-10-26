// The years a ledger has movements in, for the period selector's long jumps.
// They come from the ledger itself, never from a range of the calendar: the
// first movement in date order names a year, that year's count says how many
// movements to skip, and the movement after them names the next year. Two
// small reads per year that has movements, whatever the years between.

import { useCallback, useEffect, useState } from "react";
import type { LedgerPort } from "./ledger";
import {
  LEDGER_YEAR_MAX,
  LEDGER_YEAR_MIN,
  periodFilters,
  yearAdmitted,
} from "./ledgerGrammar";
import { readPage } from "./ledgerWindow";

/** The most years the walk reads before it stops: the grammar's own span. */
const YEARS_MAX = LEDGER_YEAR_MAX - LEDGER_YEAR_MIN + 1;

/** The years with movements, in order, or null where they could not be
 * read whole. A partial list is never offered as the whole one. */
export async function readLedgerYears(
  port: LedgerPort,
  stillWanted: () => boolean = () => true,
): Promise<number[] | null> {
  const years: number[] = [];
  let offset = 0;
  while (years.length < YEARS_MAX) {
    if (!stillWanted()) return null;
    const first = await readPage(port, {
      filters: [],
      sort_by: "date",
      sort_order: "asc",
      offset,
      limit: 1,
    });
    if (first.kind !== "answer") return null;
    const row = first.result.rows[0];
    if (!row) return offset >= first.result.total ? years : null;
    const year = Number(row.transaction.date.slice(0, 4));
    // The next year must come after the last: a ledger that changed under
    // the walk, or a count that does not join the order, ends it unread.
    if (!yearAdmitted(year) || year <= (years.at(-1) ?? -Infinity)) return null;
    const count = await readPage(port, {
      filters: periodFilters({ year, code: "0A" }),
      offset: 0,
      limit: 1,
    });
    if (count.kind !== "answer" || count.result.total < 1) return null;
    years.push(year);
    offset += count.result.total;
  }
  return null;
}

/**
 * The years with movements of one profile's ledger, read the first time
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
