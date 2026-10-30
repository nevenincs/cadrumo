// Words and formats the Import and Export dialogs share: how a refusal, a
// diagnostic and a provider are named, and how an amount, a day and a file
// size are written in the page's language.

import type {
  LedgerExportFormat,
  LedgerImportDiagnosticMessage,
  LedgerProvider,
} from "../../../shell/ledger";
import type { LedgerPeriod } from "../../../shell/ledgerGrammar";
import type { Translate } from "../../../shell/strings";
import { dateFormats } from "../../../shared/dateFormats";
import { isoDay } from "../../../shared/dates";

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
  "transactions.import.message_082074": "already_in_ledger",
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

/** An amount with its currency, in the page's language. */
export function amountText(
  locale: string,
  amount: string,
  currency: string,
): string {
  try {
    return new Intl.NumberFormat(locale, {
      style: "currency",
      currency,
      minimumFractionDigits: 2,
    }).format(Number(amount));
  } catch {
    return `${amount} ${currency}`;
  }
}

export const dayText = (locale: string, day: string) =>
  dateFormats(locale).medium.format(isoDay(day));

/** A file's size as the platform would say it. */
export function sizeText(locale: string, bytes: number | null): string {
  if (bytes === null) return "";
  const units = ["byte", "kilobyte", "megabyte", "gigabyte"] as const;
  let value = bytes;
  let unit = 0;
  while (value >= 1024 && unit < units.length - 1) {
    value /= 1024;
    unit += 1;
  }
  return new Intl.NumberFormat(locale, {
    style: "unit",
    unit: units[unit],
    unitDisplay: "short",
    maximumFractionDigits: unit === 0 ? 0 : 1,
  }).format(value);
}

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
