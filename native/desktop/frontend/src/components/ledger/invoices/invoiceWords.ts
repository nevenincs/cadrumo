// How the Invoices section names what the catalogue stores: kinds, classes,
// payment states and rate slots by their localized labels, figures in the
// page's language, and why a typed value was not taken. A token the page
// does not know is shown as itself, never guessed at.

import type {
  InvoiceKind,
  InvoiceFiguresPreviewRateSlot,
} from "../../../shell/ledgerInvoiceContract";
import type { Translate } from "../../../shell/strings";
import { formatDay } from "../../../shared/dateFormats";
import { formatDecimal } from "../../../shared/numbers";
import { isPaymentStatus } from "../../../shell/ledgerContract";
import type { PreviewFinding, Problem } from "./invoiceModel";

const lower = (token: string) => token.toLowerCase();

export const kindLabel = (t: Translate, kind: InvoiceKind) =>
  t(`desktop.ledger.invoices.kind.${kind}`);
/** The words a new invoice's kind is chosen by. */
export const kindChoice = (t: Translate, kind: InvoiceKind) =>
  t(`desktop.ledger.invoices.kind_choice.${kind}`);

export const classLabel = (t: Translate, token: string) => {
  const key = `desktop.ledger.invoices.class.${lower(token)}`;
  const said = t(key);
  return said === key ? token : said;
};

export const paymentLabel = (t: Translate, status: string) =>
  isPaymentStatus(status)
    ? t(`desktop.ledger.invoices.payment.${lower(status)}`)
    : status;

/** A rate slot in the word the ledger serves for it. */
export function rateLabel(
  t: Translate,
  slots: readonly InvoiceFiguresPreviewRateSlot[],
  token: string,
): string {
  const served = slots.find((found) => found.slot === token);
  return served ? t(served.label_key) : token;
}

/** What the ledger found, in its catalogue's words and with its values. */
export function findingText(
  t: Translate,
  finding: PreviewFinding,
  slots: readonly InvoiceFiguresPreviewRateSlot[],
): string {
  const locale = t.locale ?? "en";
  const values: Record<string, string | number> = {};
  for (const { key, value } of finding.values) {
    if (typeof value === "object")
      values[key] = formatDecimal(locale, value.decimal, { minFraction: 2 });
    else if (key === "on_date") values[key] = formatDay(locale, String(value));
    else if (key === "slot") values[key] = rateLabel(t, slots, String(value));
    else values[key] = typeof value === "number" ? value : String(value);
  }
  return t(finding.label_key, values);
}

/** Why a value was not taken, in plain words, with the spelling meant
 * where one reading is certain. */
export function problemText(t: Translate, problem: Problem): string {
  if (problem.kind === "missing")
    return t("desktop.ledger.invoices.problem.missing");
  if (problem.kind === "rule")
    return t(`desktop.ledger.invoices.problem.${problem.rule}`, problem.values);
  if (problem.kind === "finding")
    return findingText(t, problem.finding, problem.slots);
  const { key, raw, suggestion, limit } = problem.refusal;
  const said = t(`desktop.ledger.invoices.refusal.${key}`, {
    raw,
    limit: limit ?? "",
  });
  return suggestion === undefined
    ? said
    : `${said} ${t("desktop.ledger.invoices.refusal.meant", { suggestion })}`;
}
