// The typed requests and results of the ledger operations that change, check
// or trace one movement: edits, classification, manual entry, staged checks,
// splits, lifecycle, history and the model's suggestions. Field names are the
// registered Python contracts' own; a request omits the profile, which the
// host fills.

import type {
  LedgerReviewStatus,
  LedgerTransaction,
  OutputLanguage,
  PublicPeriod,
} from "./ledger";
import type { LedgerUpdateField } from "./ledgerContract";

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
  operation_date?: string | null;
  accrual_date?: string | null;
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

/** One staged change: a value to set, or a clear when `value` is null. */
export type LedgerStagedCell = { field: string; value: string | null };

export type LedgerStagedRow = {
  transaction_id: string;
  cells: LedgerStagedCell[];
  evidence_staged: boolean;
  m210_staged: boolean;
};

export type LedgerStagedDraft = {
  key: string;
  fields: { field: string; value: string }[];
};

/** Staged work and the movements asked about, answered the way the writers
 * would take them, plus the categories to judge a classification against. */
export type LedgerRuleTrialRequest = {
  description_pattern: string;
  transaction_ids: string[];
};

/** Whether the rule engine reads a pattern, which of the movements named it
 * finds, and which of those it would classify now. */
export type LedgerRuleTrialResult = {
  profile_id: string;
  outcome:
    "matched" | "empty_pattern" | "invalid_pattern" | "too_long" | "overrun";
  hits: string[];
  pending: string[];
};

/** Unsaved parts of a movement. No amount on the last asks what the others leave. */
export type LedgerSplitCheckRequest = {
  transaction_id: string;
  parts: { amount: string | null; description: string }[];
};

/** What is left for the last part, the first thing the split writer would
 * refuse, and the parts as it takes them. */
export type LedgerSplitCheckResult = {
  profile_id: string;
  remainder: string | null;
  problem: {
    kind:
      | "gone"
      | "not_active"
      | "count"
      | "amount"
      | "description"
      | "description_long"
      | "sum";
    index: number | null;
    max: number | null;
    difference: string | null;
    over: boolean | null;
  } | null;
  children: { amount: string; description: string }[];
};

export type LedgerStagedCheckRequest = {
  rows: LedgerStagedRow[];
  drafts: LedgerStagedDraft[];
  categories: string[];
  /** The language the answer's sentences are said in. */
  output_language?: OutputLanguage;
};

export type LedgerStagedRoute = {
  field: string;
  route: "bulk" | "classify" | "update" | null;
  refused: "cannot_clear" | "needs_classification" | null;
};

export type LedgerStagedBlocker = {
  kind:
    | "cannot_clear"
    | "needs_classification"
    | "mixed_needs_share"
    | "share_needs_mixed"
    | "transfer_with_tax"
    | "draft_incomplete"
    | "amount_signed"
    | "needs_withholding_category";
  fields: string[];
  /** The sentence saying why the staged work cannot be sent. */
  words: string;
  /** The sentence saying what puts it right. */
  fix_words: string;
  words_language: OutputLanguage;
};

export type LedgerStagedNote = {
  kind: "sends_current_classification" | "sends_current_share" | "new_identity";
  value: string | null;
  fields: string[];
};

export type LedgerStagedRowAnswer = {
  transaction_id: string;
  found: boolean;
  classified: boolean;
  takes_expense_category: boolean;
  takes_share: boolean;
  category_askable: boolean;
  category_settable: boolean;
  category_on_income: boolean;
  takes_changes: boolean;
  takes_invoice: boolean;
  evidence_advised: boolean;
  lifecycle_actions: ("archive" | "stash" | "restore" | "exclude")[];
  tax_set_skip: "transfer" | "personal" | null;
  transfer_locked_fields: string[];
  classifying_fields: string[];
  identity_fields: string[];
  routes: LedgerStagedRoute[];
  blockers: LedgerStagedBlocker[];
  notes: LedgerStagedNote[];
};

export type LedgerStagedCheckResult = {
  profile_id: string;
  input_digest: string;
  rows: LedgerStagedRowAnswer[];
  drafts: {
    key: string;
    takes_expense_category: boolean;
    blockers: LedgerStagedBlocker[];
  }[];
  categories: { category: string; business: boolean; mixed: boolean }[];
  /** The sentence shown beside a business share no percentage reads. */
  share_refusal_words: string;
  share_refusal_words_language: OutputLanguage;
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
