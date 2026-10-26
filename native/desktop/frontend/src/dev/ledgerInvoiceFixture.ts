// The scenario ledger's invoice writes and lookups, held to the registered
// contracts of `ledger.invoice.add`, `.update`, `.remove` and `.view`. A
// request its contract would not decode is refused before anything runs.
// An add the ledger finds invalid or already in the catalogue settles as a
// refusal carrying its validation code. A correction or removal the ledger
// refuses after it began to write ends with its effect unknown, as the
// runtime reports it: the page must read the catalogue again to learn what
// happened. Everything it answers is synthetic.

import {
  INVOICE_UPDATE_FIELDS,
  type CatalogueInvoice,
  type CatalogueInvoiceLine,
  type JsonObject,
  type JsonValue,
} from "../shell/ledger";
import type { FixtureLedger } from "./fixtures/ledger";

/** A request its registered contract would not decode. */
export class InvoiceRequestInvalid extends Error {}
/** Settled without writing, with the refusal's code and detail. */
export class InvoiceStopped extends Error {
  constructor(
    readonly reason: string,
    readonly detail: JsonObject,
  ) {
    super(reason);
  }
}
/** Refused after its effect became unknown: it ends unsettled. */
export class InvoiceUnsettled extends Error {}

type Tools = {
  profileId: string;
  events: () => string[];
  hex64: (text: string) => string;
};

const CANONICAL = /^(0|[1-9]\d*)(\.\d+)?$/;
const DATE = /^\d{4}-\d{2}-\d{2}$/;
const SLOTS: Record<string, bigint | null> = {
  RATE_0: 0n,
  RATE_2: 20n,
  RATE_4: 40n,
  "RATE_7.5": 75n,
  RATE_5: 50n,
  RATE_10: 100n,
  RATE_21: 210n,
  EXEMPT: null,
  NOT_SUBJECT: null,
};
const CLASSES = ["ORDINARIA", "SIMPLIFICADA", "RECTIFICATIVA"];
const PAYMENTS = ["PAID", "PENDING", "PARTIALLY_PAID", "OVERDUE", "CANCELLED"];
const OPERATION_TYPES = ["E", "H", "M", "S", "T", "R", "A", "I", "D", "C"];
const ADD_FIELDS = new Set([
  "kind",
  "counterparty_name",
  "counterparty_tax_id",
  "counterparty_country",
  "invoice_number",
  "issued_at",
  "taxable_base",
  "iva_rate",
  "currency",
  "notes",
  "iva_category",
  "operation_type",
  "operation_date",
  "retention_rate",
  "retention_amount",
  "invoice_class",
  "series",
  "rectifies_invoice_number",
  "recargo_amount",
  "business_premises_lease",
  "lines",
]);
const LINE_FIELDS = new Set([
  "description",
  "quantity",
  "unit_price",
  "subtotal",
  "iva_rate",
  "iva_amount",
  "spending_category_id",
  "oss_rate_kind",
]);

const invalid = (): never => {
  throw new InvoiceRequestInvalid();
};
const isObject = (value: JsonValue | undefined): value is JsonObject =>
  typeof value === "object" && value !== null && !Array.isArray(value);
const text = (
  value: JsonValue | undefined,
  required = false,
): string | null => {
  if (value === undefined || value === null) return required ? invalid() : null;
  return typeof value === "string" ? value : invalid();
};
/** A `PublicDecimal`: its text must be the decimal's own canonical form. */
function decimal(
  value: JsonValue | undefined,
  required = false,
): string | null {
  if (value === undefined || value === null) return required ? invalid() : null;
  if (!isObject(value) || Object.keys(value).length !== 1) return invalid();
  const found = value.decimal;
  return typeof found === "string" && CANONICAL.test(found) ? found : invalid();
}
/** Exact hundredths of a hundredth, so a cent is 100 units. */
const units = (value: string) => {
  const [whole, fraction = ""] = value.split(".");
  return (
    BigInt(`${whole}${fraction.padEnd(4, "0").slice(0, 4)}`) +
    (fraction.length > 4 && Number(fraction[4]) >= 5 ? 1n : 0n)
  );
};
const CENT = 100n;
const apart = (left: bigint, right: bigint) =>
  (left > right ? left - right : right - left) > CENT;
const textOf = (value: bigint) => {
  const cents = (value + 50n) / 100n;
  const digits = cents.toString().padStart(3, "0");
  return `${digits.slice(0, -2)}.${digits.slice(-2)}`;
};

export function invoiceOperations(ledger: FixtureLedger, tools: Tools) {
  const { profileId, events, hex64 } = tools;
  const refuseAdd = (
    code: "invalid_invoice" | "duplicate_invoice",
    invoiceId: string | null = null,
  ): never => {
    throw new InvoiceStopped("REFUSED_INVOICE_ADD_VALIDATION", {
      outcome: "validation_error",
      profile_id: profileId,
      invoice: null,
      invoice_id: invoiceId,
      bucket_event_ids: [],
      euro_value_pending: false,
      simplificada_tax_id_advisory_required: false,
      validation_code: code,
    });
  };

  /** The invoice an id or unambiguous prefix names, or why none. */
  function lookup(
    selector: string,
  ):
    | { kind: "found"; invoice: CatalogueInvoice }
    | { kind: "refused"; reason: string; candidates: string[] } {
    const prefix = selector.trim().toLowerCase();
    if (!prefix) return { kind: "refused", reason: "required", candidates: [] };
    const found = ledger.invoices.filter((invoice) =>
      invoice.invoice_id.startsWith(prefix),
    );
    if (found.length === 1) return { kind: "found", invoice: found[0]! };
    return found.length === 0
      ? { kind: "refused", reason: "not_found", candidates: [] }
      : {
          kind: "refused",
          reason: "ambiguous",
          candidates: found.map((invoice) => invoice.invoice_id),
        };
  }

  /** What the invoice model refuses: totals, retención, recargo and the
   * class's own facts. */
  function holds(invoice: CatalogueInvoice): boolean {
    const base = units(invoice.base_total.decimal);
    const iva = units(invoice.iva_total.decimal);
    const rectificativa = invoice.invoice_class === "RECTIFICATIVA";
    if (rectificativa && (!invoice.series || !invoice.rectifies_invoice_number))
      return false;
    if (!rectificativa && invoice.rectifies_invoice_number !== null)
      return false;
    if (
      invoice.counterparty_tax_id === null &&
      !(invoice.invoice_class === "SIMPLIFICADA" && invoice.kind === "issued")
    )
      return false;
    const rate = invoice.retention_rate?.decimal ?? null;
    const amount = invoice.retention_amount?.decimal ?? null;
    if (rate !== null) {
      if (amount === null || units(rate) > 10_000n) return false;
      if (apart(units(amount), (base * units(rate)) / 10_000n)) return false;
    }
    if (amount !== null && units(amount) > base) return false;
    if (invoice.recargo_amount && units(invoice.recargo_amount.decimal) > iva)
      return false;
    if (
      (invoice.operation_date === null) !==
      (invoice.operation_date_role === null)
    )
      return false;
    return /^[A-Z]{2}$/.test(invoice.counterparty_country);
  }

  function add(request: JsonObject): JsonObject {
    if (Object.keys(request).some((key) => !ADD_FIELDS.has(key))) invalid();
    const kind = text(request.kind, true);
    if (kind !== "issued" && kind !== "received") invalid();
    const name = text(request.counterparty_name, true)!;
    if (!name) invalid();
    const country = text(request.counterparty_country, true)!;
    if (!/^[A-Za-z]{2}$/.test(country)) invalid();
    const number = text(request.invoice_number, true)!;
    if (!number) invalid();
    const issued = text(request.issued_at, true)!;
    if (!DATE.test(issued)) invalid();
    const currency = text(request.currency, true)!;
    if (!currency || currency.length > 16) invalid();
    const operationDate = text(request.operation_date);
    if (operationDate !== null && !DATE.test(operationDate)) invalid();
    const operationType = text(request.operation_type);
    if (operationType !== null && !OPERATION_TYPES.includes(operationType))
      invalid();
    const lines = request.lines ?? [];
    if (!Array.isArray(lines)) invalid();
    const base = decimal(request.taxable_base);
    if (
      (lines as JsonValue[]).length > 0 &&
      (base !== null || request.iva_rate != null)
    )
      invalid();
    if ((lines as JsonValue[]).length === 0 && base === null) invalid();
    const parsed = (lines as JsonValue[]).map((raw): CatalogueInvoiceLine => {
      if (
        !isObject(raw) ||
        Object.keys(raw).some((key) => !LINE_FIELDS.has(key))
      )
        return invalid();
      const description = text(raw.description, true)!;
      if (!description) invalid();
      return {
        description,
        quantity: { decimal: decimal(raw.quantity, true)! },
        unit_price: { decimal: decimal(raw.unit_price, true)! },
        subtotal: { decimal: decimal(raw.subtotal, true)! },
        iva_rate: text(raw.iva_rate, true)!,
        iva_amount: { decimal: decimal(raw.iva_amount, true)! },
        spending_category_id: text(raw.spending_category_id),
        oss_rate_kind: text(raw.oss_rate_kind),
      };
    });
    const invoiceClass = text(request.invoice_class) ?? "ORDINARIA";
    if (!CLASSES.includes(invoiceClass)) refuseAdd("invalid_invoice");
    // Lines as the model holds them: subtotal and IVA to the cent.
    for (const line of parsed) {
      if (!(line.iva_rate in SLOTS)) refuseAdd("invalid_invoice");
      const quantity = units(line.quantity.decimal);
      const price = units(line.unit_price.decimal);
      const subtotal = units(line.subtotal.decimal);
      if (quantity <= 0n || apart(subtotal, (quantity * price) / 10_000n))
        refuseAdd("invalid_invoice");
      const rate = SLOTS[line.iva_rate]!;
      const iva = units(line.iva_amount.decimal);
      if (rate === null ? iva !== 0n : apart(iva, (subtotal * rate) / 1000n))
        refuseAdd("invalid_invoice");
    }
    const baseUnits = parsed.reduce(
      (sum, line) => sum + units(line.subtotal.decimal),
      0n,
    );
    const ivaUnits = parsed.reduce(
      (sum, line) => sum + units(line.iva_amount.decimal),
      0n,
    );
    const recargo = decimal(request.recargo_amount);
    const total = baseUnits + ivaUnits + (recargo ? units(recargo) : 0n);
    const taxId = text(request.counterparty_tax_id);
    const invoice: CatalogueInvoice = {
      invoice_id: hex64(
        JSON.stringify([
          kind,
          number,
          issued,
          (taxId ?? "").toUpperCase(),
          currency.toUpperCase(),
          textOf(total),
        ]),
      ),
      bucket_id: profileId,
      kind: kind as CatalogueInvoice["kind"],
      invoice_number: number,
      issued_at: issued,
      counterparty_name: name,
      counterparty_tax_id: taxId ? taxId.toUpperCase() : null,
      counterparty_country: country.toUpperCase(),
      base_total: { decimal: textOf(baseUnits) },
      iva_total: { decimal: textOf(ivaUnits) },
      grand_total: { decimal: textOf(total) },
      currency: currency.toUpperCase(),
      payment_status: "PENDING",
      linked_transaction_ids: [],
      source_filename: null,
      source_sha256: null,
      source_row_index: null,
      notes: text(request.notes) ?? "",
      retention_rate: request.retention_rate
        ? { decimal: decimal(request.retention_rate)! }
        : null,
      retention_amount: request.retention_amount
        ? { decimal: decimal(request.retention_amount)! }
        : null,
      recargo_amount: recargo ? { decimal: recargo } : null,
      operation_type: operationType,
      lines: parsed,
      invoice_class: invoiceClass,
      series: text(request.series),
      operation_date: operationDate,
      operation_date_role: operationDate ? "OPERATION_PERFORMED" : null,
      iva_category: text(request.iva_category),
      rectifies_invoice_number: text(request.rectifies_invoice_number),
      fx_rate: null,
      fx_rate_date: null,
      fx_rate_source: null,
      base_total_eur: null,
      iva_total_eur: null,
      grand_total_eur: null,
    };
    if (!holds(invoice)) refuseAdd("invalid_invoice");
    // The identity is the kind, number, issue date, tax id, currency and
    // total: the same identity is the same invoice.
    const same = ledger.invoices.find(
      (found) =>
        found.kind === invoice.kind &&
        found.invoice_number === invoice.invoice_number &&
        found.issued_at === invoice.issued_at &&
        (found.counterparty_tax_id ?? "") ===
          (invoice.counterparty_tax_id ?? "") &&
        found.currency === invoice.currency &&
        units(found.grand_total.decimal) === total,
    );
    if (same) refuseAdd("duplicate_invoice", same.invoice_id);
    ledger.invoices.push(invoice);
    return {
      outcome: "created",
      profile_id: profileId,
      invoice: invoice as unknown as JsonValue,
      invoice_id: null,
      bucket_event_ids: events().slice(0, 1),
      euro_value_pending: invoice.currency !== "EUR",
      simplificada_tax_id_advisory_required: false,
      validation_code: null,
    };
  }

  function update(request: JsonObject): JsonObject {
    const selector = text(request.invoice_id, true)!;
    if (!selector || selector.length > 64) invalid();
    const patch = request.patch;
    if (
      !isObject(patch) ||
      !isObject(patch.values) ||
      !Array.isArray(patch.fields)
    )
      return invalid();
    const fields = patch.fields as JsonValue[];
    if (
      fields.length === 0 ||
      new Set(fields).size !== fields.length ||
      fields.some(
        (field) =>
          typeof field !== "string" ||
          !(INVOICE_UPDATE_FIELDS as readonly string[]).includes(field),
      )
    )
      invalid();
    const values = patch.values;
    for (const [key, value] of Object.entries(values)) {
      if (!(INVOICE_UPDATE_FIELDS as readonly string[]).includes(key))
        invalid();
      if (value !== null && !fields.includes(key)) invalid();
    }
    for (const field of ["retention_rate", "retention_amount"] as const)
      if (fields.includes(field)) decimal(values[field]);
    const status = text(values.payment_status);
    if (status !== null && !PAYMENTS.includes(status)) invalid();
    // From here on the runtime has said its effect may be unknown.
    const found = lookup(selector);
    if (found.kind !== "found") throw new InvoiceUnsettled();
    const next = { ...found.invoice } as Record<string, unknown>;
    for (const field of fields as string[]) {
      const value = values[field] ?? null;
      next[field] = value;
    }
    const corrected = next as unknown as CatalogueInvoice;
    if (
      corrected.counterparty_name === null ||
      corrected.counterparty_country === null ||
      corrected.notes === null ||
      corrected.payment_status === null ||
      corrected.invoice_class === null ||
      !CLASSES.includes(corrected.invoice_class) ||
      (typeof next.payment_id === "string" &&
        !/^[0-9a-f]{64}$/.test(next.payment_id)) ||
      !holds(corrected)
    )
      throw new InvoiceUnsettled();
    // The catalogue does not show a payment id.
    delete (next as { payment_id?: unknown }).payment_id;
    ledger.invoices = ledger.invoices.map((invoice) =>
      invoice.invoice_id === corrected.invoice_id ? corrected : invoice,
    );
    return {
      profile_id: profileId,
      invoice_id: selector,
      invoice: corrected as unknown as JsonValue,
      bucket_event_ids: events(),
    };
  }

  function remove(request: JsonObject): JsonObject {
    const selector = text(request.invoice_id, true)!;
    if (!selector || selector.length > 64 || Object.keys(request).length !== 1)
      invalid();
    const found = lookup(selector);
    // A linked invoice is refused inside the write: its effect is unknown.
    if (
      found.kind !== "found" ||
      found.invoice.linked_transaction_ids.length > 0
    )
      throw new InvoiceUnsettled();
    ledger.invoices = ledger.invoices.filter(
      (invoice) => invoice.invoice_id !== found.invoice.invoice_id,
    );
    return {
      profile_id: profileId,
      invoice_id: selector,
      invoice: found.invoice as unknown as JsonValue,
    };
  }

  function view(request: JsonObject): JsonObject {
    const selector = text(request.invoice_id, true)!;
    const found = lookup(selector);
    if (found.kind === "found")
      return {
        profile_id: profileId,
        invoice_id: selector,
        outcome: {
          kind: "success",
          invoice: found.invoice as unknown as JsonValue,
        },
      };
    throw new InvoiceStopped("REFUSED_INVOICE_LOOKUP", {
      profile_id: profileId,
      invoice_id: selector,
      outcome: {
        kind: "refused",
        reason: found.reason,
        candidate_ids: found.candidates,
      },
    });
  }

  return {
    reads: { "ledger.invoice.view": view },
    writes: {
      "ledger.invoice.add": add,
      "ledger.invoice.update": update,
      "ledger.invoice.remove": remove,
    },
  } as const;
}
