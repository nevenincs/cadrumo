// The request and result shapes of the ledger operations that teach the
// ledger how to classify: the stored rules, the declared ratios, the
// counterparties and the model diagnostics. Field names are the registered
// Python contracts' own, and a request leaves out the profile, which the
// host fills.

import type { OutputLanguage, PublicDecimal } from "./ledger";

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
  | "empty_pattern"
  | "invalid_pattern"
  | "pattern_too_long"
  | "pattern_overrun"
  | "category"
  | "invalid_command";

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
  refused_rule_id: string | null;
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
  conflict_context: [string, string][] | null;
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
