// What every Setup section is given by the Ledger page.

import type { LedgerPort, LedgerRow } from "../../../shell/ledger";
import type { LedgerPeriod } from "../../../shell/ledgerGrammar";
import type { StageEvent, StagedContent } from "../../../shell/ledgerStage";

export type SetupProps = {
  port: LedgerPort;
  /** Whose ledger; null while the account withholds it. */
  reader: string | null;
  locale: string;
  /** The movements the page has loaded, or null where it has none. */
  rows: readonly LedgerRow[] | null;
  /** What is staged on the page, and how a section stages more. */
  stage: StagedContent;
  onStage(event: StageEvent): void;
  /** The years that hold movements, or null while they are not known. */
  years: readonly number[] | null;
  /** The year a year selector opens on. */
  fallbackYear: number;
  /** The page's period, which the Health section checks. */
  period: LedgerPeriod | null;
};
