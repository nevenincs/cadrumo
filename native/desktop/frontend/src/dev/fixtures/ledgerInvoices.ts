// Invoices the made-up studio keeps beside the ones its movements settle:
// numbers in other series and classes, a rectificativa, a simplified
// ticket, a foreign supplier and some still unpaid, so that the Invoices
// section's filters, its next-number suggestion and removal each have
// something to find. None is linked to a movement. Every name, number and
// NIF-shaped value is invented.

import type {
  CatalogueInvoice,
  CatalogueInvoiceLine,
  InvoiceKind,
  PaymentStatus,
} from "../../shell/ledger";

type Example = {
  kind: InvoiceKind;
  invoiceClass: "ORDINARIA" | "SIMPLIFICADA" | "RECTIFICATIVA";
  series: string | null;
  number: string;
  issued: string;
  name: string;
  taxId: string | null;
  country: string;
  currency: string;
  payment: PaymentStatus;
  lines: [string, string, string, string, string, string | null][];
  retention?: [string, string];
  rectifies?: string;
  notes?: string;
  referencia?: string;
};

const line = ([
  description,
  quantity,
  unitPrice,
  subtotal,
  rate,
  category,
]: Example["lines"][number]): CatalogueInvoiceLine => {
  const fraction = rate === "RATE_21" ? 21n : rate === "RATE_10" ? 10n : 0n;
  const ivaCents = (BigInt(subtotal.replace(".", "")) * fraction + 50n) / 100n;
  return {
    description,
    quantity: { decimal: quantity },
    unit_price: { decimal: unitPrice },
    subtotal: { decimal: subtotal },
    iva_rate: rate,
    iva_amount: { decimal: (Number(ivaCents) / 100).toFixed(2) },
    spending_category_id: category,
    oss_rate_kind: null,
  };
};
const sum = (values: string[]) =>
  (
    values.reduce(
      (total, value) => total + Math.round(Number(value) * 100),
      0,
    ) / 100
  ).toFixed(2);

const EXAMPLES: Example[] = [
  {
    kind: "issued",
    invoiceClass: "ORDINARIA",
    series: "F",
    number: "F-2025-099",
    issued: "2025-12-18",
    name: "Talleres Ondara, S.L.",
    taxId: "B00000017",
    country: "ES",
    currency: "EUR",
    payment: "PAID",
    lines: [["Rediseño de catálogo", "1", "800", "800.00", "RATE_21", null]],
    referencia: "9999999VH9999S0001AB",
  },
  {
    kind: "issued",
    invoiceClass: "ORDINARIA",
    series: "F",
    number: "F-2026-018",
    issued: "2026-09-12",
    name: "Hotel Mirador Azul, S.L.",
    taxId: "B00000058",
    country: "ES",
    currency: "EUR",
    payment: "PENDING",
    lines: [
      ["Señalética de recepción", "4", "95.5", "382.00", "RATE_21", null],
      ["Montaje", "3", "40", "120.00", "RATE_21", null],
    ],
    retention: ["0.15", "75.30"],
  },
  {
    kind: "issued",
    invoiceClass: "ORDINARIA",
    series: "F",
    number: "F-2026-020",
    issued: "2026-10-10",
    name: "Bodegas Peña Rubia, S.L.",
    taxId: "B00000066",
    country: "ES",
    currency: "EUR",
    payment: "OVERDUE",
    lines: [
      ["Etiquetas de la cosecha", "1", "1100", "1100.00", "RATE_21", null],
    ],
    retention: ["0.15", "165.00"],
  },
  {
    kind: "issued",
    invoiceClass: "RECTIFICATIVA",
    series: "R",
    number: "R-2026-02",
    issued: "2026-08-03",
    name: "Editorial Brisa Norte, S.A.",
    taxId: "A00000025",
    country: "ES",
    currency: "EUR",
    payment: "PAID",
    lines: [["Corrección de tirada", "1", "60", "60.00", "RATE_21", null]],
    rectifies: "2026-031",
  },
  {
    kind: "issued",
    invoiceClass: "SIMPLIFICADA",
    series: "T",
    number: "T-2026-0007",
    issued: "2026-10-02",
    name: "Venta en taller",
    taxId: null,
    country: "ES",
    currency: "EUR",
    payment: "PAID",
    lines: [["Lámina impresa", "2", "15", "30.00", "RATE_21", null]],
  },
  {
    kind: "received",
    invoiceClass: "ORDINARIA",
    series: null,
    number: "INV-88412",
    issued: "2026-10-06",
    name: "Pixel Foundry Ltd",
    taxId: "GB000000017",
    country: "GB",
    currency: "USD",
    payment: "PENDING",
    lines: [
      [
        "Type licence, desktop",
        "1",
        "240",
        "240.00",
        "NOT_SUBJECT",
        "software_suscripcion",
      ],
    ],
    notes: "Licencia anual de tipografías.",
  },
  {
    kind: "received",
    invoiceClass: "ORDINARIA",
    series: "A",
    number: "A-1093",
    issued: "2026-10-14",
    name: "Papelería Trazo, S.L.",
    taxId: "B00000082",
    country: "ES",
    currency: "EUR",
    payment: "CANCELLED",
    lines: [
      ["Papel estucado", "10", "4.2", "42.00", "RATE_21", "material_oficina"],
      ["Tóner", "1", "35", "35.00", "RATE_21", "material_oficina"],
    ],
  },
];

/** The examples, as the catalogue snapshots them. */
export function exampleInvoices(
  hex64: (text: string) => string,
): CatalogueInvoice[] {
  return EXAMPLES.map((example) => {
    const lines = example.lines.map(line);
    const base = sum(lines.map((found) => found.subtotal.decimal));
    const iva = sum(lines.map((found) => found.iva_amount.decimal));
    return {
      invoice_id: hex64(`invoice:${example.number}:${example.issued}`),
      bucket_id: null,
      kind: example.kind,
      invoice_number: example.number,
      issued_at: example.issued,
      counterparty_name: example.name,
      counterparty_tax_id: example.taxId,
      counterparty_country: example.country,
      base_total: { decimal: base },
      iva_total: { decimal: iva },
      grand_total: { decimal: sum([base, iva]) },
      currency: example.currency,
      payment_status: example.payment,
      linked_transaction_ids: [],
      source_filename: null,
      source_sha256: null,
      source_row_index: null,
      notes: example.notes ?? "",
      retention_rate: example.retention
        ? { decimal: example.retention[0] }
        : null,
      retention_amount: example.retention
        ? { decimal: example.retention[1] }
        : null,
      recargo_amount: null,
      operation_type: null,
      lines,
      invoice_class: example.invoiceClass,
      series: example.series,
      operation_date: null,
      operation_date_role: null,
      iva_category: example.currency === "EUR" ? "domestic_general" : null,
      rectifies_invoice_number: example.rectifies ?? null,
      fx_rate: null,
      fx_rate_date: null,
      fx_rate_source: null,
      base_total_eur: null,
      iva_total_eur: null,
      grand_total_eur: null,
      referencia_catastral: example.referencia ?? null,
    };
  });
}
