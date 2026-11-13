// The window's names for the request and result of the ledger operations that
// teach the ledger how to classify: the stored rules, the declared ratios, the
// counterparties and the model diagnostics. Each is the registered Python
// contract's own type, taken from the generated module by definition id, so no
// field is written here. A request leaves out the profile, which the host
// fills.

import type { LedgerClassificationContracts } from "./ledgerClassificationContract";

type Definition = keyof LedgerClassificationContracts;

/** What the window sends: the registered request without the profile. */
type Sent<D extends Definition> = Omit<
  LedgerClassificationContracts[D]["request"],
  "profile_id"
>;

/** What the operation serves. */
type Served<D extends Definition> = LedgerClassificationContracts[D]["result"];

export type LedgerRuleListResult = Served<"ledger.rule.list">;
export type LedgerRuleAddRequest = Sent<"ledger.rule.add">;
export type LedgerRuleAddResult = Served<"ledger.rule.add">;
export type LedgerRuleApplyRequest = Sent<"ledger.rule.apply">;
export type LedgerRuleApplyResult = Served<"ledger.rule.apply">;

export type LedgerRatiosYearRequest = Sent<"ledger.ratios.list">;
export type LedgerRatiosListResult = Served<"ledger.ratios.list">;
export type LedgerRatiosEligibleRequest = Sent<"ledger.ratios.eligible">;
export type LedgerRatiosEligibleResult = Served<"ledger.ratios.eligible">;
export type LedgerRatiosValidateResult = Served<"ledger.ratios.validate">;
export type LedgerRatiosSetRequest = Sent<"ledger.ratios.set">;
export type LedgerRatiosSetResult = Served<"ledger.ratios.set">;
export type LedgerRatiosUnsetRequest = Sent<"ledger.ratios.unset">;
export type LedgerRatiosUnsetResult = Served<"ledger.ratios.unset">;

export type LedgerCounterpartyRequest = Sent<"ledger.counterparty">;
export type LedgerCounterpartyResult = Served<"ledger.counterparty">;

export type LedgerLlmDiagnosticsRequest = Sent<"ledger.llm-diagnostics">;
export type LedgerLlmDiagnosticsResult = Served<"ledger.llm-diagnostics">;
