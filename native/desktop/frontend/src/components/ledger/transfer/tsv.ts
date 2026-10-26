// Tab-separated text for a spreadsheet's paste: one header row, then one row
// per record. A cell a spreadsheet would read as a formula starts with an
// apostrophe, as the product's own CSV export writes it; a plain signed
// decimal stays a number. Tabs and line breaks inside a cell become spaces,
// so a value never spills into the next cell or row.

import type {
  CatalogueInvoice,
  LedgerRow,
  PublicDecimal,
} from "../../../shell/ledger";

const FORMULA = /^\s*[=+\-@\t\r]/;
const SIGNED_DECIMAL = /^[+-]?\d+(\.\d+)?$/;

/** One cell as a spreadsheet takes it literally. */
export function tsvCell(value: string | null | undefined): string {
  const text = (value ?? "").replace(/[\t\r\n]+/g, " ");
  return FORMULA.test(text) && !SIGNED_DECIMAL.test(text.trim())
    ? `'${text}`
    : text;
}

export const tsvText = (header: readonly string[], rows: string[][]) =>
  [header, ...rows].map((row) => row.map(tsvCell).join("\t")).join("\n");

const decimal = (value: PublicDecimal | null) => value?.decimal ?? "";

/** The invoices' identity and totals, in canonical decimals. */
export function invoicesTsv(
  header: readonly string[],
  invoices: readonly CatalogueInvoice[],
): string {
  return tsvText(
    header,
    invoices.map((invoice) => [
      invoice.kind,
      invoice.series ?? "",
      invoice.invoice_number,
      invoice.issued_at,
      invoice.counterparty_name,
      invoice.counterparty_tax_id ?? "",
      invoice.counterparty_country,
      decimal(invoice.base_total),
      decimal(invoice.iva_total),
      decimal(invoice.grand_total),
      invoice.currency,
      invoice.payment_status,
    ]),
  );
}

/** The column names `invoicesTsv` writes, by chrome string key. */
export const INVOICE_TSV_COLUMNS = [
  "kind",
  "series",
  "number",
  "date",
  "counterparty",
  "tax_id",
  "country",
  "base",
  "iva",
  "total",
  "currency",
  "payment",
] as const;

/** The movements' stored facts, in canonical decimals. */
export function movementsTsv(
  header: readonly string[],
  rows: readonly LedgerRow[],
): string {
  return tsvText(
    header,
    rows.map(({ transaction, group_label }) => [
      transaction.date,
      transaction.description,
      transaction.counterparty,
      transaction.direction,
      transaction.amount,
      transaction.currency,
      transaction.business_classification,
      transaction.category_id ?? "",
      group_label ?? "",
      transaction.transaction_id,
    ]),
  );
}

/** The column names `movementsTsv` writes, by chrome string key. */
export const MOVEMENT_TSV_COLUMNS = [
  "date",
  "description",
  "counterparty",
  "direction",
  "amount",
  "currency",
  "classification",
  "category",
  "group",
  "id",
] as const;
