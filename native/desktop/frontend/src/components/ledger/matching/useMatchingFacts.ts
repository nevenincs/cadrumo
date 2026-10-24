// What matching reads beside the period's movements: the invoice catalogue,
// the links the two catalogues disagree about, and the declarations whose
// sealed figures the ledger has moved under. Each is read once it is shown
// and again when the page reads its movements again; a failed read is said
// as failed, never as nothing to match. It lives in this hook's memory and
// goes with the profile.

import { useCallback, useEffect, useRef, useState } from "react";
import type {
  CatalogueInvoice,
  LedgerCheckResult,
  LedgerPort,
  LedgerStatusResult,
} from "../../../shell/ledger";
import {
  readAnswer,
  readFailure,
  type LedgerReadFailure,
} from "../../../shell/ledgerWindow";

export type Facts<T> =
  | { phase: "reading"; value: T | null }
  | { phase: "ready"; value: T }
  | { phase: "failed"; failure: LedgerReadFailure; value: null };

export type MatchingFacts = {
  invoices: Facts<CatalogueInvoice[]>;
  inconsistencies: Facts<LedgerCheckResult["link_inconsistencies"]>;
  affected: Facts<LedgerStatusResult["stale_filings"]>;
};

const READING = { phase: "reading", value: null } as const;
const START: MatchingFacts = {
  invoices: READING,
  inconsistencies: READING,
  affected: READING,
};

async function read<T>(
  ask: () => Promise<Parameters<typeof readAnswer>[0]>,
  pick: (result: never) => T,
): Promise<Facts<T>> {
  try {
    const answer = readAnswer(await ask());
    return answer.kind === "answer"
      ? { phase: "ready", value: pick(answer.result as never) }
      : { phase: "failed", failure: answer.failure, value: null };
  } catch (error) {
    return { phase: "failed", failure: readFailure(error), value: null };
  }
}

/**
 * The facts matching needs from `reader`'s ledger, read while `shown`, and
 * again whenever `generation` names a new read of the movements.
 */
export function useMatchingFacts(
  port: LedgerPort,
  reader: string | null,
  shown: boolean,
  generation: number | null,
): { facts: MatchingFacts; reread(): void } {
  const [facts, setFacts] = useState<MatchingFacts>(START);
  const [wanted, setWanted] = useState(0);
  const asked = useRef(0);
  const lastReader = useRef(reader);

  useEffect(() => {
    if (lastReader.current !== reader) {
      lastReader.current = reader;
      setFacts(START);
    }
    if (!shown || reader === null) return;
    asked.current += 1;
    const mine = asked.current;
    const keep = <T>(held: Facts<T>): Facts<T> => ({
      phase: "reading",
      value: held.value,
    });
    setFacts((held) => ({
      invoices: keep(held.invoices),
      inconsistencies: keep(held.inconsistencies),
      affected: keep(held.affected),
    }));
    const settle =
      <K extends keyof MatchingFacts>(key: K) =>
      (value: MatchingFacts[K]) => {
        if (mine !== asked.current) return;
        setFacts((held) => ({ ...held, [key]: value }));
      };
    void read(
      () => port.submit("ledger.invoice.list", {}),
      (result: { invoices: CatalogueInvoice[] }) => result.invoices,
    ).then(settle("invoices"));
    void read(
      () => port.submit("ledger.check", {}),
      (result: LedgerCheckResult) => result.link_inconsistencies,
    ).then(settle("inconsistencies"));
    void read(
      () => port.submit("ledger.status", {}),
      (result: LedgerStatusResult) => result.stale_filings,
    ).then(settle("affected"));
  }, [port, reader, shown, generation, wanted]);

  const reread = useCallback(() => setWanted((count) => count + 1), []);
  return { facts: reader === lastReader.current ? facts : START, reread };
}
