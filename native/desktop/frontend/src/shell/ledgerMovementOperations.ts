// The window's names for the request and result of the ledger operations that
// change, check or trace one movement: edits, classification, manual entry,
// staged checks, splits, lifecycle, history and the model's suggestions. Each
// is the registered Python contract's own type, taken from the generated
// modules by definition id, so no field is written here. A request leaves out
// the profile, which the host fills.

import type { LedgerMovementCheckContracts } from "./ledgerMovementCheckContract";
import type { LedgerMovementContracts } from "./ledgerMovementContract";

type Contracts = LedgerMovementContracts & LedgerMovementCheckContracts;
type Definition = keyof Contracts;

/** What the window sends: the registered request without the profile. */
type Sent<D extends Definition> = Omit<Contracts[D]["request"], "profile_id">;

/** What the operation serves. */
type Served<D extends Definition> = Contracts[D]["result"];

export type LedgerUpdateRequest = Sent<"ledger.update">;
export type LedgerUpdateResult = Served<"ledger.update">;

export type LedgerClassifyRequest = Sent<"ledger.classify.single">;
export type LedgerClassifyResult = Served<"ledger.classify.single">;
export type LedgerClassifyField = LedgerClassifyRequest["patch_fields"][number];
export type LedgerClassifyValidation = LedgerClassifyResult["validation_kind"];

export type LedgerBulkClassifyRequest = Sent<"ledger.classify.bulk">;
export type LedgerBulkClassifyResult = Served<"ledger.classify.bulk">;

export type LedgerAddRequest = Sent<"ledger.add">;
export type LedgerAddResult = Served<"ledger.add">;
export type LedgerAddValidation = NonNullable<
  LedgerAddResult["validation_code"]
>;

export type LedgerRuleTrialRequest = Sent<"ledger.rule.trial">;
export type LedgerRuleTrialResult = Served<"ledger.rule.trial">;
export type LedgerSplitCheckRequest = Sent<"ledger.split.check">;
export type LedgerSplitCheckResult = Served<"ledger.split.check">;
export type LedgerStagedCheckRequest = Sent<"ledger.staged.check">;
export type LedgerStagedCheckResult = Served<"ledger.staged.check">;

export type LedgerLlmReviewRequest = Sent<"ledger.classify.review">;
export type LedgerLlmReviewMode = LedgerLlmReviewRequest["mode"];
/** A model's proposal for one movement: only the person applies it. */
export type LedgerLlmSuggestion = NonNullable<
  Served<"ledger.classify.review">["preview"]
>;

export type LedgerTrackRequest = Sent<"ledger.track">;
export type LedgerTrackResult = Served<"ledger.track">;
export type LedgerParticipation = NonNullable<
  LedgerTrackResult["participated_in"]
>[number];
export type LedgerHistoryRequest = Sent<"ledger.history.typed">;
export type LedgerHistoryTypedResult = Served<"ledger.history.typed">;

export type LedgerRemoveRequest = Sent<"ledger.remove">;
export type LedgerRemoveResult = Served<"ledger.remove">;
export type LedgerRevisionReference =
  LedgerRemoveResult["report"]["blocking_modelo_references"][number];

export type LedgerLifecycleRequest = Sent<"ledger.archive">;
export type LedgerLifecycleResult = Served<"ledger.archive">;

export type LedgerSplitRequest = Sent<"ledger.split.manual">;
export type LedgerSplitResult = Served<"ledger.split.manual">;
export type LedgerMergeRequest = Sent<"ledger.merge">;
export type LedgerMergeResult = Served<"ledger.merge">;

export type LedgerIvaDeriveRequest = Sent<"ledger.classify.iva-derive">;
export type LedgerIvaDeriveResult = Served<"ledger.classify.iva-derive">;
export type LedgerAllocateRequest = Sent<"ledger.allocate">;
export type LedgerAllocateResult = Served<"ledger.allocate">;
