// The invoice catalogue as the Invoices section reads it: whole, once it is
// shown, and again after a write. The ledger lists invoices by kind only, so
// the section filters, sorts and windows the whole catalogue itself. What it
// reads lives in this hook's memory and goes with the profile.

import { useCallback, useEffect, useRef, useState } from "react";
import type { CatalogueInvoice, LedgerPort } from "../../../shell/ledger";
import {
  readAnswer,
  readFailure,
  type LedgerReadFailure,
} from "../../../shell/ledgerWindow";

export type CatalogueRead =
  | { phase: "reading"; invoices: CatalogueInvoice[] | null }
  | { phase: "ready"; invoices: CatalogueInvoice[] }
  | { phase: "failed"; failure: LedgerReadFailure; invoices: null };

export function useInvoiceCatalogue(
  port: LedgerPort,
  reader: string | null,
  shown: boolean,
) {
  const [read, setRead] = useState<CatalogueRead>({
    phase: "reading",
    invoices: null,
  });
  const generation = useRef(0);
  const lastReader = useRef(reader);
  const [wanted, setWanted] = useState(0);

  useEffect(() => {
    if (lastReader.current !== reader) {
      lastReader.current = reader;
      setRead({ phase: "reading", invoices: null });
    }
    if (!shown || reader === null) return;
    generation.current += 1;
    const mine = generation.current;
    setRead((held) => ({
      phase: "reading",
      invoices: held.phase === "failed" ? null : held.invoices,
    }));
    void port
      .submit("ledger.invoice.list", {})
      .then((outcome) => {
        if (mine !== generation.current) return;
        const answer = readAnswer(outcome);
        setRead(
          answer.kind === "answer"
            ? { phase: "ready", invoices: answer.result.invoices }
            : { phase: "failed", failure: answer.failure, invoices: null },
        );
      })
      .catch((error: unknown) => {
        if (mine !== generation.current) return;
        setRead({
          phase: "failed",
          failure: readFailure(error),
          invoices: null,
        });
      });
  }, [port, reader, shown, wanted]);

  /** Reads the catalogue again; what was read stays shown meanwhile. */
  const reread = useCallback(() => setWanted((count) => count + 1), []);
  /** Puts one invoice the ledger returned in place of its stored copy. */
  const settle = useCallback(
    (invoice: CatalogueInvoice | null, removed?: string) =>
      setRead((held) => {
        if (held.invoices === null) return held;
        const rest = held.invoices.filter(
          (found) =>
            found.invoice_id !== removed &&
            found.invoice_id !== invoice?.invoice_id,
        );
        return { ...held, invoices: invoice ? [...rest, invoice] : rest };
      }),
    [],
  );
  return { read, reread, settle };
}
