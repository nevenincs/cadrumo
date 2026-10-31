// How matching says what it found: the evidence a pair stands on, which
// side of a one-sided link is missing, why a link cannot be repaired here,
// and an invoice in one line. Nothing here decides anything.

import type { CatalogueInvoice } from "../../../shell/ledger";
import type { Translate } from "../../../shell/strings";
import { formatDay } from "../../../shared/dateFormats";
import { formatAmount } from "../../../shared/numbers";
import { paymentLabel } from "../invoices/invoiceWords";
import { seriesAndNumber } from "../invoices/invoiceModel";
import type { LinkInconsistency, MatchChip } from "./matchingModel";

export function chipText(t: Translate, chip: MatchChip): string {
  switch (chip.kind) {
    case "number":
      return t("desktop.ledger.matching.chip.number");
    case "counterparty":
      return t("desktop.ledger.matching.chip.counterparty");
    case "amount":
      return t("desktop.ledger.matching.chip.amount");
    case "gap":
      return chip.days === 0
        ? t("desktop.ledger.matching.chip.same_day")
        : chip.days > 0
          ? t("desktop.ledger.matching.chip.after", { count: chip.days })
          : t("desktop.ledger.matching.chip.before", { count: -chip.days });
  }
}

export function directionText(
  t: Translate,
  direction: LinkInconsistency["direction"],
): string {
  return direction === "invoice-only"
    ? t("desktop.ledger.matching.direction.invoice_only")
    : t("desktop.ledger.matching.direction.transaction_only");
}

export function noRepairText(
  t: Translate,
  why: Extract<LinkInconsistency["repair"], { kind: "none" }>["why"],
): string {
  switch (why) {
    case "invoice_missing":
      return t("desktop.ledger.matching.no_repair.invoice_missing");
    case "cites_another":
      return t("desktop.ledger.matching.no_repair.cites_another");
    case "not_loaded":
      return t("desktop.ledger.matching.no_repair.not_loaded");
  }
}

/** An invoice in one line: number, counterparty, date and payment. */
export function invoiceLine(
  t: Translate,
  locale: string,
  invoice: CatalogueInvoice,
): string {
  return t("desktop.ledger.matching.invoice_line", {
    number: seriesAndNumber(invoice),
    counterparty: invoice.counterparty_name,
    date: formatDay(locale, invoice.issued_at),
    payment: paymentLabel(t, invoice.payment_status),
  });
}

/** What an invoice settles, with the retención it leaves out. */
export function settlesText(
  t: Translate,
  locale: string,
  invoice: CatalogueInvoice,
  settles: string,
): string {
  return invoice.retention_amount
    ? t("desktop.ledger.matching.settles_withheld", {
        amount: formatAmount(locale, settles),
        total: formatAmount(locale, invoice.grand_total.decimal),
        withheld: formatAmount(locale, invoice.retention_amount.decimal),
      })
    : t("desktop.ledger.matching.settles", {
        amount: formatAmount(locale, settles),
      });
}
