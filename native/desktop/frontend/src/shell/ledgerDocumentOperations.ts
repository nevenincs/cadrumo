// The typed requests and results of the document operations: evidence
// records, reviewable drafts and their confirmation, attachments, consent and
// pages. Field names are the registered Python contracts' own; a request omits
// the profile, which the host fills.

import type {
  FileToken,
  JsonObject,
  LedgerNextStep,
  PublicDecimal,
} from "./ledger";
import type { EvidenceUpdateField } from "./ledgerContract";
import type { CatalogueInvoice, InvoiceKind } from "./ledgerInvoiceOperations";

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
  | "invoice_class_contradicted"
  | "invoice_number_unnumbered";

/** The sentence explaining a finding and the values it quotes, as stored. */
export type FindingWords = {
  wording: string;
  params?: [string, string][];
};

export type DraftDiscrepancy = {
  kind: DraftDiscrepancyKind;
  field?: string | null;
  detail?: string;
  /** Which sentence explains it and the values it quotes, that sentence as
   * the backend serves it, and the language it is in. */
  words?: FindingWords | null;
  detail_words?: string | null;
  detail_words_language?: string | null;
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
  cause: "reader_unavailable" | "load_headroom_refused";
  unread_fields: string[];
  reader_error_type: string;
  failed_condition_id?: string | null;
  /** The agent service's own refusal code, such as `no_selection` for a
   * role with no picked model. */
  refusal_code?: string | null;
  /** The sentence the backend served for that refusal, and its language. */
  refusal_words?: string | null;
  refusal_words_language?: string | null;
  /** The step the backend served for putting it right, where it names one. */
  next_step?: LedgerNextStep | null;
};

export type ConfirmationBlockReason =
  | "closure_discrepancy"
  | "ambiguous_identity"
  | "unresolved_direction"
  | "contradicted_regime"
  | "undetermined_establishment"
  | "unmodelled_invoice_class"
  | "contradicted_invoice_class"
  | "unnumbered_invoice";

/** A finding the person answers before the reading may be confirmed. Its
 * id is derived from what it is, so the same reading raises the same ids. */
export type ConfirmationBlocker = {
  blocker_id: string;
  reason: ConfirmationBlockReason;
  /** The sentence the backend serves for the reason, and its language. */
  reason_words?: string | null;
  reason_words_language?: string | null;
  field?: string | null;
  detail?: string;
  /** Which sentence explains it and the values it quotes, that sentence as
   * the backend serves it, and the language it is in. */
  words?: FindingWords | null;
  detail_words?: string | null;
  detail_words_language?: string | null;
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
  /** The sentence served for each reason, in the order of `reasons`. */
  reason_words?: string[];
  reason_words_language?: string | null;
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
  /** Whether this profile may be asked to send its documents off this
   * computer to be read. Absent or false, no such read is offered; true, each
   * read still asks for its own acknowledgement. */
  off_host_read_offered?: boolean;
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
  retention_points?: string | null;
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
    likely_duplicate_invoice_id?: string | null;
    total_discrepancy?: {
      printed_total: PublicDecimal;
      recorded_total: PublicDecimal;
      difference: PublicDecimal;
    } | null;
    /** A withheld figure the document reads that the record does not hold. */
    retention_discrepancy?: {
      read_rate?: PublicDecimal | null;
      read_amount: PublicDecimal;
      recorded_rate?: PublicDecimal | null;
      recorded_amount?: PublicDecimal | null;
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

/** One page of a stored document: drawn as an image, or, for a structured
 * e-invoice, the facts its own record states. Names exactly one of the
 * evidence record or the attachment; `page` counts from 1, and `max_width`
 * sizes a drawn page and is ignored for a structured one. */
export type EvidencePageRequest = (
  | { evidence_id: string; attachment_id?: never }
  | { attachment_id: string; evidence_id?: never }
) & { page: number; max_width: number };

type EvidencePageShared = {
  profile_id: string;
  evidence_id?: string | null;
  attachment_id: string;
  page: number;
  page_count: number;
  source_sha256: string;
  file_name?: string | null;
};

/** A figure the record states, or text it states; never both. `number` is a
 * canonical decimal. */
export type EvidenceStructuredFact = { label_key: string } & (
  { text: string; number?: null } | { number: string; text?: null }
);

export type EvidenceStructuredInvoice = {
  /** A served catalogue key naming the e-invoice format. */
  title_key: string;
  facts: EvidenceStructuredFact[];
  lines: { facts: EvidenceStructuredFact[] }[];
};

export type EvidenceImagePage = EvidencePageShared & {
  media_type: "application/pdf" | "image/jpeg" | "image/png";
  width: number;
  height: number;
  /** A `data:image/png;base64,` URL; held in memory only. */
  image_data_url: string;
  structured_invoice?: null;
};

/** A structured e-invoice, shown as its one page of facts and never drawn. */
export type EvidenceStructuredPage = EvidencePageShared & {
  media_type: "application/xml";
  page_count: 1;
  width?: null;
  height?: null;
  image_data_url?: null;
  structured_invoice: EvidenceStructuredInvoice;
};

export type EvidencePageResult = EvidenceImagePage | EvidenceStructuredPage;

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
