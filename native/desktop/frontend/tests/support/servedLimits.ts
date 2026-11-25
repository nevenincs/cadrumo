// A spec of the entry grammar reads the limits the backend answered, recorded
// with the entry options; the page holds them the same way once they are served.
// What each classification takes is recorded with them, so it is held here too.
import "./servedClassifications";
import recorded from "@fixtures/ledger-entry-options/ledgerEntryOptions.json" with { type: "json" };
import { holdLedgerLimits } from "../../src/shell/ledgerLimits";
import type { LedgerEntryLimitsProjection } from "../../src/shell/ledgerEntryContract";

export const servedLimits = recorded.limits as LedgerEntryLimitsProjection;

holdLedgerLimits(servedLimits);
