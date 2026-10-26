// The Ledger page's port to the ledger family's registered operations, as
// the desktop host serves them over the signed-in person's session. The page
// names one admitted definition and a JSON object of its registered request
// without the profile; the host fills the profile and the runtime's contract
// decides the rest. Files travel as tokens the host issued for the person's
// own picks, never as paths, and an own account's number only as the raw
// bytes of one call. Results and staged edits live in the page's memory
// only: never in storage, a log line or an error message.

import type {
  ActivityAssetChangeResult,
  ActivityAssetClaimRequest,
  ActivityAssetClaimResult,
  ActivityAssetFilingRequest,
  ActivityAssetFilingResult,
  ActivityAssetForecastRequest,
  ActivityAssetForecastResult,
  ActivityAssetInspectRequest,
  ActivityAssetInspectResult,
  ActivityAssetRevisionRequest,
  CapitalGoodDeclareRequest,
  CapitalGoodDeclareResult,
  CapitalGoodsListResult,
  InventoryBookRequest,
  InventoryClosingAuthorityRequest,
  InventoryClosingAuthorityResult,
  InventoryCreateRequest,
  InventoryCreateResult,
  InventoryListResult,
  InventoryMovementAddRequest,
  InventoryMovementAddResult,
  InventoryValuationResult,
  LedgerCounterpartyRequest,
  LedgerCounterpartyResult,
  LedgerLlmDiagnosticsRequest,
  LedgerLlmDiagnosticsResult,
  LedgerOwnAccountRequest,
  LedgerOwnAccountResult,
  LedgerParticipationRebuildResult,
  LedgerRatiosEligibleResult,
  LedgerRatiosListResult,
  LedgerRatiosSetRequest,
  LedgerRatiosSetResult,
  LedgerRatiosUnsetRequest,
  LedgerRatiosUnsetResult,
  LedgerRatiosValidateResult,
  LedgerRatiosYearRequest,
  LedgerResetRequest,
  LedgerResetResult,
  LedgerRuleAddRequest,
  LedgerRuleAddResult,
  LedgerRuleApplyRequest,
  LedgerRuleApplyResult,
  LedgerRuleListResult,
  ProrrataDeclareSectorRequest,
  ProrrataElectEspecialRequest,
  ProrrataElectionRequest,
  ProrrataListResult,
  ProrrataMutationResult,
  ProrrataRevokeEspecialRequest,
  ProrrataSeedRequest,
  ProrrataSeedSectorRequest,
  ProrrataSettleSectorRequest,
} from "./ledgerSetup";

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
  "ledger.evidence.page",
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
  /** The own account's register id, never its number; null for none. */
  own_account_id: string | null;
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
  | "file_limit"
  /** Only the local AI reads this file and it could not be asked; the
   * file's verdict names its setup when setting it up lets the file be
   * read. */
  | "reader_unavailable";
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
  refused_files: {
    file_name: string;
    reason_code: LedgerImportRefusalCode;
    /** Present exactly for `reader_unavailable`: the reader's verdict. */
    precondition_verdict?: JsonObject | null;
  }[];
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

/** A declaration revision a movement took part in, as the participation
 * index keeps it. */
export type LedgerParticipation = {
  calculation_revision_id: string;
  work_unit_id: string;
  modelo: string;
  filing_year: number;
  period: PublicPeriod;
  revision_state: string;
  filing_record_id: string | null;
  justificante_reference: string | null;
};
/** One movement's lineage, where it came from and which finalized
 * declarations cite it. A current or a superseded id may be named. */
export type LedgerTrackRequest = { transaction_prefix: string };
export type LedgerTrackResult = {
  profile_id: string;
  transaction_prefix: string;
  transaction: LedgerTransaction;
  tracking: {
    transaction_id: string;
    created_event_id: string | null;
    evidence_provenance: {
      evidence_id: string;
      evidence_kind: string;
      actor: string;
      source_command: string;
      linked_at: string;
      bucket_event_id: string | null;
    }[];
    edit_lineage: {
      previous_transaction_id: string;
      actor: string;
      source_command: string;
      edited_at: string;
      bucket_event_id: string | null;
    }[];
    lifecycle_state: string;
    lifecycle_lineage: {
      previous_state: string;
      state: string;
      actor: string;
      source_command: string;
      changed_at: string;
      reason: string;
      bucket_event_id: string | null;
    }[];
  };
  /** Set for an imported movement, null for one added by hand. */
  imported_provenance: {
    provider_name: string;
    source_filename: string;
    source_row_index: number;
    ingested_at: string;
    import_fingerprint: string | null;
  } | null;
  /** Null where the participation index was never built. */
  participated_in: LedgerParticipation[] | null;
};

/** One movement's event chain, with its split siblings' where asked. */
export type LedgerHistoryRequest = {
  transaction_prefix: string;
  include_split_siblings?: boolean;
};
export type LedgerHistoryEventDetails = Partial<
  Record<
    | "source_command"
    | "mutation_kind"
    | "direction"
    | "amount"
    | "currency"
    | "business_pct"
    | "usage_ratio_id"
    | "prorrata_reference"
    | "previous_transaction_id"
    | "transaction_id"
    | "classification"
    | "category_id"
    | "category"
    | "iva_category"
    | "classified_by"
    | "provider"
    | "provenance"
    | "confidence"
    | "suggestion_kind"
    | "operator_reason"
    | "reason"
    | "lifecycle_state"
    | "previous_lifecycle_state"
    | "invoice_id"
    | "linked"
    | "media_kind"
    | "source_sha256"
    | "purchase_invoice_evidence_count"
    | "attachment_count"
    | "cascade_count"
    | "import_batch_id"
    | "provider_name"
    | "source_format"
    | "source_row_index"
    | "imported_count"
    | "skipped_count"
    | "split_group_id"
    | "parent_transaction_id"
    | "merged_transaction_id"
    | "child_count"
    | "export_format"
    | "include_inactive"
    | "row_count"
    | "byte_size"
    | "sha256"
    | "transaction_ids_sha256"
    | "first_transaction_id"
    | "last_transaction_id",
    string | null
  >
>;
export type LedgerHistoryTypedResult = {
  profile_id: string;
  transaction_prefix: string;
  include_split_siblings: boolean;
  transaction_id: string;
  /** The movement, its earlier ids and, where asked, its split siblings. */
  object_ids: string[];
  events: {
    event_id: string;
    event_type: string;
    occurred_at: string;
    actor: string;
    object_type: string;
    object_id: string;
    details: LedgerHistoryEventDetails;
    model_reason_withheld: boolean;
    output_path_withheld: boolean;
    undeclared_detail_count: number;
  }[];
  event_count: number;
};

/** A finalized or draft declaration revision a removal or a lifecycle
 * change meets. */
export type LedgerRevisionReference = {
  work_unit_id: string;
  calculation_revision_id: string;
  revision_state: string | null;
  modelo: string;
  filing_year: number;
  period: string;
};
/** Removes a movement; `dry_run` reports what it would take with it and
 * what stops it, and changes nothing. */
export type LedgerRemoveRequest = {
  transaction_id: string;
  reason?: string;
  dry_run?: boolean;
  actor?: string | null;
};
export type LedgerRemoveResult = {
  profile_id: string;
  report: {
    bucket_id: string;
    transaction_id: string;
    removed: boolean;
    dry_run: boolean;
    actor: string;
    reason: string;
    cascaded_purchase_invoice_evidence_ids: string[];
    cascaded_attachment_ids: string[];
    /** Finalized declarations that stop the removal. */
    blocking_modelo_references: LedgerRevisionReference[];
    /** Draft revisions the removal makes stale. */
    stale_draft_revision_references: LedgerRevisionReference[];
    bucket_event_ids: string[];
  };
};

/** Archive, set aside, restore or exclude one movement. */
export type LedgerLifecycleRequest = {
  transaction_id: string;
  reason?: string;
  actor?: string | null;
};
export type LedgerLifecycleResult = {
  outcome: "updated" | "validation_error";
  profile_id: string;
  operation_id:
    "ledger.archive" | "ledger.stash" | "ledger.restore" | "ledger.exclude";
  result: {
    profile_id: string;
    transaction: LedgerTransaction;
    review_status: LedgerReviewStatus;
    bucket_event_ids: string[];
  } | null;
  validation: {
    messages: string[];
    blocking_reference: LedgerRevisionReference | null;
  } | null;
};

/** Splits an active movement into two or more parts whose amounts add up
 * to its own, exactly. */
export type LedgerSplitRequest = {
  transaction_id: string;
  children: { amount: string; description: string }[];
  reason?: string;
  actor?: string | null;
};
export type LedgerSplitResult = {
  profile_id: string;
  parent_transaction_id: string;
  split_group_id: string;
  /** In the order the parts were sent. */
  child_transaction_ids: string[];
  bucket_event_id: string;
  parent_business_classification: string;
  child_business_classification: string;
  remerged_by: string[];
};
/** Merges every part of one split back into its parent. */
export type LedgerMergeRequest = {
  child_ids: string[];
  reason?: string;
  actor?: string | null;
};
export type LedgerMergeResult = {
  profile_id: string;
  split_group_id: string;
  parent_transaction_id: string;
  merged_transaction_id: string;
  source_child_ids: string[];
  bucket_event_id: string;
};

/** Works out and saves base, rate and IVA from the registry's rate for an
 * IVA category the person chose; a category with no single rate is
 * answered as not derivable and writes nothing. */
export type LedgerIvaDeriveRequest = {
  transaction_id: string;
  iva_category: string;
  actor?: string | null;
};
export type LedgerIvaDeriveResult = {
  profile_id: string;
  outcome: "derived" | "validation_error";
  transaction_id: string;
  iva_category: string;
  derivable: boolean;
  iva_rate: string | null;
  taxable_base: string | null;
  iva_amount: string | null;
  note: string;
  classification: LedgerClassifyResult | null;
  validation_messages: string[];
};
/** Sets a movement's business share, as a fraction, with what it is
 * allocated by. */
export type LedgerAllocateRequest = {
  transaction_id: string;
  business_pct: string;
  category_id?: string | null;
  usage_ratio_id?: string | null;
  prorrata_reference?: string | null;
  actor?: string | null;
};
export type LedgerAllocateResult = {
  profile_id: string;
  transaction: LedgerTransaction;
  review_status: LedgerReviewStatus;
  bucket_event_ids: string[];
};

// ---- Documents: evidence, reviewable drafts, consent and readers ---------

export type EvidenceMediaKind = "pdf" | "image";
/** One evidence record. `source_path` is the file's name only: the host
 * keeps where it is. `iva_rate` is a percentage, `21` for 21%. */
export type EvidenceRecord = {
  evidence_id: string;
  bucket_id: string;
  source_sha256: string;
  attachment_id: string;
  media_kind: EvidenceMediaKind;
  supplier?: string | null;
  invoice_number?: string | null;
  invoice_date?: string | null;
  taxable_base?: string | null;
  iva_rate?: string | null;
  iva_amount?: string | null;
  notes?: string;
  created_at: string;
  updated_at: string;
  source_path: string;
};
/** Registers one document as evidence; the host fills its folder. */
export type EvidenceAddRequest = {
  source_path: FileToken;
  supplier?: string | null;
  invoice_number?: string | null;
  invoice_date?: string | null;
  taxable_base?: string | null;
  iva_rate?: string | null;
  iva_amount?: string | null;
  notes?: string;
  idempotency_key?: string | null;
};
/** A record added, corrected or removed. */
export type EvidenceRecordResult = {
  profile_id: string;
  record: EvidenceRecord;
  bucket_event_ids: string[];
};
export type EvidenceListResult = {
  profile_id: string;
  count: number;
  rows: EvidenceRecord[];
};
export type EvidenceViewRequest = { evidence_id: string };
export type EvidenceViewResult = {
  result_version?: 2;
  profile_id: string;
  outcome:
    | { kind: "success"; record: EvidenceRecord }
    | { kind: "refused"; evidence_record_present: false };
};
export const EVIDENCE_UPDATE_FIELDS = [
  "supplier",
  "invoice_number",
  "invoice_date",
  "taxable_base",
  "iva_rate",
  "iva_amount",
  "notes",
] as const;
export type EvidenceUpdateField = (typeof EVIDENCE_UPDATE_FIELDS)[number];
/** A correction: `patch_fields` names what changes, and a named field sent
 * as null clears it. Decimals are in their shortest spelling. */
export type EvidenceUpdateRequest = {
  evidence_id: string;
  patch: Partial<Record<EvidenceUpdateField, string | null>>;
  patch_fields: EvidenceUpdateField[];
};
export type EvidenceRemoveRequest = { evidence_id: string };

export type FieldOrigin =
  | "exact_structured"
  | "text_layer"
  | "text_rules"
  | "vision"
  | "tabular_mapped"
  | "operator"
  | "derived";
export type FieldGrounding =
  "reconciled" | "anchored" | "unanchored" | "ambiguous" | "contradicted";
export type AmbiguityCandidate = {
  value: string;
  anchor?: string | null;
  note?: string;
};
/** Where one field of a reading came from, and whether the page agrees. */
export type FieldProvenance = {
  field: string;
  origin: FieldOrigin;
  grounding: FieldGrounding;
  anchor?: string | null;
  refused_anchor?: string | null;
  candidates?: AmbiguityCandidate[];
  anchor_self_reported?: boolean;
  derived_from?: string[];
  role_evidence?: string | null;
  attribution_unverified?: boolean;
  note?: string;
};
export type DraftDiscrepancyKind =
  | "arithmetic_closure"
  | "rate_inconsistent"
  | "breakdown_inconsistent"
  | "identity_unverified"
  | "role_unresolved"
  | "regime_contradicted"
  | "direction_contradicted"
  | "postal_code_unreadable"
  | "party_attribution_contradicted"
  | "invoice_class_unmodelled"
  | "invoice_class_contradicted";
export type DraftDiscrepancy = {
  kind: DraftDiscrepancyKind;
  field?: string | null;
  detail?: string;
  expected?: PublicDecimal | null;
  observed?: PublicDecimal | null;
};
export type EvidenceDraftLine = {
  description?: string | null;
  quantity?: PublicDecimal | null;
  unit_price?: PublicDecimal | null;
  taxable_base?: PublicDecimal | null;
  iva_rate?: PublicDecimal | null;
  iva_amount?: PublicDecimal | null;
  recargo_rate?: PublicDecimal | null;
  recargo_amount?: PublicDecimal | null;
};
/** A reading of one invoice document, a proposal until it is confirmed.
 * Its rates are whole percentages, `21` for 21%. */
export type EvidenceDraft = {
  supplier_tax_id?: string | null;
  supplier_name?: string | null;
  customer_tax_id?: string | null;
  customer_name?: string | null;
  supplier_postal_code?: string | null;
  customer_postal_code?: string | null;
  supplier_country?: string | null;
  customer_country?: string | null;
  supplier_country_code?: string | null;
  customer_country_code?: string | null;
  supplier_stated_country_code?: string | null;
  customer_stated_country_code?: string | null;
  invoice_number?: string | null;
  invoice_series?: string | null;
  rectifies_invoice_number?: string | null;
  proposed_supply_nature?: "goods" | "services" | null;
  invoice_date?: string | null;
  taxable_base?: PublicDecimal | null;
  iva_rate?: PublicDecimal | null;
  iva_amount?: PublicDecimal | null;
  grand_total?: PublicDecimal | null;
  currency?: string | null;
  regime_legend?: string | null;
  recargo_amount?: PublicDecimal | null;
  retencion_rate?: PublicDecimal | null;
  retencion_amount?: PublicDecimal | null;
  suplidos_amount?: PublicDecimal | null;
  lines?: EvidenceDraftLine[];
  iva_breakdown?: {
    iva_rate?: PublicDecimal | null;
    taxable_base?: PublicDecimal | null;
    iva_amount?: PublicDecimal | null;
    recargo_rate?: PublicDecimal | null;
    recargo_amount?: PublicDecimal | null;
  }[];
  iva_category?: string | null;
  suggested_kind?: InvoiceKind | null;
  transcription_sha256?: string | null;
  provenance?: FieldProvenance[];
  discrepancies?: DraftDiscrepancy[];
  raw_text_length?: number;
  facturae_invoice_class?: {
    source_code: string;
    kind: "ordinary" | "corrective" | "summary";
  } | null;
};
/** Why some fields were left unread: the model fill did not run. */
export type LabelReadingFallback = {
  cause: "reader_unavailable" | "load_headroom_refused" | "inference_slot_busy";
  unread_fields: string[];
  reader_error_type: string;
  failed_condition_id?: string | null;
  /** The operator action that would let the model fill run, such as the
   * local AI setup; an identifier for routing, never shown. */
  recovery_action_id?: string | null;
};
export type ConfirmationBlockReason =
  | "closure_discrepancy"
  | "ambiguous_identity"
  | "unresolved_direction"
  | "contradicted_regime"
  | "undetermined_establishment"
  | "unmodelled_invoice_class"
  | "contradicted_invoice_class";
/** A finding the person answers before the reading may be confirmed. Its
 * id is derived from what it is, so the same reading raises the same ids. */
export type ConfirmationBlocker = {
  blocker_id: string;
  reason: ConfirmationBlockReason;
  field?: string | null;
  detail?: string;
  candidates?: AmbiguityCandidate[];
};
export type ReviewAdvisoryKind =
  "party_attribution" | "country_code_unassigned" | "country_code_uncatalogued";
export type EvidenceReviewListRequest = {
  reason?: ConfirmationBlockReason | null;
  finding?: DraftDiscrepancyKind | null;
  advisory?: ReviewAdvisoryKind | null;
  blocking_only?: boolean;
};
/** One reading waiting for review. `evidence_reference` is the evidence
 * record's id, or the attachment's where the reading has no record. */
export type EvidenceReviewRow = {
  evidence_reference: string;
  extractor: string;
  drafted_at: string;
  blocking_count: number;
  reasons?: ConfirmationBlockReason[];
  advisory_count: number;
  advisories?: ReviewAdvisoryKind[];
};
export type EvidenceReviewListResult = {
  profile_id: string;
  filters?: string[];
  rows?: EvidenceReviewRow[];
};
export type EvidenceReviewViewRequest = { evidence_reference: string };
export type EvidenceReviewViewResult = {
  profile_id: string;
  evidence_reference: string;
  extractor: string;
  drafted_at: string;
  draft: EvidenceDraft;
  label_reading_fallback?: LabelReadingFallback | null;
  blockers?: ConfirmationBlocker[];
  party_attribution_advisory?: {
    parties: {
      role: string;
      fields?: string[];
      scope_if_attributed?: string | null;
    }[];
  } | null;
  country_vocabulary_advisory?: {
    parties: {
      role: string;
      field: string;
      stated_code: string;
      status: "catalogued" | "unassigned" | "uncatalogued";
      detail: string;
    }[];
  } | null;
};
/** Reads one document into a reviewable draft: on this computer, or off it
 * only with the provider named and acknowledged for this one call. */
export type EvidenceExtractRequest = {
  evidence_id?: string | null;
  attachment_id?: string | null;
  off_host_provider?: "AGENT" | null;
  acknowledge_off_host?: boolean;
};
export type EvidenceExtractResult = {
  profile_id: string;
  evidence_id?: string | null;
  attachment_id?: string | null;
  source_sha256: string;
  draft_review_sha256: string;
  off_host_provider?: "AGENT" | "LOCAL" | null;
  consent_audit_effect: "none" | "updated" | "partial" | "unknown";
  draft: EvidenceDraft;
  label_reading_fallback?: LabelReadingFallback | null;
};
export type FindingResolutionAction =
  "choose_candidate" | "supply_value" | "attest";
/** One finding answered: a reading chosen, a value supplied, or the value
 * as read attested with a note. */
export type FindingResolution = {
  blocker_id: string;
  action: FindingResolutionAction;
  value?: string | null;
  note?: string;
};
/** Confirms one reading as a catalogue invoice. It is bound to the source
 * bytes and the reading the person reviewed: a changed file or reading is
 * refused. The country is always sent. */
export type EvidenceConfirmRequest = {
  evidence_id?: string | null;
  attachment_id?: string | null;
  expected_source_sha256: string;
  expected_draft_review_sha256: string;
  kind: InvoiceKind;
  counterparty_country: string;
  counterparty_tax_id?: string | null;
  counterparty_name?: string | null;
  invoice_number?: string | null;
  invoice_date?: string | null;
  taxable_base?: string | null;
  iva_rate?: string | null;
  iva_amount?: string | null;
  currency?: string | null;
  iva_category?: string | null;
  operation_type?: string | null;
  operation_date?: string | null;
  retention_rate?: string | null;
  retention_amount?: string | null;
  recargo_amount?: string | null;
  invoice_class?: string | null;
  supply_nature?: "goods" | "services" | null;
  series?: string | null;
  rectifies_invoice_number?: string | null;
  notes?: string;
  resolutions?: FindingResolution[];
};
export type EvidenceConfirmResult = {
  profile_id: string;
  evidence_id?: string | null;
  attachment_id?: string | null;
  source_sha256: string;
  reviewed_draft_sha256: string;
  confirmation: {
    invoice: CatalogueInvoice;
    draft: EvidenceDraft;
    /** False where the catalogue already held this confirmation. */
    created: boolean;
    total_discrepancy?: {
      printed_total: PublicDecimal;
      recorded_total: PublicDecimal;
      difference: PublicDecimal;
    } | null;
    confirmation_id?: string | null;
    confirmed_provenance?: FieldProvenance[];
    establishment?: JsonObject | null;
    label_reading_fallback?: LabelReadingFallback | null;
  };
};
export type AttachmentSource =
  "LOCAL_FILE" | "GMAIL" | "GOOGLE_DRIVE" | "URL" | "INLINE";
/** A stored attachment waiting for invoice review. Its `provider_locator`
 * may name a place, and the page never shows it. */
export type AttachmentReviewItem = {
  attachment_id: string;
  sha256: string;
  mime_type: string;
  bytes_size: number;
  source: AttachmentSource;
  provider_locator: string;
  captured_at: string;
  linked_invoice_ids: string[];
  pending_review: boolean;
};
export type AttachmentQueueResult = {
  profile_id: string;
  count: number;
  rows?: AttachmentReviewItem[];
};
export type AttachmentViewRequest = { attachment_id: string };
/** One page of a stored document, drawn as an image. Names exactly one of
 * the evidence record or the attachment; `page` counts from 1. */
export type EvidencePageRequest = (
  | { evidence_id: string; attachment_id?: never }
  | { attachment_id: string; evidence_id?: never }
) & { page: number; max_width: number };
export type EvidencePageResult = {
  profile_id: string;
  evidence_id?: string | null;
  attachment_id: string;
  media_type: "application/pdf" | "image/jpeg" | "image/png";
  page: number;
  page_count: number;
  width: number;
  height: number;
  source_sha256: string;
  file_name?: string | null;
  /** A `data:image/png;base64,` URL; held in memory only. */
  image_data_url: string;
};
export type AttachmentViewResult = {
  profile_id: string;
  item: AttachmentReviewItem;
};
/** Every document that left this computer to be read, and what was made
 * from one. What was sent cannot be recalled. */
export type EvidenceConsentListResult = {
  profile_id: string;
  survey: {
    consented_dispatches?: {
      profile_bucket_id: string;
      evidence_content_address: string;
      provider: string;
      model: string;
      surface: string;
      recorded_at: string;
    }[];
    cloud_derived_artefacts?: {
      evidence_reference: string;
      provenance_stamp: string;
      transport?: string | null;
      drafted_at: string;
    }[];
    transmitted_bytes_are_unrecallable?: true;
  };
};
export type ReaderRole = {
  role: string;
  model?: string | null;
  installed?: boolean | null;
  resident?: boolean | null;
  load_admitted?: boolean | null;
  contention_causes?: string[];
  ready: boolean;
  failed_condition_id?: string | null;
  /** The operator action the reader check named for `failed_condition_id`,
   * such as the local AI setup for a runtime that does not answer or a
   * model that is not installed; absent where setup cannot change what is
   * missing. An identifier for routing, never shown. */
  recovery_action_id?: string | null;
};
/** What can read documents on this computer. */
export type ReaderReadinessResult = {
  profile_id: string;
  host: {
    platform: "windows" | "macos" | "linux" | "other";
    endpoint_url?: string | null;
    endpoint_local: boolean;
    executable_located: boolean;
    reachable: boolean;
    version?: string | null;
    version_withheld?: boolean;
    available: boolean;
    failed_condition_id?: string | null;
  };
  roles: ReaderRole[];
  extraction_ready: boolean;
  document_readiness: "all_documents" | "text_layer_only";
  text_layer_model_fill_available: boolean;
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
  reason?: "missing_invoice" | "cross_bucket_invoice" | null;
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
  "ledger.evidence.add": EvidenceAddRequest;
  "ledger.evidence.list": Record<string, never>;
  "ledger.evidence.view": EvidenceViewRequest;
  "ledger.evidence.update": EvidenceUpdateRequest;
  "ledger.evidence.remove": EvidenceRemoveRequest;
  "ledger.evidence.review.list": EvidenceReviewListRequest;
  "ledger.evidence.review.view": EvidenceReviewViewRequest;
  "ledger.evidence.extract": EvidenceExtractRequest;
  "ledger.evidence.confirm": EvidenceConfirmRequest;
  "ledger.evidence.attachment_queue": Record<string, never>;
  "ledger.evidence.attachment_view": AttachmentViewRequest;
  "ledger.evidence.page": EvidencePageRequest;
  "ledger.evidence.consent.list": Record<string, never>;
  "ledger.evidence.reader-readiness": Record<string, never>;
  "ledger.link": LedgerLinkRequest;
  "ledger.attach": LedgerAttachRequest;
  "ledger.detach": LedgerDetachRequest;
  "ledger.check": LedgerCheckRequest;
  "ledger.split.review": LedgerLlmReviewRequest;
  "ledger.track": LedgerTrackRequest;
  "ledger.history.typed": LedgerHistoryRequest;
  "ledger.remove": LedgerRemoveRequest;
  "ledger.archive": LedgerLifecycleRequest;
  "ledger.stash": LedgerLifecycleRequest;
  "ledger.restore": LedgerLifecycleRequest;
  "ledger.exclude": LedgerLifecycleRequest;
  "ledger.split.manual": LedgerSplitRequest;
  "ledger.merge": LedgerMergeRequest;
  "ledger.classify.iva-derive": LedgerIvaDeriveRequest;
  "ledger.allocate": LedgerAllocateRequest;
  "ledger.rule.list": Record<string, never>;
  "ledger.rule.add": LedgerRuleAddRequest;
  "ledger.rule.apply": LedgerRuleApplyRequest;
  "ledger.ratios.list": LedgerRatiosYearRequest;
  "ledger.ratios.eligible": LedgerRatiosYearRequest;
  "ledger.ratios.validate": Record<string, never>;
  "ledger.ratios.set": LedgerRatiosSetRequest;
  "ledger.ratios.unset": LedgerRatiosUnsetRequest;
  "ledger.counterparty": LedgerCounterpartyRequest;
  "ledger.llm-diagnostics": LedgerLlmDiagnosticsRequest;
  "ledger.own_account": LedgerOwnAccountRequest;
  "ledger.prorrata.list": Record<string, never>;
  "ledger.prorrata.seed": ProrrataSeedRequest;
  "ledger.prorrata.declare_sector": ProrrataDeclareSectorRequest;
  "ledger.prorrata.elect_general": ProrrataElectionRequest;
  "ledger.prorrata.elect_especial": ProrrataElectEspecialRequest;
  "ledger.prorrata.revoke_especial": ProrrataRevokeEspecialRequest;
  "ledger.prorrata.seed_sector": ProrrataSeedSectorRequest;
  "ledger.prorrata.settle_sector": ProrrataSettleSectorRequest;
  "ledger.bienes_inversion.list": Record<string, never>;
  "ledger.bienes_inversion.declare": CapitalGoodDeclareRequest;
  "ledger.inventory.list": Record<string, never>;
  "ledger.inventory.create": InventoryCreateRequest;
  "ledger.inventory.movement.add": InventoryMovementAddRequest;
  "ledger.inventory.valuation.preview": InventoryBookRequest;
  "ledger.inventory.closing-authority.record": InventoryClosingAuthorityRequest;
  "ledger.actividad-asset.create": ActivityAssetRevisionRequest;
  "ledger.actividad-asset.inspect": ActivityAssetInspectRequest;
  "ledger.actividad-asset.correct": ActivityAssetRevisionRequest;
  "ledger.actividad-asset.forecast": ActivityAssetForecastRequest;
  "ledger.actividad-asset.claim": ActivityAssetClaimRequest;
  "ledger.actividad-asset.filing-handoff": ActivityAssetFilingRequest;
  "ledger.participation.rebuild": Record<string, never>;
  "ledger.reset": LedgerResetRequest;
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
  "ledger.evidence.add": EvidenceRecordResult;
  "ledger.evidence.list": EvidenceListResult;
  "ledger.evidence.view": EvidenceViewResult;
  "ledger.evidence.update": EvidenceRecordResult;
  "ledger.evidence.remove": EvidenceRecordResult;
  "ledger.evidence.review.list": EvidenceReviewListResult;
  "ledger.evidence.review.view": EvidenceReviewViewResult;
  "ledger.evidence.extract": EvidenceExtractResult;
  "ledger.evidence.confirm": EvidenceConfirmResult;
  "ledger.evidence.attachment_queue": AttachmentQueueResult;
  "ledger.evidence.attachment_view": AttachmentViewResult;
  "ledger.evidence.page": EvidencePageResult;
  "ledger.evidence.consent.list": EvidenceConsentListResult;
  "ledger.evidence.reader-readiness": ReaderReadinessResult;
  "ledger.link": LedgerLinkResult;
  "ledger.attach": LedgerAttachResult;
  "ledger.detach": LedgerAttachResult;
  "ledger.check": LedgerCheckResult;
  "ledger.track": LedgerTrackResult;
  "ledger.history.typed": LedgerHistoryTypedResult;
  "ledger.remove": LedgerRemoveResult;
  "ledger.archive": LedgerLifecycleResult;
  "ledger.stash": LedgerLifecycleResult;
  "ledger.restore": LedgerLifecycleResult;
  "ledger.exclude": LedgerLifecycleResult;
  "ledger.split.manual": LedgerSplitResult;
  "ledger.merge": LedgerMergeResult;
  "ledger.classify.iva-derive": LedgerIvaDeriveResult;
  "ledger.allocate": LedgerAllocateResult;
  "ledger.rule.list": LedgerRuleListResult;
  "ledger.rule.add": LedgerRuleAddResult;
  "ledger.rule.apply": LedgerRuleApplyResult;
  "ledger.ratios.list": LedgerRatiosListResult;
  "ledger.ratios.eligible": LedgerRatiosEligibleResult;
  "ledger.ratios.validate": LedgerRatiosValidateResult;
  "ledger.ratios.set": LedgerRatiosSetResult;
  "ledger.ratios.unset": LedgerRatiosUnsetResult;
  "ledger.counterparty": LedgerCounterpartyResult;
  "ledger.llm-diagnostics": LedgerLlmDiagnosticsResult;
  "ledger.own_account": LedgerOwnAccountResult;
  "ledger.prorrata.list": ProrrataListResult;
  "ledger.prorrata.seed": ProrrataMutationResult;
  "ledger.prorrata.declare_sector": ProrrataMutationResult;
  "ledger.prorrata.elect_general": ProrrataMutationResult;
  "ledger.prorrata.elect_especial": ProrrataMutationResult;
  "ledger.prorrata.revoke_especial": ProrrataMutationResult;
  "ledger.prorrata.seed_sector": ProrrataMutationResult;
  "ledger.prorrata.settle_sector": ProrrataMutationResult;
  "ledger.bienes_inversion.list": CapitalGoodsListResult;
  "ledger.bienes_inversion.declare": CapitalGoodDeclareResult;
  "ledger.inventory.list": InventoryListResult;
  "ledger.inventory.create": InventoryCreateResult;
  "ledger.inventory.movement.add": InventoryMovementAddResult;
  "ledger.inventory.valuation.preview": InventoryValuationResult;
  "ledger.inventory.closing-authority.record": InventoryClosingAuthorityResult;
  "ledger.actividad-asset.create": ActivityAssetChangeResult;
  "ledger.actividad-asset.inspect": ActivityAssetInspectResult;
  "ledger.actividad-asset.correct": ActivityAssetChangeResult;
  "ledger.actividad-asset.forecast": ActivityAssetForecastResult;
  "ledger.actividad-asset.claim": ActivityAssetClaimResult;
  "ledger.actividad-asset.filing-handoff": ActivityAssetFilingResult;
  "ledger.participation.rebuild": LedgerParticipationRebuildResult;
  "ledger.reset": LedgerResetResult;
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
  /** Shows an exported file selected in the system file manager, by the
   * save token it was exported to; refused `file_unavailable` until the
   * file is there, and `invalid` for a token picked to be read. */
  revealFile(token: FileToken): Promise<void>;
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
