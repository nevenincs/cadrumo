// What the Assets tab's forms decide without drawing: how each act's request
// is put together from the values a form states, how a read of the register
// says whether a write held in doubt landed, and how a refusal is read. The
// options a form shows, the units of a request and every verdict come from the
// backend; nothing here lists a method, a reason or a year.

import { listed } from "../../../shell/compose";
import type { LedgerPort, OutputLanguage } from "../../../shell/ledger";
import { sameDecimal } from "../../../shell/ledgerGrammar";
import type {
  AcquisitionCandidate,
  ActivityAssetDescribeRequest,
  ActivityAssetFilingRequest,
  ActivityAssetForecastRequest,
  ActivityAssetListResult,
  DescriptorFacts,
  DisposalFacts,
  PlanClaim,
  PlanRow,
  ReasonFact,
  ReasonFactKind,
  TimelineEvent,
} from "../../../shell/ledgerSetup";
import type { Translate } from "../../../shell/strings";
import { setupCall, type SetupCall } from "../setup/setupModel";
import type { Landing, LandingCheck } from "../WritePause";
import {
  formKeyOf,
  type FormField,
  type FormValue,
  type FormValues,
} from "./assetFields";
import { fieldWord, reasonText } from "./assetsWords";

const textOf = (found: FormValue | undefined): string | null =>
  typeof found === "string" ? found : null;
const amountOf = (found: FormValue | undefined) =>
  found !== null && typeof found === "object" ? found : null;

/** The descriptor a description states: every fact the form holds, so what
 * the person left as it was is stated again as it was. */
export const describeRequest = (
  assetId: string,
  values: FormValues,
): ActivityAssetDescribeRequest => {
  const descriptor: DescriptorFacts = {
    name: textOf(values.name) ?? "",
    serial_number: textOf(values.serial_number),
    description: textOf(values.description),
    document_kind: textOf(values.document_kind),
    document_number: textOf(values.document_number),
    supplier_name: textOf(values.supplier_name),
    supplier_tax_id: textOf(values.supplier_tax_id),
  };
  return { asset_id: assetId, descriptor };
};

/** What a purchase states for the figures of the add form, by field key; null
 * where the ledger does not know it, which is never read as zero. */
export function purchaseValues(
  purchase: AcquisitionCandidate | undefined,
): Record<string, string | null> {
  return {
    basis_amount: purchase?.taxable_base?.decimal ?? null,
    non_deductible_iva:
      purchase?.non_deductible_iva_state === "known"
        ? (purchase.non_deductible_iva?.decimal ?? null)
        : null,
  };
}

/** What a baja states, from the form: the last day of service, the reason, the
 * amounts and the optional facts. Null while a fact every baja states is
 * missing: none is read as zero. The backend judges the rest by the reason. */
export function disposalOf(values: FormValues): DisposalFacts | null {
  const date = textOf(values.date);
  const reason = textOf(values.reason);
  const proceeds = amountOf(values.proceeds);
  const costs = amountOf(values.transmission_costs);
  if (date === null || reason === null || proceeds === null || costs === null)
    return null;
  return {
    disposal_date: date,
    reason,
    proceeds,
    transmission_costs: costs,
    market_value: amountOf(values.market_value),
    prior_free_depreciation_regime: textOf(
      values.prior_free_depreciation_regime,
    ),
    later_affectation_on: textOf(values.later_affectation_on),
  };
}

/** The forecast of a span; null while the span lacks its first or its last
 * day. The last day is the one typed, sent as it stands: no day is worked
 * out here. */
export function forecastRequest(
  assetId: string,
  values: FormValues,
  supersedes: string | null,
): ActivityAssetForecastRequest | null {
  const from = textOf(values.covered_from);
  const through = textOf(values.covered_through);
  if (from === null || through === null) return null;
  return {
    asset_id: assetId,
    covered_from: from,
    covered_through: through,
    requested_free_amount: amountOf(values.free_amount),
    supersedes_claim_id: supersedes,
  };
}

/** The read of where a year's claims go: the year alone states the
 * Modelo 100 boxes, and a quarter, where one is chosen, adds Modelo 130. No
 * quarter is invented for a year without one. */
export const handoffRequest = (
  year: number,
  period: string,
  language: OutputLanguage,
): ActivityAssetFilingRequest => ({
  tax_year: year,
  output_language: language,
  ...(period === "" ? {} : { m130_period: period }),
});

/** The fact of an overlap refusal that names the recorded dotaciones in the
 * way, comma-joined. It says which one to offer to correct and is never
 * drawn. */
export const CONFLICTING_CLAIMS = "conflicting_claim_ids";

/** The one recorded dotación a refusal says is in the way; null where it
 * names none or several. */
export function claimInTheWay(
  reasonFacts: readonly ReasonFact[],
): string | null {
  const named = reasonFacts.find((fact) => fact.key === CONFLICTING_CLAIMS);
  if (named === undefined) return null;
  const ids = named.value.split(",").filter((id) => id !== "");
  return ids.length === 1 ? ids[0]! : null;
}

// ---- What the register says of a write held in doubt ---------------------------

const listLanding =
  (
    port: LedgerPort,
    judge: (list: ActivityAssetListResult) => Landing,
  ): LandingCheck =>
  async () => {
    const read = await setupCall(
      port,
      "ledger.actividad-asset.list",
      {},
      false,
    );
    return read.kind === "done" ? judge(read.result) : null;
  };

export const elementLanding = (port: LedgerPort, assetId: string) =>
  listLanding(port, (list) => elementLanded(list, assetId));
export const correctionLanding = (
  port: LedgerPort,
  assetId: string,
  superseded: number,
) => listLanding(port, (list) => correctionLanded(list, assetId, superseded));

/** A description landed if the element's history holds as many as the write
 * would have made. */
export const descriptorLanding =
  (port: LedgerPort, assetId: string, count: number): LandingCheck =>
  async () => {
    const read = await setupCall(
      port,
      "ledger.actividad-asset.timeline",
      { asset_id: assetId },
      false,
    );
    return read.kind === "done" && read.result.events !== null
      ? descriptorLanded(read.result.events, count)
      : null;
  };

export type SentClaim = {
  tax_year: number;
  from: string;
  until: string;
  amount: string;
};

export const claimLanding =
  (port: LedgerPort, assetId: string, sent: SentClaim): LandingCheck =>
  async () => {
    const read = await setupCall(
      port,
      "ledger.actividad-asset.plan",
      { asset_id: assetId },
      false,
    );
    return read.kind === "done" && read.result.rows !== null
      ? claimLanded(read.result.rows, sent)
      : null;
  };

/** An add landed if the register lists the id the window minted. */
export function elementLanded(
  list: ActivityAssetListResult,
  assetId: string,
): Landing {
  return (list.rows ?? []).some((row) => row.asset_id === assetId)
    ? "saved"
    : "not_saved";
}

/** A correction landed if the element stands past the revision it
 * superseded; an element the register no longer lists cannot be told. */
export function correctionLanded(
  list: ActivityAssetListResult,
  assetId: string,
  superseded: number,
): Landing {
  const found = (list.rows ?? []).find((row) => row.asset_id === assetId);
  if (!found) return "untold";
  return found.revision_number > superseded ? "saved" : "not_saved";
}

/** A description landed if the element's history holds at least `count`. */
export function descriptorLanded(
  events: readonly TimelineEvent[],
  count: number,
): Landing {
  const described = events.filter((event) => event.kind === "descriptor");
  return described.length >= count ? "saved" : "not_saved";
}

/** A claim landed if its year holds an effective claim of that span and
 * amount; a year the plan no longer holds cannot be told. */
export function claimLanded(
  rows: readonly PlanRow[],
  sent: SentClaim,
): Landing {
  const year = rows.find((row) => row.tax_year === sent.tax_year);
  if (!year) return "untold";
  return year.claims.some(
    (claim) =>
      claim.effective &&
      claim.covered_from === sent.from &&
      claim.covered_until === sent.until &&
      sameDecimal(claim.amount.decimal, sent.amount),
  )
    ? "saved"
    : "not_saved";
}

/** The effective claims that no longer match the schedule, with their year:
 * the ones a correction can record again in the same write. The plan states
 * on each claim whether it is in effect and whether it still matches. */
export function staleClaims(
  rows: readonly PlanRow[],
): { year: number; claim: PlanClaim }[] {
  return rows.flatMap((row) =>
    row.claims
      .filter((claim) => claim.effective && !claim.matches_current_schedule)
      .map((claim) => ({ year: row.tax_year, claim })),
  );
}

/** The element's descriptor as it stands: for each fact, the latest value the
 * history states for it. A fact the history has cleared is null. */
export function currentDescriptor(
  events: readonly TimelineEvent[],
): DescriptorFacts {
  const facts: Record<string, string | null> = {};
  for (const event of events) {
    if (event.kind !== "descriptor") continue;
    for (const change of event.changes) facts[change.field] = change.after;
  }
  return {
    name: facts.name ?? "",
    serial_number: facts.serial_number ?? null,
    description: facts.description ?? null,
    document_kind: facts.document_kind ?? null,
    document_number: facts.document_number ?? null,
    supplier_name: facts.supplier_name ?? null,
    supplier_tax_id: facts.supplier_tax_id ?? null,
  };
}

// ---- How a write ended -----------------------------------------------------------

/** The refusal code this tab treats apart. */
export const INCOMPLETE = "REFUSED_ACTIVIDAD_ASSET_INCOMPLETE";
/** The refusal of a dotación that meets one already recorded, and its reason. */
export const CLAIM_CONFLICT = "REFUSED_ACTIVIDAD_ASSET_CLAIM_CONFLICT";
export const CLAIMS_OVERLAP = "ledger.actividad_asset.errors.claims_overlap";

export type Refusal = {
  code: string | null;
  reasonKey: string | null;
  reasonFacts: ReasonFact[];
  /** The fields the backend says are still to fill in. */
  missing: string[];
};

export type WriteView =
  | { kind: "none" }
  | { kind: "saved"; reused: boolean }
  /** `reason` is the host's own closed token for a refusal that carries no
   * detail of the register's. */
  | ({ kind: "refused"; reason: string | null } & Refusal)
  | { kind: "failed" | "unknown" | "saved_unread" };

const asRecord = (found: unknown): Record<string, unknown> | null =>
  typeof found === "object" && found !== null && !Array.isArray(found)
    ? (found as Record<string, unknown>)
    : null;

const FACT_KINDS: readonly string[] = [
  "text",
  "date",
  "amount",
  "percent",
  "count",
];
const isFactKind = (found: unknown): found is ReasonFactKind =>
  typeof found === "string" && FACT_KINDS.includes(found);

/** The refusal in a result or in the detail of a refused outcome. */
export function refusalOf(body: unknown): Refusal {
  const result = asRecord(body);
  const refusal = asRecord(result?.refusal);
  const verdict = asRecord(refusal?.precondition_verdict);
  const missing = Array.isArray(verdict?.missing_field_keys)
    ? verdict.missing_field_keys.filter(
        (key): key is string => typeof key === "string",
      )
    : [];
  const facts = Array.isArray(refusal?.reason_facts)
    ? refusal.reason_facts.flatMap((fact): ReasonFact[] => {
        const found = asRecord(fact);
        return typeof found?.key === "string" &&
          typeof found.value === "string" &&
          isFactKind(found.kind)
          ? [{ key: found.key, value: found.value, kind: found.kind }]
          : [];
      })
    : [];
  return {
    code: typeof refusal?.code === "string" ? refusal.code : null,
    reasonKey:
      typeof refusal?.reason_key === "string" ? refusal.reason_key : null,
    reasonFacts: facts,
    missing,
  };
}

/** How the last call of a form ended, for the line under it. `reused` says
 * whether a settled answer found the record already there. */
export function viewOf(
  call: SetupCall<unknown> | null,
  reused: (result: unknown) => boolean,
): WriteView {
  if (call === null) return { kind: "none" };
  if (call.kind === "done") {
    return asRecord(call.result)?.outcome === "refused"
      ? { kind: "refused", reason: null, ...refusalOf(call.result) }
      : { kind: "saved", reused: reused(call.result) };
  }
  if (call.kind === "refused")
    return { kind: "refused", reason: call.reason, ...refusalOf(call.detail) };
  return { kind: call.kind };
}

export const claimReused = (result: unknown) =>
  asRecord(asRecord(result)?.claim_result)?.reused_existing_claim === true;
export const neverReused = () => false;

// ---- Words for a refusal ---------------------------------------------------------

/** A refusal in words by its reason: the catalogue sentence the backend named,
 * filled in with its facts, else null where the caller shows the generic
 * refused word. */
export const refusalWord = (
  t: Translate,
  refusal: Pick<Refusal, "reasonKey" | "reasonFacts">,
): string | null => reasonText(t, refusal.reasonKey, refusal.reasonFacts);

/** The fields still to fill in, by their labels. */
export function missingLabels(
  t: Translate,
  fields: readonly FormField[],
  keys: readonly string[],
): string {
  return listed(
    t,
    keys.map((key) => {
      const found = fields.find((field) => field.key === formKeyOf(key));
      return found ? t(found.label_key) : fieldWord(t, key);
    }),
  );
}
