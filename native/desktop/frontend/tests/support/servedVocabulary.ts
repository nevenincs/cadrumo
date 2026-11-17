import recorded from "@fixtures/ledger-entry-options/ledgerEntryOptions.json" with { type: "json" };
import { servedVocabulary } from "../../src/shell/ledgerServedVocabulary";
import { answerPeriods } from "../../src/dev/periodRecording";
import type {
  LedgerEntryLimitsProjection,
  LedgerEntryOptionsProjection,
} from "../../src/shell/ledgerEntryContract";

/** The registry's lists as `ledger.entry-options` served them in the
 * recording, read the way the window reads them. */
export const SERVED = servedVocabulary(
  {
    profile_id: "p",
    default_currency: recorded.default_currency,
    families: recorded.families as LedgerEntryOptionsProjection["families"],
    classifications:
      recorded.classifications as LedgerEntryOptionsProjection["classifications"],
    limits: recorded.limits as LedgerEntryLimitsProjection,
    // The recording predates the served link fields, which this reads none of.
    link_fields: [],
    periods: answerPeriods("en", {})!,
  },
  "ready",
);
