// The typed requests and results of the invoice catalogue's operations: list,
// add, preview, correct, remove, import, duplicate and match checks, and the
// links between movements and invoices. Field names are the registered Python
// contracts' own; a request omits the profile, which the host fills.

import type {
  FileToken,
  LedgerReviewStatus,
  LedgerTransaction,
  PublicDecimal,
  PublicPeriod,
} from "./ledger";
import type {
  InvoiceUpdateField,
  LedgerPreflightReason,
  PaymentStatus,
} from "./ledgerContract";

export type InvoiceKind = "issued" | "received";

export type CatalogueInvoiceLine = {
  description: string;
  quantity: PublicDecimal;
  unit_price: PublicDecimal;
  subtotal: PublicDecimal;
  iva_rate: string;
  iva_amount: PublicDecimal;
  spending_category_id: string | null;
  oss_rate_kind: string | null;
};

export type CatalogueInvoice = {
  invoice_id: string;
  bucket_id: string | null;
  kind: InvoiceKind;
  invoice_number: string;
  issued_at: string;
  counterparty_name: string;
  counterparty_tax_id: string | null;
  counterparty_country: string;
  base_total: PublicDecimal;
  iva_total: PublicDecimal;
  grand_total: PublicDecimal;
  currency: string;
  payment_status: PaymentStatus;
  linked_transaction_ids: string[];
  source_filename: string | null;
  source_sha256: string | null;
  source_row_index: number | null;
  notes: string;
  retention_rate: PublicDecimal | null;
  retention_amount: PublicDecimal | null;
  recargo_amount: PublicDecimal | null;
  operation_type: string | null;
  lines: CatalogueInvoiceLine[];
  invoice_class: string;
  series: string | null;
  operation_date: string | null;
  operation_date_role: string | null;
  iva_category: string | null;
  rectifies_invoice_number: string | null;
  fx_rate: PublicDecimal | null;
  fx_rate_date: string | null;
  fx_rate_source: string | null;
  base_total_eur: PublicDecimal | null;
  iva_total_eur: PublicDecimal | null;
  grand_total_eur: PublicDecimal | null;
  /** The issued invoice's leased premises' cadastral reference, as the
   * ledger holds it. */
  referencia_catastral: string | null;
  /** The cash the invoice settles for: its total less the retención withheld
   * at source. */
  settlement_amount: PublicDecimal;
};

/** The catalogue filters by kind only. */
export type InvoiceListRequest = { kind?: InvoiceKind | null };

export type InvoiceListResult = {
  profile_id: string;
  kind: InvoiceKind | null;
  invoices: CatalogueInvoice[];
};

/** One structured line of a new invoice. `iva_rate` is the registry's rate
 * slot (`RATE_21`, `EXEMPT`, ...); subtotal and IVA must agree with the
 * quantity, price and rate to the cent. */
export type InvoiceAddLine = {
  description: string;
  quantity: PublicDecimal;
  unit_price: PublicDecimal;
  subtotal: PublicDecimal;
  iva_rate: string;
  iva_amount: PublicDecimal;
  spending_category_id?: string | null;
  oss_rate_kind?: string | null;
};

/** A new invoice. Its kind, number, issue date, counterparty tax id,
 * currency and total are its identity, fixed once it is in the catalogue. */
export type InvoiceAddRequest = {
  kind: InvoiceKind;
  counterparty_name: string;
  counterparty_tax_id?: string | null;
  counterparty_country: string;
  invoice_number: string;
  issued_at: string;
  taxable_base?: PublicDecimal | null;
  iva_rate?: PublicDecimal | null;
  currency: string;
  notes?: string;
  iva_category?: string | null;
  operation_type?: string | null;
  operation_date?: string | null;
  retention_rate?: PublicDecimal | null;
  retention_amount?: PublicDecimal | null;
  invoice_class?: string | null;
  series?: string | null;
  rectifies_invoice_number?: string | null;
  recargo_amount?: PublicDecimal | null;
  business_premises_lease?: {
    situacion_inmueble?: string | null;
    referencia_catastral?: string | null;
  } | null;
  lines?: InvoiceAddLine[];
};

export type InvoiceAddValidation = "invalid_invoice" | "duplicate_invoice";

/** A created invoice. A refused one settles as a refusal whose detail is
 * this shape with `outcome: "validation_error"`. */
export type InvoiceAddResult = {
  outcome: "created" | "validation_error";
  profile_id: string;
  invoice: CatalogueInvoice | null;
  /** The invoice already in the catalogue, for a duplicate. */
  invoice_id: string | null;
  bucket_event_ids: string[];
  euro_value_pending: boolean;
  simplificada_tax_id_advisory_required: boolean;
  validation_code: InvoiceAddValidation | null;
  /** Why a refused one was refused, as the backend served it. */
  refusal_words?: string | null;
  refusal_words_language?: string | null;
};

/** One line of a draft invoice. A figure the draft does not state yet is
 * left out, which is never the same as zero. `key` correlates the answer's
 * line to this one. */
export type InvoicePreviewLine = {
  key: string;
  description?: string | null;
  quantity?: PublicDecimal | null;
  unit_price?: PublicDecimal | null;
  iva_rate?: string | null;
  subtotal?: PublicDecimal | null;
  iva_amount?: PublicDecimal | null;
  spending_category_id?: string | null;
  oss_rate_kind?: string | null;
};

/** What a correction restates of the stored invoice it corrects. */
export type InvoicePreviewStored = {
  invoice_id: string;
  grand_total: PublicDecimal;
  operation_date_role?: string | null;
};

/** What a document states, as read or corrected. */
export type LedgerInvoiceDuplicateRequest = {
  kind: InvoiceKind;
  invoice_number: string | null;
  counterparty_tax_id: string | null;
  invoice_date: string | null;
  grand_total: string | null;
};

/** The stored invoice the document may already be, and what they share. */
export type LedgerInvoiceDuplicateResult = {
  profile_id: string;
  invoice_id: string | null;
  basis: "number" | "party_day_total" | null;
};

/** A link the person has staged and not saved. */
export type LedgerInvoiceMatchStagedLink = {
  transaction_id: string;
  invoice_id: string;
};

/** What to propose given the staged links. With `invoice_id` only that invoice
 * is weighed and the open movements near its day come back as choices; with
 * `transaction_id` the invoices of that movement's flow come back as choices
 * and only its suggestion is returned. */
export type LedgerInvoiceMatchRequest = {
  staged: LedgerInvoiceMatchStagedLink[];
  invoice_id?: string | null;
  transaction_id?: string | null;
  /** Links to state the differences of; they take nothing from the
   * suggestions. */
  judge?: LedgerInvoiceMatchStagedLink[];
};

/** One way a judged movement and invoice do not agree; the fields besides
 * `kind` are the kind's own and null otherwise. */
export type LedgerInvoiceMatchMismatch = {
  kind: "amount" | "currency" | "counterparty" | "linked_elsewhere";
  /** `amount`: the magnitude of the movement's amount less what the invoice
   * settles for. */
  difference: { decimal: string } | null;
  /** `currency`: the movement's currency. */
  movement: string | null;
  /** `currency`: the invoice's currency. */
  invoice: string | null;
  /** `linked_elsewhere`: how many other movements already hold the invoice. */
  count: number | null;
};

/** What stands against one named link; `found` is false when the movement or
 * the invoice is gone. */
export type LedgerInvoiceMatchJudgement = {
  transaction_id: string;
  invoice_id: string;
  found: boolean;
  mismatches: LedgerInvoiceMatchMismatch[];
};

/** One movement and one invoice that settle each other, and the evidence the
 * pair stands on. */
export type LedgerInvoiceMatchPair = {
  transaction_id: string;
  invoice_id: string;
  /** The description names the invoice's number. */
  number: boolean;
  /** Days from the invoice's date to the movement's; negative when paid first. */
  gap: number;
  /** The counterparty names overlap. */
  counterparty: boolean;
};

/** A movement's best invoice, with what competes with it. */
export type LedgerInvoiceMatchSuggestion = LedgerInvoiceMatchPair & {
  ambiguous: boolean;
  ties: LedgerInvoiceMatchPair[];
  others: LedgerInvoiceMatchPair[];
};

/** The ledger's proposals, newest movement first, and the by-hand choices the
 * request asked for. */
export type LedgerInvoiceMatchResult = {
  profile_id: string;
  suggestions: LedgerInvoiceMatchSuggestion[];
  /** How many days either side of an invoice's issue day the movement
   * choices reach. */
  window_days: number;
  invoice_choices:
    | {
        invoice_id: string;
        settles: boolean;
        staged_for: string | null;
        linked: number;
      }[]
    | null;
  movement_choices: { transaction_id: string; settles: boolean }[] | null;
  /** One judgement per link named in `judge`, in the order named. */
  judgements: LedgerInvoiceMatchJudgement[];
};

/** A draft invoice, every field optional because it is incomplete while it
 * is typed. It states `lines` or a bare `base_total`, never both; a correction
 * states the bare base with `stored`. */
export type InvoicePreviewRequest = {
  operation_date?: string | null;
  issued_at?: string | null;
  lines?: InvoicePreviewLine[];
  base_total?: PublicDecimal | null;
  recargo_amount?: PublicDecimal | null;
  retention_rate?: PublicDecimal | null;
  retention_amount?: PublicDecimal | null;
  printed_total?: PublicDecimal | null;
  kind?: InvoiceKind | null;
  invoice_number?: string | null;
  counterparty_name?: string | null;
  counterparty_tax_id?: string | null;
  counterparty_country?: string | null;
  currency?: string | null;
  invoice_class?: string | null;
  iva_category?: string | null;
  operation_type?: string | null;
  series?: string | null;
  rectifies_invoice_number?: string | null;
  notes?: string;
  business_premises_lease?: {
    situacion_inmueble?: string | null;
    referencia_catastral?: string | null;
  } | null;
  stored?: InvoicePreviewStored | null;
};

export type InvoicePreviewOnDateSource =
  "operation_date" | "issued_at" | "today";

export type InvoicePreviewVerdict =
  "incomplete" | "would_accept" | "would_refuse";

export type InvoicePreviewFigureVerdict =
  "equal" | "within_tolerance" | "refused" | "not_checked";

export type InvoicePreviewSeverity = "refusal" | "warning";

/** A rate slot's standing on the draft's date. `fraction` is null when no
 * rate applies; `label_key` names the slot's word. */
export type InvoicePreviewRateSlot = {
  slot: string;
  fraction: PublicDecimal | null;
  in_force: boolean;
  coverage_gap: boolean;
  label_key: string;
};

/** The backend's figure, the stated one with its verdict, and the one add
 * would store. */
export type InvoicePreviewFigure = {
  computed: PublicDecimal | null;
  stated: PublicDecimal | null;
  verdict: InvoicePreviewFigureVerdict | null;
  submitted: PublicDecimal | null;
};

export type InvoicePreviewLineResult = {
  key: string;
  subtotal: InvoicePreviewFigure;
  iva_amount: InvoicePreviewFigure;
};

/** A total is null until every part of it is known. */
export type InvoicePreviewTotals = {
  base: PublicDecimal | null;
  iva: PublicDecimal | null;
  recargo: PublicDecimal | null;
  total: PublicDecimal | null;
  net_of_retention: PublicDecimal | null;
};

export type InvoicePreviewRetention = {
  rate: PublicDecimal | null;
  amount: PublicDecimal | null;
  implied: PublicDecimal | null;
};

/** One closed finding. `code` is stable, `values` are what it compared and
 * `label_key` names its word. */
export type InvoicePreviewFinding = {
  code: string;
  severity: InvoicePreviewSeverity;
  fields: string[];
  line_key: string | null;
  values: { key: string; value: string | number | boolean | PublicDecimal }[];
  label_key: string;
};

/** What a verdict was reached over. `correction_facts` judged only what a
 * correction states: the update checks the whole stored record again and can
 * still refuse. */
export type InvoicePreviewVerdictScope = "whole_draft" | "correction_facts";

/** The backend's whole answer for one draft, bound to it by `input_digest`.
 * `would_accept` on a whole draft is acceptance's own verdict; a duplicate is
 * decided only when the invoice is added. `rule_findings` names the document
 * rules outside the figures, as far as an incomplete draft lets them be asked. */
export type InvoicePreviewResult = {
  profile_id: string;
  input_digest: string;
  on_date: string;
  on_date_source: InvoicePreviewOnDateSource;
  rate_slots: InvoicePreviewRateSlot[];
  lines: InvoicePreviewLineResult[];
  totals: InvoicePreviewTotals;
  retention: InvoicePreviewRetention;
  findings: InvoicePreviewFinding[];
  missing_fields: string[];
  verdict: InvoicePreviewVerdict;
  refusal_code: string | null;
  invoice_id: string | null;
  rule_findings: InvoicePreviewFinding[];
  verdict_scope: InvoicePreviewVerdictScope;
};

export type InvoiceUpdateValues = {
  counterparty_name?: string | null;
  counterparty_country?: string | null;
  notes?: string | null;
  payment_status?: PaymentStatus | null;
  iva_category?: string | null;
  operation_type?: string | null;
  operation_date?: string | null;
  retention_rate?: PublicDecimal | null;
  retention_amount?: PublicDecimal | null;
  series?: string | null;
  invoice_class?: string | null;
  rectifies_invoice_number?: string | null;
  payment_id?: string | null;
};

/** A correction: `fields` names what changes, and a named field sent as
 * null clears it. A value outside `fields` is refused. */
export type InvoiceUpdateRequest = {
  invoice_id: string;
  patch: { values: InvoiceUpdateValues; fields: InvoiceUpdateField[] };
};

export type InvoiceUpdateResult = {
  profile_id: string;
  invoice_id: string;
  invoice: CatalogueInvoice;
  bucket_event_ids: string[];
};

/** Keeps one document as an invoice's source; the host fills its folder.
 * The same document again changes nothing and says it was already there. */
export type InvoiceDocumentAttachRequest = {
  invoice_id: string;
  source_path: FileToken;
};

export type InvoiceDocumentAttachResult = {
  profile_id: string;
  invoice_id: string;
  attachment_id: string;
  already_linked: boolean;
};

/** Removes an invoice that no movement is linked to. */
export type InvoiceRemoveRequest = { invoice_id: string };

export type InvoiceRemoveResult = {
  profile_id: string;
  invoice_id: string;
  invoice: CatalogueInvoice;
};

/** One invoice by its id or an unambiguous prefix of it. A lookup that
 * finds none or several settles as a refusal whose detail is this shape. */
export type InvoiceViewRequest = { invoice_id: string };

export type InvoiceViewResult = {
  profile_id: string;
  invoice_id: string;
  outcome:
    | { kind: "success"; invoice: CatalogueInvoice }
    | {
        kind: "refused";
        reason: "required" | "not_found" | "ambiguous";
        candidate_ids: string[];
      };
};

/** An invoice book, imported row by row: it has no dry run, and a refused
 * row leaves the others created. */
export type InvoiceImportRequest = {
  kind: InvoiceKind;
  source_path: FileToken;
  source_sha256?: string | null;
  /** Two letters, for a book that has no country column. */
  country?: string | null;
};

export type InvoiceImportResult = {
  profile_id: string;
  /** The digest of the bytes the import read. */
  source_sha256: string;
  rows: number;
  created: number;
  skipped_duplicate: number;
  refused: { row_number: number; field: string; reason: string }[];
  created_invoice_ids: string[];
  unmapped_column_headers: string[];
  mapping_reasons: string[];
};

// ---- Links between movements and invoices ---------------------------------

/** Links one movement to one invoice, both sides at once. A link cannot be
 * removed. */
export type LedgerLinkRequest = {
  transaction_id: string;
  invoice_id: string;
  actor?: string | null;
};

export type LedgerLinkResult = {
  profile_id: string;
  transaction_id: string;
  invoice_id: string;
  outcome: "linked" | "refused";
  projection?: {
    profile_id: string;
    operation?: "link";
    bucket_id: string;
    transaction_id: string;
    invoice_id: string;
    actor: string;
    bucket_event_ids: string[];
    review_status: LedgerReviewStatus;
    transaction: LedgerTransaction;
  } | null;
  reason?:
    | "missing_invoice"
    | "cross_bucket_invoice"
    | "transaction_takes_no_invoice"
    | null;
};

/** Attaches evidence and attachments to one movement. */
export type LedgerAttachRequest = {
  transaction_id: string;
  purchase_invoice_evidence_id?: string | null;
  attachment_ids?: string[];
  actor?: string | null;
};

export type LedgerDetachRequest = {
  transaction_id: string;
  attachment_ids: string[];
  actor?: string | null;
};

export type LedgerAttachResult = {
  outcome: "updated" | "validation_error";
  profile_id: string;
  operation_id: "ledger.attach" | "ledger.detach";
  result?: {
    profile_id: string;
    operation_id: "ledger.attach" | "ledger.detach";
    transaction: LedgerTransaction;
    review_status: LedgerReviewStatus;
    bucket_event_ids: string[];
    stale_finalized_revisions?: {
      work_unit_id: string;
      calculation_revision_id: string;
      revision_state: string;
      modelo: string;
      filing_year: number;
      period: string;
    }[];
  } | null;
  validation_messages?: string[];
};

/** Which side of a link cites the other without being cited back. */
export type LinkInconsistencyDirection = "invoice-only" | "transaction-only";

export type LedgerCheckRequest = { period?: PublicPeriod | null };

/** The ledger's anomalies over every period a movement touches, and every
 * link the two catalogues disagree about. */
export type LedgerCheckResult = {
  profile_id: string;
  period: PublicPeriod | null;
  bucket_id: string;
  periods: string[];
  checked_transaction_count: number;
  issues: {
    transaction_id: string;
    reason: LedgerPreflightReason;
    detail: string;
  }[];
  link_inconsistencies: {
    invoice_id: string;
    transaction_id: string;
    direction: LinkInconsistencyDirection;
  }[];
  ready: boolean;
};
