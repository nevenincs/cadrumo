// The window's names for the request and result of the ledger operations the
// Setup sections submit for the inventory and activity asset registers, the
// entry options, and the declaration-link rebuild and reset. Each is the
// registered Python contract's own type, taken from the generated modules by
// definition id, so no field is written here. A request leaves out the
// profile and the folder it fills for a chosen document. A refused result
// comes back as the refusal's detail, in the same shape.

import type { LedgerActivityAssetContracts } from "./ledgerActivityAssetContract";
import type { LedgerActivityAssetReadContracts } from "./ledgerActivityAssetReadContract";
import type { LedgerEntryContracts } from "./ledgerEntryContract";
import type { LedgerInventoryContracts } from "./ledgerInventoryContract";

type Contracts = LedgerInventoryContracts &
  LedgerActivityAssetContracts &
  LedgerActivityAssetReadContracts &
  LedgerEntryContracts;
type Definition = keyof Contracts;

/** What the window sends: the registered request without the profile and
 * without the `Host` fields the host fills. */
type Sent<D extends Definition, Host extends string = never> = Omit<
  Contracts[D]["request"],
  "profile_id" | Host
>;

/** What the operation serves. */
type Served<D extends Definition> = Contracts[D]["result"];

// ---- Inventory -----------------------------------------------------------

export type InventoryListResult = Served<"ledger.inventory.list">;
export type InventoryBookRow = InventoryListResult["rows"][number];
export type ValuationMethod = InventoryBookRow["valuation_method"];

export type InventoryInspectResult = Served<"ledger.inventory.inspect">;
export type InventoryBook = NonNullable<InventoryInspectResult["ledger"]>;
export type InventoryRefusal = NonNullable<InventoryInspectResult["refusal"]>;
export type InventoryAdvisory = InventoryBook["advisories"][number];
export type InventoryMovement = InventoryBook["period_movements"][number];
export type InventoryHistoryEntry = InventoryBook["history"][number];
export type InventoryHistoryKind = InventoryHistoryEntry["kind"];

export type InventoryCreateRequest = Sent<"ledger.inventory.create">;
export type InventoryCreateResult = Served<"ledger.inventory.create">;

export type InventoryMovementAddRequest = Sent<"ledger.inventory.movement.add">;
export type InventoryMovementAddResult =
  Served<"ledger.inventory.movement.add">;
export type InventoryAcquisitionCostRequest = NonNullable<
  InventoryMovementAddRequest["acquisition_cost"]
>;
/** A named piece of proof: a fingerprint of the file the person attached,
 * under a reference minted for it. */
export type InventoryProof =
  InventoryAcquisitionCostRequest["evidence"][number];

export type InventoryBookRequest = Sent<"ledger.inventory.inspect">;
export type InventoryValuationResult =
  Served<"ledger.inventory.valuation.preview">;

export type InventoryClosingAuthorityRequest =
  Sent<"ledger.inventory.closing-authority.record">;
export type InventoryClosingAuthorityResult =
  Served<"ledger.inventory.closing-authority.record">;
export type InventoryClosingValueRequest =
  Sent<"ledger.inventory.closing-value.record">;
export type InventoryOptionsResult = Served<"ledger.inventory.options">;

export type InventoryEvidenceAddRequest = Sent<
  "ledger.inventory.evidence.add",
  "source_directory"
>;
export type InventoryEvidenceAddResult =
  Served<"ledger.inventory.evidence.add">;

export type InventoryDescribeRequest = Sent<"ledger.inventory.describe">;
export type InventoryCorrectRequest = Sent<"ledger.inventory.correct">;
export type InventoryMovementCorrectRequest =
  Sent<"ledger.inventory.movement.correct">;
export type InventoryMovementReverseRequest =
  Sent<"ledger.inventory.movement.reverse">;
export type InventoryMovementClaimRequest =
  Sent<"ledger.inventory.movement.claim">;
export type InventoryRetireRequest = Sent<"ledger.inventory.retire">;
export type InventoryRestoreRequest = Sent<"ledger.inventory.restore">;

/** A change applied, or found already applied under the same reference. */
export type InventoryChangeResult = Served<"ledger.inventory.correct">;

// ---- Activity assets -----------------------------------------------------

export type ActivityAssetCreateRequest = Sent<"ledger.actividad-asset.create">;
export type ActivityAssetCorrectRequest =
  Sent<"ledger.actividad-asset.correct">;
/** The revision a correction states: the one it supersedes, whole, with what
 * the person changed. */
export type ActivityAssetCorrection = ActivityAssetCorrectRequest["revision"];
export type ActivityAssetRevision = ActivityAssetCreateRequest["revision"];
export type ActivityAssetChangeResult = Served<"ledger.actividad-asset.create">;
export type ActivityAssetRefusal = NonNullable<
  ActivityAssetChangeResult["refusal"]
>;
export type ReasonFact = ActivityAssetRefusal["reason_facts"][number];
export type ReasonFactKind = ReasonFact["kind"];

export type ActivityAssetInspectRequest =
  Sent<"ledger.actividad-asset.inspect">;
export type ActivityAssetInspectResult =
  Served<"ledger.actividad-asset.inspect">;

export type ActivityAssetForecastRequest =
  Sent<"ledger.actividad-asset.forecast">;
export type ActivityAssetForecastResult =
  Served<"ledger.actividad-asset.forecast">;
/** A scheduled charge: a forecast records nothing until it is claimed. */
export type ActivityAssetForecast = NonNullable<
  ActivityAssetForecastResult["forecast"]
>;

export type ActivityAssetClaimRequest = Sent<"ledger.actividad-asset.claim">;
export type ActivityAssetClaimResult = Served<"ledger.actividad-asset.claim">;

export type ActivityAssetDescribeRequest =
  Sent<"ledger.actividad-asset.describe">;
/** What the operator states about an element, none of it a tax fact. */
export type DescriptorFacts = ActivityAssetDescribeRequest["descriptor"];
export type ActivityAssetDisposeRequest =
  Sent<"ledger.actividad-asset.dispose">;
/** What a baja states. */
export type DisposalFacts = ActivityAssetDisposeRequest["disposal"];

export type ActivityAssetFilingRequest =
  Sent<"ledger.actividad-asset.filing-handoff">;
export type ActivityAssetFilingResult =
  Served<"ledger.actividad-asset.filing-handoff">;

// ---- The element list ----------------------------------------------------

export type ActivityAssetListRequest = Sent<"ledger.actividad-asset.list">;
export type ActivityAssetListResult = Served<"ledger.actividad-asset.list">;
export type AssetListRow = NonNullable<ActivityAssetListResult["rows"]>[number];
export type AssetKind = AssetListRow["asset_kind"];
export type AssetCounts = AssetListRow["findings"];
export type ListDisposal = NonNullable<AssetListRow["disposal"]>;

// ---- The amortization plan -----------------------------------------------

export type ActivityAssetPlanRequest = Sent<"ledger.actividad-asset.plan">;
export type ActivityAssetPlanResult = Served<"ledger.actividad-asset.plan">;
export type PlanRow = NonNullable<ActivityAssetPlanResult["rows"]>[number];
export type PlanClaim = PlanRow["claims"][number];
export type ElectionLimits = NonNullable<ActivityAssetPlanResult["limits"]>;
export type LegalCitation = ElectionLimits["legal_citations"][number];

// ---- The append-only timeline --------------------------------------------

export type ActivityAssetTimelineRequest =
  Sent<"ledger.actividad-asset.timeline">;
export type ActivityAssetTimelineResult =
  Served<"ledger.actividad-asset.timeline">;
export type TimelineEvent = NonNullable<
  ActivityAssetTimelineResult["events"]
>[number];
export type TimelineChange = TimelineEvent["changes"][number];
export type TimelineClaimUse = NonNullable<TimelineEvent["claim"]>;

// ---- Form options and purchases ------------------------------------------

export type ActivityAssetFormOptionsRequest =
  Sent<"ledger.actividad-asset.form-options">;
export type ActivityAssetFormOptionsResult =
  Served<"ledger.actividad-asset.form-options">;
/** What the registry admits for one asset kind and tax year. */
export type FormOptions = NonNullable<
  ActivityAssetFormOptionsResult["options"]
>;
export type TableGroup = FormOptions["table_groups"][number];
export type DisposalReasonOption = FormOptions["disposal_reasons"][number];
export type MethodFact = FormOptions["method_facts"][number]["facts"][number];
export type MethodFactKind = MethodFact["kind"];
export type BasisStageOption = FormOptions["basis_stages"][number];
export type OpeningStatusOption = FormOptions["opening_statuses"][number];
export type ConditionOption = FormOptions["acquired_conditions"][number];

export type ActivityAssetAcquisitionCandidatesResult =
  Served<"ledger.actividad-asset.acquisition-candidates">;
/** A ledger payment an element could name as its acquisition. */
export type AcquisitionCandidate = NonNullable<
  ActivityAssetAcquisitionCandidatesResult["candidates"]
>[number];

// ---- A baja ----------------------------------------------------------------

export type ActivityAssetDisposalCalculateRequest =
  Sent<"ledger.actividad-asset.disposal-calculate">;
export type ActivityAssetDisposalCalculateResult =
  Served<"ledger.actividad-asset.disposal-calculate">;
export type DisposalCalculation = NonNullable<
  ActivityAssetDisposalCalculateResult["calculation"]
>;
export type DisposalFinding = DisposalCalculation["findings"][number];

// ---- Entry options -------------------------------------------------------

export type LedgerEntryOptionsRequest = Sent<"ledger.entry-options">;
export type LedgerEntryOptionsResult = Served<"ledger.entry-options">;
export type LedgerEntryClassification =
  LedgerEntryOptionsResult["classifications"][number];
export type LedgerEntryLimits = LedgerEntryOptionsResult["limits"];
export type TextLimitName = LedgerEntryLimits["text_limits"][number]["name"];
export type LedgerServedPeriods = LedgerEntryOptionsResult["periods"];
export type LedgerServedPeriod = LedgerServedPeriods["periods"][number];
export type LedgerServedDay = LedgerServedPeriods["containing"];

// ---- Declaration links and reset ----------------------------------------------------

export type LedgerParticipationRebuildResult =
  Served<"ledger.participation.rebuild">;
export type LedgerResetRequest = Sent<"ledger.reset">;
export type LedgerResetResult = Served<"ledger.reset">;
