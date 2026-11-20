// Words and formats the Import and Export dialogs share: how a refusal, a
// diagnostic and a provider are named, and what the save dialog suggests.

import type {
  ExportSerializationFormat,
  LedgerImportDiagnosticMessage,
  LedgerProviderID,
} from "../../../shell/ledgerTransferContract";
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
  "format_not_installed",
  "statement_account_missing",
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

/** Why a preview could not be read at all, by the code the call failed with. */
const PREVIEW_FAILURES: Readonly<Record<string, string>> = {
  unavailable: "desktop.ledger.import.failure.unavailable",
  not_signed_in: "desktop.ledger.import.failure.not_signed_in",
  too_large: "desktop.ledger.import.failure.too_large",
  not_admitted: "desktop.ledger.import.failure.not_admitted",
  invalid: "desktop.ledger.import.failure.invalid",
  file_unavailable: "desktop.ledger.import.failure.file_unavailable",
};

/** The reason a file could not be previewed, in plain words: a file refusal
 * in its own words, a failed call by its code, and any other code by a
 * general sentence, so the reason is never empty. */
export function previewFailure(t: Translate, code: string): string {
  if (IMPORT_REFUSALS.has(code)) return importRefusal(t, code);
  return Object.hasOwn(PREVIEW_FAILURES, code)
    ? t(PREVIEW_FAILURES[code]!)
    : t("desktop.ledger.import.failure.other");
}

/** Why a call failed, in plain words: the file refusal the runtime named,
 * else the code the call failed with. The sentence is never empty. */
export function failureWords(
  t: Translate,
  code: string,
  reason: string | null,
): string {
  return reason !== null && IMPORT_REFUSALS.has(reason)
    ? importRefusal(t, reason)
    : previewFailure(t, code);
}

/** Why a book was not imported: the sentence the backend served for the
 * refusal, else its code in plain words, else a general sentence. */
export function bookRefusalWords(
  t: Translate,
  refusal: { words: string | null; reason: string | null },
): string {
  return refusal.words ?? failureWords(t, "refused", refusal.reason);
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

export const providerName = (t: Translate, provider: LedgerProviderID) =>
  t(`desktop.ledger.import.provider.${provider.replace("-", "_")}`);

/** The name the save dialog suggests: the ledger, its period and format,
 * with no folder. */
export function exportFileName(
  t: Translate,
  period: LedgerPeriod | null,
  format: ExportSerializationFormat,
): string {
  const stem = t("desktop.ledger.export.file_stem");
  const when = period ? `-${period.year}-${period.code}` : "";
  return `${stem}${when}.${format}`;
}
