// The operations the Assets tab reads and writes before the backend serves
// them. Their names and shapes are drafts: they are kept apart from the
// admitted list so no page can send one to the host, and the one cast that
// lets a story's port answer them is `submitProvisional`. When the backend
// lands, the shapes move to the ledger's setup contract, the ids join the
// admitted list, and this module goes; the compiler then names every
// consumer.

import type {
  LedgerDefinitionId,
  LedgerOutcome,
  LedgerPort,
  PublicDecimal,
} from "../../../shell/ledger";
import type {
  ActivityAssetForecast,
  ActivityAssetForecastRequest,
  ActivityAssetRefusal,
} from "../../../shell/ledgerSetup";

/** An amount the backend states or does not. Null is unknown and never
 * zero; a recorded zero is `{ decimal: "0.00" }`. */
export type Amount = PublicDecimal | null;

// ---- The element list ----------------------------------------------------

/** How many years of an element need a person's attention, by kind. */
export type AssetCounts = {
  missing: number;
  incomplete: number;
  conflict: number;
  stale: number;
};

/** An element's baja: the date entered is its last day of service. */
export type AssetBaja = { date: string; reason_key: string };

export type AssetListRow = {
  asset_id: string;
  /** From the element's latest descriptor; null until one is recorded. */
  name: string | null;
  serial: string | null;
  kind_key: string;
  method_key: string;
  in_service_date: string;
  revision_number: number;
  baja?: AssetBaja | null;
  counts: AssetCounts;
};

export type AssetListResult = {
  rows: AssetListRow[];
  /** The tax years the stepper offers, as the backend reports them. */
  years: number[];
};

// ---- The amortization plan -----------------------------------------------

export type PlanAuthority = {
  edition: string;
  /** Rates carried forward from the last edition: they serve the forecast
   * and Modelo 130, not Modelo 100. */
  projected: boolean;
};

/** The method election a year stands on; a new fingerprint is a change. */
export type PlanElection = {
  fingerprint: string;
  method_key: string;
  revision_number: number;
};

export type PlanClaim = {
  claim_id: string;
  amount: Amount;
  from: string;
  until: string;
  effective: boolean;
  superseded_by: string | null;
  /** The revision the claim was recorded under. */
  revision_number: number;
  matches_current_schedule: boolean;
  used_by: string[];
};

export type PlanRow = {
  tax_year: number;
  state_key: string;
  finding_keys: string[];
  authority: PlanAuthority;
  election: PlanElection;
  service_days: number | null;
  calendar_days: number | null;
  planned: Amount;
  /** Why `planned` is null. */
  planned_absent_key: string | null;
  claimed: Amount;
  /** The value still to amortize at the year's end. */
  pending_end: Amount;
  claimable: { from: string; until: string } | null;
  claims: PlanClaim[];
};

// ---- The append-only timeline --------------------------------------------

export type TimelineChange = {
  field_key: string;
  before: string | null;
  after: string | null;
};

export type TimelineEvent = {
  sequence: number;
  /** Null for an event recorded before time was kept. */
  recorded_at: string | null;
  type_key: string;
  origin_key: string;
  effect_date: string | null;
  replaces_sequence: number | null;
  changes: TimelineChange[];
  affects_calculation: boolean;
};

// ---- Forms ---------------------------------------------------------------

export type FormKind =
  "element" | "descriptor" | "correction" | "claim" | "baja";

/** `candidate` is a choice among the purchases the backend offers, picked
 * and never typed. */
export type FormControl =
  "text" | "date" | "amount" | "whole" | "choice" | "flag" | "candidate";

export type FormField = {
  key: string;
  label_key: string;
  control: FormControl;
  required: boolean;
  choices: { token: string; label_key: string }[];
  /** The least and most a date or an amount may be, as text. */
  bounds: { min: string | null; max: string | null } | null;
  /** What the record states now, as text, where the form starts from it;
   * null or absent where it states nothing. */
  current?: string | null;
  /** The word that says how to write the value. */
  hint_key?: string | null;
};

export type FormOptions = {
  kind: FormKind;
  tax_year: number | null;
  fields: FormField[];
  /** The number the next descriptor, revision or claim of this act takes,
   * where the act is numbered. */
  next_sequence?: number | null;
};

export type DescriptorField = { key: string; value: string | null };

export type Descriptor = {
  asset_id: string;
  sequence: number;
  name: string | null;
  serial: string | null;
  fields: DescriptorField[];
};

/** A purchase an element can come from. `values` states what the purchase
 * gives each field of the add form, by field key; null is not known, never
 * zero. */
export type AcquisitionCandidate = {
  candidate_id: string;
  description: string;
  date: string;
  amount: Amount;
  values: Record<string, string | null>;
};

/** What a form states, by field key: text, a decimal, a whole number, a
 * choice's token, a flag, or null where nothing was stated. */
export type FormValue = string | number | boolean | PublicDecimal | null;
export type FormValues = Record<string, FormValue>;

// ---- Operations ----------------------------------------------------------

export type ResultBase = {
  outcome: "succeeded" | "refused";
  refusal: (ActivityAssetRefusal & { reason_key?: string | null }) | null;
};

/** Whether an operation may change records: the host's class once admitted. */
export const PROVISIONAL_OPERATIONS = {
  "ledger.actividad-asset.list": { effect: "read" },
  "ledger.actividad-asset.plan": { effect: "read" },
  "ledger.actividad-asset.timeline": { effect: "read" },
  "ledger.actividad-asset.form-options": { effect: "read" },
  "ledger.actividad-asset.acquisition-candidates": { effect: "read" },
  "ledger.actividad-asset.describe": { effect: "write" },
  "ledger.actividad-asset.dispose": { effect: "write" },
} as const satisfies Record<string, { effect: "read" | "write" }>;

export type ProvisionalOperationId = keyof typeof PROVISIONAL_OPERATIONS;

export function isProvisionalOperation(
  id: string,
): id is ProvisionalOperationId {
  return Object.hasOwn(PROVISIONAL_OPERATIONS, id);
}

export type ProvisionalRequests = {
  "ledger.actividad-asset.list": Record<string, never>;
  "ledger.actividad-asset.plan": { asset_id: string };
  "ledger.actividad-asset.timeline": { asset_id: string };
  "ledger.actividad-asset.form-options": {
    kind: FormKind;
    asset_id?: string;
    tax_year?: number;
    supersedes_claim_id?: string;
  };
  "ledger.actividad-asset.acquisition-candidates": Record<string, never>;
  "ledger.actividad-asset.describe": {
    asset_id: string;
    name: string | null;
    serial: string | null;
    fields: DescriptorField[];
  };
  "ledger.actividad-asset.dispose": {
    asset_id: string;
    date: string | null;
    reason_key: string | null;
  };
};

export type ProvisionalResults = {
  "ledger.actividad-asset.list": ResultBase & AssetListResult;
  "ledger.actividad-asset.plan": ResultBase & {
    asset_id: string;
    rows: PlanRow[];
  };
  "ledger.actividad-asset.timeline": ResultBase & {
    asset_id: string;
    events: TimelineEvent[];
  };
  "ledger.actividad-asset.form-options": ResultBase & {
    options: FormOptions | null;
  };
  "ledger.actividad-asset.acquisition-candidates": ResultBase & {
    candidates: AcquisitionCandidate[];
  };
  "ledger.actividad-asset.describe": ResultBase & {
    descriptor: Descriptor | null;
  };
  "ledger.actividad-asset.dispose": ResultBase & {
    baja: AssetBaja | null;
    /** The effective claims the baja replaced in the same write. */
    superseded_claim_ids: string[];
  };
};

/**
 * Submits a provisional operation through the page's port, which answers it
 * only where the scenario host does. The port's type names admitted
 * definitions alone, so the id and payload cross it here and nowhere else.
 */
export function submitProvisional<D extends ProvisionalOperationId>(
  port: LedgerPort,
  id: D,
  payload: ProvisionalRequests[D],
): Promise<LedgerOutcome<ProvisionalResults[D]>> {
  return port.submit(
    id as unknown as LedgerDefinitionId,
    payload as never,
  ) as unknown as Promise<LedgerOutcome<ProvisionalResults[D]>>;
}

// ---- The admitted operations in their drafted shapes ----------------------

/** The admitted operations whose request and answer the backend is changing:
 * they keep their ids, and these are the shapes the Assets tab sends and
 * reads until the admitted types conform. A forecast keeps its admitted
 * shape. */
export type DraftedOperationId =
  | "ledger.actividad-asset.forecast"
  | "ledger.actividad-asset.claim"
  | "ledger.actividad-asset.create"
  | "ledger.actividad-asset.correct";

/** The claim a new claim overlaps, as the backend states it. */
export type ClaimConflict = {
  claim_id: string;
  from: string;
  until: string;
  amount: Amount;
};

export type DraftedRequests = {
  "ledger.actividad-asset.forecast": ActivityAssetForecastRequest;
  "ledger.actividad-asset.claim": {
    forecast: ActivityAssetForecast;
    /** The claim this one replaces, in the same write. */
    supersedes_claim_id: string | null;
  };
  /** The element's id is minted by the window and never shown. */
  "ledger.actividad-asset.create": { asset_id: string; values: FormValues };
  "ledger.actividad-asset.correct": {
    asset_id: string;
    /** The revision the person was looking at. */
    revision_number: number;
    /** Only the facts that change. */
    values: FormValues;
    /** Effective claims recorded again under the corrected figures, in the
     * same write. */
    supersede_claim_ids: string[];
  };
};

export type DraftedResults = {
  "ledger.actividad-asset.forecast": ResultBase & {
    forecast: ActivityAssetForecast | null;
  };
  "ledger.actividad-asset.claim": ResultBase & {
    claim_id: string | null;
    reused_existing_claim: boolean;
    superseded_claim_id: string | null;
    conflicting_claim: ClaimConflict | null;
  };
  "ledger.actividad-asset.create": ResultBase & {
    asset_id: string | null;
    reused_existing_element: boolean;
  };
  "ledger.actividad-asset.correct": ResultBase & {
    revision_number: number | null;
    superseded_claim_ids: string[];
  };
};

/** Submits an admitted operation with its drafted request, as the scenario
 * ledger answers it. The port's type names the admitted shapes alone, so the
 * payload crosses it here and nowhere else. */
export function submitDrafted<D extends DraftedOperationId>(
  port: LedgerPort,
  id: D,
  payload: DraftedRequests[D],
): Promise<LedgerOutcome<DraftedResults[D]>> {
  return port.submit(id, payload as never) as unknown as Promise<
    LedgerOutcome<DraftedResults[D]>
  >;
}
