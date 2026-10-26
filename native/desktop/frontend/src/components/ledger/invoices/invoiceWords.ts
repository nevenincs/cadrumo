// How the Invoices section names what the catalogue stores: kinds, classes,
// payment states and rate slots by their localized labels, figures in the
// page's language, and why a typed value was not taken. A token the page
// does not know is shown as itself, never guessed at.

import type { InvoiceKind, PaymentStatus } from "../../../shell/ledger";
import type { Translate } from "../../../shell/strings";
import {
  INVOICE_CLASSES,
  PAYMENT_STATUSES,
  RATE_SLOTS,
  isRateSlot,
  type Problem,
} from "./invoiceModel";

const lower = (token: string) => token.toLowerCase();

export const kindLabel = (t: Translate, kind: InvoiceKind) =>
  t(`desktop.ledger.invoices.kind.${kind}`);
/** The words a new invoice's kind is chosen by. */
export const kindChoice = (t: Translate, kind: InvoiceKind) =>
  t(`desktop.ledger.invoices.kind_choice.${kind}`);

export const classLabel = (t: Translate, token: string) =>
  (INVOICE_CLASSES as readonly string[]).includes(token)
    ? t(`desktop.ledger.invoices.class.${lower(token)}`)
    : token;

export const paymentLabel = (t: Translate, status: string) =>
  PAYMENT_STATUSES.includes(status as PaymentStatus)
    ? t(`desktop.ledger.invoices.payment.${lower(status)}`)
    : status;

const percents = new Map<string, Intl.NumberFormat>();
/** A rate slot as the invoice prints it: `21%`, or Exempt or Not subject. */
export function rateLabel(t: Translate, locale: string, slot: string): string {
  if (!isRateSlot(slot)) return slot;
  const fraction = RATE_SLOTS.find((found) => found.slot === slot)!.fraction;
  if (fraction === null)
    return t(`desktop.ledger.invoices.rate.${lower(slot)}`);
  let format = percents.get(locale);
  if (!format) {
    format = new Intl.NumberFormat(locale, {
      style: "percent",
      maximumFractionDigits: 1,
    });
    percents.set(locale, format);
  }
  return format.format(Number(fraction));
}

const figures = new Map<string, Intl.NumberFormat>();
/** A figure to the cent in the page's grouping. It is drawn from exact
 * decimal text, never computed with. */
export function figureText(locale: string, amount: string): string {
  let format = figures.get(locale);
  if (!format) {
    format = new Intl.NumberFormat(locale, {
      minimumFractionDigits: 2,
      maximumFractionDigits: 2,
    });
    figures.set(locale, format);
  }
  return format.format(Number(amount));
}

/** Why a value was not taken, in plain words, with the spelling meant
 * where one reading is certain. */
export function problemText(t: Translate, problem: Problem): string {
  if (problem.kind === "missing")
    return t("desktop.ledger.invoices.problem.missing");
  if (problem.kind === "rule")
    return t(`desktop.ledger.invoices.problem.${problem.rule}`, problem.values);
  const { key, raw, suggestion, limit } = problem.refusal;
  const said = t(`desktop.ledger.invoices.refusal.${key}`, {
    raw,
    limit: limit ?? "",
  });
  return suggestion === undefined
    ? said
    : `${said} ${t("desktop.ledger.invoices.refusal.meant", { suggestion })}`;
}
