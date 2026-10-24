// The Ledger page's port to the ledger family's registered operations, as
// the desktop host serves them over the signed-in person's session. The page
// names one admitted definition and a JSON object of its registered request
// without the profile; the host fills the profile and the runtime's contract
// decides the rest. Files travel as tokens the host issued for the person's
// own picks, never as paths, and an own account's number only as the raw
// bytes of one call. Results and staged edits live in the page's memory
// only: never in storage, a log line or an error message.

/** The definitions the host admits, mirroring its closed list. */
export const LEDGER_DEFINITIONS = [
  "ledger.actividad-asset.claim",
  "ledger.actividad-asset.correct",
  "ledger.actividad-asset.create",
  "ledger.actividad-asset.filing-handoff",
  "ledger.actividad-asset.forecast",
  "ledger.actividad-asset.inspect",
  "ledger.add",
  "ledger.allocate",
  "ledger.archive",
  "ledger.attach",
  "ledger.bienes_inversion.declare",
  "ledger.bienes_inversion.list",
  "ledger.check",
  "ledger.classify.bulk",
  "ledger.classify.iva-derive",
  "ledger.classify.review",
  "ledger.classify.single",
  "ledger.counterparty",
  "ledger.detach",
  "ledger.evidence.add",
  "ledger.evidence.attachment_queue",
  "ledger.evidence.attachment_view",
  "ledger.evidence.batch",
  "ledger.evidence.confirm",
  "ledger.evidence.consent.list",
  "ledger.evidence.extract",
  "ledger.evidence.list",
  "ledger.evidence.query",
  "ledger.evidence.reader-readiness",
  "ledger.evidence.remove",
  "ledger.evidence.review.list",
  "ledger.evidence.review.summary",
  "ledger.evidence.review.view",
  "ledger.evidence.update",
  "ledger.evidence.view",
  "ledger.exclude",
  "ledger.export",
  "ledger.history",
  "ledger.history.typed",
  "ledger.import",
  "ledger.inventory.closing-authority.record",
  "ledger.inventory.create",
  "ledger.inventory.list",
  "ledger.inventory.movement.add",
  "ledger.inventory.valuation.preview",
  "ledger.invoice.add",
  "ledger.invoice.import",
  "ledger.invoice.list",
  "ledger.invoice.remove",
  "ledger.invoice.update",
  "ledger.invoice.view",
  "ledger.invoice.wizard",
  "ledger.link",
  "ledger.list",
  "ledger.llm-diagnostics",
  "ledger.merge",
  "ledger.own_account",
  "ledger.participation",
  "ledger.participation.rebuild",
  "ledger.preflight",
  "ledger.prorrata.declare_sector",
  "ledger.prorrata.elect_especial",
  "ledger.prorrata.elect_general",
  "ledger.prorrata.list",
  "ledger.prorrata.revoke_especial",
  "ledger.prorrata.seed",
  "ledger.prorrata.seed_sector",
  "ledger.prorrata.settle_sector",
  "ledger.ratios.eligible",
  "ledger.ratios.list",
  "ledger.ratios.set",
  "ledger.ratios.unset",
  "ledger.ratios.validate",
  "ledger.remove",
  "ledger.reset",
  "ledger.restore",
  "ledger.review",
  "ledger.rule.add",
  "ledger.rule.apply",
  "ledger.rule.list",
  "ledger.split.manual",
  "ledger.split.review",
  "ledger.stash",
  "ledger.status",
  "ledger.track",
  "ledger.update",
  "ledger.view",
] as const;
export type LedgerDefinitionId = (typeof LEDGER_DEFINITIONS)[number];
export function isLedgerDefinition(id: string): id is LedgerDefinitionId {
  return (LEDGER_DEFINITIONS as readonly string[]).includes(id);
}

/** The longest payload, in characters of compact JSON, the host sends on.
 * The host refuses a longer one with `too_large` before anything is sent; the
 * page splits a batch into several requests and shows them as one apply. */
export const LEDGER_PAYLOAD_LIMIT = 12_032;

export type JsonValue =
  string | number | boolean | null | JsonValue[] | { [key: string]: JsonValue };
export type JsonObject = { [key: string]: JsonValue };

/** Why a ledger call did not answer an outcome. `unknown` is a write whose
 * settlement was not observed: it may have committed, is never sent again,
 * and holds further writes until the page reads the ledger again. */
export const LEDGER_FAILURE_CODES = [
  "unavailable",
  "not_signed_in",
  "refused",
  "unknown",
  "saved_unread",
  "review_changed",
  "too_large",
  "not_admitted",
  "invalid",
  "file_unavailable",
] as const;
export type LedgerFailureCode = (typeof LEDGER_FAILURE_CODES)[number];
export type LedgerFailure = {
  code: LedgerFailureCode;
  operation_id: string | null;
  /** The runtime's closed refusal code, where it gave one. */
  reason?: string;
};
/** The typed failure of a rejected ledger call. A rejection that is not the
 * host's own answer never reached it, so nothing was sent. */
export function ledgerFailure(error: unknown): LedgerFailure {
  const found = error as {
    code?: unknown;
    operation_id?: unknown;
    reason?: unknown;
  } | null;
  const code = (LEDGER_FAILURE_CODES as readonly unknown[]).includes(
    found?.code,
  )
    ? (found?.code as LedgerFailureCode)
    : "unavailable";
  return {
    code,
    operation_id:
      typeof found?.operation_id === "string" ? found.operation_id : null,
    ...(typeof found?.reason === "string" ? { reason: found.reason } : {}),
  };
}

/** The registered error detail a settled refusal carries, where its
 * definition declares one. */
export type LedgerErrorDetail = {
  detail_version: 1;
  kind: string;
  error_code: string | null;
  message_key: string | null;
  context: { key: string; value: JsonValue }[];
  context_entries_omitted: number;
  precondition_verdict_json: string | null;
};

/** Where an operation the page submitted stands. */
export type LedgerOutcome<Result = JsonObject> =
  | {
      kind: "settled";
      operation_id: string;
      revision: number;
      result: Result;
    }
  | {
      /** Settled without changing anything. */
      kind: "refused";
      operation_id: string;
      revision: number;
      reason: string | null;
      detail: LedgerErrorDetail | null;
    }
  | {
      /** Paused until the person answers the review it shows. */
      kind: "review";
      operation_id: string;
      revision: number;
      cancellable: boolean;
    }
  | {
      kind: "running";
      operation_id: string;
      revision: number;
      cancellable: boolean;
    };

/** The review a paused operation shows. An answer names its digest; a
 * changed review is refused with `review_changed` and needs a new answer. */
export type LedgerReview<Review = JsonObject> = {
  operation_id: string;
  revision: number;
  review_digest: string;
  expires_at: string | null;
  review: Review;
};
export type LedgerDecision = "apply" | "reject";

/** An opaque name for a file the person picked or dropped, valid only for
 * the signed-in session that it was issued for. */
export type FileToken = string & { readonly __fileToken: unique symbol };
export type FilePurpose =
  "bank_statements" | "invoice_books" | "documents" | "export";
/** One file, several, or every file of the purpose's kinds in a folder. */
export type FilePick = "file" | "files" | "folder";
export type PickedFile = {
  token: FileToken;
  name: string;
  bytes: number | null;
};
/** The files a dialog or a drop gave the page, and how many were not of the
 * purpose's kinds. */
export type FilePicks = { files: PickedFile[]; refused: number };
export type LedgerDropSignal =
  { kind: "over" } | { kind: "left" } | ({ kind: "dropped" } & FilePicks);

// ---- Typed requests and results, by definition --------------------------
// Field names are the registered Python contracts' own. A request omits the
// profile, which the host fills.

export type PublicPeriod = { filing_year: number; code: string };
export type PublicDecimal = { decimal: string };
export type LedgerReviewStatus =
  "pending" | "reviewed" | "skipped" | "excluded";
export type LedgerSortField =
  | "date"
  | "value_date"
  | "amount"
  | "description"
  | "created_at"
  | "modified_at"
  | "classified_at"
  | "lifecycle_state"
  | "classification";
export type LedgerSortOrder = "asc" | "desc";
export type OutputLanguage = "es" | "en" | "ca" | "hu";

export type LedgerM210Income = {
  official_tipo_renta_code: string;
  gross_income_amount: string;
  applicable_rate: string;
  payer_mode: string;
  payer_id: string | null;
  asset_or_right_id: string | null;
};
/** One movement as the product projects it. Amounts are canonical decimal
 * text; the amount is a magnitude and `direction` carries its sense. */
export type LedgerTransaction = {
  transaction_id: string;
  date: string;
  booked_date: string;
  value_date: string | null;
  amount: string;
  currency: string;
  direction: string;
  counterparty: string;
  description: string;
  business_classification: string;
  business_pct: string | null;
  category_id: string | null;
  taxable_base: string | null;
  iva_rate: string | null;
  iva_amount: string | null;
  iva_category: string | null;
  counterparty_country: string | null;
  counterparty_identification_state: string | null;
  irpf_category: string | null;
  m210_income_classification: LedgerM210Income | null;
  usage_ratio_id: string | null;
  prorrata_reference: string | null;
  purchase_invoice_evidence_id: string | null;
  invoice_id: string | null;
  attachment_ids: string[];
  notes: string;
  lifecycle_state: string;
  classified_by: string;
  classified_at: string | null;
  classification_reason: string;
  classification_confidence: string | null;
  source_jurisdiction: string | null;
  value_in_eur: string | null;
  fx_rate: string | null;
  created_at: string;
  modified_at: string;
};
export type LedgerRow = {
  transaction: LedgerTransaction;
  review_status: LedgerReviewStatus;
  group_label: string | null;
};

/** The order is the product's: filter, group selection, sort, group
 * partition, then the page. `filters` are `key=value` clauses. */
export type LedgerListRequest = {
  filters?: string[];
  group?: string | null;
  by_group?: boolean;
  limit?: number | null;
  offset?: number;
  sort_by?: LedgerSortField | null;
  sort_order?: LedgerSortOrder;
  exclude_llm_rejected?: boolean;
};
export type LedgerListResult = {
  profile_id: string;
  rows: LedgerRow[];
  total: number;
  truncated: boolean;
  offset: number;
  limit: number | null;
  by_group: boolean;
};

export type LedgerViewRequest = { transaction_prefix: string };
export type LedgerViewResult = {
  profile_id: string;
  transaction_prefix: string;
  transaction: LedgerTransaction;
  review_status: LedgerReviewStatus;
  latest_llm_rejection: { occurred_at: string; operator_reason: string } | null;
};

export const LEDGER_UPDATE_FIELDS = [
  "booked_date",
  "value_date",
  "amount",
  "direction",
  "currency",
  "counterparty",
  "description",
  "taxable_base",
  "iva_rate",
  "iva_amount",
  "irpf_category",
  "notes",
  "group_label",
  "own_account_id",
] as const;
export type LedgerUpdateField = (typeof LEDGER_UPDATE_FIELDS)[number];
/** Editing the amount, description, date or own account gives the movement
 * a new `transaction_id`; the result names it. */
export type LedgerUpdateRequest = {
  transaction_id: string;
  patch: Partial<Record<LedgerUpdateField, string | null>>;
  patch_fields: LedgerUpdateField[];
  actor?: string | null;
};
export type LedgerUpdateResult = {
  outcome: "updated" | "validation_error";
  profile_id: string;
  source_transaction_id: string | null;
  transaction: LedgerTransaction | null;
  review_status: LedgerReviewStatus | null;
  bucket_event_ids: string[];
  group_label: string | null;
  own_account_id: string | null;
  validation_messages: string[];
};

export const LEDGER_CLASSIFY_FIELDS = [
  "business_classification",
  "business_pct",
  "category_id",
  "taxable_base",
  "iva_rate",
  "iva_amount",
  "irpf_category",
  "m210_income_classification",
  "iva_category",
  "deduction_fact_kind",
  "investment_asset_id",
  "counterparty_country",
  "counterparty_identification_state",
  "notes",
] as const;
export type LedgerClassifyField = (typeof LEDGER_CLASSIFY_FIELDS)[number];
export type LedgerClassifyRequest = {
  transaction_id: string;
  patch: Partial<
    Record<
      Exclude<LedgerClassifyField, "m210_income_classification">,
      string | null
    >
  >;
  patch_fields: LedgerClassifyField[];
  m210?: {
    tipo_renta_code?: string | null;
    gross_income_amount?: string | null;
    applicable_rate?: string | null;
    payer_mode?: string | null;
    payer_id?: string | null;
    asset_or_right_id?: string | null;
  } | null;
  actor?: string | null;
  reaffirm?: boolean;
};
export type LedgerClassifyValidation =
  "none" | "input" | "m210_incoming_only" | "m210_required_options";
export type LedgerClassifyResult = {
  outcome: "classified" | "validation_error";
  profile_id: string;
  transaction: LedgerTransaction | null;
  deduction_fact_kind: string | null;
  investment_asset_id: string | null;
  review_status: LedgerReviewStatus | null;
  bucket_event_ids: string[];
  validation_kind: LedgerClassifyValidation;
  validation_messages: string[];
};

/** The columns a bulk classification CSV may carry; `transaction_id` and
 * `classification` are required on every row. */
export const LEDGER_BULK_CLASSIFY_COLUMNS = [
  "transaction_id",
  "classification",
  "category_id",
  "business_pct",
  "usage_ratio_id",
  "taxable_base",
  "iva_rate",
  "iva_amount",
  "iva_category",
  "irpf_category",
  "notes",
] as const;
export type LedgerBulkClassifyRequest = {
  csv_text: string;
  actor?: string | null;
  output_language?: OutputLanguage;
};
export type LedgerBulkClassifyResult = {
  profile_id: string;
  outcome: "classified" | "validation_error";
  result: {
    total: number;
    applied: number;
    skipped: number;
    failures: { row_index: number; transaction_id: string; reason: string }[];
    bucket_event_ids: string[];
  } | null;
  validation_messages: string[];
};

/** One manual movement. A retry with the same `idempotency_key` and the same
 * content returns the stored row instead of adding another. */
export type LedgerAddRequest = {
  booked_date: string;
  amount: string;
  direction: string;
  description: string;
  value_date?: string | null;
  currency?: string;
  counterparty?: string | null;
  business_classification?: string;
  business_pct?: string | null;
  category_id?: string | null;
  taxable_base?: string | null;
  iva_rate?: string | null;
  iva_amount?: string | null;
  iva_category?: string | null;
  deduction_fact_kind?: string | null;
  investment_asset_id?: string | null;
  counterparty_country?: string | null;
  counterparty_identification_state?: string | null;
  recargo_amount?: string | null;
  irpf_category?: string | null;
  usage_ratio_id?: string | null;
  prorrata_reference?: string | null;
  art_104_tres_exclusion?: string | null;
  input_classification?: string | null;
  prorrata_sector?: string | null;
  purchase_invoice_evidence_id?: string | null;
  attachment_ids?: string[];
  notes?: string;
  actor?: string | null;
  idempotency_key?: string | null;
  source_jurisdiction?: string | null;
  own_account_id?: string | null;
};
export type LedgerAddValidation =
  | "source_jurisdiction_required_irnr"
  | "source_jurisdiction_required_beckham"
  | "invalid_command";
export type LedgerAddResult = {
  outcome: "created" | "validation_error";
  profile_id: string;
  transaction: LedgerTransaction | null;
  review_status: LedgerReviewStatus | null;
  bucket_event_ids: string[];
  advisory_input_classification: string | null;
  advisory_input_classification_inert: boolean;
  advisory_sector_id: string | null;
  advisory_sector_unmatched: boolean;
  validation_code: LedgerAddValidation | null;
  validation_messages: string[];
};

export type InvoiceKind = "issued" | "received";
export type PaymentStatus =
  "PAID" | "PENDING" | "PARTIALLY_PAID" | "OVERDUE" | "CANCELLED";
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
};

/** The fields a stored invoice may be corrected in; its identity and lines
 * are not among them. */
export const INVOICE_UPDATE_FIELDS = [
  "counterparty_name",
  "counterparty_country",
  "notes",
  "payment_status",
  "iva_category",
  "operation_type",
  "operation_date",
  "retention_rate",
  "retention_amount",
  "series",
  "invoice_class",
  "rectifies_invoice_number",
  "payment_id",
] as const;
export type InvoiceUpdateField = (typeof INVOICE_UPDATE_FIELDS)[number];
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

export type LedgerStatusRequest = { period?: PublicPeriod | null };
export type LedgerStatusResult = {
  profile_id: string;
  period: PublicPeriod | null;
  business_income_total: string;
  business_expense_total: string;
  business_net_total: string;
  total_count: number;
  active_count: number;
  archived_count: number;
  stashed_count: number;
  split_count: number;
  pending_review_count: number;
  reviewed_count: number;
  skipped_count: number;
  checked_transaction_count: number;
  readiness_issue_count: number;
  unconverted_currency_count: number;
  /** Unknown is not ready: null means readiness was not measured. */
  ready: boolean | null;
  readiness_issues: {
    transaction_id: string;
    reason: string;
    detail: string;
    transaction_present: boolean;
    business_classification: string | null;
    category_id: string | null;
    taxable_base: string | null;
    iva_rate: string | null;
    iva_amount: string | null;
  }[];
  stale_filings: {
    modelo: string;
    filing_year: number;
    period: string;
    calculation_revision_id: string;
    work_unit_id: string;
    changed_count: number;
    removed_count: number;
    covers_current_fact_set: boolean;
  }[];
};

export type LedgerPreflightReason =
  | "missing_business_classification"
  | "missing_category"
  | "missing_taxable_base"
  | "missing_iva_amount"
  | "missing_iva_rate"
  | "missing_eur_tax_substrate"
  | "missing_counterparty_identification_state"
  | "domestic_identification_on_intra_community_transaction"
  | "eu_member_state_on_export_transaction"
  | "missing_counterparty_establishment_on_export"
  | "inadmissible_deduction_classification"
  | "missing_proportionality_reference"
  | "unsupported_currency"
  | "unsupported_period"
  | "censo_ratio_mismatch"
  | "missing_home_office_afectacion"
  | "anomaly_non_declarable_iva_category"
  | "anomaly_non_declarable_recargo_equivalencia";
export type LedgerPreflightRequest = { period: PublicPeriod };
export type LedgerPreflightResult = {
  profile_id: string;
  period: PublicPeriod;
  bucket_id: string;
  checked_transaction_count: number;
  issues: {
    transaction_id: string;
    reason: LedgerPreflightReason;
    detail: string;
  }[];
  ready: boolean;
};

export type LedgerProvider =
  "auto" | "csv" | "ofx" | "qfx" | "xlsx" | "xls" | "pdf";
/** A bank statement import. Preview with `dry_run`, then apply naming the
 * previewed files' digests in `expected_source_sha256`: a file that changed
 * since the preview is refused. */
export type LedgerImportRequest = {
  files: FileToken[];
  provider: LedgerProvider;
  dry_run?: boolean;
  verify?: boolean;
  verify_source?: FileToken | null;
  period?: PublicPeriod | null;
  own_account_id?: string | null;
  expected_source_sha256?: string[] | null;
};
export type LedgerTransactionRef = {
  bucket_id: string;
  transaction_id: string;
};
export type LedgerImportRefusalCode =
  | "transaction_validation"
  | "own_account_mismatch"
  | "result_limit"
  | "source_changed"
  | "empty_directory"
  | "file_limit";
export type LedgerImportDiagnosticKind =
  "original-file" | "gap" | "duplicate" | "parser";
/** The translation keys a diagnostic names, from the product's closed set. */
export type LedgerImportDiagnosticMessage =
  | "transactions.import.message_185962"
  | "transactions.import.message_082074"
  | "transactions.import.batch_id_collision"
  | "transactions.import.message_053465"
  | "transactions.import.message_829073"
  | "transactions.import.verified"
  | "transactions.import.unreadable";
/** One import's outcome over every file it planned, without paths or
 * provider prose. A likely duplicate is imported and listed, never skipped;
 * `skipped` rows were already in the ledger. Each planned file's digest is
 * named by its position in the plan, for an apply to bind to. */
export type LedgerImportResult = {
  profile_id: string;
  rows: number;
  imported: number;
  skipped: number;
  likely_duplicates: number;
  dry_run: boolean;
  verify: boolean;
  period: PublicPeriod | null;
  bucket_id: string;
  /** Set where one file's rows were imported; a request of several files
   * that each import has no single batch. */
  import_batch_id: string | null;
  bucket_event_ids: string[];
  imported_transaction_refs: LedgerTransactionRef[];
  skipped_transaction_refs: LedgerTransactionRef[];
  likely_duplicate_transaction_refs: LedgerTransactionRef[];
  validations: {
    valid: boolean;
    warning_count: number;
    encoding: string | null;
  }[];
  sources: { requested: boolean; sha256: string | null }[];
  diagnostics: {
    kind: LedgerImportDiagnosticKind;
    severity: "info" | "warning" | "error";
    message: LedgerImportDiagnosticMessage;
    affected_transaction_ids: string[];
  }[];
  refused_files: { file_name: string; reason_code: LedgerImportRefusalCode }[];
  source_digests: { file_index: number; sha256: string }[];
};

export type LedgerExportFormat = "csv" | "jsonl" | "xlsx";
/** An export replaces the file the person chose in the save dialog, for
 * the same format. */
export type LedgerExportRequest = {
  output_path: FileToken;
  export_format?: LedgerExportFormat;
  include_inactive?: boolean;
  period?: PublicPeriod | null;
  actor?: string | null;
};
export type LedgerExportResult = {
  profile_id: string;
  bucket_id: string;
  export_id: string;
  export_format: LedgerExportFormat;
  media_type: string;
  filename_extension: string;
  row_count: number;
  byte_size: number;
  sha256: string;
  fieldnames: string[];
  rows: Record<string, string>[];
  bucket_event_ids: string[];
  /** The file's name; the host keeps where it is. */
  output_path: string;
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

/** Documents added as evidence in one direction, read on this computer. */
export type EvidenceBatchRequest = {
  sources: FileToken[];
  direction: InvoiceKind;
};
export type EvidenceBatchItemStatus =
  "ingested" | "no_op" | "refused" | "pending_review" | "paused";
export type EvidenceBatchResult = {
  profile_id: string;
  write_count: number;
  effect: "none" | "updated" | "partial" | "unknown";
  direction: InvoiceKind;
  run: {
    items: {
      content_address: string;
      identity: string;
      direction: InvoiceKind;
      source_name: string;
      status: EvidenceBatchItemStatus;
      refusal_code: string | null;
      needed_inference: boolean;
    }[];
    unresolved: { source_name: string; refusal_code: string }[];
    inference_pause: JsonObject | null;
  };
};

export type LedgerLlmReviewMode =
  "classification" | "saturated" | "auto_split" | "split";
export type LedgerLlmReviewRequest = {
  transaction_id: string;
  mode: LedgerLlmReviewMode;
  origin:
    | "classify_llm_apply"
    | "classify_llm_reject"
    | "classify_llm_saturate_apply"
    | "classify_iva_category_saturate"
    | "classify_auto_split"
    | "split_llm";
  business_pct?: string | null;
  actor?: string | null;
  read_evidence?: boolean;
  vision_model?: string | null;
  reason?: string;
  preview?: boolean;
};
/** A model's proposal for one movement: only the person applies it. */
export type LedgerLlmSuggestion = {
  projection_version: 1;
  profile_id: string;
  reviewed_proposal_digest: string;
  suggestion: {
    kind: "classification" | "saturated" | "split";
    transaction_id: string;
    provenance: string;
    reason: string;
    evidence_id: string | null;
    classification: string | null;
    category: string | null;
    confidence: string | null;
    multiple_components: boolean | null;
    business_pct: string | null;
    iva_category: string | null;
    iva_rate: string | null;
    taxable_base: string | null;
    iva_amount: string | null;
    rate_derivable: boolean;
    derivation_note: string;
    evidence_advisory: string;
    parent_amount: string | null;
    children: {
      proportion: string;
      amount: string;
      description: string;
      category: string | null;
      iva_category: string | null;
      iva_rate: string | null;
      taxable_base: string | null;
      iva_amount: string | null;
      rate_derivable: boolean;
      derivation_note: string;
      evidence_citation: string;
    }[];
  };
};

export interface LedgerRequests {
  "ledger.list": LedgerListRequest;
  "ledger.view": LedgerViewRequest;
  "ledger.update": LedgerUpdateRequest;
  "ledger.classify.single": LedgerClassifyRequest;
  "ledger.classify.bulk": LedgerBulkClassifyRequest;
  "ledger.classify.review": LedgerLlmReviewRequest;
  "ledger.add": LedgerAddRequest;
  "ledger.invoice.list": InvoiceListRequest;
  "ledger.invoice.view": InvoiceViewRequest;
  "ledger.invoice.add": InvoiceAddRequest;
  "ledger.invoice.update": InvoiceUpdateRequest;
  "ledger.invoice.remove": InvoiceRemoveRequest;
  "ledger.status": LedgerStatusRequest;
  "ledger.preflight": LedgerPreflightRequest;
  "ledger.import": LedgerImportRequest;
  "ledger.export": LedgerExportRequest;
  "ledger.invoice.import": InvoiceImportRequest;
  "ledger.evidence.batch": EvidenceBatchRequest;
}
export interface LedgerResults {
  "ledger.list": LedgerListResult;
  "ledger.view": LedgerViewResult;
  "ledger.update": LedgerUpdateResult;
  "ledger.classify.single": LedgerClassifyResult;
  "ledger.classify.bulk": LedgerBulkClassifyResult;
  "ledger.add": LedgerAddResult;
  "ledger.invoice.list": InvoiceListResult;
  "ledger.invoice.view": InvoiceViewResult;
  "ledger.invoice.add": InvoiceAddResult;
  "ledger.invoice.update": InvoiceUpdateResult;
  "ledger.invoice.remove": InvoiceRemoveResult;
  "ledger.status": LedgerStatusResult;
  "ledger.preflight": LedgerPreflightResult;
  "ledger.import": LedgerImportResult;
  "ledger.export": LedgerExportResult;
  "ledger.invoice.import": InvoiceImportResult;
  "ledger.evidence.batch": EvidenceBatchResult;
}
export type LedgerRequest<D extends LedgerDefinitionId> =
  D extends keyof LedgerRequests ? LedgerRequests[D] : JsonObject;
export type LedgerResult<D extends LedgerDefinitionId> =
  D extends keyof LedgerResults ? LedgerResults[D] : JsonObject;

/** An own account added or changed, with its number or bank block. */
export type OwnAccountChange = {
  action: "add" | "update";
  own_account_id?: string;
  label?: string;
  holding?: string;
  iban?: string;
  swift_bic?: string;
  bank_name?: string;
  bank_address?: string;
  bank_city?: string;
  bank_country_code?: string;
  currency?: string;
  opened_on?: string;
};
/** The one document an own account change sends, as UTF-8 bytes. */
export function ownAccountChange(change: OwnAccountChange): Uint8Array {
  return new TextEncoder().encode(JSON.stringify(change));
}

export type LedgerPort = {
  /** Submits one admitted operation and follows it until it settles or
   * waits on the person. One attempt: nothing is retried. */
  submit<D extends LedgerDefinitionId>(
    definition: D,
    payload: LedgerRequest<D>,
  ): Promise<LedgerOutcome<LedgerResult<D>>>;
  /** Where an operation this page submitted stands now. */
  observe(operation: string): Promise<LedgerOutcome>;
  /** The review a paused operation shows, with its digest. */
  review<Review = JsonObject>(operation: string): Promise<LedgerReview<Review>>;
  /** Answers the review whose digest the page showed. */
  answer(
    operation: string,
    reviewDigest: string,
    decision: LedgerDecision,
  ): Promise<LedgerOutcome>;
  /** Asks to cancel at the revision the page observed. */
  cancel(operation: string, revision: number): Promise<LedgerOutcome>;
  /** Opens the native dialog for files of `purpose`; `filterLabel` names the
   * kinds it offers in the page's language. */
  pickFiles(
    purpose: Exclude<FilePurpose, "export">,
    pick: FilePick,
    filterLabel: string,
  ): Promise<FilePicks>;
  /** Opens the native save dialog for an export in `format`. */
  saveFile(
    format: LedgerExportFormat,
    filterLabel: string,
    suggestedName?: string,
  ): Promise<FilePicks>;
  /** Forgets tokens the page no longer shows. */
  forgetFiles(tokens: FileToken[]): Promise<void>;
  /** Calls `listener` as files of `purpose` are dragged over and dropped on
   * the window, until the returned function stops it. */
  observeDrops(
    purpose: Exclude<FilePurpose, "export">,
    listener: (signal: LedgerDropSignal) => void,
  ): Promise<() => void>;
  /** Adds an own account or changes its details with the bytes of
   * `ownAccountChange`, which this one call consumes and zeroes. */
  changeOwnAccount(change: Uint8Array): Promise<LedgerOutcome>;
};
