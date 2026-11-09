import recorded from "@fixtures/ledger-entry-options/ledgerEntryOptions.json" with { type: "json" };
import { servedVocabulary } from "../../src/shell/ledgerServedVocabulary";
import { answerPeriods } from "../../src/dev/periodRecording";
import type { LedgerEntryLimits } from "../../src/shell/ledgerSetup";

/** The registry's lists as `ledger.entry-options` served them in the
 * recording, read the way the window reads them. */
export const SERVED = servedVocabulary(
  {
    profile_id: "p",
    default_currency: recorded.default_currency,
    families: recorded.families,
    classifications: recorded.classifications,
    limits: recorded.limits as LedgerEntryLimits,
    periods: answerPeriods("en", {})!,
  },
  "ready",
);
