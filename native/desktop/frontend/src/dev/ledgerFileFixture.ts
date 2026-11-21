// The scenario ledger's made-up files: what each purpose accepts and picks,
// the statements and invoice books the import reads, and the readers of
// their rows. Everything it answers is synthetic.

import type { FilePurpose } from "../shell/ledger";
import type { LedgerTransactionProjection } from "../shell/ledgerInvoiceContract";

export const PURPOSE_KINDS: Record<FilePurpose, readonly string[]> = {
  bank_statements: ["csv", "txt", "tsv", "xlsx", "xls", "ofx", "qfx", "pdf"],
  invoice_books: ["csv", "tsv", "xlsx", "xlsm", "xls"],
  documents: [
    "pdf",
    "xml",
    "png",
    "jpg",
    "jpeg",
    "tif",
    "tiff",
    "webp",
    "heic",
    "heif",
  ],
  export: ["csv", "jsonl", "xlsx"],
};
/** What each dialog of the made-up computer offers. */
export const PICKABLE: Record<Exclude<FilePurpose, "export">, string[]> = {
  bank_statements: [
    "extracto-cuenta-estudio-2026-10.csv",
    "extracto-cuenta-personal-2026-10.ofx",
    "movimientos-tarjeta.pdf",
    "notas-del-banco.docx",
  ],
  invoice_books: ["libro-facturas-recibidas-2026.xlsx"],
  documents: [
    "ticket-gasolinera-ruta7.jpg",
    "factura-papeleria-trazo.pdf",
    "factura-estudio-lumen.xml",
  ],
};
/** What the add's bytes probe finds in each made-up document: a structured
 * e-invoice, a PDF with a text layer, or an image. A name not listed is read
 * by its kind. */
export const DOCUMENT_SHAPES: Readonly<Record<string, string>> = {
  "ticket-gasolinera-ruta7.jpg": "image",
  "factura-papeleria-trazo.pdf": "pdf_text_layer",
  "factura-estudio-lumen.xml": "xml_ubl",
};
/** The shapes that carry one structured invoice, which the probe offers as
 * a purchase invoice. */
export const STRUCTURED_SHAPES: ReadonlySet<string> = new Set([
  "xml_cii",
  "xml_ubl",
  "xml_facturae",
  "pdf_embedded_xml",
]);
/** What the add's probe finds in the made-up document `name`, and the
 * purchase invoice a structured e-invoice is offered as. */
export function probedDocument(name: string) {
  const kind = name.split(".").pop()?.toLowerCase() ?? "";
  const shape =
    DOCUMENT_SHAPES[name] ??
    (kind === "xml" ? "xml_ubl" : kind === "pdf" ? "pdf_text_layer" : "image");
  return {
    document_shape: shape,
    kind_proposal: STRUCTURED_SHAPES.has(shape)
      ? { kind: "purchase_invoice", basis: shape }
      : null,
  };
}
/** What each made-up statement holds: the own account its rows name, if
 * any, how many rows it has, how many fall on the day and amount of a
 * movement already in the ledger, and whether its dates leave a gap. A name
 * not listed reads as a short statement that names no account.
 * `mask` is the masked number of an account the statement names that no own
 * account has until the import registers it; `installed` is whether this
 * installation carries the reader of the file's format; `stops` is the
 * refusal code that stops the whole read. */
type Statement = {
  names: string | null;
  rows: number;
  duplicates: number;
  gap: boolean;
  readable: boolean;
  mask?: string;
  installed?: boolean;
  stops?: string;
};
/** A statement that names an account no own account has yet. */
export const UNREGISTERED_STATEMENT = "extracto-bbva-2026-10.csv";
/** A statement of a format whose reader this installation does not carry. */
export const UNINSTALLED_STATEMENT = "extracto-antiguo-2026-10.xls";
/** A statement whose read the ledger stops with a refusal. */
export const STOPPED_STATEMENT = "extracto-roto-2026-10.csv";
export const STATEMENTS: Record<string, Statement> = {
  "extracto-cuenta-estudio-2026-10.csv": {
    names: null,
    rows: 14,
    duplicates: 2,
    gap: false,
    readable: true,
  },
  "extracto-cuenta-personal-2026-10.ofx": {
    names: "acc-02",
    rows: 9,
    duplicates: 0,
    gap: true,
    readable: true,
  },
  "movimientos-tarjeta.pdf": {
    names: null,
    rows: 0,
    duplicates: 0,
    gap: false,
    readable: false,
  },
  [UNREGISTERED_STATEMENT]: {
    names: null,
    mask: "ES**1332",
    rows: 7,
    duplicates: 0,
    gap: false,
    readable: true,
  },
  [UNINSTALLED_STATEMENT]: {
    names: null,
    rows: 5,
    duplicates: 0,
    gap: false,
    readable: true,
    installed: false,
  },
  [STOPPED_STATEMENT]: {
    names: null,
    rows: 0,
    duplicates: 0,
    gap: false,
    readable: true,
    stops: "ERROR_TRANSACTION_VALIDATION",
  },
};
export const STATEMENT: Statement = {
  names: null,
  rows: 6,
  duplicates: 0,
  gap: false,
  readable: true,
};
/** The rows of each made-up invoice book that its import refuses. */
export const BOOK_REFUSALS: Record<
  string,
  { row_number: number; field: string; reason: string }[]
> = {
  "libro-facturas-recibidas-2026.xlsx": [
    {
      row_number: 5,
      field: "counterparty_nif",
      reason: "B0000004 is not a valid tax identification number.",
    },
  ],
};

/** The meanings a made-up invoice book's column can be given, as the import
 * serves them: the importer field each feeds and whether the book must
 * supply it. */
export const BOOK_ROLES = [
  { role: "counterparty_nif", field: "counterparty_nif", required: true },
  { role: "counterparty_name", field: "counterparty_name", required: true },
  { role: "invoice_number", field: "invoice_number", required: true },
  { role: "invoice_date", field: "invoice_date", required: true },
  { role: "taxable_base", field: "taxable_base", required: true },
  { role: "iva_rate", field: "iva_rate", required: true },
  { role: "retencion_amount", field: "retencion_amount", required: false },
  { role: "retencion_rate", field: "retencion_rate", required: false },
  { role: "currency", field: "currency", required: false },
  { role: "country_code", field: "country_code", required: false },
  { role: "notes", field: "notes", required: false },
] as const;

/** One column of a made-up invoice book: its header, and the role and
 * origin the preview reads for it before anyone changes it. */
type BookColumnRead = {
  header: string;
  role: string;
  source: "exact" | "model" | "unmapped";
};

/** What each made-up invoice book holds. The received book's headers match
 * nothing and the local AI cannot be asked, so nothing is read for it; the
 * issued book names its columns as the import does but one, which the local
 * AI places; the empty book has no invoice rows. */
export const BOOKS: Record<
  string,
  { rows: number; columns: BookColumnRead[]; readerUnavailable: boolean }
> = {
  "libro-facturas-recibidas-2026.xlsx": {
    rows: 6,
    readerUnavailable: true,
    columns: [
      "Nº registro",
      "Fecha asiento",
      "Proveedor",
      "CIF proveedor",
      "Base",
      "Tipo",
      "Observaciones",
    ].map((header) => ({ header, role: "unmapped", source: "unmapped" })),
  },
  "libro-facturas-emitidas-2026.csv": {
    rows: 6,
    readerUnavailable: false,
    columns: [
      ...[
        "invoice_number",
        "invoice_date",
        "counterparty_name",
        "counterparty_nif",
        "taxable_base",
        "iva_rate",
      ].map((header) => ({ header, role: header, source: "exact" as const })),
      { header: "Observaciones", role: "notes", source: "model" as const },
    ],
  },
  "libro-facturas-vacio-2026.csv": {
    rows: 0,
    readerUnavailable: false,
    columns: [
      "invoice_number",
      "invoice_date",
      "counterparty_name",
      "counterparty_nif",
      "taxable_base",
      "iva_rate",
    ].map((header) => ({ header, role: header, source: "exact" as const })),
  },
};

/** A blank imported movement the import fills in. */
export function fixtureTemplate(): LedgerTransactionProjection {
  return {
    transaction_id: "",
    date: "",
    booked_date: "",
    value_date: null,
    operation_date: null,
    accrual_date: null,
    amount: "0.00",
    currency: "EUR",
    direction: "OUTGOING",
    counterparty: "",
    description: "",
    business_classification: "NOT_YET_PROCESSED",
    business_pct: null,
    category_id: null,
    taxable_base: null,
    iva_rate: null,
    iva_amount: null,
    recargo_amount: null,
    iva_category: null,
    deduction_fact_kind: null,
    investment_asset_id: null,
    counterparty_country: null,
    counterparty_identification_state: null,
    irpf_category: null,
    m210_income_classification: null,
    usage_ratio_id: null,
    prorrata_reference: null,
    arrendamiento_ref: null,
    inmueble_ref: null,
    gasto_capital_inmobiliario: null,
    link_fields: [],
    purchase_invoice_evidence_id: null,
    invoice_id: null,
    attachment_ids: [],
    notes: "",
    lifecycle_state: "ACTIVE",
    classified_by: "",
    classification_decided_by: "",
    figures_derived: false,
    classified_at: null,
    classification_reason: "",
    classification_confidence: null,
    source_jurisdiction: null,
    statement_reference: null,
    value_in_eur: null,
    fx_rate: null,
    created_at: "",
    modified_at: "",
  };
}

/** Rows of RFC 4180 CSV: quoted cells may hold commas, quotes and breaks. */
export function parseCsv(source: string): string[][] {
  const rows: string[][] = [];
  let cells: string[] = [];
  let cell = "";
  let quoted = false;
  for (let at = 0; at < source.length; at += 1) {
    const char = source[at]!;
    if (quoted) {
      if (char === '"' && source[at + 1] === '"') {
        cell += '"';
        at += 1;
      } else if (char === '"') quoted = false;
      else cell += char;
    } else if (char === '"') quoted = true;
    else if (char === ",") {
      cells.push(cell);
      cell = "";
    } else if (char === "\n" || char === "\r") {
      if (char === "\r" && source[at + 1] === "\n") at += 1;
      cells.push(cell);
      rows.push(cells);
      cells = [];
      cell = "";
    } else cell += char;
  }
  if (cell !== "" || cells.length) {
    cells.push(cell);
    rows.push(cells);
  }
  return rows.filter((line) => line.some((value) => value.trim() !== ""));
}
