import recorded from "../../src/dev/fixtures/ledgerEntryOptions.json" with { type: "json" };
import { servedVocabulary } from "../../src/shell/ledgerServedVocabulary";
import type { LedgerEntryLimits } from "../../src/shell/ledgerSetup";

/** The registry's lists as `ledger.entry-options` served them in the
 * recording, read the way the window reads them. */
export const SERVED = servedVocabulary(
  {
    profile_id: "p",
    families: recorded.families,
    limits: recorded.limits as LedgerEntryLimits,
  },
  "ready",
);
