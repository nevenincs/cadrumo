// When the Ledger page runs its readiness checks: once for each period
// window it has read whole, and again when that window is read again. What
// they found is kept as it stood, and dropped with the profile.

import { useEffect, useRef, useState } from "react";
import type { LedgerPort } from "./ledger";
import { samePeriod, type LedgerPeriod } from "./ledgerGrammar";
import {
  checkReadiness,
  readinessSnapshot,
  type Readiness,
} from "./ledgerWindow";

const NOT_CHECKED: Readiness = { kind: "not_checked" };

/**
 * The readiness of `period` in `reader`'s ledger, checked whenever `read`
 * names a window read that has not been checked yet; null asks for nothing.
 * Only the latest check is shown. A check that fails is said as failed,
 * never as ready.
 */
export function useLedgerReadiness(
  port: LedgerPort | undefined,
  reader: string | null,
  period: LedgerPeriod | null,
  read: number | null,
): Readiness {
  const [state, setState] = useState<{
    reader: string | null;
    readiness: Readiness;
  }>({ reader, readiness: NOT_CHECKED });
  const asked = useRef<{ reader: string; read: number } | null>(null);

  useEffect(() => {
    if (!port || reader === null || read === null) return;
    if (asked.current?.reader === reader && asked.current.read === read) return;
    const mine = { reader, read };
    asked.current = mine;
    setState((current) => ({
      reader,
      readiness: {
        kind: "checking",
        held:
          current.reader === reader
            ? readinessSnapshot(current.readiness)
            : null,
      },
    }));
    void checkReadiness(port, period, Date.now).then((answer) => {
      if (asked.current !== mine) return;
      setState((current) => ({
        reader,
        readiness:
          answer.kind === "checked"
            ? answer
            : {
                kind: "failed",
                failure: answer.failure,
                held:
                  current.reader === reader
                    ? readinessSnapshot(current.readiness)
                    : null,
              },
      }));
    });
  }, [port, reader, read, period]);

  if (state.reader !== reader) return NOT_CHECKED;
  // What was checked for another period says nothing of this one.
  const snapshot = readinessSnapshot(state.readiness);
  if (snapshot && !samePeriod(snapshot.period, period)) return NOT_CHECKED;
  return state.readiness;
}
