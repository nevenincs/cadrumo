// The request and result shapes of the ledger operations the Setup sections
// submit: rules, ratios, counterparties and model diagnostics; the own
// account, prorrata, capital goods, inventory and activity asset registers;
// and the declaration-link rebuild and reset. The port's map in ./ledger
// names each by its definition. Field names are the registered Python
// contracts' own, and a request leaves out the profile, which the host
// fills. A result is the operation's public projection; a refused one comes
// back as the refusal's detail, in the same shape.

import type { JsonObject, OutputLanguage, PublicDecimal } from "./ledger";

// ---- Rules ---------------------------------------------------------------

/** One stored rule. Its id is made of its pattern, classification and
 * category, so adding the same three again changes only its order. */
export type LedgerRuleRow = {
  rule_id: string;
  /** A regular expression matched, ignoring case, anywhere in a
   * movement's description. */
  description_pattern: string;
  classification: string;
  category_id: string | null;
  /** The lower number runs first; equal ones run oldest first. */
  priority: number;
  actor: string;
  created_at: string;
};
export type LedgerRuleListResult = {
  profile_id: string;
  rules: LedgerRuleRow[];
};
export type LedgerRuleAddRequest = {
  description_pattern: string;
  classification: string;
  category_id?: string | null;
  priority?: number;
  actor?: string | null;
};
export type LedgerRuleValidation =
  "empty_pattern" | "invalid_pattern" | "category" | "invalid_command";
export type LedgerRuleAddResult = {
  profile_id: string;
  outcome: "added" | "validation_error";
  rule: LedgerRuleRow | null;
  validation_code: LedgerRuleValidation | null;
  validation_messages: string[];
  category_example: string | null;
};
/** Runs every rule over the movements still to classify, or with
 * `reaffirm` over those a rule classified as well. A dry run writes
 * nothing and names what it would classify. */
export type LedgerRuleApplyRequest = {
  reaffirm?: boolean;
  dry_run?: boolean;
  actor?: string | null;
};
export type LedgerRuleApplyResult = {
  profile_id: string;
  outcome: "dry_run" | "applied" | "validation_error";
  dry_run: true | null;
  would_match:
    | {
        transaction_id: string;
        description: string;
        matched_rule_id: string;
        classification: string;
      }[]
    | null;
  count: number | null;
  rules_evaluated: number | null;
  transactions_scanned: number | null;
  matched: number | null;
  skipped_already_classified: number | null;
  no_match: number | null;
  applied:
    | {
        transaction_id: string;
        matched_rule_id: string;
        classification: string;
      }[]
    | null;
  bucket_event_count: number;
  validation_code: LedgerRuleValidation | null;
  validation_messages: string[];
};

// ---- Business-use ratios -------------------------------------------------

export type LedgerRatiosYearRequest = { year: number };
/** The eligible categories of a year, their wording said in the language
 * the window shows. */
export type LedgerRatiosEligibleRequest = {
  year: number;
  output_language: OutputLanguage;
};
export type LedgerRatiosListResult = {
  profile_id: string;
  year: number;
  /** A mismatch with the censo withholds the ratios rather than show stale
   * ones. */
  outcome: "available" | "censo_mismatch";
  rows: { category: string; ratio: string }[];
  count: number;
};
export type LedgerRatiosEligibleResult = {
  profile_id: string;
  year: number;
  rows: {
    category: string;
    /** The registry's name for the category, in the requested language. */
    label: string;
    /** The registry's notes on how the category is deducted, in the
     * requested language. */
    notes: string;
    proportionality_kind: string;
    override_present: boolean;
  }[];
  count: number;
};
export type LedgerRatiosValidateResult = {
  profile_id: string;
  profile_present: boolean;
  eligible_count: number;
  overrides_count: number;
  missing_overrides: string[];
  findings: { category: string; kind: string; detail: string }[];
};
/** A ratio is a canonical fraction from 0 to 1. */
export type LedgerRatiosSetRequest = {
  category: string;
  ratio: string;
  year: number;
};
export type LedgerRatiosSetResult = {
  profile_id: string;
  requested_category: string;
  category: string;
  ratio: string;
  prior_ratio: string | null;
};
/** Clears a category's override; one that has none is refused, with this
 * result as its detail. */
export type LedgerRatiosUnsetRequest = { category: string };
export type LedgerRatiosUnsetResult = {
  profile_id: string;
  requested_category: string;
  category: string;
  outcome: "cleared" | "no_override";
  prior_ratio: string | null;
};

// ---- Counterparties ------------------------------------------------------

export type LedgerCounterpartyRequest = {
  action: "view" | "confirm" | "withdraw";
  tax_identifier: string;
  country_code?: string | null;
  territorial_scope?: string | null;
  identification_state?: string | null;
  evidenced_scope?: string | null;
  note?: string;
  asserted_by?: string | null;
};
export type LedgerCounterpartyResult = {
  profile_id: string;
  action: "view" | "confirm" | "withdraw";
  tax_identifier: string;
  country_code: string | null;
  evidenced_scope: string | null;
  /** What the person confirmed, where anything stands. */
  facts: {
    counterparty_key: string;
    canonical_tax_identifier: string;
    territorial_scope: string | null;
    identification_state: string | null;
    asserted_by: string;
    asserted_at: string;
    note: string;
  } | null;
  /** What the ledger answers for it now, and where each answer comes from. */
  resolution: {
    territorial_scope: string | null;
    territorial_source: string | null;
    identification_state: string | null;
    identification_source: string | null;
    confirmed_scope: string | null;
    evidenced_scope: string | null;
    contradiction_detail: string | null;
  } | null;
  recorded: boolean | null;
  withdrawn: boolean | null;
  changed: boolean;
};

// ---- Model diagnostics ---------------------------------------------------

export type LedgerLlmDiagnosticsRequest = {
  since?: string | null;
  until?: string | null;
  low_confidence_threshold: PublicDecimal;
};
export type LedgerLlmDiagnosticsResult = {
  profile_id: string;
  since: string | null;
  until: string | null;
  low_confidence_threshold: PublicDecimal;
  report: {
    usage_providers: {
      provider: string;
      calls: number;
      cache_hits: number;
      input_tokens: number;
      output_tokens: number;
      total_tokens: number;
      cost_estimate_usd: PublicDecimal | null;
      unpriced_calls: number;
    }[];
    total_calls: number;
    total_cache_hits: number;
    total_input_tokens: number;
    total_output_tokens: number;
    total_cost_estimate_usd: PublicDecimal | null;
    total_unpriced_calls: number;
    confidence_providers: {
      provider: string;
      classified_count: number;
      low_confidence_count: number;
      medium_confidence_count: number;
      high_confidence_count: number;
      min_confidence: PublicDecimal | null;
      max_confidence: PublicDecimal | null;
      mean_confidence: PublicDecimal | null;
    }[];
    total_classified: number;
    total_low_confidence: number;
  };
};

// ---- Own accounts --------------------------------------------------------

export type OwnAccountRole = "charge" | "refund";
export type OwnAccountHolding = "titular" | "cotitular";
/** An own account action without account details. Adding an account or
 * changing its details travels only as `changeOwnAccount`'s raw bytes. */
export type LedgerOwnAccountRequest =
  | { action: "list" }
  | { action: "show"; own_account_id: string }
  | { action: "update"; own_account_id: string; label: string }
  | { action: "close"; own_account_id: string; closed_on: string }
  | { action: "remove"; own_account_id: string }
  | {
      action: "designate";
      own_account_id: string;
      role: OwnAccountRole;
      modelo?: string | null;
    }
  | { action: "undesignate"; role: OwnAccountRole; modelo?: string | null };
/** An account as the product publishes it: its number masked, its bank
 * block only as whether there is one. */
export type OwnAccount = {
  own_account_id: string;
  label: string;
  holding: OwnAccountHolding;
  masked_iban: string;
  country_code: string;
  sepa_marca: string;
  has_swift_bic: boolean;
  has_bank_block: boolean;
  currency: string;
  opened_on: string | null;
  closed_on: string | null;
};
/** A designation without a modelo covers every modelo. */
export type OwnAccountDesignation = {
  role: OwnAccountRole;
  modelo: string | null;
  own_account_id: string;
};
export type LedgerOwnAccountResult = {
  profile_id: string;
  action: string;
  own_account_id: string | null;
  accounts: OwnAccount[];
  designations: OwnAccountDesignation[];
  changed: boolean;
};

// ---- Prorrata register ---------------------------------------------------

export type ProrrataEntry = {
  ejercicio: number;
  regime: string;
  especial_transition: { kind: string; evidence_reference: string } | null;
  sector_id: string | null;
  interrupted: boolean;
  provisional_percentage: PublicDecimal | null;
  provisional_provenance: string | null;
  authorisation_reference: string | null;
  definitive_percentage: PublicDecimal | null;
  definitive_volume_con_derecho: PublicDecimal | null;
  definitive_volume_sin_derecho: PublicDecimal | null;
  source_observation_ref: string | null;
  source_registry_snapshot_refs: {
    modelo: string;
    revision_id: string;
    modelo_year: number;
    period: string;
  }[];
  schema_version: string;
};
export type ProrrataSector = {
  sector_id: string;
  letra: string;
  member_activity_codes: string[];
};
export type ProrrataListResult = {
  profile_id: string;
  entries: ProrrataEntry[];
  sectors: ProrrataSector[];
  count: number;
};
export type ProrrataFinding = {
  code: string;
  blocking: boolean;
  message: string;
  source_modelo: string;
  source_filing_year: number;
  source_period: string;
  stamped_revision_id: string;
  selected_revision_id: string | null;
};
export type ProrrataRefusalReason =
  | "validation"
  | "provenance_required"
  | "provenance_not_electable"
  | "reference_required"
  | "reference_not_permitted"
  | "seed_source_absent"
  | "seed_source_blocked"
  | "seed_existing_blocked"
  | "regulated_override_standing"
  | "sector_prior_definitive_absent"
  | "sector_settlement_entry_absent";
/** What a prorrata change did; a refused one is the refusal's detail. */
export type ProrrataMutationResult = {
  operation_id: string;
  profile_id: string;
  outcome: "success" | "refused";
  entry: ProrrataEntry | null;
  sector_definition: ProrrataSector | null;
  seed_source: {
    modelo: string;
    filing_year: number;
    period: string;
    casilla_id: string;
    stamped_revision_id: string;
  } | null;
  findings: ProrrataFinding[];
  prior_ejercicio: number | null;
  count: number | null;
  refusal: {
    code: string;
    reason: ProrrataRefusalReason;
    detail: string;
    ejercicio: number | null;
    sector_id: string | null;
    findings: ProrrataFinding[];
    accepted_provenances: string[];
    existing_provenance: string | null;
  } | null;
};
export type ProrrataSeedRequest = { ejercicio: number };
export type ProrrataDeclareSectorRequest = {
  sector_id: string;
  letra: string;
  member_activity_codes?: string[];
};
/** An operator-declared provisional percentage and where it comes from. */
export type ProrrataElectionRequest = {
  ejercicio: number;
  percentage: PublicDecimal;
  provenance?: string | null;
  reference?: string | null;
  sector_id?: string | null;
};
export type ProrrataElectEspecialRequest = ProrrataElectionRequest & {
  evidence_reference?: string | null;
};
export type ProrrataRevokeEspecialRequest = ProrrataElectionRequest & {
  evidence_reference: string;
};
export type ProrrataSeedSectorRequest = {
  ejercicio: number;
  sector_id: string;
};
export type ProrrataSettleSectorRequest = {
  ejercicio: number;
  sector_id: string;
  con_derecho_volume: PublicDecimal;
  sin_derecho_volume: PublicDecimal;
};

// ---- Bienes de inversión -------------------------------------------------

export type CapitalGood = {
  identifier: string;
  description: string;
  acquisition_year: number;
  cuota_soportada: PublicDecimal;
  prorrata_inicial_pct: PublicDecimal;
  kind: string;
  art108_elegible: boolean;
  acquisition_ledger_id: string;
  prorrata_sector_id: string | null;
  disposal: { year: number; regime: string } | null;
  deduccion_efectuada: PublicDecimal;
  schema_version: string;
};
export type CapitalGoodsListResult = {
  profile_id: string;
  rows: CapitalGood[];
};
export type CapitalGoodDeclareRequest = {
  identifier: string;
  description: string;
  acquisition_year: number;
  acquisition_ledger_id: string;
  cuota_soportada: PublicDecimal;
  prorrata_inicial_pct: PublicDecimal;
  kind: string;
  art108_elegible?: boolean;
  prorrata_sector_id?: string | null;
  disposal_year?: number | null;
  disposal_regime?: string | null;
};
export type CapitalGoodDeclareResult = {
  outcome: "declared" | "refused";
  profile_id: string;
  record: CapitalGood | null;
  count: number | null;
  refusal: {
    code: string;
    reason: "validation" | "disposal_incomplete" | "duplicate_identifier";
    missing: "year" | "regime" | null;
    identifier: string | null;
  } | null;
};

// ---- Inventory -----------------------------------------------------------

export type ValuationMethod = "fifo" | "pmp" | "coste_medio";
export type InventoryMovementKind = "opening" | "purchase" | "cogs" | "count";
/** The kinds of proof a purchase or an extra cost can rest on, and the two
 * checks a purchase states it made. */
export type InventoryProofKind =
  | "purchase_invoice"
  | "transport_document"
  | "insurance_document"
  | "customs_declaration"
  | "contract"
  | "other_acquisition_evidence"
  | "attributable_cost_review"
  | "iva_recoverability_review";
export type InventoryCostKind =
  | "freight"
  | "insurance"
  | "customs_duty"
  | "handling"
  | "professional_fee"
  | "other_directly_attributable";
export type InventoryRetirementReason =
  "created_in_error" | "activity_ceased" | "no_stock_held";
export type InventoryBookRow = {
  actividad_id: string;
  year: number;
  valuation_method: ValuationMethod;
  opening_stock: PublicDecimal;
  movement_count: number;
  /** The name given to the book, where one has been. */
  label?: string | null;
  retired?: boolean;
  retirement_reason?: InventoryRetirementReason | null;
  correction_count?: number;
};
export type InventoryListResult = {
  profile_id: string;
  rows: InventoryBookRow[];
};
export type InventoryRefusal = {
  code: string;
  reason:
    | "activity_conflict"
    | "activity_not_found"
    | "invalid_valuation_method"
    | "duplicate_movement_id"
    | "inventory_validation"
    | "closing_authority_conflict"
    | "closing_authority_invalid"
    | "closing_authority_recorded"
    | "later_closing_authority_recorded"
    | "inventory_retired"
    | "inventory_already_retired"
    | "inventory_not_retired"
    | "movement_not_found"
    | "movement_already_superseded"
    | "movement_outside_year"
    | "stock_would_go_negative"
    | "count_would_raise_stock"
    | "correction_id_conflict"
    | "correction_changes_nothing";
  actividad_id: string | null;
  year: number | null;
  movement_id: string | null;
  valuation_method: string | null;
  reason_key?: string | null;
  reason_facts?: ReasonFact[];
};
/** The totals of a purchase's cost, as a movement shows them. */
export type InventoryAcquisitionSummary = {
  consideration_excluding_iva: PublicDecimal;
  directly_attributable_cost_total: PublicDecimal;
  nonrecoverable_iva_included: PublicDecimal;
  recoverable_iva_excluded: PublicDecimal;
  total_acquisition_cost: PublicDecimal;
  component_count: number;
  evidence_count: number;
  complete: true;
};
export type InventoryMovement = {
  movement_id: string;
  movement_date: string;
  kind: InventoryMovementKind;
  sku: string;
  quantity: PublicDecimal;
  unit_cost: PublicDecimal | null;
  taxable_base: PublicDecimal | null;
  iva_rate: PublicDecimal;
  iva_amount: PublicDecimal | null;
  deductible_iva_ratio: PublicDecimal;
  acquisition_cost?: InventoryAcquisitionSummary | null;
};
export type InventoryCorrectionReason =
  | "keying_error"
  | "source_document_corrected"
  | "duplicate_entry"
  | "operation_did_not_occur";
export type InventoryHistoryKind =
  | "described"
  | "opening_corrected"
  | "movement_corrected"
  | "movement_reversed"
  | "retired"
  | "restored";
export type InventoryDescriptor = {
  label: string;
  description: string | null;
};
/** One change kept with what it displaced. */
export type InventoryHistoryEntry = {
  correction_id: string;
  kind: InventoryHistoryKind;
  recorded_at: string;
  actor: string;
  correction_reason: InventoryCorrectionReason | null;
  retirement_reason: InventoryRetirementReason | null;
  superseded_movement: InventoryMovement | null;
  replacement_movement_id: string | null;
  prior_opening_stock: PublicDecimal | null;
  prior_valuation_method: ValuationMethod | null;
  prior_descriptor: InventoryDescriptor | null;
};
export type InventoryBook = {
  actividad_id: string;
  year: number;
  valuation_method: ValuationMethod;
  opening_stock: PublicDecimal;
  /** The effective movements: what a correction or a reversal took out is
   * not here but in the history. */
  period_movements: InventoryMovement[];
  closing_authority_fingerprints: JsonObject | null;
  schema_version: string;
  descriptor?: InventoryDescriptor | null;
  retired?: boolean;
  retirement_reason?: InventoryRetirementReason | null;
  history?: InventoryHistoryEntry[];
};
export type InventoryCreateRequest = {
  actividad_id: string;
  year: number;
  valuation_method: string;
  opening_stock?: PublicDecimal;
};
export type InventoryCreateResult = {
  outcome: "created" | "refused";
  profile_id: string;
  ledger: InventoryBook | null;
  bucket_event_ids: string[];
  refusal: InventoryRefusal | null;
};
export type InventoryMovementAddRequest = {
  actividad_id: string;
  year: number;
  movement_id: string;
  movement_date: string;
  kind: InventoryMovementKind;
  quantity: PublicDecimal;
  unit_cost?: PublicDecimal | null;
  taxable_base?: PublicDecimal | null;
  /** What a purchase cost, and what proves it. Only a purchase states it,
   * and a purchase states no unit cost or taxable base beside it. */
  acquisition_cost?: InventoryAcquisitionCostRequest | null;
};
/** A named piece of proof: a fingerprint of the file the person attached,
 * under a reference minted for it. */
export type InventoryProof = {
  reference: { reference: string };
  evidence_kind: InventoryProofKind;
  content_digest: string;
};
/** A cost that goes into the purchase besides its price. */
export type InventoryCostComponent = {
  component_id: string;
  kind: InventoryCostKind;
  taxable_base: PublicDecimal;
  iva_amount: PublicDecimal;
  deductible_iva_ratio: PublicDecimal;
  evidence_references: { reference: string }[];
};
export type InventoryAcquisitionCostRequest = {
  consideration_excluding_iva: PublicDecimal;
  consideration_iva_amount: PublicDecimal;
  consideration_deductible_iva_ratio: PublicDecimal;
  attributable_cost_components: InventoryCostComponent[];
  evidence: InventoryProof[];
  completeness: {
    consideration_evidence: { reference: string };
    attributable_cost_review_evidence: { reference: string };
    iva_recoverability_review_evidence: { reference: string };
  };
  directly_attributable_cost_total: PublicDecimal;
  nonrecoverable_iva_included: PublicDecimal;
  recoverable_iva_excluded: PublicDecimal;
  total_acquisition_cost: PublicDecimal;
};
export type InventoryMovementAddResult = {
  outcome: "added" | "refused";
  profile_id: string;
  ledger: InventoryBook | null;
  refusal: InventoryRefusal | null;
};
export type InventoryBookRequest = { actividad_id: string; year: number };
/** A preview: nothing is recorded. */
export type InventoryValuationResult = {
  outcome: "previewed" | "refused";
  preview: {
    profile_id: string;
    actividad_id: string;
    year: number;
    valuation_method: ValuationMethod;
    derived_closing_value: PublicDecimal;
    cogs: PublicDecimal;
    bucket_event_ids: string[];
  } | null;
  refusal: InventoryRefusal | null;
};
/** The closing authority's record: its decision, an optional physical
 * count and the link to the prior year's closing, as one document. */
export type InventoryClosingAuthorityRequest = {
  actividad_id: string;
  year: number;
  authority_record: JsonObject;
};
export type InventoryClosingAuthorityResult = {
  outcome: "recorded" | "refused";
  record: {
    profile_id: string;
    actividad_id: string;
    year: number;
    authority_record_fingerprint: string;
    decision_fingerprint: string;
    physical_observation_fingerprint: string | null;
    prior_closing_link_fingerprint: string;
    changed: boolean;
  } | null;
  refusal: InventoryRefusal | null;
};

/** One change to a book. Sent again under the same reference it changes
 * nothing: the reference is minted when the form opens. */
export type InventoryChangeRequest = InventoryBookRequest & {
  correction_id: string;
};
export type InventoryInspectResult = {
  outcome: "found" | "refused";
  profile_id: string;
  ledger: InventoryBook | null;
  refusal: InventoryRefusal | null;
};
export type InventoryDescribeRequest = InventoryChangeRequest & {
  label: string;
  description: string | null;
};
export type InventoryCorrectRequest = InventoryChangeRequest & {
  reason: InventoryCorrectionReason;
  opening_stock: PublicDecimal | null;
  valuation_method: ValuationMethod | null;
};
export type InventoryMovementCorrectRequest = InventoryChangeRequest & {
  target_movement_id: string;
  reason: InventoryCorrectionReason;
  movement_id: string;
  movement_date: string;
  kind: InventoryMovementKind;
  quantity: PublicDecimal;
  unit_cost?: PublicDecimal | null;
  taxable_base?: PublicDecimal | null;
  acquisition_cost?: InventoryAcquisitionCostRequest | null;
};
export type InventoryMovementReverseRequest = InventoryChangeRequest & {
  target_movement_id: string;
  reason: InventoryCorrectionReason;
};
export type InventoryRetireRequest = InventoryChangeRequest & {
  reason: InventoryRetirementReason;
};
export type InventoryRestoreRequest = InventoryChangeRequest;
/** A change applied, or found already applied under the same reference. */
export type InventoryChangeResult = {
  outcome: "applied" | "replayed" | "refused";
  profile_id: string;
  ledger: InventoryBook | null;
  bucket_event_ids: string[];
  refusal: InventoryRefusal | null;
};

// ---- Activity assets -----------------------------------------------------

/** One revision of an activity asset. Revisions are never edited: a
 * correction is a new revision that names the one it supersedes. */
export type ActivityAssetRevision = JsonObject & {
  asset_id: string;
  revision_number: number;
  supersedes_revision_id?: string | null;
};
/** One fact that fills a reason's sentence. */
export type ReasonFact = { key: string; value: string };
/** Why the backend refused: a coarse code, and the catalogue key that says
 * why with the facts that fill it in. */
export type ActivityAssetRefusal = {
  code: string;
  /** Holds `missing_field_keys` where fields are still to state. */
  precondition_verdict: JsonObject | null;
  accelerated_da18: JsonObject | null;
  reason_key: string | null;
  reason_facts: ReasonFact[];
};
/** An amount the backend states or does not. Null is unknown and never
 * zero; a recorded zero is `{ decimal: "0.00" }`. */
export type Amount = PublicDecimal | null;
export type ActivityAssetResultBase = {
  profile_id: string;
  authority: { logical_generation: string; reader_incarnation: string };
  outcome: "succeeded" | "refused";
  refusal: ActivityAssetRefusal | null;
};
export type ActivityAssetHistory = {
  revisions: ActivityAssetRevision[];
  claims: JsonObject[];
  descriptors?: JsonObject[];
  events?: JsonObject[];
};
/** A recorded claim a correction replaces; the backend works out the new
 * figure, and a free method states the amount it asks for. */
export type ActivityAssetSupersedingClaim = {
  supersedes_claim_id: string;
  requested_free_amount: PublicDecimal | null;
};
export type ActivityAssetCreateRequest = {
  revision: ActivityAssetRevision;
  descriptor: DescriptorFacts;
};
export type ActivityAssetCorrectRequest = {
  revision: ActivityAssetRevision;
  superseding_claims: ActivityAssetSupersedingClaim[];
};
export type ActivityAssetChangeResult = ActivityAssetResultBase & {
  history: ActivityAssetHistory | null;
};
export type ActivityAssetInspectRequest = { asset_id: string };
export type ActivityAssetInspectResult = ActivityAssetResultBase & {
  asset_id: string | null;
  revisions: { revision: ActivityAssetRevision; revision_id: string }[] | null;
};
export type ActivityAssetForecastRequest = {
  asset_id: string;
  covered_from: string;
  covered_until: string;
  requested_free_amount?: PublicDecimal | null;
  supersedes_claim_id?: string | null;
};
/** A scheduled charge: a forecast records nothing until it is claimed. */
export type ActivityAssetForecast = JsonObject & {
  asset_id: string;
  asset_revision_id: string;
  tax_year: number;
  covered_from: string;
  covered_until: string;
  service_days: number;
  calendar_days: number;
  amount: PublicDecimal;
};
export type ActivityAssetForecastResult = ActivityAssetResultBase & {
  forecast: ActivityAssetForecast | null;
};
export type ActivityAssetClaimRequest = {
  forecast: ActivityAssetForecast;
  /** The claim this one replaces, in the same write. */
  supersedes_claim_id: string | null;
};
export type ActivityAssetClaimResult = ActivityAssetResultBase & {
  claim_result: {
    history: ActivityAssetHistory;
    claim: JsonObject;
    reused_existing_claim: boolean;
  } | null;
  claim_id: string | null;
};
export type ActivityAssetFilingRequest = {
  tax_year: number;
  m130_period: string;
};
/** What the effective claims of a year add up to in a Modelo 100 casilla. */
export type ClaimProjection = {
  target_casilla_id: string;
  tax_year: number;
  claim_ids: string[];
  amount: PublicDecimal;
};
/** One amount behind Modelo 130 casilla 02: a recorded claim, or else the
 * element's schedule. */
export type M130Contribution = {
  asset_id: string;
  amount: PublicDecimal;
  claim_id: string | null;
  schedule_fingerprint: string | null;
};
/** The accrual of one asset kind for Modelo 130. Elements it could not work
 * out are named: their share is missing from `amount`, not zero. */
export type M130Projection = {
  target_casilla_id: string;
  tax_year: number;
  amount: PublicDecimal;
  contributions: M130Contribution[];
  unavailable_asset_ids: string[];
};
export type ActivityAssetFilingResult = ActivityAssetResultBase & {
  tax_year: number | null;
  m130_period: string | null;
  filing_handoff: {
    material_m100: ClaimProjection;
    intangible_m100: ClaimProjection;
    material_m130: M130Projection;
    intangible_m130: M130Projection;
  } | null;
};

// ---- The element list ----------------------------------------------------

/** How many years or claims of an element need a person's attention, by kind. */
export type AssetCounts = {
  missing: number;
  incomplete: number;
  conflict: number;
  stale: number;
};

export type AssetListRow = {
  asset_id: string;
  /** From the element's latest descriptor; null until one is recorded. */
  name: string | null;
  serial_number: string | null;
  asset_kind: string;
  state: string;
  in_service_date: string;
  method: string;
  revision_number: number;
  basis: PublicDecimal;
  /** The opening amount plus the effective claims; null where the opening
   * history is not known. */
  accumulated: Amount;
  /** The basis left to amortize; null where `accumulated` is. */
  pending: Amount;
  findings: AssetCounts;
  /** The tax years the element can be read in. */
  years: number[];
  /** The later service years, whose figures are an estimate until the
   * registry publishes their tables. */
  projected_years: number[];
  /** The baja the element's current revision records; null while it has none. */
  disposal: ListDisposal | null;
};

export type ListDisposal = {
  disposal_date: string;
  reason: string;
  /** The catalogue key that words `reason`. */
  reason_key: string;
};

/** `years` are the register's: every year of any element, in order. */
export type AssetListResult = { rows: AssetListRow[] | null; years: number[] };

// ---- The amortization plan -----------------------------------------------

/** The Modelo 100 edition a year stands on. */
export type PlanEdition = {
  revision_id: string;
  authored_filing_year: number;
  /** Rates carried forward from the nearest authored edition: they serve a
   * forecast and Modelo 130, not a filed Modelo 100. */
  projected: boolean;
};

export type PlanClaim = {
  claim_id: string;
  amount: PublicDecimal;
  covered_from: string;
  covered_until: string;
  /** The last day the claim covers, which is what a reader sees as its end;
   * `covered_until` is the exclusive boundary the schedule computes with. */
  covered_through: string;
  effective: boolean;
  superseded_by: string | null;
  revision_id: string;
};

export type ClaimableInterval = {
  covered_from: string;
  covered_until: string;
  /** The last day the interval covers, as `PlanClaim.covered_through`. */
  covered_through: string;
};

export type PlanRow = {
  /** Minimum amortization from entry to this year's end, which reduces cost at
   * a baja; `minimum_complete` is false where an earlier year has none. */
  minimum_through: Amount;
  minimum_complete: boolean;
  tax_year: number;
  method: string;
  coefficient: Amount;
  planned: Amount;
  /** Why `planned` is null: the typed absence, and the reason when the
   * backend gives one. */
  absence: string | null;
  absence_reason_key: string | null;
  absence_reason_facts: ReasonFact[];
  claimed: PublicDecimal;
  claim_state: string;
  claimable_intervals: ClaimableInterval[];
  claimable_refusal_key: string | null;
  edition: PlanEdition | null;
  service_days: number | null;
  calendar_days: number | null;
  claims: PlanClaim[];
};

/** What the registry allows the element's election. A table method carries
 * its class and corridor; any other states the limit it has instead and why. */
export type LegalCitation = { text: string; permalink: string };
export type ElectionLimits = {
  class_key: string | null;
  /** The class's official name, as served; null where there is no class. */
  class_label: string | null;
  maximum_coefficient: Amount;
  minimum_coefficient: Amount;
  maximum_period_years: Amount;
  maximum_period_ends_on: string | null;
  /** The provisions behind the figures, each with its official link. */
  legal_citations: LegalCitation[];
  /** False where a cited provision could not be resolved, so the list is
   * partial. */
  legal_citations_complete: boolean;
  not_table_bound: string | null;
  unavailable_reason_key: string | null;
};

/** A warning on the plan that changes no figure and refuses nothing; the
 * backend words it by the catalogue key it serves. */
export type PlanAdvisory = { kind: string; label_key: string };

export type PlanResult = {
  asset_id: string | null;
  rows: PlanRow[] | null;
  limits: ElectionLimits | null;
  advisories: PlanAdvisory[];
};

// ---- The append-only timeline --------------------------------------------

export type TimelineChange = {
  /** The record's field as the backend names it, a dotted path. */
  field: string;
  before: string | null;
  /** The catalogue keys that word `before` and `after` where the field
   * carries a token. */
  before_key: string | null;
  after_key: string | null;
  after: string | null;
  /** The text that words `before` and `after` where the field carries a share
   * or a table class; null for any other field. */
  before_label: string | null;
  after_label: string | null;
};

export type TimelineClaimUse = {
  used_by: string[];
  matches_current_schedule: boolean;
  stale_reason: string | null;
};

export type TimelineEvent = {
  sequence: number;
  /** Null for a record written before time was kept. */
  recorded_at: string | null;
  kind: string;
  asset_id: string;
  /** The record's identity: a claim's id for a claim event. */
  record_id: string;
  effect_date: string | null;
  /** The operation that wrote the record; free text, null when none stated. */
  origin: string | null;
  changes: TimelineChange[];
  affects_calculation: boolean;
  claim: TimelineClaimUse | null;
};

export type TimelineResult = {
  asset_id: string | null;
  events: TimelineEvent[] | null;
};

// ---- Form options and purchases ------------------------------------------

/** One table class with its coefficient corridor. */
export type TableGroup = {
  class_key: string;
  /** The class's official name, as served. */
  class_label: string;
  maximum_coefficient: PublicDecimal;
  minimum_coefficient: PublicDecimal;
  maximum_period_years: PublicDecimal;
};

/** What the registry admits for one asset kind and tax year. */
/** One fact an election of a method states, as the options serve it. */
export type MethodFact = {
  /** From the election down to the fact. */
  path: string[];
  kind: string;
  required: boolean;
  /** Required once the fact's optional group is stated. */
  required_with_group: boolean;
  token_family: string | null;
  tokens: string[];
};

export type FormOptions = {
  tax_year: number;
  asset_kind: string;
  regime: string;
  edition: PlanEdition;
  methods: string[];
  table_groups: TableGroup[];
  acquisition_shapes: string[];
  declared_activities: string[];
  method_facts: { method: string; facts: MethodFact[] }[];
};

/** A ledger payment an element could name as its acquisition. What the
 * ledger does not know is null, never zero. */
export type AcquisitionCandidate = {
  transaction_id: string;
  booked_date: string;
  description: string;
  amount: PublicDecimal;
  currency: string;
  paid_in_euro: Amount;
  taxable_base: Amount;
  iva_amount: Amount;
  non_deductible_iva_state: string;
  non_deductible_iva_state_key: string;
  non_deductible_iva: Amount;
  invoice_evidence_id: string | null;
  evidence_fingerprint: string | null;
};

/** What the operator states about an element, none of it a tax fact. */
export type DescriptorFacts = {
  name: string;
  serial_number: string | null;
  description: string | null;
  document_kind: string | null;
  document_number: string | null;
  supplier_name: string | null;
  supplier_tax_id: string | null;
};

// ---- A baja ----------------------------------------------------------------

/** What a baja states. The disposal date is the last day of service; the
 * backend judges the rest of it by the reason. */
export type DisposalFacts = {
  disposal_date: string;
  reason: string;
  proceeds: PublicDecimal;
  transmission_costs: PublicDecimal;
  market_value: PublicDecimal | null;
  prior_free_depreciation_regime: string | null;
  later_affectation_on: string | null;
};

export type DisposalFinding = {
  kind: string;
  /** The catalogue key that words the finding. */
  label_key: string;
  tax_year: number | null;
  effect_on_cost: Amount;
};

export type DisposalYear = {
  tax_year: number;
  claims: PublicDecimal;
  deducted_through: PublicDecimal;
  /** Null from the first year no edition covers. */
  minimum_through: Amount;
  reduction_through: PublicDecimal;
};

/** The figures of one baja, as the backend works them out. A figure the reason
 * does not compute is null. */
export type DisposalCalculation = {
  disposal_date: string;
  reason: string;
  acquisition_value: PublicDecimal;
  deducted: PublicDecimal;
  /** Null where a year in service has no edition, so it is not worked out. */
  minimum: Amount;
  reduction: PublicDecimal;
  excess: PublicDecimal;
  net_value: PublicDecimal;
  transmission_value: Amount;
  transmission_costs: Amount;
  result: Amount;
  route_changed_by_later_affectation: boolean;
  years: DisposalYear[];
  findings: DisposalFinding[];
};

// ---- The register's reads and the baja, in the shapes the tab sends ---------

export type ActivityAssetListResult = ActivityAssetResultBase & AssetListResult;
export type ActivityAssetPlanRequest = { asset_id: string };
export type ActivityAssetPlanResult = ActivityAssetResultBase & PlanResult;
export type ActivityAssetTimelineRequest = { asset_id: string };
export type ActivityAssetTimelineResult = ActivityAssetResultBase &
  TimelineResult;
export type ActivityAssetFormOptionsRequest = {
  asset_kind: string;
  tax_year: number;
};
export type ActivityAssetFormOptionsResult = ActivityAssetResultBase & {
  options: FormOptions | null;
};
export type ActivityAssetAcquisitionCandidatesResult =
  ActivityAssetResultBase & { candidates: AcquisitionCandidate[] | null };
export type ActivityAssetDescribeRequest = {
  asset_id: string;
  descriptor: DescriptorFacts;
};
export type ActivityAssetDisposeRequest = {
  asset_id: string;
  disposal: DisposalFacts;
};
export type ActivityAssetDisposalCalculateRequest = {
  asset_id: string;
  /** Null reads the recorded baja; a stated one is a preview. */
  disposal: DisposalFacts | null;
};
export type ActivityAssetDisposalCalculateResult = ActivityAssetResultBase & {
  asset_id: string | null;
  calculation: DisposalCalculation | null;
};

// ---- Declaration links and reset ----------------------------------------------------

export type LedgerParticipationRebuildResult = {
  profile_id: string;
  transaction_count: number;
  participation_count: number;
  revision_count: number;
  stale_removed_count: number;
};
export type LedgerResetRequest = {
  reason?: string;
  dry_run?: boolean;
  actor?: string | null;
};
/** A finalized or draft declaration revision that cites movements. */
export type LedgerRemovalBlocker = {
  work_unit_id: string;
  calculation_revision_id: string;
  revision_state: string;
  modelo: string;
  filing_year: number;
  period: string;
};
export type LedgerResetResult = {
  profile_id: string;
  report: {
    bucket_id: string;
    dry_run: boolean;
    actor: string;
    reason: string;
    cascaded_purchase_invoice_evidence_ids: string[];
    cascaded_attachment_ids: string[];
    /** Revisions a reset cannot pass: it is refused while there are any. */
    blocking_modelo_references: LedgerRemovalBlocker[];
    stale_draft_revision_references: LedgerRemovalBlocker[];
    bucket_event_ids: string[];
    removed_transaction_ids: string[];
    reset: boolean;
  };
};
