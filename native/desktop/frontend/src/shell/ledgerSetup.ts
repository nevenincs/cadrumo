// The request and result shapes of the ledger operations the Setup sections
// submit for the inventory and activity asset registers, the entry options,
// and the declaration-link rebuild and reset. The port's map in ./ledger
// names each by its definition. Field names are the registered Python
// contracts' own, and a request leaves out the profile, which the host
// fills. A result is the operation's public projection; a refused one comes
// back as the refusal's detail, in the same shape.

import type {
  FileToken,
  JsonObject,
  OutputLanguage,
  PublicDecimal,
  PublicPeriod,
} from "./ledger";
import type { PurchaseLedgerRow } from "./ledgerContract";

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
  advisories?: InventoryAdvisory[];
};

/** Something the person should know about a book: the sentence's key in the
 * backend's catalogue, filled in with the year. */
export type InventoryAdvisory = {
  code: string;
  key: string;
  year: number;
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
    | "correction_changes_nothing"
    | "evidence_file_not_admitted";
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
  /** What a purchase rests on, served by the inspect read alone. */
  acquisition_detail?: InventoryAcquisitionDetail | null;
};

export type InventoryAcquisitionDetail = {
  consideration_iva_amount: PublicDecimal;
  consideration_deductible_iva_ratio: PublicDecimal;
  components: {
    component_id: string;
    kind: InventoryCostKind;
    taxable_base: PublicDecimal;
    iva_amount: PublicDecimal;
    deductible_iva_ratio: PublicDecimal;
    evidence_references: string[];
  }[];
  documents: {
    reference: string;
    evidence_kind: InventoryProofKind;
    content_digest: string;
    /** The file's bare name, where the book knows it. */
    file_name?: string | null;
  }[];
  consideration_evidence: string;
  attributable_cost_review_evidence: string;
  iva_recoverability_review_evidence: string;
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
  advisories?: InventoryAdvisory[];
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
  /** One of the movement kinds the options read serves. */
  kind: string;
  quantity: PublicDecimal;
  unit_cost?: PublicDecimal | null;
  taxable_base?: PublicDecimal | null;
  /** What a purchase cost, and what proves it. Only a purchase states it,
   * and a purchase states no unit cost or taxable base beside it. */
  acquisition_cost?: InventoryAcquisitionCostRequest | null;
  /** What the purchase states about the ledger transaction that books it. */
  ledger_row?: PurchaseLedgerRow;
  /** The transaction a claimed purchase books, named exactly when claimed. */
  claimed_transaction_id?: string | null;
};

/** A named piece of proof: a fingerprint of the file the person attached,
 * under a reference minted for it. */
export type InventoryProof = {
  reference: { reference: string };
  evidence_kind: string;
  content_digest: string;
};

/** A cost that goes into the purchase besides its price. */
export type InventoryCostComponent = {
  component_id: string;
  kind: string;
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
  /** Left out, the backend adds these up from the figures above. */
  directly_attributable_cost_total?: PublicDecimal;
  nonrecoverable_iva_included?: PublicDecimal;
  recoverable_iva_excluded?: PublicDecimal;
  total_acquisition_cost?: PublicDecimal;
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

/** The words the options read serves for each closed choice a form offers. */
export type InventoryOptionsResult = {
  profile_id: string;
  families: {
    family: string;
    options: {
      value: string;
      label_key: string;
      role?: string | null;
      /** The key of the sentence saying what choosing the value does, served
       * for the families that have one. */
      effect_key?: string | null;
    }[];
  }[];
};

/** What the entry options read is asked for besides the vocabularies: the
 * periods of one year (the year of the reference day when none is named), the
 * period that holds a span, and the periods that hold each of some days. */
export type LedgerEntryOptionsRequest = {
  /** The language the period names are said in. */
  output_language?: OutputLanguage;
  periods?: {
    year?: number;
    covering?: { first_day: string; last_day: string };
    days?: string[];
  };
};

/** The cadence of a served period. */
export type LedgerServedPeriodKind = "annual" | "quarterly" | "monthly";

/** One selectable period of a year as the backend serves it: its days, the
 * periods either side of it across year ends (null where there is none), and
 * its name and its label with the year, said in `name_words_language`. */
export type LedgerServedPeriod = {
  period: PublicPeriod;
  kind: LedgerServedPeriodKind;
  first_day: string;
  last_day: string;
  previous: PublicPeriod | null;
  next: PublicPeriod | null;
  name_words: string;
  name_words_language: OutputLanguage;
  label_words: string;
  label_words_language: OutputLanguage;
};

/** The year, the quarter and the month that hold one day. */
export type LedgerServedDay = {
  day: string;
  annual: PublicPeriod;
  quarterly: PublicPeriod;
  monthly: PublicPeriod;
};

/** The periods of one year, the periods of the reference day (today in Spain
 * when none was given) and what else was asked. */
export type LedgerServedPeriods = {
  year: number;
  /** The code that names the whole year. */
  annual_code: string;
  periods: LedgerServedPeriod[];
  containing: LedgerServedDay;
  /** The shortest period that holds the span asked, or null where none does,
   * as when it crosses a year end. */
  covering?: {
    first_day: string;
    last_day: string;
    period: PublicPeriod | null;
  } | null;
  days?: LedgerServedDay[];
};

/** What a ledger entry form offers. A code with no key is named by the window
 * with `Intl`; a code's list says what is known, not what is allowed. A
 * `group` is the family a value is filed under, as the spending categories
 * are. */
export type LedgerEntryOptionsResult = {
  profile_id: string;
  /** The ledger's functional currency: what a new movement is offered when
   * the profile's own accounts name none. */
  default_currency: string;
  families: {
    family: string;
    options: {
      value: string;
      label_key: string | null;
      group?: string | null;
    }[];
  }[];
  /** What each classification takes, one row per classification in the
   * backend's order. */
  classifications: LedgerEntryClassification[];
  limits: LedgerEntryLimits;
  periods: LedgerServedPeriods;
};

/** What one classification takes, each flag the verdict of the predicate the
 * backend's writers enforce it with, except the advisory one. */
export type LedgerEntryClassification = {
  classification: string;
  /** A movement so classified carries a business share, and the ledger
   * refuses one that does not. */
  takes_business_share: boolean;
  /** A movement so classified carries a usage ratio. */
  takes_usage_ratio: boolean;
  /** A movement so classified carries business figures: a taxable base and
   * the like. */
  carries_business_figures: boolean;
  /** A movement so classified keeps the spending category it names. */
  keeps_category: boolean;
  /** A rule deciding it may name a spending category, and the ledger
   * refuses a category on any other rule. */
  rule_may_name_category: boolean;
  /** Advice, not a refusal: a split part so classified is asked for a
   * spending category, and no write refuses it without one, though
   * readiness holds an expense row that has none. */
  split_part_requires_category: boolean;
};

/** The limits an entry form holds typed text to; `shell/ledgerLimits` holds
 * them for the page. Figures are decimal text, unread here. */
export type LedgerEntryLimits = {
  decimal_text_max: number;
  two_way_decimal: string;
  decimal_rules: {
    rule: "amount" | "tax_amount" | "quantity" | "unit_price";
    decimals: number;
    zero: boolean;
  }[];
  percent_decimals: number;
  percent_points_max: string;
  percent_fraction_max: string;
  percent_bare_fraction_ceiling: string;
  document_percent_fields: {
    field: string;
    unit: "points" | "fraction";
  }[];
  rule_pattern_max: number;
  /** The shape of a payment id once trimmed and lowercased. */
  payment_id_pattern: string;
  text_limits: { name: TextLimitName; max: number }[];
};

/** What a served text limit bounds: the characters one entry takes, or, for
 * `split_parts`, the most parts one split makes. */
export type TextLimitName =
  | "split_parts"
  | "split_part_description"
  | "entry_text"
  | "group_label"
  | "classify_token"
  | "usage_ratio_id"
  | "event_payload_value"
  | "evidence_label"
  | "evidence_note"
  | "own_account_iban"
  | "own_account_swift_bic"
  | "counterparty_tax_id"
  | "counterparty_note"
  | "counterparty_asserted_by"
  | "confirm_label"
  | "confirm_note"
  | "own_account_label"
  | "own_account_currency"
  | "invoice_counterparty_name";

/** A document the person chose, now kept: what a purchase or a closing
 * value names it by. */
export type InventoryEvidenceAddRequest = { source_path: FileToken };

export type InventoryEvidenceAddResult = {
  outcome: "stored" | "refused";
  profile_id: string;
  reference?: string | null;
  content_digest?: string | null;
  /** Why the file was not kept, in the backend's own sentence. */
  refusal?: InventoryRefusal | null;
};

/** A document a closing value rests on. */
export type InventoryClosingDocument = {
  reference: { reference: string };
  role: string;
  content_digest: string;
};

export type InventoryClosingValueRequest = {
  actividad_id: string;
  year: number;
  facts: {
    decision_id: string;
    authority: string;
    reason: string;
    decision_evidence: InventoryClosingDocument[];
    physical_count?: {
      observed_on: string;
      closing_value: PublicDecimal;
      valuation_basis: string;
      evidence: InventoryClosingDocument[];
    } | null;
    prior_evidence: {
      reference: { reference: string };
      content_digest: string;
    }[];
  };
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
  reason: string;
  opening_stock: PublicDecimal | null;
  valuation_method: string | null;
};

export type InventoryMovementCorrectRequest = InventoryChangeRequest & {
  target_movement_id: string;
  reason: string;
  movement_id: string;
  movement_date: string;
  kind: string;
  quantity: PublicDecimal;
  unit_cost?: PublicDecimal | null;
  taxable_base?: PublicDecimal | null;
  acquisition_cost?: InventoryAcquisitionCostRequest | null;
};

export type InventoryMovementReverseRequest = InventoryChangeRequest & {
  target_movement_id: string;
  reason: string;
};

/** States which ledger transaction books one purchase, that none does, or
 * clears the statement; a transaction is named exactly when it is claimed. */
export type InventoryMovementClaimRequest = InventoryChangeRequest & {
  movement_id: string;
  ledger_row: PurchaseLedgerRow;
  claimed_transaction_id?: string | null;
};

export type InventoryRetireRequest = InventoryChangeRequest & {
  reason: string;
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

/** What a reason fact's value is, so a screen draws it by type: a date is an
 * ISO date, an amount a plain decimal, a percent a fraction, a count a whole
 * number such as a tax year, and a text is shown as it stands. */
export type ReasonFactKind = "text" | "date" | "amount" | "percent" | "count";

/** One fact that fills a reason's sentence. */
export type ReasonFact = { key: string; value: string; kind: ReasonFactKind };

/** Why the backend refused: a coarse code, and the catalogue key that says
 * why with the facts that fill it in. */
export type ActivityAssetRefusal = {
  code: string;
  /** Holds `missing_field_keys` where fields are still to state. */
  precondition_verdict: JsonObject | null;
  accelerated_da18: JsonObject | null;
  reason_key: string | null;
  reason_facts: ReasonFact[];
  /** The finished sentence for the refusal, said in
   * `refusal_words_language`; null where the backend has none to say. */
  refusal_words?: string | null;
  refusal_words_language?: OutputLanguage | null;
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

/** The revision a correction states: the one it supersedes, whole, with what
 * the person changed. Its number is left out, since the register numbers it;
 * its baja is always stated, another baja to replace the recorded one and null
 * to remove it. */
export type ActivityAssetCorrection = JsonObject & {
  asset_id: string;
  supersedes_revision_id: string;
  disposal: JsonObject | null;
};

export type ActivityAssetCorrectRequest = {
  revision: ActivityAssetCorrection;
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
  /** The last day the span covers, inclusive. */
  covered_through: string;
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
  /** The last day the span covers, for display. */
  covered_through?: string;
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
  /** The language the boxes are named in. */
  output_language: OutputLanguage;
  /** The Modelo 130 quarter to project; left out, the Modelo 100 boxes alone
   * are stated. */
  m130_period?: string;
};

/** What the effective claims of a year add up to in a Modelo 100 casilla. */
export type ClaimProjection = {
  target_casilla_id: string;
  /** The box in the filer's words; null where none is named. */
  box_name: string | null;
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
 * out are named: their share is missing from `amount`, not zero. Elements
 * whose method leaves an amount to the taxpayer, and those of an agricultural
 * activity, are named too, and are not in `amount` either. */
export type M130Projection = {
  /** Which kind of element this accrual states; both kinds share the one
   * box, so the name tells the two rows apart. */
  asset_kind: string;
  target_casilla_id: string;
  /** The box in the filer's words with the asset kind; null where none is
   * named. */
  box_name: string | null;
  tax_year: number;
  amount: PublicDecimal;
  contributions: M130Contribution[];
  unavailable_asset_ids: string[];
  free_gap_asset_ids: string[];
  agrarian_excluded_asset_ids: string[];
  /** The sentence saying the amount leaves out the elements that could not
   * be worked out; present exactly when some could not. */
  partial_words?: string | null;
  words_language?: OutputLanguage | null;
};

/** What can be said about an interval of the year no claim covers. */
export type M100GapKind =
  "accrued" | "free_method" | "unavailable" | "box_unbound";

/** An interval of the year Modelo 100 leaves out of an element because no
 * claim records it, or because the edition has no box for its kind.
 * `accrued` is stated only where it can be worked out. */
export type M100ClaimGap = {
  asset_id: string;
  kind: M100GapKind;
  covered_from: string;
  covered_until: string;
  /** The last day the interval covers, which is what a reader sees as its
   * end; `covered_until` is the exclusive boundary. */
  covered_through: string;
  accrued: PublicDecimal | null;
  /** The interval said whole, by the name the register holds for the
   * element; null where it cannot be said whole. */
  words?: string | null;
  words_language?: OutputLanguage | null;
};

/** What a reason leaves out of the Modelo 130 amounts. */
export type M130LeftOutReason =
  "free_gap" | "agrarian_excluded" | "unavailable";

/** The elements one reason leaves out of the handoff's Modelo 130 amounts,
 * said whole. */
export type M130LeftOut = {
  reason: M130LeftOutReason;
  asset_ids: string[];
  words: string;
  words_language: OutputLanguage;
};

export type ActivityAssetFilingResult = ActivityAssetResultBase & {
  tax_year: number | null;
  m130_period: string | null;
  filing_handoff: {
    /** Null for a kind the edition has no Modelo 100 box for; the gaps name
     * its elements. */
    material_m100: ClaimProjection | null;
    intangible_m100: ClaimProjection | null;
    m100_gaps: M100ClaimGap[];
    /** Both null when no quarter was asked. */
    material_m130: M130Projection | null;
    intangible_m130: M130Projection | null;
    /** What the Modelo 130 amounts leave out, one entry per reason across
     * both kinds of element. */
    left_out: M130LeftOut[];
  } | null;
};

// ---- The element list ----------------------------------------------------

/** How many years or claims of an element need a person's attention, by kind. */
export type AssetCounts = {
  missing: number;
  incomplete: number;
  conflict: number;
  /** Years of an election the register cannot work out yet. */
  unsupported: number;
  /** Years no Modelo 100 edition covers, which have no table to work from. */
  without_tables: number;
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
  /** False once a baja is recorded: nothing is left to amortize, so `pending`
   * is not drawn. */
  pending_applies: boolean;
  /** What to fill in when the opening amount is unknown. */
  opening_remedy_field_key: string | null;
  /** The sentence telling where to enter the unknown opening amount; present
   * exactly when the field key is, said in `words_language`. */
  opening_remedy_words?: string | null;
  words_language?: OutputLanguage | null;
  findings: AssetCounts;
  /** The year a dotación form opens on; null where no year has anything left
   * to record. */
  default_claim_year: number | null;
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

/** `years` are the register's: every year of any element, in order.
 * `default_year` is the year the register opens on, null where it has none. */
export type AssetListResult = {
  rows: AssetListRow[] | null;
  years: number[];
  default_year: number | null;
};

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
  /** Whether the claim still matches the element's current schedule. */
  matches_current_schedule: boolean;
  /** Why it no longer does; null exactly when it still does. */
  stale_reason: StaleReason | null;
};

/** Why a claim no longer matches the schedule. */
export type StaleReason =
  "revision_changed" | "authority_changed" | "schedule_unavailable";

export type ClaimableInterval = {
  covered_from: string;
  covered_until: string;
  /** The last day the interval covers, as `PlanClaim.covered_through`. */
  covered_through: string;
};

export type PlanRow = {
  /** Minimum amortization from entry to this year's end, which reduces cost at
   * a baja. Null while an earlier year has no minimum, with the reason in
   * `minimum_reason_key`. */
  minimum_through: Amount;
  /** The catalogue key of the sentence that says why `minimum_through` is
   * null. */
  minimum_reason_key: string | null;
  /** The sentence for `minimum_reason_key`, said in `words_language`. */
  minimum_reason_words?: string | null;
  /** True when `minimum_through` is null because the method has no table
   * minimum: a year that adds nothing to the reduction of cost, not a figure
   * left unknown. */
  minimum_has_no_table: boolean;
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
  /** The sentence for the absence, filled in with its facts; null where it
   * cannot be said whole. */
  absence_reason_words?: string | null;
  /** The catalogue word of the entry that supplies what the absence lacks,
   * when filling it in is the remedy; null otherwise. */
  absence_remedy_field_key: string | null;
  /** The sentence telling where to enter what the absence lacks. */
  absence_remedy_words?: string | null;
  /** Whether the year has something to work out: false for a known state of
   * nothing to work out with no span open. */
  applies: boolean;
  claimed: PublicDecimal;
  claim_state: string;
  claimable_intervals: ClaimableInterval[];
  claimable_refusal_key: string | null;
  claimable_refusal_facts: ReasonFact[];
  /** The sentence for the refusal, filled in with its facts. */
  claimable_refusal_words?: string | null;
  /** As `absence_remedy_field_key`, for the refusal. */
  claimable_refusal_remedy_field_key: string | null;
  claimable_refusal_remedy_words?: string | null;
  /** The language of every sentence this year carries. */
  words_language?: OutputLanguage | null;
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
  /** The first day after the maximum period; the day the schedule works to,
   * not the one a reader sees it end on. */
  maximum_period_ends_on: string | null;
  /** The last day of the maximum period, which is the day it ends on. */
  maximum_period_last_day: string | null;
  /** The provisions behind the figures, each with its official link. */
  legal_citations: LegalCitation[];
  /** False where a cited provision could not be resolved, so the list is
   * partial. */
  legal_citations_complete: boolean;
  not_table_bound: string | null;
  unavailable_reason_key: string | null;
  unavailable_reason_facts: ReasonFact[];
  /** The sentence for why the limits are not available. */
  unavailable_reason_words?: string | null;
  words_language?: OutputLanguage | null;
};

/** A warning on the plan that changes no figure and refuses nothing; the
 * backend words it by the catalogue key it serves. */
export type PlanAdvisory = {
  kind: string;
  label_key: string;
  /** The advisory said whole, in `words_language`. */
  words?: string | null;
  words_language?: OutputLanguage | null;
};

export type PlanResult = {
  asset_id: string | null;
  rows: PlanRow[] | null;
  limits: ElectionLimits | null;
  advisories: PlanAdvisory[];
};

// ---- The append-only timeline --------------------------------------------

export type TimelineChange = {
  /** Whether the event gave the field its first value, changed it or took it away. */
  kind: "added" | "changed" | "removed";
  /** The record's field as the backend names it, a dotted path. */
  field: string;
  /** The catalogue key that words `field`; null for a path no fact of the
   * timeline has. */
  field_key: string | null;
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
  /** False for a dotación a later one replaced; only one in effect can
   * disagree with the schedule. */
  in_effect: boolean;
  tax_year: number | null;
  covered_from: string | null;
  /** The last day the dotación covers. */
  covered_through: string | null;
};

export type TimelineEvent = {
  sequence: number;
  /** Null for a record written before time was kept. */
  recorded_at: string | null;
  /** What kind of record this is in the register's storage. */
  kind: string;
  /** What the record did to the element: created, corrected, a baja recorded,
   * changed or removed, a dotación recorded or replaced, or a description. */
  event_kind: string | null;
  asset_id: string;
  /** The record's identity: a claim's id for a claim event. */
  record_id: string;
  /** The day the record takes effect: the day the element entered service for a
   * creation or correction, the baja's day for a baja, the first day a
   * dotación covers. */
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
  /** Whether an element of this class is charged only on a vehicle
   * declaration, which it then has to state. */
  requires_vehicle_declaration: boolean;
};

/** One reason a baja is accepted with, and the catalogue key that words it. */
export type DisposalReasonOption = { reason: string; label_key: string };

/** How an election's fact is stated, as the options serve it. */
export type MethodFactKind =
  | "text"
  | "date"
  | "whole"
  | "flag"
  | "choice"
  | "class"
  | "amount"
  | "share"
  | "decimal"
  | "rows";

/** One fact an election of a method states, as the options serve it. */
export type MethodFact = {
  /** From the election down to the fact. */
  path: string[];
  kind: MethodFactKind;
  required: boolean;
  /** Required once the fact's optional group is stated. */
  required_with_group: boolean;
  token_family: string | null;
  tokens: string[];
};

/** One stage a basis can be stated at, with the facts only that stage states. */
export type BasisStageOption = {
  stage: string;
  /** The names of the basis facts this stage states. */
  facts: string[];
  /** Whether the basis is the whole property's, which makes the element a
   * property. */
  is_property: boolean;
  /** The facts that state a purchase used wholly for the activity under this
   * stage; empty where the stage has no such path. */
  wholly_business_facts: { fact: string; value: PublicDecimal }[];
};

/** One status an opening history can have, with the facts it can state. */
export type OpeningStatusOption = { status: string; facts: string[] };

/** One condition an element can be acquired in, with the facts only that
 * condition states. */
export type ConditionOption = { condition: string; facts: string[] };

/** What the registry admits for one asset kind and tax year. */
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
  /** The reasons a baja is accepted with, in the order the backend admits
   * them. */
  disposal_reasons: DisposalReasonOption[];
  basis_stages: BasisStageOption[];
  opening_statuses: OpeningStatusOption[];
  acquired_conditions: ConditionOption[];
  /** The shapes a later payment or cost of an element's acquisition takes. */
  further_acquisition_shapes: string[];
  /** The Modelo 130 periods the registry serves for the tax year. */
  m130_periods: string[];
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
  /** The finding said whole, in `words_language`. */
  words?: string | null;
  words_language?: OutputLanguage | null;
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

/** The language the sentences of a register read are said in. */
export type ActivityAssetWordsRequest = { output_language?: OutputLanguage };

export type ActivityAssetListRequest = ActivityAssetWordsRequest;

export type ActivityAssetPlanRequest = ActivityAssetWordsRequest & {
  asset_id: string;
};

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

export type ActivityAssetDisposalCalculateRequest =
  ActivityAssetWordsRequest & {
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
