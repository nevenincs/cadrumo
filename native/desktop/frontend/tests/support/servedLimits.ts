// A spec of the entry grammar reads the limits the backend answered, recorded
// with the entry options; the page holds them the same way once they are served.
import recorded from "../../src/dev/fixtures/ledgerEntryOptions.json" with { type: "json" };
import { holdLedgerLimits } from "../../src/shell/ledgerLimits";
import type { LedgerEntryLimits } from "../../src/shell/ledgerSetup";

export const servedLimits = recorded.limits as LedgerEntryLimits;

holdLedgerLimits(servedLimits);
