// `ledger.invoice.duplicate` for the fixtures. Stories correct readings freely
// over a generated catalogue, so a recording cannot hold each question: this
// stand-in works the answer out. the generated `ledgerInvoiceDuplicate.json` holds what
// the real backend answered, a test in the owning Python package holds that
// recording to the live answer, and a test here holds this stand-in to it.

import { sameDecimal } from "../shell/ledgerGrammar";
import type {
  LedgerInvoiceDuplicateRequest,
  LedgerInvoiceDuplicateResult,
} from "../shell/ledgerInvoiceOperations";
import type { CatalogueInvoiceSnapshot } from "../shell/ledgerInvoiceContract";

const folded = (text: string | null | undefined) =>
  (text ?? "").toUpperCase().replace(/[^A-Z0-9]+/g, "");

type Stored = Pick<
  CatalogueInvoiceSnapshot,
  "invoice_id" | "kind" | "invoice_number" | "counterparty_tax_id" | "issued_at"
> & { grand_total: { decimal: string } };

export function answerInvoiceDuplicate(
  request: LedgerInvoiceDuplicateRequest,
  invoices: readonly Stored[],
  profileId: string,
): LedgerInvoiceDuplicateResult {
  const same = invoices.filter((invoice) => invoice.kind === request.kind);
  const number = folded(request.invoice_number);
  const taxId = folded(request.counterparty_tax_id);
  const byNumber = same.find((invoice) => {
    const theirs = folded(invoice.counterparty_tax_id);
    return (
      !!number &&
      folded(invoice.invoice_number) === number &&
      (!taxId || !theirs || taxId === theirs)
    );
  });
  if (byNumber)
    return {
      profile_id: profileId,
      invoice_id: byNumber.invoice_id,
      basis: "number",
    };
  const total = request.grand_total;
  const byDay = same.find(
    (invoice) =>
      !!taxId &&
      taxId === folded(invoice.counterparty_tax_id) &&
      request.invoice_date === invoice.issued_at &&
      !!total &&
      sameDecimal(total, invoice.grand_total.decimal),
  );
  return byDay
    ? {
        profile_id: profileId,
        invoice_id: byDay.invoice_id,
        basis: "party_day_total",
      }
    : { profile_id: profileId, invoice_id: null, basis: null };
}
