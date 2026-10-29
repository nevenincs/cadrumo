// The scenario ledger's documents and links, held to the registered
// contracts of `ledger.evidence.*`, `ledger.link`, `ledger.attach`,
// `ledger.detach` and `ledger.check`. A reading is a reviewable draft keyed
// by its evidence record, or by its attachment where it has none; its
// review digest is the digest of the reading itself, so a reading that
// changes refuses a confirmation bound to the old one. A read off this
// computer needs a stored record, the provider and the acknowledgement of
// that one call, and is recorded as a dispatch. Results are the flat public
// projections, naming files by name only. The `documents` shape adds the
// documents, attachments and pairs the Documents and Matching sections
// exercise. Without the local AI, readings stand on what the labels print and
// name its setup, a scan refuses with the reader probe's verdict, and the
// readers are not ready. Everything it answers is synthetic.

import type {
  AttachmentReviewItem,
  CatalogueInvoice,
  ConfirmationBlocker,
  EvidenceDraft,
  FieldProvenance,
  InvoiceKind,
  JsonObject,
  JsonValue,
  LabelReadingFallback,
  PublicDecimal,
} from "../shell/ledger";
import type {
  FixtureEvidence,
  FixtureLedger,
  FixtureMovement,
} from "./fixtures/ledger";
import { DOCUMENT_PAGE } from "./fixtures/documentPage";
import { InvoiceRequestInvalid, InvoiceStopped } from "./ledgerInvoiceFixture";

declare global {
  interface Window {
    /** Controls for what the scenario's documents cannot get from a
     * person. */
    __scenarioDocuments?: {
      /** Reads the named document again with a different result, as a
       * changed reader would. */
      changeReading(fileName: string): void;
      /** Changes the named document's bytes, as editing it on disk
       * would. */
      changeSource(fileName: string): void;
      /** Makes drawing a page of the named document refuse with the
       * page read's `reason`, such as `TOO_LARGE`; `null` lifts it. */
      refusePage(fileName: string, reason: string | null): void;
    };
  }
}

type Tools = {
  profileId: string;
  events: () => string[];
  hex64: (text: string) => string;
  now: () => string;
  /** The file behind a token the page was given for documents. */
  fileOf: (token: JsonValue | undefined) => { name: string };
  /** The readiness issues of a period, as the preflight finds them. */
  issuesFor: (
    period: JsonValue,
  ) => { transaction_id: string; reason: string; detail: string }[];
  /** Whether to add the documents, attachments and pairs to match. */
  seed: boolean;
  /** Whether the local AI is missing on this computer. */
  readerMissing: boolean;
};

type Reading = {
  draft: EvidenceDraft;
  blockers: ConfirmationBlocker[];
  fallback: LabelReadingFallback | null;
  extractor: string;
  drafted_at: string;
  confirmed: boolean;
  /** How often the reader read it differently since the page loaded. */
  version: number;
};

const CANONICAL = /^(0|[1-9]\d*)(\.\d+)?$/;
const DATE = /^\d{4}-\d{2}-\d{2}$/;
const HEX64 = /^[0-9a-f]{64}$/;
const invalid = (): never => {
  throw new InvoiceRequestInvalid();
};
const text = (value: JsonValue | undefined): string | null =>
  typeof value === "string" ? value : null;
const decimal = (value: string | null): PublicDecimal | null =>
  value === null ? null : { decimal: value };
const fileName = (path: string) => path.split(/[\\/]/).pop() || path;

/** A label reading that stood without the model fill the local AI gives. */
const withoutReader = (unread: string[]): LabelReadingFallback => ({
  cause: "reader_unavailable",
  unread_fields: unread,
  reader_error_type: "InvoiceDraftReaderUnavailableError",
});

/** The registered refusal of a read that needed the missing local AI. */
const readerRefusal = () =>
  new InvoiceStopped("REFUSED_LEDGER_EVIDENCE_READER", {
    detail_version: 1,
    kind: "registered_error",
    error_code: "REFUSED_LEDGER_EVIDENCE_READER",
    message_key: "errors.refused.refused_ledger_evidence_reader_unavailable",
    context: [],
    context_entries_omitted: 0,
    precondition_verdict_json: null,
  });

/** A value of any shape in one comparable text, keys sorted. */
function stable(value: unknown): string {
  if (Array.isArray(value)) return `[${value.map(stable).join(",")}]`;
  if (value && typeof value === "object")
    return `{${Object.keys(value)
      .filter((key) => (value as Record<string, unknown>)[key] !== undefined)
      .sort()
      .map(
        (key) =>
          `${JSON.stringify(key)}:${stable((value as Record<string, unknown>)[key])}`,
      )
      .join(",")}}`;
  return JSON.stringify(value ?? null);
}

/** One field read, and where it was read from. */
const read = (
  field: string,
  origin: FieldProvenance["origin"],
  grounding: FieldProvenance["grounding"],
  extra: Partial<FieldProvenance> = {},
): FieldProvenance => ({ field, origin, grounding, ...extra });

/** The fields a plain reading read, all agreeing with the page. */
const agreeing = (origin: FieldProvenance["origin"], fields: string[]) =>
  fields.map((field) =>
    read(field, origin, field === "grand_total" ? "reconciled" : "anchored"),
  );

type Spec = {
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
  blockers?: Omit<ConfirmationBlocker, "blocker_id">[];
};

/** The picture of an invented ticket: what its reading read, printed where
 * its notes say, both tax ids included, so the page can be checked against
 * the questions. */
function ticketPage(spec: Spec): {
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
const DOCUMENTS: Spec[] = [
  {
    name: "factura-domestika-lettering.pdf",
    media: "pdf",
    kind: "received",
    party: "Domestika SL",
    taxId: "B66000099",
    number: "DK-2026-55120",
    date: "2026-10-07",
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
    date: "2026-10-15",
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
        detail: "Two tax ids are printed on the ticket.",
        candidates: [
          { value: "B87000001", note: "top of the ticket" },
          { value: "B87000007", note: "footer" },
        ],
      },
      {
        reason: "closure_discrepancy",
        field: "grand_total",
        detail: "Base plus IVA is 58.39; the ticket prints 58.40.",
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
    date: "2026-10-01",
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
const MOVEMENTS: Pairing[] = [
  {
    key: "turia",
    date: "2026-10-05",
    amount: "1548.80",
    direction: "OUTGOING",
    counterparty: "Imprenta Gráficas Turia SL",
    description: "TRANSF IMPRENTA TURIA FRA GT-2026-0917",
  },
  {
    key: "arroyo-cuota",
    date: "2026-10-06",
    amount: "72.60",
    direction: "OUTGOING",
    counterparty: "Arroyo Asesores SL",
    description: "ARROYO ASESORES CUOTA OCT",
  },
  {
    key: "arroyo-linked",
    date: "2026-10-02",
    amount: "72.60",
    direction: "OUTGOING",
    counterparty: "Arroyo Asesores SL",
    description: "ARROYO ASESORES SEPT",
    cites: "AA-2026-104",
  },
  {
    key: "norte-a",
    date: "2026-10-12",
    amount: "605.00",
    direction: "INCOMING",
    counterparty: "Norte Digital SL",
    description: "NORTE DIGITAL PAGO",
  },
  {
    key: "norte-b",
    date: "2026-10-12",
    amount: "605.00",
    direction: "INCOMING",
    counterparty: "Norte Digital SL",
    description: "NORTE DIGITAL PAGO",
  },
  {
    key: "correos",
    date: "2026-10-14",
    amount: "39.90",
    direction: "OUTGOING",
    counterparty: "Sociedad Estatal Correos",
    description: "CORREOS ENVIO PAQUETE",
  },
  {
    key: "trazo",
    date: "2026-10-15",
    amount: "18.17",
    direction: "OUTGOING",
    counterparty: "Papelería Trazo",
    description: "PAPELERIA TRAZO 0412",
    cites: "PT-2026-0412",
  },
  {
    key: "lost",
    date: "2026-10-16",
    amount: "12.10",
    direction: "OUTGOING",
    counterparty: "Copistería Centro",
    description: "COPISTERIA CENTRO",
    cites: "gone",
  },
  {
    key: "domestika",
    date: "2026-10-08",
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
const INVOICES: SeedInvoice[] = [
  {
    number: "GT-2026-0917",
    kind: "received",
    issued: "2026-09-17",
    party: "Imprenta Gráficas Turia SL",
    taxId: "B46000017",
    base: "1280.00",
    iva: "268.80",
    lists: [],
  },
  {
    number: "AA-2026-118",
    kind: "received",
    issued: "2026-10-01",
    party: "Arroyo Asesores SL",
    taxId: "B98000013",
    base: "60.00",
    iva: "12.60",
    lists: [],
  },
  {
    number: "AA-2026-119",
    kind: "received",
    issued: "2026-10-01",
    party: "Arroyo Asesores SL",
    taxId: "B98000013",
    base: "60.00",
    iva: "12.60",
    lists: [],
  },
  {
    number: "AA-2026-104",
    kind: "received",
    issued: "2026-10-01",
    party: "Arroyo Asesores SL",
    taxId: "B98000013",
    base: "60.00",
    iva: "12.60",
    lists: ["arroyo-linked"],
  },
  {
    number: "N-2026-0005",
    kind: "issued",
    issued: "2026-10-09",
    party: "Norte Digital SL",
    taxId: "B48000031",
    base: "500.00",
    iva: "105.00",
    lists: [],
  },
  {
    number: "C-2026-7781",
    kind: "received",
    issued: "2026-10-13",
    party: "Sociedad Estatal Correos",
    taxId: "A83000052",
    base: "32.98",
    iva: "6.92",
    lists: ["correos"],
  },
  {
    number: "PT-2026-0412",
    kind: "received",
    issued: "2026-10-15",
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

function catalogueInvoice(
  hex64: Tools["hex64"],
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
  };
}

const ATTACHMENTS: Omit<AttachmentReviewItem, "attachment_id" | "sha256">[] = [
  {
    mime_type: "application/pdf",
    bytes_size: 84_211,
    source: "GMAIL",
    provider_locator: "msg-18c2f0a1",
    captured_at: "2026-10-03T08:14:00Z",
    linked_invoice_ids: [],
    pending_review: true,
  },
  {
    mime_type: "application/pdf",
    bytes_size: 51_022,
    source: "GOOGLE_DRIVE",
    provider_locator: "drive-1AbCdEf",
    captured_at: "2026-10-19T17:40:00Z",
    linked_invoice_ids: [],
    pending_review: false,
  },
];

type Controls = NonNullable<Window["__scenarioDocuments"]>;
/** Every ledger the page made; the controls reach the one it uses. */
const made = new Set<Controls>();

export function evidenceOperations(ledger: FixtureLedger, tools: Tools) {
  const { profileId, events, hex64, now } = tools;
  const readings = new Map<string, Reading>();
  const attachments: AttachmentReviewItem[] = [];
  /** The page read's refusal, by file name, a document is held to. */
  const pageRefusals = new Map<string, string>();
  const dispatches: {
    profile_bucket_id: string;
    evidence_content_address: string;
    provider: string;
    model: string;
    surface: string;
    recorded_at: string;
  }[] = [];
  const artefacts: {
    evidence_reference: string;
    provenance_stamp: string;
    transport: string | null;
    drafted_at: string;
  }[] = [];
  const keyed = new Map<string, string>();
  const blockerId = (blocker: Omit<ConfirmationBlocker, "blocker_id">) =>
    hex64(
      stable({
        detail: blocker.detail ?? "",
        field: blocker.field ?? "",
        reason: blocker.reason,
      }),
    ).slice(0, 16);

  // What was in the ledger before the page loaded is settled: its
  // documents are confirmed or kept as evidence, and have no reading.
  const settled = new Set(ledger.evidence.map((record) => record.evidence_id));

  function specReading(spec: Spec): Reading {
    return {
      draft: {
        supplier_name: spec.kind === "issued" ? null : spec.party,
        supplier_tax_id: spec.kind === "issued" ? null : spec.taxId,
        customer_name: spec.kind === "issued" ? spec.party : null,
        customer_tax_id: spec.kind === "issued" ? spec.taxId : null,
        supplier_country_code: spec.kind === "issued" ? null : "ES",
        invoice_number: spec.number,
        invoice_date: spec.date,
        taxable_base: decimal(spec.base),
        iva_rate: decimal(spec.rate),
        iva_amount: decimal(spec.iva),
        grand_total: decimal(spec.total),
        currency: "EUR",
        suggested_kind: spec.kind,
        provenance: spec.provenance,
        discrepancies: [],
        raw_text_length: 1200 + spec.name.length,
        lines: [],
      },
      blockers: (spec.blockers ?? []).map((blocker) => ({
        blocker_id: blockerId(blocker),
        ...blocker,
      })),
      fallback: null,
      extractor: spec.media === "image" ? "vision:local" : "text_layer",
      drafted_at: now(),
      confirmed: false,
      version: 0,
    };
  }

  /** The reading of a document added in this run, from what its name
   * says: an image the reader was too busy for leaves fields unread. */
  function nameReading(record: FixtureEvidence): Reading {
    const name = fileName(record.source_path);
    const party = name
      .replace(/\.[a-z0-9]+$/i, "")
      .replace(/^(factura|ticket|recibo)-/i, "")
      .split(/[-_]/)
      .filter((word) => /^[a-z]+$/i.test(word))
      .slice(0, 2)
      .map((word) => word[0]!.toUpperCase() + word.slice(1))
      .join(" ");
    const image = record.media_kind === "image";
    return {
      draft: {
        supplier_name: party || null,
        invoice_number: image
          ? null
          : name.replace(/\.[a-z0-9]+$/i, "").toUpperCase(),
        invoice_date: image ? null : "2026-10-20",
        taxable_base: image ? null : decimal("50.00"),
        iva_rate: image ? null : decimal("21"),
        iva_amount: image ? null : decimal("10.50"),
        grand_total: image ? null : decimal("60.50"),
        currency: image ? null : "EUR",
        suggested_kind: null,
        provenance: image
          ? [read("supplier_name", "text_rules", "unanchored")]
          : agreeing("text_layer", [
              "supplier_name",
              "invoice_number",
              "invoice_date",
              "taxable_base",
              "iva_rate",
              "iva_amount",
              "grand_total",
              "currency",
            ]),
        discrepancies: [],
        raw_text_length: image ? 0 : 900,
        lines: [],
      },
      blockers: [],
      fallback: image
        ? {
            cause: "load_headroom_refused",
            unread_fields: ["invoice_number", "grand_total", "invoice_date"],
            reader_error_type: "LLMContentionError",
          }
        : tools.readerMissing
          ? withoutReader(["retencion_rate", "retencion_amount"])
          : null,
      extractor: image ? "text_rules" : "text_layer",
      drafted_at: now(),
      confirmed: false,
      version: 0,
    };
  }

  if (tools.seed) seed();

  function seed() {
    const template = ledger.movements.find(
      (movement) =>
        movement.transaction.lifecycle_state === "ACTIVE" &&
        movement.transaction.business_classification === "BUSINESS" &&
        movement.transaction.direction === "OUTGOING" &&
        movement.transaction.currency === "EUR",
    );
    if (!template) return;
    const ids = new Map<string, string>();
    for (const pairing of MOVEMENTS) {
      const movement = structuredClone(template) as FixtureMovement;
      const id = hex64(`documents:${pairing.key}`);
      ids.set(pairing.key, id);
      Object.assign(movement, {
        group_label: null,
        import_batch_id: null,
        issue: null,
        sealed: false,
        llm_rejected: false,
        idempotency_key: null,
      });
      Object.assign(movement.transaction, {
        transaction_id: id,
        date: pairing.date,
        booked_date: pairing.date,
        value_date: pairing.date,
        amount: pairing.amount,
        direction: pairing.direction,
        counterparty: pairing.counterparty,
        description: pairing.description,
        business_classification: "BUSINESS",
        invoice_id: null,
        purchase_invoice_evidence_id: null,
        attachment_ids: [],
        created_at: `${pairing.date}T09:00:00Z`,
        modified_at: `${pairing.date}T09:00:00Z`,
      });
      ledger.movements.push(movement);
    }
    for (const seeded of INVOICES)
      ledger.invoices.push(
        catalogueInvoice(hex64, {
          ...seeded,
          country: "ES",
          currency: "EUR",
          linked: seeded.lists.map((key) => ids.get(key)!),
        }),
      );
    for (const pairing of MOVEMENTS) {
      if (!pairing.cites) continue;
      const movement = ledger.movements.find(
        (found) => found.transaction.transaction_id === ids.get(pairing.key),
      )!;
      const invoice = ledger.invoices.find(
        (found) => found.invoice_number === pairing.cites,
      );
      movement.transaction.invoice_id =
        invoice?.invoice_id ?? hex64(`invoice:${pairing.cites}`);
    }
    for (const spec of DOCUMENTS) {
      const sha = hex64(`document-bytes:${spec.name}`);
      const record: FixtureEvidence = {
        evidence_id: hex64(`evidence:${spec.name}`).slice(0, 16),
        bucket_id: profileId,
        source_sha256: sha,
        attachment_id: sha,
        media_kind: spec.media,
        supplier: null,
        invoice_number: null,
        invoice_date: null,
        taxable_base: null,
        iva_rate: null,
        iva_amount: null,
        notes: "",
        created_at: "2026-10-20T10:00:00Z",
        updated_at: "2026-10-20T10:00:00Z",
        source_path: spec.name,
      };
      ledger.evidence.push(record);
      const reading = specReading(spec);
      // A page with text is read by its labels alone; the withholding the
      // text model would have filled is left unread.
      if (tools.readerMissing && spec.media === "pdf")
        reading.fallback = withoutReader([
          "retencion_rate",
          "retencion_amount",
        ]);
      readings.set(record.evidence_id, reading);
    }
    ATTACHMENTS.forEach((attachment, at) => {
      const sha = hex64(`attachment:${at}`);
      attachments.push({
        ...attachment,
        attachment_id: sha,
        sha256: sha,
        linked_invoice_ids:
          at === 1
            ? [
                ledger.invoices.find(
                  (found) => found.invoice_number === "GT-2026-0917",
                )!.invoice_id,
              ]
            : [],
      });
    });
    const sent = ledger.evidence[0];
    if (sent) {
      dispatches.push({
        profile_bucket_id: profileId,
        evidence_content_address: sent.source_sha256,
        provider: "AGENT",
        model: "assistant-reader",
        surface: "runtime:ledger.evidence.extract",
        recorded_at: "2026-10-11T09:12:00Z",
      });
      artefacts.push({
        evidence_reference: sent.evidence_id,
        provenance_stamp: "llm:assistant-reader",
        transport: "https",
        drafted_at: "2026-10-11T09:12:04Z",
      });
    }
  }

  const recordOf = (id: JsonValue | undefined) => {
    const wanted = text(id);
    if (!wanted || wanted.length > 64) invalid();
    return ledger.evidence.find((record) => record.evidence_id === wanted);
  };
  const projected = (record: FixtureEvidence): JsonObject => ({
    ...(record as unknown as JsonObject),
    source_path: fileName(record.source_path),
  });
  const notFound = (): never => {
    throw new InvoiceStopped("ERROR_EVIDENCE_NOT_FOUND", {});
  };

  /** The reading of `reference`, made where the document is new. */
  function readingOf(reference: string): Reading | null {
    const held = readings.get(reference);
    if (held) return held;
    const record = ledger.evidence.find(
      (found) => found.evidence_id === reference,
    );
    if (record && !settled.has(record.evidence_id)) {
      const made = nameReading(record);
      readings.set(reference, made);
      return made;
    }
    return null;
  }
  /** The reading as the reader gives it now. */
  const current = (reading: Reading): EvidenceDraft =>
    reading.version === 0
      ? reading.draft
      : {
          ...reading.draft,
          raw_text_length:
            (reading.draft.raw_text_length ?? 0) + reading.version,
        };
  const digestOf = (reading: Reading) => hex64(stable(current(reading)));

  // Every new document has a reading to review.
  const pending = () => {
    for (const record of ledger.evidence) readingOf(record.evidence_id);
    return [...readings.entries()].filter(([, reading]) => !reading.confirmed);
  };

  function list(): JsonObject {
    return {
      profile_id: profileId,
      count: ledger.evidence.length,
      rows: ledger.evidence.map(projected),
    };
  }
  function view(request: JsonObject): JsonObject {
    const record = recordOf(request.evidence_id);
    return {
      result_version: 2,
      profile_id: profileId,
      outcome: record
        ? { kind: "success", record: projected(record) }
        : { kind: "refused", evidence_record_present: false },
    };
  }
  function add(request: JsonObject): JsonObject {
    const file = tools.fileOf(request.source_path);
    const key = text(request.idempotency_key);
    const kind = file.name.split(".").pop()?.toLowerCase() ?? "";
    const facts = {
      supplier: text(request.supplier),
      invoice_number: text(request.invoice_number),
      invoice_date: text(request.invoice_date),
      taxable_base: text(request.taxable_base),
      iva_rate: text(request.iva_rate),
      iva_amount: text(request.iva_amount),
      notes: text(request.notes) ?? "",
    };
    for (const field of ["taxable_base", "iva_rate", "iva_amount"] as const)
      if (facts[field] !== null && !CANONICAL.test(facts[field]!)) invalid();
    if (facts.invoice_date !== null && !DATE.test(facts.invoice_date))
      invalid();
    const sha = hex64(`document-bytes:${file.name}`);
    if (key !== null) {
      const prior = keyed.get(key);
      const record = prior
        ? ledger.evidence.find((found) => found.evidence_id === prior)
        : undefined;
      if (record) {
        const same =
          record.source_sha256 === sha &&
          (Object.keys(facts) as (keyof typeof facts)[]).every(
            (field) => (record[field] ?? null) === facts[field],
          );
        if (!same)
          throw new InvoiceStopped("REFUSED_LEDGER_EVIDENCE_INPUT", {});
        return {
          profile_id: profileId,
          record: projected(record),
          bucket_event_ids: [],
        };
      }
    }
    const at = now();
    const record: FixtureEvidence = {
      evidence_id: (key !== null
        ? hex64(`evidence-key:${key}`)
        : hex64(`evidence:${file.name}:${at}`)
      ).slice(0, 16),
      bucket_id: profileId,
      source_sha256: sha,
      attachment_id: sha,
      media_kind: kind === "pdf" || kind === "xml" ? "pdf" : "image",
      ...facts,
      created_at: at,
      updated_at: at,
      source_path: file.name,
    };
    ledger.evidence.push(record);
    if (key !== null) keyed.set(key, record.evidence_id);
    return {
      profile_id: profileId,
      record: projected(record),
      bucket_event_ids: events(),
    };
  }
  const UPDATE_FIELDS = [
    "supplier",
    "invoice_number",
    "invoice_date",
    "taxable_base",
    "iva_rate",
    "iva_amount",
    "notes",
  ];
  function update(request: JsonObject): JsonObject {
    const record = recordOf(request.evidence_id) ?? notFound();
    const patch = request.patch;
    const fields = request.patch_fields;
    if (
      !patch ||
      typeof patch !== "object" ||
      Array.isArray(patch) ||
      !Array.isArray(fields) ||
      fields.some((field) => !UPDATE_FIELDS.includes(field as string))
    )
      invalid();
    const values = patch as JsonObject;
    for (const [field, value] of Object.entries(values))
      if (value !== null && !(fields as string[]).includes(field)) invalid();
    for (const field of fields as string[]) {
      const value = values[field] ?? null;
      if (value !== null && typeof value !== "string") invalid();
      if (
        ["taxable_base", "iva_rate", "iva_amount"].includes(field) &&
        value !== null &&
        (!CANONICAL.test(value as string) ||
          /\.\d*0$/.test(value as string) ||
          (field === "iva_rate" && Number(value) > 100))
      )
        invalid();
      if (
        field === "invoice_date" &&
        value !== null &&
        !DATE.test(value as string)
      )
        invalid();
    }
    for (const field of fields as string[])
      (record as unknown as Record<string, unknown>)[field] =
        field === "notes"
          ? ((values[field] as string | null) ?? "")
          : (values[field] ?? null);
    record.updated_at = now();
    return {
      profile_id: profileId,
      record: projected(record),
      bucket_event_ids: events(),
    };
  }
  function remove(request: JsonObject): JsonObject {
    const record = recordOf(request.evidence_id) ?? notFound();
    if (
      ledger.movements.some(
        (movement) =>
          movement.transaction.purchase_invoice_evidence_id ===
          record.evidence_id,
      )
    )
      throw new InvoiceStopped("REFUSED_LEDGER_EVIDENCE_IN_USE", {});
    ledger.evidence = ledger.evidence.filter((found) => found !== record);
    readings.delete(record.evidence_id);
    return {
      profile_id: profileId,
      record: projected(record),
      bucket_event_ids: events(),
    };
  }

  function reviewRow(reference: string, reading: Reading): JsonObject {
    return {
      evidence_reference: reference,
      extractor: reading.extractor,
      drafted_at: reading.drafted_at,
      blocking_count: reading.blockers.length,
      reasons: reading.blockers.map((blocker) => blocker.reason),
      advisory_count: 0,
      advisories: [],
    };
  }
  function reviewList(request: JsonObject): JsonObject {
    const rows = pending()
      .filter(
        ([, reading]) =>
          (request.blocking_only !== true || reading.blockers.length > 0) &&
          (!request.reason ||
            reading.blockers.some(
              (blocker) => blocker.reason === request.reason,
            )),
      )
      .map(([reference, reading]) => reviewRow(reference, reading))
      .sort((left, right) =>
        String(right.drafted_at).localeCompare(String(left.drafted_at)),
      );
    return { profile_id: profileId, filters: [], rows };
  }
  function reviewView(request: JsonObject): JsonObject {
    const reference = text(request.evidence_reference);
    if (!reference || reference.length > 64) invalid();
    const reading = readingOf(reference!);
    if (!reading || reading.confirmed) notFound();
    return {
      profile_id: profileId,
      evidence_reference: reference,
      extractor: reading!.extractor,
      drafted_at: reading!.drafted_at,
      draft: current(reading!) as unknown as JsonObject,
      label_reading_fallback: reading!.fallback as unknown as JsonValue,
      blockers: reading!.blockers as unknown as JsonValue,
      party_attribution_advisory: null,
      country_vocabulary_advisory: null,
    };
  }

  /** The source a request names: one record or one attachment, never
   * both. */
  function sourceOf(request: JsonObject): {
    reference: string;
    sha: string;
    record: FixtureEvidence | null;
  } {
    const evidence = text(request.evidence_id);
    const attachment = text(request.attachment_id);
    if ((evidence === null) === (attachment === null)) invalid();
    if (evidence !== null) {
      const record = recordOf(evidence) ?? notFound();
      return {
        reference: record.evidence_id,
        sha: record.source_sha256,
        record,
      };
    }
    const found =
      attachments.find((item) => item.attachment_id === attachment) ??
      notFound();
    return { reference: found.attachment_id, sha: found.sha256, record: null };
  }

  function extract(request: JsonObject): JsonObject {
    const provider = request.off_host_provider ?? null;
    const acknowledged = request.acknowledge_off_host === true;
    if (provider === null && acknowledged) invalid();
    if (
      provider !== null &&
      (provider !== "AGENT" || !acknowledged || !request.evidence_id)
    )
      invalid();
    const source = sourceOf(request);
    // A scan has no text for the labels: it cannot be read here at all.
    if (
      tools.readerMissing &&
      provider === null &&
      source.record?.media_kind === "image"
    )
      throw readerRefusal();
    let reading = readingOf(source.reference);
    if (!reading) {
      // An attachment read for the first time.
      reading = {
        ...nameReading({
          evidence_id: source.reference,
          bucket_id: profileId,
          source_sha256: source.sha,
          attachment_id: source.sha,
          media_kind: "pdf",
          supplier: null,
          invoice_number: null,
          invoice_date: null,
          taxable_base: null,
          iva_rate: null,
          iva_amount: null,
          notes: "",
          created_at: now(),
          updated_at: now(),
          source_path: "factura-adjunta.pdf",
        }),
      };
      readings.set(source.reference, reading);
    }
    reading.confirmed = false;
    reading.drafted_at = now();
    if (provider !== null) {
      dispatches.push({
        profile_bucket_id: profileId,
        evidence_content_address: source.sha,
        provider: "AGENT",
        model: "assistant-reader",
        surface: "runtime:ledger.evidence.extract",
        recorded_at: reading.drafted_at,
      });
      artefacts.push({
        evidence_reference: source.reference,
        provenance_stamp: "llm:assistant-reader",
        transport: "https",
        drafted_at: reading.drafted_at,
      });
    }
    return {
      profile_id: profileId,
      ...(source.record
        ? { evidence_id: source.reference }
        : { attachment_id: source.reference }),
      source_sha256: source.sha,
      draft_review_sha256: digestOf(reading),
      off_host_provider: provider,
      consent_audit_effect: provider === null ? "none" : "updated",
      draft: current(reading) as unknown as JsonObject,
      label_reading_fallback: reading.fallback as unknown as JsonValue,
    };
  }

  function confirm(request: JsonObject): JsonObject {
    const source = sourceOf(request);
    const kind = request.kind;
    const country = text(request.counterparty_country) ?? invalid();
    if (kind !== "issued" && kind !== "received") invalid();
    if (!/^[A-Z]{2}$/.test(country)) invalid();
    for (const field of [
      "expected_source_sha256",
      "expected_draft_review_sha256",
    ])
      if (!HEX64.test(text(request[field]) ?? "")) invalid();
    for (const field of [
      "taxable_base",
      "iva_rate",
      "iva_amount",
      "retention_rate",
      "retention_amount",
      "recargo_amount",
    ]) {
      const value = request[field];
      if (
        value !== undefined &&
        value !== null &&
        !CANONICAL.test(String(value))
      )
        invalid();
    }
    const reading = readingOf(source.reference);
    if (!reading || reading.confirmed) notFound();
    if (request.expected_source_sha256 !== source.sha)
      throw new InvoiceStopped("ERROR_VALIDATION", {});
    if (request.expected_draft_review_sha256 !== digestOf(reading!))
      throw new InvoiceStopped("ERROR_VALIDATION", {});
    const resolutions = Array.isArray(request.resolutions)
      ? (request.resolutions as JsonObject[])
      : [];
    for (const resolution of resolutions) {
      const action = resolution.action;
      const value = text(resolution.value);
      const note = text(resolution.note) ?? "";
      if (
        !reading!.blockers.some(
          (blocker) => blocker.blocker_id === resolution.blocker_id,
        ) ||
        (action === "attest" && (value !== null || !note.trim())) ||
        (action !== "attest" &&
          action !== "choose_candidate" &&
          action !== "supply_value") ||
        (action !== "attest" && !value?.trim())
      )
        invalid();
    }
    if (
      reading!.blockers.some(
        (blocker) =>
          !resolutions.some((found) => found.blocker_id === blocker.blocker_id),
      )
    )
      throw new InvoiceStopped(
        "REFUSED_LEDGER_EVIDENCE_CONFIRMATION_BLOCKED",
        {},
      );
    const draft = current(reading!);
    const party =
      text(request.counterparty_name) ??
      (kind === "issued" ? draft.customer_name : draft.supplier_name) ??
      null;
    const taxField = kind === "issued" ? "customer_tax_id" : "supplier_tax_id";
    const resolvedTaxId = resolutions.find(
      (found) =>
        found.action !== "attest" &&
        reading!.blockers.some(
          (blocker) =>
            blocker.blocker_id === found.blocker_id &&
            blocker.field === taxField,
        ),
    )?.value;
    const taxId =
      text(request.counterparty_tax_id) ??
      text(resolvedTaxId) ??
      draft[taxField] ??
      null;
    const number = text(request.invoice_number) ?? draft.invoice_number ?? null;
    const issued = text(request.invoice_date) ?? draft.invoice_date ?? null;
    const currency = text(request.currency) ?? draft.currency ?? null;
    const base =
      text(request.taxable_base) ?? draft.taxable_base?.decimal ?? null;
    const iva = text(request.iva_amount) ?? draft.iva_amount?.decimal ?? null;
    if (!party || !number || !issued || !currency || !base || !iva)
      throw new InvoiceStopped("ERROR_VALIDATION", {});
    const existing = ledger.invoices.find(
      (invoice) => invoice.source_sha256 === source.sha,
    );
    const invoice =
      existing ??
      catalogueInvoice(hex64, {
        number,
        kind: kind as InvoiceKind,
        issued,
        party,
        taxId,
        country,
        base,
        iva,
        currency,
        linked: [],
        sourceName: source.record ? fileName(source.record.source_path) : null,
        sourceSha: source.sha,
      });
    if (!existing) ledger.invoices.push(invoice);
    reading!.confirmed = true;
    return {
      profile_id: profileId,
      ...(source.record
        ? { evidence_id: source.reference }
        : { attachment_id: source.reference }),
      source_sha256: source.sha,
      reviewed_draft_sha256: digestOf(reading!),
      confirmation: {
        invoice: invoice as unknown as JsonObject,
        draft: draft as unknown as JsonObject,
        created: !existing,
        total_discrepancy: null,
        confirmation_id: hex64(`confirmation:${source.reference}`),
        confirmed_provenance: [],
        establishment: null,
        label_reading_fallback: null,
      },
    };
  }

  function attachmentQueue(): JsonObject {
    return {
      profile_id: profileId,
      count: attachments.length,
      rows: attachments as unknown as JsonValue,
    };
  }
  function attachmentView(request: JsonObject): JsonObject {
    const id = text(request.attachment_id);
    if (!id || !HEX64.test(id)) invalid();
    const item =
      attachments.find((found) => found.attachment_id === id) ?? notFound();
    return { profile_id: profileId, item: item as unknown as JsonObject };
  }
  /** One page of a stored document, drawn: an invented ticket prints what
   * its reading read, and every other page is the same invented picture. A
   * PDF has two pages and an image one; any other document cannot be
   * drawn. */
  function page(request: JsonObject): JsonObject {
    const evidenceId = text(request.evidence_id);
    const attachmentId = text(request.attachment_id);
    const number = typeof request.page === "number" ? request.page : NaN;
    const width =
      typeof request.max_width === "number" ? request.max_width : NaN;
    if (
      (evidenceId === null) === (attachmentId === null) ||
      !Number.isInteger(number) ||
      number < 1 ||
      !Number.isInteger(width) ||
      width < 64 ||
      width > 4096
    )
      invalid();
    const refused = (reason: string): never => {
      throw new InvoiceStopped(`REFUSED_LEDGER_EVIDENCE_PAGE_${reason}`, {});
    };
    let facts: { id: string; sha: string; name: string | null; media: string };
    if (evidenceId !== null) {
      const record = recordOf(evidenceId) ?? refused("NOT_FOUND");
      facts = {
        id: record.attachment_id,
        sha: record.source_sha256,
        name: fileName(record.source_path),
        media: record.media_kind === "pdf" ? "application/pdf" : "image/jpeg",
      };
    } else {
      if (!HEX64.test(attachmentId!)) invalid();
      const item =
        attachments.find((found) => found.attachment_id === attachmentId) ??
        refused("NOT_FOUND");
      facts = {
        id: item.attachment_id,
        sha: item.sha256,
        name: null,
        media: item.mime_type,
      };
    }
    const held = facts.name === null ? undefined : pageRefusals.get(facts.name);
    if (held) refused(held);
    const count =
      facts.media === "application/pdf"
        ? 2
        : facts.media === "image/jpeg" || facts.media === "image/png"
          ? 1
          : refused("UNSUPPORTED_MEDIA");
    if (number > count) refused("OUT_OF_RANGE");
    const ticket = DOCUMENTS.find(
      (spec) => spec.name === facts.name && spec.media === "image",
    );
    const drawn = ticket ? ticketPage(ticket) : DOCUMENT_PAGE;
    return {
      profile_id: profileId,
      evidence_id: evidenceId,
      attachment_id: facts.id,
      media_type: facts.media,
      page: number,
      page_count: count,
      width: drawn.width,
      height: drawn.height,
      source_sha256: facts.sha,
      file_name: facts.name,
      image_data_url: drawn.image_data_url,
    };
  }
  function consentList(): JsonObject {
    return {
      profile_id: profileId,
      survey: {
        consented_dispatches: dispatches,
        cloud_derived_artefacts: artefacts,
        transmitted_bytes_are_unrecallable: true,
      },
    };
  }
  // ---- Links -------------------------------------------------------------------

  function movementOf(id: JsonValue | undefined): FixtureMovement {
    const prefix = text(id)?.toLowerCase();
    if (!prefix || prefix.length > 64) invalid();
    const found = ledger.movements.filter((movement) =>
      movement.transaction.transaction_id.startsWith(prefix!),
    );
    if (found.length !== 1)
      throw new InvoiceStopped("ERROR_TRANSACTION_VALIDATION", {});
    return found[0]!;
  }
  function link(request: JsonObject): JsonObject {
    const movement = movementOf(request.transaction_id);
    const invoiceId = text(request.invoice_id);
    if (!invoiceId || invoiceId.length > 64) invalid();
    const invoice = ledger.invoices.find(
      (found) => found.invoice_id === invoiceId,
    );
    if (!invoice)
      throw new InvoiceStopped("REFUSED_LEDGER_LINK_VALIDATION", {
        profile_id: profileId,
        transaction_id: request.transaction_id as string,
        invoice_id: invoiceId,
        outcome: "refused",
        projection: null,
        reason: "missing_invoice",
      });
    const id = movement.transaction.transaction_id;
    movement.transaction.invoice_id = invoice.invoice_id;
    movement.transaction.modified_at = now();
    if (!invoice.linked_transaction_ids.includes(id)) {
      const linked = {
        ...invoice,
        linked_transaction_ids: [...invoice.linked_transaction_ids, id],
      };
      ledger.invoices = ledger.invoices.map((found) =>
        found === invoice ? linked : found,
      );
    }
    return {
      profile_id: profileId,
      transaction_id: request.transaction_id as string,
      invoice_id: invoice.invoice_id,
      outcome: "linked",
      projection: {
        profile_id: profileId,
        operation: "link",
        bucket_id: profileId,
        transaction_id: id,
        invoice_id: invoice.invoice_id,
        actor: "operator",
        bucket_event_ids: events(),
        review_status:
          movement.transaction.business_classification === "NOT_YET_PROCESSED"
            ? "pending"
            : "reviewed",
        transaction: { ...movement.transaction } as unknown as JsonObject,
      },
      reason: null,
    };
  }
  const knownAttachment = (id: string) =>
    ledger.evidence.some((record) => record.attachment_id === id) ||
    attachments.some((item) => item.attachment_id === id) ||
    ledger.movements.some((movement) =>
      movement.transaction.attachment_ids.includes(id),
    );
  function attach(request: JsonObject, detach: boolean): JsonObject {
    const movement = movementOf(request.transaction_id);
    const ids = request.attachment_ids ?? [];
    if (!Array.isArray(ids) || ids.some((id) => typeof id !== "string"))
      invalid();
    const evidence = detach ? null : text(request.purchase_invoice_evidence_id);
    if (detach && (ids as string[]).length === 0) invalid();
    if (!detach && evidence === null && (ids as string[]).length === 0)
      invalid();
    if (evidence !== null && !recordOf(evidence))
      throw new InvoiceStopped("ERROR_EVIDENCE_NOT_FOUND", {});
    if (!detach && (ids as string[]).some((id) => !knownAttachment(id)))
      throw new InvoiceStopped("ERROR_ATTACHMENT_NOT_FOUND", {});
    const t = movement.transaction;
    if (detach)
      t.attachment_ids = t.attachment_ids.filter(
        (id) => !(ids as string[]).includes(id),
      );
    else {
      if (evidence !== null) t.purchase_invoice_evidence_id = evidence;
      t.attachment_ids = [
        ...t.attachment_ids,
        ...(ids as string[]).filter((id) => !t.attachment_ids.includes(id)),
      ];
    }
    t.modified_at = now();
    const operation = detach ? "ledger.detach" : "ledger.attach";
    return {
      outcome: "updated",
      profile_id: profileId,
      operation_id: operation,
      result: {
        profile_id: profileId,
        operation_id: operation,
        transaction: { ...t } as unknown as JsonObject,
        review_status:
          t.business_classification === "NOT_YET_PROCESSED"
            ? "pending"
            : "reviewed",
        bucket_event_ids: events(),
        stale_finalized_revisions: [],
      },
      validation_messages: [],
    };
  }
  function check(request: JsonObject): JsonObject {
    const period = request.period ?? null;
    const issues = period === null ? [] : tools.issuesFor(period);
    const byInvoice = new Map(
      ledger.invoices.map((invoice) => [invoice.invoice_id, invoice]),
    );
    const byMovement = new Map(
      ledger.movements.map((movement) => [
        movement.transaction.transaction_id,
        movement,
      ]),
    );
    const inconsistencies: JsonObject[] = [];
    for (const invoice of ledger.invoices)
      for (const id of invoice.linked_transaction_ids)
        if (byMovement.get(id)?.transaction.invoice_id !== invoice.invoice_id)
          inconsistencies.push({
            invoice_id: invoice.invoice_id,
            transaction_id: id,
            direction: "invoice-only",
          });
    for (const movement of ledger.movements) {
      const cited = movement.transaction.invoice_id;
      if (
        cited !== null &&
        !byInvoice
          .get(cited)
          ?.linked_transaction_ids.includes(movement.transaction.transaction_id)
      )
        inconsistencies.push({
          invoice_id: cited,
          transaction_id: movement.transaction.transaction_id,
          direction: "transaction-only",
        });
    }
    inconsistencies.sort((left, right) =>
      `${left.invoice_id}${left.transaction_id}`.localeCompare(
        `${right.invoice_id}${right.transaction_id}`,
      ),
    );
    return {
      profile_id: profileId,
      period,
      bucket_id: profileId,
      periods: [],
      checked_transaction_count: ledger.movements.length,
      issues: issues as unknown as JsonValue,
      link_inconsistencies: inconsistencies,
      ready: issues.length === 0 && inconsistencies.length === 0,
    };
  }

  const byName = (name: string) =>
    ledger.evidence.find((record) => fileName(record.source_path) === name);
  made.add({
    changeReading(name: string) {
      const record = byName(name);
      const reading = record && readingOf(record.evidence_id);
      if (reading) reading.version += 1;
    },
    changeSource(name: string) {
      const record = byName(name);
      if (record) {
        const sha = hex64(`document-bytes:${name}:changed`);
        record.source_sha256 = sha;
        record.attachment_id = sha;
      }
    },
    refusePage(name: string, reason: string | null) {
      if (reason === null) pageRefusals.delete(name);
      else pageRefusals.set(name, reason);
    },
  });
  window.__scenarioDocuments = {
    changeReading: (name) => made.forEach((one) => one.changeReading(name)),
    changeSource: (name) => made.forEach((one) => one.changeSource(name)),
    refusePage: (name, reason) =>
      made.forEach((one) => one.refusePage(name, reason)),
  };
  return {
    reads: {
      "ledger.evidence.list": list,
      "ledger.evidence.view": view,
      "ledger.evidence.review.list": reviewList,
      "ledger.evidence.review.view": reviewView,
      "ledger.evidence.attachment_queue": attachmentQueue,
      "ledger.evidence.attachment_view": attachmentView,
      "ledger.evidence.page": page,
      "ledger.evidence.consent.list": consentList,
      "ledger.check": check,
    } satisfies Record<string, (request: JsonObject) => JsonObject>,
    writes: {
      "ledger.evidence.add": add,
      "ledger.evidence.update": update,
      "ledger.evidence.remove": remove,
      "ledger.evidence.extract": extract,
      "ledger.evidence.confirm": confirm,
      "ledger.link": link,
      "ledger.attach": (request: JsonObject) => attach(request, false),
      "ledger.detach": (request: JsonObject) => attach(request, true),
    } satisfies Record<string, (request: JsonObject) => JsonObject>,
  };
}
