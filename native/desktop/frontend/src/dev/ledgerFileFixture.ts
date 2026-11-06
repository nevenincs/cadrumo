// The scenario ledger's made-up files: what each purpose accepts and picks,
// the statements and invoice books the import reads, and the readers of
// their rows. Everything it answers is synthetic.

import type { FilePurpose, LedgerTransaction } from "../shell/ledger";

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
/** What each made-up statement holds: the own account its rows name, if
 * any, how many rows it has, how many fall on the day and amount of a
 * movement already in the ledger, and whether its dates leave a gap. A name
 * not listed reads as a short statement that names no account. */
type Statement = {
  names: string | null;
  rows: number;
  duplicates: number;
  gap: boolean;
  readable: boolean;
};
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

/** A blank imported movement the import fills in. */
export function fixtureTemplate(): LedgerTransaction {
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
    iva_category: null,
    deduction_fact_kind: null,
    investment_asset_id: null,
    counterparty_country: null,
    counterparty_identification_state: null,
    irpf_category: null,
    m210_income_classification: null,
    usage_ratio_id: null,
    prorrata_reference: null,
    purchase_invoice_evidence_id: null,
    invoice_id: null,
    attachment_ids: [],
    notes: "",
    lifecycle_state: "ACTIVE",
    classified_by: "",
    classified_at: null,
    classification_reason: "",
    classification_confidence: null,
    source_jurisdiction: null,
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
