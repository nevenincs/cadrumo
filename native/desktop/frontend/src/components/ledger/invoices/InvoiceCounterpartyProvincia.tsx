import { useCallback, useEffect, useRef, useState } from "react";
import type { LedgerPort } from "../../../shell/ledger";
import type { LedgerCounterpartyResult } from "../../../shell/ledgerClassificationSetup";
import { CounterpartyProvincia } from "../setup/CounterpartyProvincia";
import { setupCall } from "../setup/setupModel";
import { useStrings } from "../../../shell/strings";
import { EditorSection } from "./InvoiceFields";

/** Who states a provincia from the invoice editor, which asks for no name. */
export const LEDGER_INVOICE_ACTOR = "operator:desktop-ledger";

/**
 * The provincia of a Spanish counterparty's domicilio fiscal, stated from one
 * of its invoices. It belongs to the counterparty, so every invoice of that
 * counterparty shows the same answer and Modelo 347 declares it on each record.
 */
export function InvoiceCounterpartyProvincia({
  port,
  taxId,
  country,
}: {
  port: LedgerPort;
  taxId: string | null;
  country: string;
}) {
  const t = useStrings();
  const [result, setResult] = useState<LedgerCounterpartyResult | null>(null);
  const generation = useRef(0);
  const spanish = taxId !== null && country.toUpperCase() === "ES";
  const read = useCallback(async () => {
    if (!spanish || taxId === null) return;
    const mine = ++generation.current;
    const call = await setupCall(
      port,
      "ledger.counterparty",
      { action: "view", tax_identifier: taxId, country_code: "ES" },
      false,
    );
    if (mine === generation.current)
      setResult(call.kind === "done" ? call.result : null);
  }, [port, taxId, spanish]);
  useEffect(() => {
    setResult(null);
    void read();
    return () => {
      generation.current += 1;
    };
  }, [read]);

  if (!spanish || result === null) return null;
  return (
    <EditorSection title={t("desktop.ledger.counterparty.provincia")}>
      <CounterpartyProvincia
        key={result.provincia_code ?? ""}
        port={port}
        result={result}
        country="ES"
        actor={LEDGER_INVOICE_ACTOR}
        onSaved={read}
      />
    </EditorSection>
  );
}
