// The request and result shapes of the ledger operations the Setup sections
// submit: rules, ratios, counterparties and model diagnostics; the own
// account, prorrata, capital goods, inventory and activity asset registers;
// and the declaration-link rebuild and reset. The port's map in ./ledger
// names each by its definition. Field names are the registered Python
// contracts' own, and a request leaves out the profile, which the host
// fills. A result is the operation's public projection; a refused one comes
// back as the refusal's detail, in the same shape.

import type { JsonObject, PublicDecimal } from "./ledger";

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
    proportionality_kind: string;
    default_ratio: string | null;
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
export type InventoryBookRow = {
  actividad_id: string;
  year: number;
  valuation_method: ValuationMethod;
  opening_stock: PublicDecimal;
  movement_count: number;
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
    | "closing_authority_invalid";
  actividad_id: string | null;
  year: number | null;
  movement_id: string | null;
  valuation_method: string | null;
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
};
export type InventoryBook = {
  actividad_id: string;
  year: number;
  valuation_method: ValuationMethod;
  opening_stock: PublicDecimal;
  period_movements: InventoryMovement[];
  closing_authority_fingerprints: JsonObject | null;
  schema_version: string;
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

// ---- Activity assets -----------------------------------------------------

/** One revision of an activity asset. Revisions are never edited: a
 * correction is a new revision that names the one it supersedes. */
export type ActivityAssetRevision = JsonObject & {
  asset_id: string;
  revision_number: number;
  supersedes_revision_id?: string | null;
};
export type ActivityAssetRefusal = {
  code: string;
  precondition_verdict: JsonObject | null;
  accelerated_da18: JsonObject | null;
};
type ActivityAssetResultBase = {
  profile_id: string;
  authority: { logical_generation: string; reader_incarnation: string };
  outcome: "succeeded" | "refused";
  refusal: ActivityAssetRefusal | null;
};
export type ActivityAssetHistory = {
  revisions: ActivityAssetRevision[];
  claims: JsonObject[];
};
export type ActivityAssetRevisionRequest = {
  revision: ActivityAssetRevision;
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
  creating_operation: string;
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
export type ClaimProjection = {
  target_casilla_id: string;
  tax_year: number;
  claim_ids: string[];
  amount: PublicDecimal;
};
export type ActivityAssetFilingResult = ActivityAssetResultBase & {
  tax_year: number | null;
  m130_period: string | null;
  filing_handoff: {
    material_m100: ClaimProjection;
    intangible_m100: ClaimProjection;
    material_m130: ClaimProjection;
    intangible_m130: ClaimProjection;
  } | null;
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
