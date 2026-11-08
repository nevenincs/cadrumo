// Words and formats the Import and Export dialogs share: how a refusal, a
// diagnostic and a provider are named, and what the save dialog suggests.

import type {
  LedgerExportFormat,
  LedgerImportDiagnosticMessage,
  LedgerProvider,
} from "../../../shell/ledger";
import type { LedgerPeriod } from "../../../shell/ledgerGrammar";
import type { Translate } from "../../../shell/strings";

const IMPORT_REFUSALS = new Set([
  "transaction_validation",
  "own_account_mismatch",
  "result_limit",
  "source_changed",
  "empty_directory",
  "file_limit",
  "reader_unavailable",
]);

/** Why a file was not imported, in plain words; a code the page does not
 * know is named as it came, after a general sentence. A file only the local
 * AI reads says the local AI is not ready where `setup` names its setup, and
 * that it cannot read the file on this computer where nothing does. */
export function importRefusal(
  t: Translate,
  reason: string,
  setup: string | null = null,
): string {
  if (reason === "reader_unavailable" && setup === null)
    return t("desktop.ledger.import.refusal.reader_unavailable_here");
  return IMPORT_REFUSALS.has(reason)
    ? t(`desktop.ledger.import.refusal.${reason}`)
    : t("desktop.ledger.import.refusal.other");
}

const DIAGNOSTICS: Record<LedgerImportDiagnosticMessage, string> = {
  "transactions.import.message_185962": "no_rows",
  "transactions.import.all_rows_already_in_ledger": "all_already_in_ledger",
  "transactions.import.some_rows_already_in_ledger": "already_in_ledger",
  "transactions.import.batch_id_collision": "same_identity",
  "transactions.import.message_053465": "repeated",
  "transactions.import.message_829073": "gap",
  "transactions.import.verified": "verified",
  "transactions.import.unreadable": "unreadable",
};
export const diagnosticText = (
  t: Translate,
  message: LedgerImportDiagnosticMessage,
) =>
  t(`desktop.ledger.import.diagnostic.${DIAGNOSTICS[message] ?? "unreadable"}`);

export const providerName = (t: Translate, provider: LedgerProvider) =>
  t(`desktop.ledger.import.provider.${provider.replace("-", "_")}`);

/** The name the save dialog suggests: the ledger, its period and format,
 * with no folder. */
export function exportFileName(
  t: Translate,
  period: LedgerPeriod | null,
  format: LedgerExportFormat,
): string {
  const stem = t("desktop.ledger.export.file_stem");
  const when = period ? `-${period.year}-${period.code}` : "";
  return `${stem}${when}.${format}`;
}
