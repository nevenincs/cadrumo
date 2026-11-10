// The Ledger page's port to the ledger family's registered operations, as
// the desktop host serves them over the signed-in person's session. The page
// names one admitted definition and a JSON object of its registered request
// without the profile; the host fills the profile and the runtime's contract
// decides the rest. Files travel as tokens the host issued for the person's
// own picks, never as paths, and an own account's number only as the raw
// bytes of one call. Results and staged edits live in the page's memory
// only: never in storage, a log line or an error message.

import type { LedgerPreflightReason } from "./ledgerContract";
import type {
  AttachmentQueueResult,
  AttachmentViewRequest,
  AttachmentViewResult,
  EvidenceAddRequest,
  EvidenceBatchRequest,
  EvidenceBatchResult,
  EvidenceConfirmRequest,
  EvidenceConfirmResult,
  EvidenceConsentListResult,
  EvidenceExtractRequest,
  EvidenceExtractResult,
  EvidenceListResult,
  EvidencePageRequest,
  EvidencePageResult,
  EvidenceRecordResult,
  EvidenceRemoveRequest,
  EvidenceReviewListRequest,
  EvidenceReviewListResult,
  EvidenceReviewViewRequest,
  EvidenceReviewViewResult,
  EvidenceUpdateRequest,
  EvidenceViewRequest,
  EvidenceViewResult,
} from "./ledgerDocumentOperations";
import type {
  InvoiceAddRequest,
  InvoiceAddResult,
  InvoiceDocumentAttachRequest,
  InvoiceDocumentAttachResult,
  InvoiceImportRequest,
  InvoiceImportResult,
  InvoiceListRequest,
  InvoiceListResult,
  InvoicePreviewRequest,
  InvoicePreviewResult,
  InvoiceRemoveRequest,
  InvoiceRemoveResult,
  InvoiceUpdateRequest,
  InvoiceUpdateResult,
  InvoiceViewRequest,
  InvoiceViewResult,
  LedgerAttachRequest,
  LedgerAttachResult,
  LedgerCheckRequest,
  LedgerCheckResult,
  LedgerDetachRequest,
  LedgerInvoiceDuplicateRequest,
  LedgerInvoiceDuplicateResult,
  LedgerInvoiceMatchRequest,
  LedgerInvoiceMatchResult,
  LedgerLinkRequest,
  LedgerLinkResult,
} from "./ledgerInvoiceOperations";
import type {
  LedgerAddRequest,
  LedgerAddResult,
  LedgerAllocateRequest,
  LedgerAllocateResult,
  LedgerBulkClassifyRequest,
  LedgerBulkClassifyResult,
  LedgerClassifyRequest,
  LedgerClassifyResult,
  LedgerHistoryRequest,
  LedgerHistoryTypedResult,
  LedgerIvaDeriveRequest,
  LedgerIvaDeriveResult,
  LedgerLifecycleRequest,
  LedgerLifecycleResult,
  LedgerLlmReviewRequest,
  LedgerMergeRequest,
  LedgerMergeResult,
  LedgerRemoveRequest,
  LedgerRemoveResult,
  LedgerRuleTrialRequest,
  LedgerRuleTrialResult,
  LedgerSplitCheckRequest,
  LedgerSplitCheckResult,
  LedgerSplitRequest,
  LedgerSplitResult,
  LedgerStagedCheckRequest,
  LedgerStagedCheckResult,
  LedgerTrackRequest,
  LedgerTrackResult,
  LedgerUpdateRequest,
  LedgerUpdateResult,
} from "./ledgerMovementOperations";
import type {
  ActivityAssetAcquisitionCandidatesResult,
  ActivityAssetChangeResult,
  ActivityAssetClaimRequest,
  ActivityAssetClaimResult,
  ActivityAssetCorrectRequest,
  ActivityAssetCreateRequest,
  ActivityAssetDescribeRequest,
  ActivityAssetDisposalCalculateRequest,
  ActivityAssetDisposalCalculateResult,
  ActivityAssetDisposeRequest,
  ActivityAssetFilingRequest,
  ActivityAssetFilingResult,
  ActivityAssetForecastRequest,
  ActivityAssetForecastResult,
  ActivityAssetFormOptionsRequest,
  ActivityAssetFormOptionsResult,
  ActivityAssetInspectRequest,
  ActivityAssetInspectResult,
  ActivityAssetListRequest,
  ActivityAssetListResult,
  ActivityAssetPlanRequest,
  ActivityAssetPlanResult,
  ActivityAssetTimelineRequest,
  ActivityAssetTimelineResult,
  InventoryBookRequest,
  InventoryChangeResult,
  InventoryClosingAuthorityRequest,
  InventoryClosingAuthorityResult,
  InventoryClosingValueRequest,
  InventoryCorrectRequest,
  InventoryCreateRequest,
  InventoryCreateResult,
  InventoryDescribeRequest,
  InventoryEvidenceAddRequest,
  InventoryEvidenceAddResult,
  InventoryInspectResult,
  InventoryListResult,
  InventoryMovementAddRequest,
  InventoryMovementAddResult,
  InventoryMovementCorrectRequest,
  InventoryMovementReverseRequest,
  InventoryOptionsResult,
  InventoryRestoreRequest,
  InventoryRetireRequest,
  InventoryValuationResult,
  LedgerEntryOptionsRequest,
  LedgerEntryOptionsResult,
  LedgerParticipationRebuildResult,
  LedgerResetRequest,
  LedgerResetResult,
} from "./ledgerSetup";
import type {
  CapitalGoodDeclareRequest,
  CapitalGoodDeclareResult,
  CapitalGoodsListResult,
  LedgerOwnAccountRequest,
  LedgerOwnAccountResult,
  ProrrataDeclareGrossRequest,
  ProrrataDeclareSectorRequest,
  ProrrataElectEspecialRequest,
  ProrrataElectionRequest,
  ProrrataListResult,
  ProrrataMutationResult,
  ProrrataRemoveGrossRequest,
  ProrrataRevokeEspecialRequest,
  ProrrataSeedRequest,
  ProrrataSeedSectorRequest,
  ProrrataSettleSectorRequest,
  WithholdingAbsenceListRequest,
  WithholdingAbsenceListResult,
  WithholdingAbsenceResult,
  WithholdingAttestRequest,
  WithholdingListRequest,
  WithholdingListResult,
  WithholdingMutationResult,
  WithholdingRecordRequest,
  WithholdingRemoveRequest,
  WithholdingWithdrawRequest,
} from "./ledgerRegisterOperations";
import type {
  LedgerCounterpartyRequest,
  LedgerCounterpartyResult,
  LedgerLlmDiagnosticsRequest,
  LedgerLlmDiagnosticsResult,
  LedgerRatiosEligibleRequest,
  LedgerRatiosEligibleResult,
  LedgerRatiosListResult,
  LedgerRatiosSetRequest,
  LedgerRatiosSetResult,
  LedgerRatiosUnsetRequest,
  LedgerRatiosUnsetResult,
  LedgerRatiosValidateResult,
  LedgerRatiosYearRequest,
  LedgerRuleAddRequest,
  LedgerRuleAddResult,
  LedgerRuleApplyRequest,
  LedgerRuleApplyResult,
  LedgerRuleListResult,
} from "./ledgerClassificationSetup";

/** The definitions the host admits, mirroring its closed list. */
export const LEDGER_DEFINITIONS = [
  "ledger.actividad-asset.acquisition-candidates",
  "ledger.actividad-asset.claim",
  "ledger.actividad-asset.correct",
  "ledger.actividad-asset.create",
  "ledger.actividad-asset.describe",
  "ledger.actividad-asset.disposal-calculate",
  "ledger.actividad-asset.dispose",
  "ledger.actividad-asset.filing-handoff",
  "ledger.actividad-asset.forecast",
  "ledger.actividad-asset.form-options",
  "ledger.actividad-asset.inspect",
  "ledger.actividad-asset.list",
  "ledger.actividad-asset.plan",
  "ledger.actividad-asset.timeline",
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
  "ledger.entry-options",
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
  "ledger.inventory.closing-value.record",
  "ledger.inventory.correct",
  "ledger.inventory.create",
  "ledger.inventory.describe",
  "ledger.inventory.evidence.add",
  "ledger.inventory.inspect",
  "ledger.inventory.list",
  "ledger.inventory.movement.add",
  "ledger.inventory.movement.correct",
  "ledger.inventory.movement.reverse",
  "ledger.inventory.options",
  "ledger.inventory.restore",
  "ledger.inventory.retire",
  "ledger.inventory.valuation.preview",
  "ledger.invoice.add",
  "ledger.invoice.attach_document",
  "ledger.invoice.duplicate",
  "ledger.invoice.import",
  "ledger.invoice.list",
  "ledger.invoice.match",
  "ledger.invoice.preview",
  "ledger.invoice.remove",
  "ledger.invoice.update",
  "ledger.invoice.view",
  "ledger.invoice.wizard",
  "ledger.known-values",
  "ledger.link",
  "ledger.list",
  "ledger.llm-diagnostics",
  "ledger.merge",
  "ledger.own_account",
  "ledger.participation",
  "ledger.participation.rebuild",
  "ledger.preflight",
  "ledger.prorrata.declare_gross",
  "ledger.prorrata.declare_sector",
  "ledger.prorrata.elect_especial",
  "ledger.prorrata.elect_general",
  "ledger.prorrata.list",
  "ledger.prorrata.remove_gross",
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
  "ledger.retencion_soportada.attest_absence",
  "ledger.retencion_soportada.list",
  "ledger.retencion_soportada.list_absences",
  "ledger.retencion_soportada.record",
  "ledger.retencion_soportada.remove",
  "ledger.retencion_soportada.withdraw_absence",
  "ledger.review",
  "ledger.rule.add",
  "ledger.rule.apply",
  "ledger.rule.list",
  "ledger.rule.remove",
  "ledger.rule.trial",
  "ledger.split.check",
  "ledger.split.manual",
  "ledger.split.review",
  "ledger.staged.check",
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

/** Native-observed terminal failure; execution stopped, effects unresolved.
 * These words alone come from the definition's admitted error projection. */
export type TerminalOperationFailure = {
  operation_id: string;
  definition_id: string;
  effect: "unknown" | "partial" | "updated";
  refusal_words: string | null;
};

export type LedgerFailure = {
  code: LedgerFailureCode;
  operation_id: string | null;
  /** The runtime's closed refusal code, where it gave one. */
  reason?: string;
  terminal_failure?: TerminalOperationFailure;
};

/** The typed failure of a rejected ledger call. A rejection that is not the
 * host's own answer never reached it, so nothing was sent. */
export function ledgerFailure(error: unknown): LedgerFailure {
  const found = error as {
    code?: unknown;
    operation_id?: unknown;
    reason?: unknown;
    terminal_failure?: unknown;
  } | null;
  const code = (LEDGER_FAILURE_CODES as readonly unknown[]).includes(
    found?.code,
  )
    ? (found?.code as LedgerFailureCode)
    : "unavailable";
  const operationId =
    typeof found?.operation_id === "string" ? found.operation_id : null;
  const terminal =
    found?.terminal_failure as Partial<TerminalOperationFailure> | null;
  const terminalFailure =
    code === "unknown" &&
    terminal &&
    terminal.operation_id === operationId &&
    typeof operationId === "string" &&
    /^[a-f0-9]{64}$/.test(operationId) &&
    typeof terminal.definition_id === "string" &&
    /^[a-z][a-z0-9_.-]{0,159}$/.test(terminal.definition_id) &&
    (terminal.effect === "unknown" ||
      terminal.effect === "partial" ||
      terminal.effect === "updated") &&
    (terminal.refusal_words === null ||
      (typeof terminal.refusal_words === "string" &&
        terminal.refusal_words.trim() !== "" &&
        [...terminal.refusal_words].length <= 2048))
      ? ({
          operation_id: operationId,
          definition_id: terminal.definition_id,
          effect: terminal.effect,
          refusal_words: terminal.refusal_words,
        } satisfies TerminalOperationFailure)
      : undefined;
  return {
    code,
    operation_id: operationId,
    ...(typeof found?.reason === "string" ? { reason: found.reason } : {}),
    ...(terminalFailure ? { terminal_failure: terminalFailure } : {}),
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
  /** The finished sentence the backend served for this stop, and its
   * language. Absent on a detail recorded before sentences were served. */
  refusal_words?: string | null;
  refusal_words_language?: string | null;
  /** The registered operation the refusal names for putting it right, where
   * it names one. */
  next_step?: LedgerNextStep | null;
};

/** The step a refusal serves for putting it right: a closed kind, what it
 * concerns and the words that offer it, in the language of the refusal's own
 * sentence. The window does what it already knows for the kind: runs the
 * creation or the calculation, opens the declaration whose own form says what
 * it lacks, opens the profile at one detail, or offers declaring the profile
 * setup complete. It holds no table of operator actions. */
export type LedgerNextStep =
  | {
      kind: "create_work";
      modelo: string;
      filing_year: number;
      period_code: string;
      words: string;
    }
  | { kind: "calculate_work"; work_unit_id: string; words: string }
  | { kind: "open_work"; work_unit_id: string; words: string }
  /** `path` is the profile detail's own schema address, which the profile
   * page already addresses its rows by. */
  | { kind: "open_profile_field"; path: string; words: string }
  | { kind: "complete_profile_setup"; words: string }
  /** Opens one ledger movement in the Libro, where the fact the refusal
   * names is recorded. */
  | { kind: "open_movement"; transaction_id: string; words: string }
  /** Opens the IVA balance of the declaration one work unit holds, where its
   * carried compensation is recorded. */
  | { kind: "open_iva_wallet"; work_unit_id: string; words: string }
  /** Opens the IVA balance of the declaration named here, at the entry that
   * records the opening balance its carry reads. */
  | {
      kind: "open_iva_wallet_opening_balance";
      modelo: string;
      filing_year: number;
      period_code: string;
      words: string;
    }
  /** Opens the model picker of the agent column, where the person picks the
   * model documents are read with. */
  | { kind: "choose_reading_model"; words: string };

/** The step the agent column's model picker answers. */
export type LedgerReadingModelStep = Extract<
  LedgerNextStep,
  { kind: "choose_reading_model" }
>;

/** The steps the profile page answers, the two a readiness refusal serves. */
export type LedgerProfileStep = Extract<
  LedgerNextStep,
  { kind: "open_profile_field" } | { kind: "complete_profile_setup" }
>;

/** The step a declaration's IVA balance answers, naming the declaration whose
 * opening balance is missing. */
export type LedgerIvaWalletStep = Extract<
  LedgerNextStep,
  { kind: "open_iva_wallet_opening_balance" } | { kind: "open_iva_wallet" }
>;

/** The step the Libro answers, naming one movement. */
export type LedgerMovementStep = Extract<
  LedgerNextStep,
  { kind: "open_movement" }
>;

/** The steps a declaration surface answers, each naming a declaration. */
export type LedgerWorkStep = Extract<
  LedgerNextStep,
  { kind: "create_work" } | { kind: "calculate_work" } | { kind: "open_work" }
>;

/** Whether a served step is one a declaration surface answers. */
export const isWorkStep = (step: LedgerNextStep): step is LedgerWorkStep =>
  step.kind === "create_work" ||
  step.kind === "calculate_work" ||
  step.kind === "open_work";

/** Whether a served step is one the profile page answers. */
export const isProfileStep = (
  step: LedgerNextStep,
): step is LedgerProfileStep =>
  step.kind === "open_profile_field" || step.kind === "complete_profile_setup";

/** The step the backend served on a refusal's detail; null when it served
 * none, or one of a kind this window does not run. */
export function servedNextStep(detail: unknown): LedgerNextStep | null {
  if (typeof detail !== "object" || detail === null) return null;
  const step = (detail as { next_step?: unknown }).next_step;
  if (typeof step !== "object" || step === null) return null;
  const served = step as Record<string, unknown>;
  const text = (key: string) =>
    typeof served[key] === "string" && served[key] !== ""
      ? (served[key] as string)
      : null;
  const words = text("words");
  if (words === null) return null;
  if (served.kind === "create_work") {
    const modelo = text("modelo");
    const period = text("period_code");
    const year = served.filing_year;
    return modelo !== null && period !== null && typeof year === "number"
      ? {
          kind: "create_work",
          modelo,
          filing_year: year,
          period_code: period,
          words,
        }
      : null;
  }
  if (served.kind === "open_iva_wallet_opening_balance") {
    const modelo = text("modelo");
    const period = text("period_code");
    const year = served.filing_year;
    return modelo !== null && period !== null && typeof year === "number"
      ? {
          kind: "open_iva_wallet_opening_balance",
          modelo,
          filing_year: year,
          period_code: period,
          words,
        }
      : null;
  }
  if (served.kind === "open_movement") {
    const movement = text("transaction_id");
    return movement === null
      ? null
      : { kind: "open_movement", transaction_id: movement, words };
  }
  if (
    served.kind === "calculate_work" ||
    served.kind === "open_work" ||
    served.kind === "open_iva_wallet"
  ) {
    const unit = text("work_unit_id");
    return unit === null
      ? null
      : { kind: served.kind, work_unit_id: unit, words };
  }
  if (served.kind === "open_profile_field") {
    const path = text("path");
    return path === null ? null : { kind: "open_profile_field", path, words };
  }
  if (served.kind === "complete_profile_setup")
    return { kind: "complete_profile_setup", words };
  if (served.kind === "choose_reading_model")
    return { kind: "choose_reading_model", words };
  return null;
}

/** The sentence the backend served for a refusal, read from whichever
 * detail it settled with; null when it served none. The window shows it as
 * served and never words a refusal from its code. */
export function servedRefusalWords(detail: unknown): string | null {
  if (typeof detail !== "object" || detail === null) return null;
  const words = (detail as { refusal_words?: unknown }).refusal_words;
  return typeof words === "string" && words.trim() !== "" ? words : null;
}

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

/** The retención a received invoice leaves on the movement that pays it, as
 * the declarations read it. `retencion` is the euro amount recognised on this
 * payment, canonical decimal text; `held_back` names why the invoice reaches
 * no declaration yet, so a payment the declaration waits on is never shown
 * as a payment without retención. Exactly one of the two is set. */
export type LedgerMovementWithholding = {
  invoice_id: string;
  invoice_number: string;
  modelo: string | null;
  scheme: string | null;
  retencion: string | null;
  recognised_on: string | null;
  held_back: string | null;
};

/** One movement as the product projects it. Amounts are canonical decimal
 * text; the amount is a magnitude and `direction` carries its sense. */
export type LedgerTransaction = {
  transaction_id: string;
  date: string;
  booked_date: string;
  value_date: string | null;
  operation_date: string | null;
  accrual_date: string | null;
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
  deduction_fact_kind: string | null;
  investment_asset_id: string | null;
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
  /** What the invoices this movement pays leave on it; empty where it pays
   * none that states a retención, which is absent, not zero. */
  withholding: LedgerMovementWithholding[];
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

/** The kinds of text a profile's own records can offer. */
export type LedgerKnownValueKind =
  | "counterparty"
  | "description"
  | "group_label"
  | "m210_payer"
  | "m210_asset"
  | "asset_reference";

export type LedgerKnownValuesRequest = { kinds: LedgerKnownValueKind[] };

/** One party as the records name it. The tax id comes from an invoice; a
 * movement states none, and joins one only if its name can mean no other. */
export type KnownCounterparty = {
  name: string;
  tax_id: string | null;
  country: string | null;
  identification_state: string | null;
  uses: number;
  last_used: string;
};

export type KnownText = {
  text: string;
  uses: number;
  last_used: string;
  counterparty: string | null;
};

/** Each list is the newest of its kind; `truncated` names the kinds that hold
 * more than they show. */
export type LedgerKnownValuesResult = {
  profile_id: string;
  counterparties: KnownCounterparty[];
  descriptions: KnownText[];
  group_labels: KnownText[];
  m210_payers: KnownText[];
  m210_assets: KnownText[];
  asset_references: KnownText[];
  truncated: LedgerKnownValueKind[];
};

export type LedgerViewRequest = { transaction_prefix: string };

export type LedgerViewResult = {
  profile_id: string;
  transaction_prefix: string;
  transaction: LedgerTransaction;
  review_status: LedgerReviewStatus;
  latest_llm_rejection: { occurred_at: string; operator_reason: string } | null;
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

/** A statement format as `ledger.entry-options` serves it; the ledger refuses
 * one it does not parse. */
export type LedgerProvider = string;

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
  | "transactions.import.all_rows_already_in_ledger"
  | "transactions.import.some_rows_already_in_ledger"
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
  }[];
  source_digests: { file_index: number; sha256: string }[];
};

/** An export serialisation as `ledger.entry-options` serves it. */
export type LedgerExportFormat = string;

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

export interface LedgerRequests {
  "ledger.known-values": LedgerKnownValuesRequest;
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
  "ledger.invoice.preview": InvoicePreviewRequest;
  "ledger.rule.trial": LedgerRuleTrialRequest;
  "ledger.invoice.duplicate": LedgerInvoiceDuplicateRequest;
  "ledger.invoice.match": LedgerInvoiceMatchRequest;
  "ledger.split.check": LedgerSplitCheckRequest;
  "ledger.staged.check": LedgerStagedCheckRequest;
  "ledger.invoice.update": InvoiceUpdateRequest;
  "ledger.invoice.remove": InvoiceRemoveRequest;
  "ledger.invoice.attach_document": InvoiceDocumentAttachRequest;
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
  "ledger.ratios.eligible": LedgerRatiosEligibleRequest;
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
  "ledger.prorrata.declare_gross": ProrrataDeclareGrossRequest;
  "ledger.prorrata.remove_gross": ProrrataRemoveGrossRequest;
  "ledger.retencion_soportada.list": WithholdingListRequest;
  "ledger.retencion_soportada.list_absences": WithholdingAbsenceListRequest;
  "ledger.retencion_soportada.record": WithholdingRecordRequest;
  "ledger.retencion_soportada.remove": WithholdingRemoveRequest;
  "ledger.retencion_soportada.attest_absence": WithholdingAttestRequest;
  "ledger.retencion_soportada.withdraw_absence": WithholdingWithdrawRequest;
  "ledger.bienes_inversion.list": Record<string, never>;
  "ledger.bienes_inversion.declare": CapitalGoodDeclareRequest;
  "ledger.inventory.list": Record<string, never>;
  "ledger.inventory.create": InventoryCreateRequest;
  "ledger.inventory.movement.add": InventoryMovementAddRequest;
  "ledger.inventory.valuation.preview": InventoryBookRequest;
  "ledger.inventory.closing-authority.record": InventoryClosingAuthorityRequest;
  "ledger.inventory.closing-value.record": InventoryClosingValueRequest;
  "ledger.inventory.evidence.add": InventoryEvidenceAddRequest;
  "ledger.inventory.options": Record<string, never>;
  "ledger.entry-options": LedgerEntryOptionsRequest;
  "ledger.inventory.inspect": InventoryBookRequest;
  "ledger.inventory.describe": InventoryDescribeRequest;
  "ledger.inventory.correct": InventoryCorrectRequest;
  "ledger.inventory.movement.correct": InventoryMovementCorrectRequest;
  "ledger.inventory.movement.reverse": InventoryMovementReverseRequest;
  "ledger.inventory.retire": InventoryRetireRequest;
  "ledger.inventory.restore": InventoryRestoreRequest;
  "ledger.actividad-asset.create": ActivityAssetCreateRequest;
  "ledger.actividad-asset.inspect": ActivityAssetInspectRequest;
  "ledger.actividad-asset.correct": ActivityAssetCorrectRequest;
  "ledger.actividad-asset.list": ActivityAssetListRequest;
  "ledger.actividad-asset.plan": ActivityAssetPlanRequest;
  "ledger.actividad-asset.timeline": ActivityAssetTimelineRequest;
  "ledger.actividad-asset.form-options": ActivityAssetFormOptionsRequest;
  "ledger.actividad-asset.acquisition-candidates": Record<string, never>;
  "ledger.actividad-asset.describe": ActivityAssetDescribeRequest;
  "ledger.actividad-asset.dispose": ActivityAssetDisposeRequest;
  "ledger.actividad-asset.disposal-calculate": ActivityAssetDisposalCalculateRequest;
  "ledger.actividad-asset.forecast": ActivityAssetForecastRequest;
  "ledger.actividad-asset.claim": ActivityAssetClaimRequest;
  "ledger.actividad-asset.filing-handoff": ActivityAssetFilingRequest;
  "ledger.participation.rebuild": Record<string, never>;
  "ledger.reset": LedgerResetRequest;
}

export interface LedgerResults {
  "ledger.known-values": LedgerKnownValuesResult;
  "ledger.list": LedgerListResult;
  "ledger.view": LedgerViewResult;
  "ledger.update": LedgerUpdateResult;
  "ledger.classify.single": LedgerClassifyResult;
  "ledger.classify.bulk": LedgerBulkClassifyResult;
  "ledger.add": LedgerAddResult;
  "ledger.invoice.list": InvoiceListResult;
  "ledger.invoice.view": InvoiceViewResult;
  "ledger.invoice.add": InvoiceAddResult;
  "ledger.invoice.preview": InvoicePreviewResult;
  "ledger.rule.trial": LedgerRuleTrialResult;
  "ledger.invoice.duplicate": LedgerInvoiceDuplicateResult;
  "ledger.invoice.match": LedgerInvoiceMatchResult;
  "ledger.split.check": LedgerSplitCheckResult;
  "ledger.staged.check": LedgerStagedCheckResult;
  "ledger.invoice.update": InvoiceUpdateResult;
  "ledger.invoice.remove": InvoiceRemoveResult;
  "ledger.invoice.attach_document": InvoiceDocumentAttachResult;
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
  "ledger.prorrata.declare_gross": ProrrataMutationResult;
  "ledger.prorrata.remove_gross": ProrrataMutationResult;
  "ledger.retencion_soportada.list": WithholdingListResult;
  "ledger.retencion_soportada.list_absences": WithholdingAbsenceListResult;
  "ledger.retencion_soportada.record": WithholdingMutationResult;
  "ledger.retencion_soportada.remove": WithholdingMutationResult;
  "ledger.retencion_soportada.attest_absence": WithholdingAbsenceResult;
  "ledger.retencion_soportada.withdraw_absence": WithholdingAbsenceResult;
  "ledger.bienes_inversion.list": CapitalGoodsListResult;
  "ledger.bienes_inversion.declare": CapitalGoodDeclareResult;
  "ledger.inventory.list": InventoryListResult;
  "ledger.inventory.create": InventoryCreateResult;
  "ledger.inventory.movement.add": InventoryMovementAddResult;
  "ledger.inventory.valuation.preview": InventoryValuationResult;
  "ledger.inventory.closing-authority.record": InventoryClosingAuthorityResult;
  "ledger.inventory.closing-value.record": InventoryClosingAuthorityResult;
  "ledger.inventory.evidence.add": InventoryEvidenceAddResult;
  "ledger.inventory.options": InventoryOptionsResult;
  "ledger.entry-options": LedgerEntryOptionsResult;
  "ledger.inventory.inspect": InventoryInspectResult;
  "ledger.inventory.describe": InventoryChangeResult;
  "ledger.inventory.correct": InventoryChangeResult;
  "ledger.inventory.movement.correct": InventoryChangeResult;
  "ledger.inventory.movement.reverse": InventoryChangeResult;
  "ledger.inventory.retire": InventoryChangeResult;
  "ledger.inventory.restore": InventoryChangeResult;
  "ledger.actividad-asset.create": ActivityAssetChangeResult;
  "ledger.actividad-asset.inspect": ActivityAssetInspectResult;
  "ledger.actividad-asset.correct": ActivityAssetChangeResult;
  "ledger.actividad-asset.list": ActivityAssetListResult;
  "ledger.actividad-asset.plan": ActivityAssetPlanResult;
  "ledger.actividad-asset.timeline": ActivityAssetTimelineResult;
  "ledger.actividad-asset.form-options": ActivityAssetFormOptionsResult;
  "ledger.actividad-asset.acquisition-candidates": ActivityAssetAcquisitionCandidatesResult;
  "ledger.actividad-asset.describe": ActivityAssetChangeResult;
  "ledger.actividad-asset.dispose": ActivityAssetChangeResult;
  "ledger.actividad-asset.disposal-calculate": ActivityAssetDisposalCalculateResult;
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
