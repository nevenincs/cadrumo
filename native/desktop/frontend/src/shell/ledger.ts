// The Ledger page's port to the ledger family's registered operations, as
// the desktop host serves them over the signed-in person's session. The page
// names one admitted definition and a JSON object of its registered request
// without the profile; the host fills the profile and the runtime's contract
// decides the rest. Files travel as tokens the host issued for the person's
// own picks, never as paths, and an own account's number only as the raw
// bytes of one call. Results and staged edits live in the page's memory
// only: never in storage, a log line or an error message.

import type { LedgerProrrataContracts } from "./ledgerProrrataContract";
import type { LedgerReadContracts } from "./ledgerReadContract";
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
  InventoryInspectWindowRequest,
  InventoryLedgerChangeProjection,
  InventoryClosingAuthorityRecordWindowRequest,
  InventoryClosingAuthorityOperationProjection,
  InventoryClosingValueRecordWindowRequest,
  InventoryCorrectWindowRequest,
  InventoryCreateWindowRequest,
  InventoryCreateProjection,
  InventoryDescribeWindowRequest,
  InventoryEvidenceAddWindowRequest,
  InventoryEvidenceAddProjection,
  InventoryInspectProjection,
  InventoryListProjection,
  InventoryMovementAddWindowRequest,
  InventoryMovementAddProjection,
  InventoryMovementClaimWindowRequest,
  InventoryMovementCorrectWindowRequest,
  InventoryMovementReverseWindowRequest,
  InventoryOptionsProjection,
  InventoryRestoreWindowRequest,
  InventoryRetireWindowRequest,
  InventoryValuationOperationProjection,
} from "./ledgerInventoryContract";
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
  LedgerEntryOptionsRequest,
  LedgerEntryOptionsResult,
  LedgerParticipationRebuildResult,
  LedgerResetRequest,
  LedgerResetResult,
} from "./ledgerSetup";
import type { WithholdingRecordRequest } from "./ledgerRegisterOperations";
import type { LedgerCapitalGoodsContracts } from "./ledgerCapitalGoodsContract";
import type { LedgerOwnAccountContracts } from "./ledgerOwnAccountContract";
import type {
  ExportSerializationFormat,
  LedgerTransferContracts,
} from "./ledgerTransferContract";
import type { LedgerWithholdingContracts } from "./ledgerWithholdingContract";
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
  "ledger.inventory.movement.claim",
  "ledger.inventory.movement.claim-candidates",
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
  "ledger.operaciones_vinculadas.list",
  "ledger.operaciones_vinculadas.state_none",
  "ledger.operaciones_vinculadas.state_operation",
  "ledger.operaciones_vinculadas.state_turnover",
  "ledger.operaciones_vinculadas.withdraw_none",
  "ledger.operaciones_vinculadas.withdraw_operation",
  "ledger.operaciones_vinculadas.withdraw_turnover",
  "ledger.own_account",
  "ledger.participation",
  "ledger.participation.rebuild",
  "ledger.preflight",
  "ledger.prevision_social.list",
  "ledger.prevision_social.record",
  "ledger.prevision_social.remove",
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

export type PublicDecimal = { decimal: string };

/** An export format as the host's save dialog command names it. */
export type LedgerExportFormat = string;

export interface LedgerRequests {
  "ledger.known-values": Omit<
    LedgerReadContracts["ledger.known-values"]["request"],
    "profile_id"
  >;
  "ledger.list": Omit<
    LedgerReadContracts["ledger.list"]["request"],
    "profile_id"
  >;
  "ledger.view": Omit<
    LedgerReadContracts["ledger.view"]["request"],
    "profile_id"
  >;
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
  "ledger.status": Omit<
    LedgerReadContracts["ledger.status"]["request"],
    "profile_id"
  >;
  "ledger.preflight": Omit<
    LedgerReadContracts["ledger.preflight"]["request"],
    "profile_id"
  >;
  "ledger.import": Omit<
    LedgerTransferContracts["ledger.import"]["request"],
    "profile_id"
  >;
  "ledger.export": Omit<
    LedgerTransferContracts["ledger.export"]["request"],
    "profile_id"
  >;
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
  "ledger.own_account": Omit<
    LedgerOwnAccountContracts["ledger.own_account"]["request"],
    "profile_id" | OwnAccountSecret
  >;
  "ledger.prorrata.list": Omit<
    LedgerProrrataContracts["ledger.prorrata.list"]["request"],
    "profile_id"
  >;
  "ledger.prorrata.seed": Omit<
    LedgerProrrataContracts["ledger.prorrata.seed"]["request"],
    "profile_id"
  >;
  "ledger.prorrata.declare_sector": Omit<
    LedgerProrrataContracts["ledger.prorrata.declare_sector"]["request"],
    "profile_id"
  >;
  "ledger.prorrata.elect_general": Omit<
    LedgerProrrataContracts["ledger.prorrata.elect_general"]["request"],
    "profile_id"
  >;
  "ledger.prorrata.elect_especial": Omit<
    LedgerProrrataContracts["ledger.prorrata.elect_especial"]["request"],
    "profile_id"
  >;
  "ledger.prorrata.revoke_especial": Omit<
    LedgerProrrataContracts["ledger.prorrata.revoke_especial"]["request"],
    "profile_id"
  >;
  "ledger.prorrata.seed_sector": Omit<
    LedgerProrrataContracts["ledger.prorrata.seed_sector"]["request"],
    "profile_id"
  >;
  "ledger.prorrata.settle_sector": Omit<
    LedgerProrrataContracts["ledger.prorrata.settle_sector"]["request"],
    "profile_id"
  >;
  "ledger.prorrata.declare_gross": Omit<
    LedgerProrrataContracts["ledger.prorrata.declare_gross"]["request"],
    "profile_id"
  >;
  "ledger.prorrata.remove_gross": Omit<
    LedgerProrrataContracts["ledger.prorrata.remove_gross"]["request"],
    "profile_id"
  >;
  "ledger.retencion_soportada.list": Omit<
    LedgerWithholdingContracts["ledger.retencion_soportada.list"]["request"],
    "profile_id"
  >;
  "ledger.retencion_soportada.list_absences": Omit<
    LedgerWithholdingContracts["ledger.retencion_soportada.list_absences"]["request"],
    "profile_id"
  >;
  "ledger.retencion_soportada.record": WithholdingRecordRequest;
  "ledger.retencion_soportada.remove": Omit<
    LedgerWithholdingContracts["ledger.retencion_soportada.remove"]["request"],
    "profile_id"
  >;
  "ledger.retencion_soportada.attest_absence": Omit<
    LedgerWithholdingContracts["ledger.retencion_soportada.attest_absence"]["request"],
    "profile_id"
  >;
  "ledger.retencion_soportada.withdraw_absence": Omit<
    LedgerWithholdingContracts["ledger.retencion_soportada.withdraw_absence"]["request"],
    "profile_id"
  >;
  "ledger.bienes_inversion.list": Omit<
    LedgerCapitalGoodsContracts["ledger.bienes_inversion.list"]["request"],
    "profile_id"
  >;
  "ledger.bienes_inversion.declare": Omit<
    LedgerCapitalGoodsContracts["ledger.bienes_inversion.declare"]["request"],
    "profile_id"
  >;
  "ledger.inventory.list": Record<string, never>;
  "ledger.inventory.create": InventoryCreateWindowRequest;
  "ledger.inventory.movement.add": InventoryMovementAddWindowRequest;
  "ledger.inventory.valuation.preview": InventoryInspectWindowRequest;
  "ledger.inventory.closing-authority.record": InventoryClosingAuthorityRecordWindowRequest;
  "ledger.inventory.closing-value.record": InventoryClosingValueRecordWindowRequest;
  "ledger.inventory.evidence.add": InventoryEvidenceAddWindowRequest;
  "ledger.inventory.options": Record<string, never>;
  "ledger.entry-options": LedgerEntryOptionsRequest;
  "ledger.inventory.inspect": InventoryInspectWindowRequest;
  "ledger.inventory.describe": InventoryDescribeWindowRequest;
  "ledger.inventory.correct": InventoryCorrectWindowRequest;
  "ledger.inventory.movement.claim": InventoryMovementClaimWindowRequest;
  "ledger.inventory.movement.correct": InventoryMovementCorrectWindowRequest;
  "ledger.inventory.movement.reverse": InventoryMovementReverseWindowRequest;
  "ledger.inventory.retire": InventoryRetireWindowRequest;
  "ledger.inventory.restore": InventoryRestoreWindowRequest;
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
  "ledger.known-values": LedgerReadContracts["ledger.known-values"]["result"];
  "ledger.list": LedgerReadContracts["ledger.list"]["result"];
  "ledger.view": LedgerReadContracts["ledger.view"]["result"];
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
  "ledger.status": LedgerReadContracts["ledger.status"]["result"];
  "ledger.preflight": LedgerReadContracts["ledger.preflight"]["result"];
  "ledger.import": LedgerTransferContracts["ledger.import"]["result"];
  "ledger.export": LedgerTransferContracts["ledger.export"]["result"];
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
  "ledger.own_account": LedgerOwnAccountContracts["ledger.own_account"]["result"];
  "ledger.prorrata.list": LedgerProrrataContracts["ledger.prorrata.list"]["result"];
  "ledger.prorrata.seed": LedgerProrrataContracts["ledger.prorrata.seed"]["result"];
  "ledger.prorrata.declare_sector": LedgerProrrataContracts["ledger.prorrata.declare_sector"]["result"];
  "ledger.prorrata.elect_general": LedgerProrrataContracts["ledger.prorrata.elect_general"]["result"];
  "ledger.prorrata.elect_especial": LedgerProrrataContracts["ledger.prorrata.elect_especial"]["result"];
  "ledger.prorrata.revoke_especial": LedgerProrrataContracts["ledger.prorrata.revoke_especial"]["result"];
  "ledger.prorrata.seed_sector": LedgerProrrataContracts["ledger.prorrata.seed_sector"]["result"];
  "ledger.prorrata.settle_sector": LedgerProrrataContracts["ledger.prorrata.settle_sector"]["result"];
  "ledger.prorrata.declare_gross": LedgerProrrataContracts["ledger.prorrata.declare_gross"]["result"];
  "ledger.prorrata.remove_gross": LedgerProrrataContracts["ledger.prorrata.remove_gross"]["result"];
  "ledger.retencion_soportada.list": LedgerWithholdingContracts["ledger.retencion_soportada.list"]["result"];
  "ledger.retencion_soportada.list_absences": LedgerWithholdingContracts["ledger.retencion_soportada.list_absences"]["result"];
  "ledger.retencion_soportada.record": LedgerWithholdingContracts["ledger.retencion_soportada.record"]["result"];
  "ledger.retencion_soportada.remove": LedgerWithholdingContracts["ledger.retencion_soportada.remove"]["result"];
  "ledger.retencion_soportada.attest_absence": LedgerWithholdingContracts["ledger.retencion_soportada.attest_absence"]["result"];
  "ledger.retencion_soportada.withdraw_absence": LedgerWithholdingContracts["ledger.retencion_soportada.withdraw_absence"]["result"];
  "ledger.bienes_inversion.list": LedgerCapitalGoodsContracts["ledger.bienes_inversion.list"]["result"];
  "ledger.bienes_inversion.declare": LedgerCapitalGoodsContracts["ledger.bienes_inversion.declare"]["result"];
  "ledger.inventory.list": InventoryListProjection;
  "ledger.inventory.create": InventoryCreateProjection;
  "ledger.inventory.movement.add": InventoryMovementAddProjection;
  "ledger.inventory.valuation.preview": InventoryValuationOperationProjection;
  "ledger.inventory.closing-authority.record": InventoryClosingAuthorityOperationProjection;
  "ledger.inventory.closing-value.record": InventoryClosingAuthorityOperationProjection;
  "ledger.inventory.evidence.add": InventoryEvidenceAddProjection;
  "ledger.inventory.options": InventoryOptionsProjection;
  "ledger.entry-options": LedgerEntryOptionsResult;
  "ledger.inventory.inspect": InventoryInspectProjection;
  "ledger.inventory.describe": InventoryLedgerChangeProjection;
  "ledger.inventory.correct": InventoryLedgerChangeProjection;
  "ledger.inventory.movement.claim": InventoryLedgerChangeProjection;
  "ledger.inventory.movement.correct": InventoryLedgerChangeProjection;
  "ledger.inventory.movement.reverse": InventoryLedgerChangeProjection;
  "ledger.inventory.retire": InventoryLedgerChangeProjection;
  "ledger.inventory.restore": InventoryLedgerChangeProjection;
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

/** An own account's number and bank block: private input the host refuses
 * in an ordinary request, so it travels only in `changeOwnAccount`'s bytes. */
type OwnAccountSecret =
  | "iban"
  | "swift_bic"
  | "bank_name"
  | "bank_address"
  | "bank_city"
  | "bank_country_code";

type OwnAccountRequest =
  LedgerOwnAccountContracts["ledger.own_account"]["request"];

/** An own account added or changed, with its number or bank block. */
export type OwnAccountChange = Omit<
  OwnAccountRequest,
  "profile_id" | "action" | "closed_on" | "role" | "modelo"
> & { action: Extract<OwnAccountRequest["action"], "add" | "update"> };

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
    format: ExportSerializationFormat,
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
