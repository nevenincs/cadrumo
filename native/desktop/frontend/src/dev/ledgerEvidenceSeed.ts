// The documents, movements, invoices and attachments the scenario ledger's
// `documents` shape adds, every one invented, and the pictures and
// catalogue records made from them.

import type {
  AttachmentReviewItem,
  ConfirmationBlocker,
  FieldProvenance,
} from "../shell/ledgerDocumentOperations";
import type {
  CatalogueInvoice,
  InvoiceKind,
} from "../shell/ledgerInvoiceOperations";
import type { PublicDecimal } from "../shell/ledger";
import { fixtureDay, fixtureInstant } from "@/dev/fixtureDates";

export const decimal = (value: string | null): PublicDecimal | null =>
  value === null ? null : { decimal: value };

/** One field read, and where it was read from. */
export const read = (
  field: string,
  origin: FieldProvenance["origin"],
  grounding: FieldProvenance["grounding"],
  extra: Partial<FieldProvenance> = {},
): FieldProvenance => ({ field, origin, grounding, ...extra });

/** The fields a plain reading read, all agreeing with the page. */
export const agreeing = (origin: FieldProvenance["origin"], fields: string[]) =>
  fields.map((field) =>
    read(field, origin, field === "grand_total" ? "reconciled" : "anchored"),
  );

export type Spec = {
  name: string;
  media: "pdf" | "image";
  kind: InvoiceKind | null;
  party: string;
  taxId: string | null;
  number: string;
  date: string;
  base: string;
  rate: string;
  iva: string;
  total: string;
  provenance: FieldProvenance[];
  blockers?: SeedBlocker[];
};

/** A finding the seed raises: its reason, the sentence that explains it and
 * the values that sentence quotes, worded by the fixture from the backend's
 * served words. */
export type SeedBlocker = Pick<
  ConfirmationBlocker,
  "reason" | "field" | "candidates"
> & {
  wording: string;
  params: Record<string, string>;
};

/** The picture of an invented ticket: what its reading read, printed where
 * its notes say, both tax ids included, so the page can be checked against
 * the questions. */
export function ticketPage(spec: Spec): {
  width: number;
  height: number;
  image_data_url: string;
} {
  const width = 360;
  const height = 520;
  const ids =
    spec.blockers?.find((blocker) => blocker.field === "supplier_tax_id")
      ?.candidates ?? [];
  const [top, foot] = [ids[0]?.value ?? "", ids[1]?.value ?? ""];
  const line = (y: number, text: string, size = 16, weight = 400) =>
    `<text x="24" y="${y}" font-family="monospace" font-size="${size}" font-weight="${weight}">${text}</text>`;
  const svg = [
    `<svg xmlns="http://www.w3.org/2000/svg" width="${width}" height="${height}" viewBox="0 0 ${width} ${height}">`,
    `<rect width="${width}" height="${height}" fill="#fbfaf7"/>`,
    line(48, spec.party.toUpperCase(), 22, 700),
    line(76, `NIF ${top}`),
    line(124, `TICKET ${spec.number}`),
    line(150, spec.date),
    line(214, `BASE ${spec.base}`),
    line(240, `IVA ${spec.rate}% ${spec.iva}`),
    line(292, `TOTAL ${spec.total} EUR`, 20, 700),
    line(height - 48, `NIF ${foot}`, 13),
    `</svg>`,
  ].join("");
  return {
    width,
    height,
    image_data_url: `data:image/svg+xml;base64,${btoa(svg)}`,
  };
}

/** The documents the `documents` shape adds, every one invented. */
export const DOCUMENTS: Spec[] = [
  {
    name: "factura-domestika-lettering.pdf",
    media: "pdf",
    kind: "received",
    party: "Domestika SL",
    taxId: "B66000099",
    number: "DK-2026-55120",
    date: fixtureDay(10, 7),
    base: "200.00",
    rate: "21",
    iva: "42.00",
    total: "242.00",
    provenance: agreeing("text_layer", [
      "supplier_name",
      "supplier_tax_id",
      "invoice_number",
      "invoice_date",
      "taxable_base",
      "iva_rate",
      "iva_amount",
      "grand_total",
      "currency",
    ]),
  },
  {
    name: "ticket-plenoil-1015.jpg",
    media: "image",
    kind: null,
    party: "Plenoil SL",
    taxId: null,
    number: "T-1015-0042",
    date: fixtureDay(10, 15),
    base: "48.26",
    rate: "21",
    iva: "10.13",
    total: "58.40",
    provenance: [
      read("supplier_name", "vision", "anchored"),
      read("supplier_tax_id", "vision", "ambiguous", {
        candidates: [
          { value: "B87000001", note: "top of the ticket" },
          { value: "B87000007", note: "footer" },
        ],
      }),
      read("invoice_number", "vision", "anchored"),
      read("invoice_date", "vision", "anchored"),
      read("taxable_base", "vision", "unanchored"),
      read("iva_rate", "vision", "anchored"),
      read("iva_amount", "vision", "anchored"),
      read("grand_total", "vision", "contradicted"),
      read("currency", "derived", "anchored"),
    ],
    blockers: [
      {
        reason: "ambiguous_identity",
        field: "supplier_tax_id",
        wording: "identity_readings_compete",
        params: { count: "2", field: "supplier_tax_id" },
        candidates: [
          { value: "B87000001", note: "top of the ticket" },
          { value: "B87000007", note: "footer" },
        ],
      },
      {
        reason: "closure_discrepancy",
        field: "grand_total",
        wording: "total_not_closed",
        params: { computed: "58.39", total: "58.40" },
        candidates: [],
      },
    ],
  },
  {
    name: "factura-arroyo-2026-10.pdf",
    media: "pdf",
    kind: "received",
    party: "Arroyo Asesores SL",
    taxId: "B98000013",
    number: "AA-2026-104",
    date: fixtureDay(10, 1),
    base: "60.00",
    rate: "21",
    iva: "12.60",
    total: "72.60",
    provenance: agreeing("text_layer", [
      "supplier_name",
      "supplier_tax_id",
      "invoice_number",
      "invoice_date",
      "taxable_base",
      "iva_rate",
      "iva_amount",
      "grand_total",
      "currency",
    ]),
  },
];

/** The movements the `documents` shape adds, and the invoices that settle
 * them or disagree with them. */
type Pairing = {
  key: string;
  date: string;
  amount: string;
  direction: "INCOMING" | "OUTGOING";
  counterparty: string;
  description: string;
  /** The invoice this movement cites, where it cites one. */
  cites?: string;
};
export const MOVEMENTS: Pairing[] = [
  {
    key: "turia",
    date: fixtureDay(10, 5),
    amount: "1548.80",
    direction: "OUTGOING",
    counterparty: "Imprenta Gráficas Turia SL",
    description: "TRANSF IMPRENTA TURIA FRA GT-2026-0917",
  },
  {
    key: "arroyo-cuota",
    date: fixtureDay(10, 6),
    amount: "72.60",
    direction: "OUTGOING",
    counterparty: "Arroyo Asesores SL",
    description: "ARROYO ASESORES CUOTA OCT",
  },
  {
    key: "arroyo-linked",
    date: fixtureDay(10, 2),
    amount: "72.60",
    direction: "OUTGOING",
    counterparty: "Arroyo Asesores SL",
    description: "ARROYO ASESORES SEPT",
    cites: "AA-2026-104",
  },
  {
    key: "norte-a",
    date: fixtureDay(10, 12),
    amount: "605.00",
    direction: "INCOMING",
    counterparty: "Norte Digital SL",
    description: "NORTE DIGITAL PAGO",
  },
  {
    key: "norte-b",
    date: fixtureDay(10, 12),
    amount: "605.00",
    direction: "INCOMING",
    counterparty: "Norte Digital SL",
    description: "NORTE DIGITAL PAGO",
  },
  {
    key: "correos",
    date: fixtureDay(10, 14),
    amount: "39.90",
    direction: "OUTGOING",
    counterparty: "Sociedad Estatal Correos",
    description: "CORREOS ENVIO PAQUETE",
  },
  {
    key: "trazo",
    date: fixtureDay(10, 15),
    amount: "18.17",
    direction: "OUTGOING",
    counterparty: "Papelería Trazo",
    description: "PAPELERIA TRAZO 0412",
    cites: "PT-2026-0412",
  },
  {
    key: "lost",
    date: fixtureDay(10, 16),
    amount: "12.10",
    direction: "OUTGOING",
    counterparty: "Copistería Centro",
    description: "COPISTERIA CENTRO",
    cites: "gone",
  },
  {
    key: "domestika",
    date: fixtureDay(10, 8),
    amount: "242.00",
    direction: "OUTGOING",
    counterparty: "Domestika SL",
    description: "DOMESTIKA CURSO LETTERING",
  },
];
type SeedInvoice = {
  number: string;
  kind: InvoiceKind;
  issued: string;
  party: string;
  taxId: string;
  base: string;
  iva: string;
  /** The movements it lists. */
  lists: string[];
};
export const INVOICES: SeedInvoice[] = [
  {
    number: "GT-2026-0917",
    kind: "received",
    issued: fixtureDay(9, 17),
    party: "Imprenta Gráficas Turia SL",
    taxId: "B46000017",
    base: "1280.00",
    iva: "268.80",
    lists: [],
  },
  {
    number: "AA-2026-118",
    kind: "received",
    issued: fixtureDay(10, 1),
    party: "Arroyo Asesores SL",
    taxId: "B98000013",
    base: "60.00",
    iva: "12.60",
    lists: [],
  },
  {
    number: "AA-2026-119",
    kind: "received",
    issued: fixtureDay(10, 1),
    party: "Arroyo Asesores SL",
    taxId: "B98000013",
    base: "60.00",
    iva: "12.60",
    lists: [],
  },
  {
    number: "AA-2026-104",
    kind: "received",
    issued: fixtureDay(10, 1),
    party: "Arroyo Asesores SL",
    taxId: "B98000013",
    base: "60.00",
    iva: "12.60",
    lists: ["arroyo-linked"],
  },
  {
    number: "N-2026-0005",
    kind: "issued",
    issued: fixtureDay(10, 9),
    party: "Norte Digital SL",
    taxId: "B48000031",
    base: "500.00",
    iva: "105.00",
    lists: [],
  },
  {
    number: "C-2026-7781",
    kind: "received",
    issued: fixtureDay(10, 13),
    party: "Sociedad Estatal Correos",
    taxId: "A83000052",
    base: "32.98",
    iva: "6.92",
    lists: ["correos"],
  },
  {
    number: "PT-2026-0412",
    kind: "received",
    issued: fixtureDay(10, 15),
    party: "Papelería Trazo",
    taxId: "B12000045",
    base: "15.02",
    iva: "3.15",
    lists: [],
  },
];

const sum = (left: string, right: string) => {
  const units = (value: string) => Math.round(Number(value) * 100);
  return ((units(left) + units(right)) / 100).toFixed(2);
};

export function catalogueInvoice(
  hex64: (text: string) => string,
  facts: {
    number: string;
    kind: InvoiceKind;
    issued: string;
    party: string;
    taxId: string | null;
    country: string;
    base: string;
    iva: string;
    total?: string;
    currency: string;
    linked: string[];
    sourceName?: string | null;
    sourceSha?: string | null;
  },
): CatalogueInvoice {
  const total = facts.total ?? sum(facts.base, facts.iva);
  return {
    invoice_id: hex64(`invoice:${facts.kind}:${facts.number}:${facts.issued}`),
    bucket_id: null,
    kind: facts.kind,
    invoice_number: facts.number,
    issued_at: facts.issued,
    counterparty_name: facts.party,
    counterparty_tax_id: facts.taxId,
    counterparty_country: facts.country,
    base_total: { decimal: facts.base },
    iva_total: { decimal: facts.iva },
    grand_total: { decimal: total },
    currency: facts.currency,
    payment_status: facts.linked.length ? "PAID" : "PENDING",
    linked_transaction_ids: facts.linked,
    source_filename: facts.sourceName ?? null,
    source_sha256: facts.sourceSha ?? null,
    source_row_index: null,
    notes: "",
    retention_rate: null,
    retention_amount: null,
    recargo_amount: null,
    operation_type: null,
    lines: [
      {
        description: facts.number,
        quantity: { decimal: "1" },
        unit_price: { decimal: facts.base },
        subtotal: { decimal: facts.base },
        iva_rate: "RATE_21",
        iva_amount: { decimal: facts.iva },
        spending_category_id: null,
        oss_rate_kind: null,
      },
    ],
    invoice_class: "ORDINARIA",
    series: null,
    operation_date: facts.issued,
    operation_date_role: "OPERATION_PERFORMED",
    iva_category: "domestic_general",
    rectifies_invoice_number: null,
    fx_rate: null,
    fx_rate_date: null,
    fx_rate_source: null,
    base_total_eur: null,
    iva_total_eur: null,
    grand_total_eur: null,
    referencia_catastral: null,
    settlement_amount: { decimal: total },
  };
}

export const ATTACHMENTS: Omit<
  AttachmentReviewItem,
  "attachment_id" | "sha256"
>[] = [
  {
    mime_type: "application/pdf",
    bytes_size: 84_211,
    source: "GMAIL",
    provider_locator: "msg-18c2f0a1",
    captured_at: fixtureInstant(10, 3, "08:14:00Z"),
    linked_invoice_ids: [],
    pending_review: true,
  },
  {
    mime_type: "application/pdf",
    bytes_size: 51_022,
    source: "GOOGLE_DRIVE",
    provider_locator: "drive-1AbCdEf",
    captured_at: fixtureInstant(10, 19, "17:40:00Z"),
    linked_invoice_ids: [],
    pending_review: false,
  },
];
