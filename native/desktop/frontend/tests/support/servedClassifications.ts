// A spec of the ledger's models reads what each classification takes as the
// backend answered, recorded with the entry options; the page holds it the same
// way once it is served.
import recorded from "@fixtures/ledger-entry-options/ledgerEntryOptions.json" with { type: "json" };
import { holdLedgerClassifications } from "../../src/shell/ledgerClassifications";
import type { LedgerEntryClassificationProjection } from "../../src/shell/ledgerEntryContract";

export const servedClassifications =
  recorded.classifications as LedgerEntryClassificationProjection[];

holdLedgerClassifications(servedClassifications);
