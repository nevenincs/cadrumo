// What the Assets tab's forms decide without drawing: how typed text becomes
// the values of a request, how each act is sent, how a read of the register
// says whether a write held in doubt landed, and how a refusal is worded.
// The options a form shows, the units of a request and every verdict come
// from the backend; nothing here lists a method, a reason or a field.

import type { LedgerPort } from "../../../shell/ledger";
import {
  parseDecimal,
  parseIsoDate,
  parseLine,
  sameDecimal,
  TAX_AMOUNT_RULE,
  type GrammarRefusal,
  type Parsed,
} from "../../../shell/ledgerGrammar";
import type { ActivityAssetForecastRequest } from "../../../shell/ledgerSetup";
import type { Translate } from "../../../shell/strings";
import { callFailure, callOutcome, type SetupCall } from "../setup/setupModel";
import type { Landing, LandingCheck } from "../WritePause";
import {
  submitDrafted,
  submitProvisional,
  type AssetListResult,
  type ClaimConflict,
  type DraftedOperationId,
  type DraftedRequests,
  type DraftedResults,
  type FormField,
  type FormOptions,
  type FormValue,
  type FormValues,
  type PlanClaim,
  type PlanRow,
  type ProvisionalOperationId,
  type ProvisionalRequests,
  type ProvisionalResults,
  type TimelineEvent,
} from "./assetsContract";
import { fieldWord } from "./assetsWords";

// ---- Sending ----------------------------------------------------------------

/** One attempt at a provisional operation, and how it ended. A write that was
 * not seen to settle is unknown and is never sent again from here. */
export async function provisionalCall<D extends ProvisionalOperationId>(
  port: LedgerPort,
  id: D,
  payload: ProvisionalRequests[D],
  writes: boolean,
): Promise<SetupCall<ProvisionalResults[D]>> {
  try {
    return callOutcome(await submitProvisional(port, id, payload), writes);
  } catch (error) {
    return callFailure(error);
  }
}

/** The same for an admitted operation sent in its drafted shape. */
export async function draftedCall<D extends DraftedOperationId>(
  port: LedgerPort,
  id: D,
  payload: DraftedRequests[D],
  writes: boolean,
): Promise<SetupCall<DraftedResults[D]>> {
  try {
    return callOutcome(await submitDrafted(port, id, payload), writes);
  } catch (error) {
    return callFailure(error);
  }
}

// ---- Typed text into values ---------------------------------------------------

/** The text typed into each field of a form, by field key. */
export type FormDraft = Record<string, string>;

/** Each field starting from what the record states now. */
export const draftOf = (options: FormOptions): FormDraft =>
  Object.fromEntries(
    options.fields.map((field) => [field.key, field.current ?? ""]),
  );

/** What the options state as current, which is all a form's start depends
 * on: an answer that changes nothing there leaves what was typed alone. */
export const optionsSignature = (options: FormOptions): string =>
  JSON.stringify([
    options.kind,
    options.tax_year,
    options.fields.map((field) => [field.key, field.current ?? null]),
  ]);

const empty: Parsed<FormValue> = { kind: "empty" };
const value = (found: FormValue): Parsed<FormValue> => ({
  kind: "value",
  value: found,
});

/** One field's text as the value its control takes. Nothing typed is empty;
 * a refusal says why the text cannot be read. */
export function parseField(field: FormField, raw: string): Parsed<FormValue> {
  switch (field.control) {
    case "text":
      return parseLine(raw, 200);
    case "date":
      return parseIsoDate(raw);
    case "amount": {
      const parsed = parseDecimal(raw, TAX_AMOUNT_RULE);
      return parsed.kind === "value"
        ? value({ decimal: parsed.value })
        : parsed;
    }
    case "whole": {
      const text = raw.trim();
      if (text === "") return { kind: "empty" };
      return /^\d{1,9}$/.test(text)
        ? value(Number(text))
        : { kind: "refused", refusal: { key: "not_a_number", raw } };
    }
    case "flag":
      return raw === "yes" ? value(true) : raw === "no" ? value(false) : empty;
    case "choice":
    case "candidate":
      return raw === "" ? empty : value(raw);
  }
}
export type Answered = {
  values: FormValues;
  problems: Record<string, GrammarRefusal>;
};

/**
 * What a form's text says. A full form states every field, null where
 * nothing was typed, so the backend names what is missing. Given `initial`,
 * only the fields changed from it and not emptied are stated, and the rest
 * are left as the record has them.
 */
export function answer(
  options: FormOptions,
  draft: FormDraft,
  initial: FormDraft | null,
): Answered {
  const values: FormValues = {};
  const problems: Record<string, GrammarRefusal> = {};
  for (const field of options.fields) {
    const raw = draft[field.key] ?? "";
    if (initial !== null && raw === (initial[field.key] ?? "")) continue;
    const parsed = parseField(field, raw);
    if (parsed.kind === "refused") problems[field.key] = parsed.refusal;
    else if (parsed.kind === "value") values[field.key] = parsed.value;
    else if (initial === null) values[field.key] = null;
  }
  return { values, problems };
}

const textOf = (found: FormValue | undefined): string | null =>
  typeof found === "string" ? found : null;
const amountOf = (found: FormValue | undefined) =>
  found !== null && typeof found === "object" ? found : null;

export const describeRequest = (
  assetId: string,
  values: FormValues,
): ProvisionalRequests["ledger.actividad-asset.describe"] => {
  const { name, serial, ...rest } = values;
  return {
    asset_id: assetId,
    name: textOf(name),
    serial: textOf(serial),
    fields: Object.entries(rest).map(([key, found]) => ({
      key,
      value: textOf(found),
    })),
  };
};

export const disposeRequest = (
  assetId: string,
  values: FormValues,
): ProvisionalRequests["ledger.actividad-asset.dispose"] => ({
  asset_id: assetId,
  date: textOf(values.date),
  reason_key: textOf(values.reason_key),
});

/** The forecast of a span; null while the span is not both dates. */
export function forecastRequest(
  assetId: string,
  values: FormValues,
  supersedes: string | null,
): ActivityAssetForecastRequest | null {
  const from = textOf(values.from);
  const until = textOf(values.until);
  if (from === null || until === null) return null;
  return {
    asset_id: assetId,
    covered_from: from,
    covered_until: until,
    requested_free_amount: amountOf(values.free_amount),
    supersedes_claim_id: supersedes,
  };
}

// ---- What the register says of a write held in doubt ---------------------------

const listLanding =
  (port: LedgerPort, judge: (list: AssetListResult) => Landing): LandingCheck =>
  async () => {
    const read = await provisionalCall(
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
  revision: number,
) => listLanding(port, (list) => correctionLanded(list, assetId, revision));
export const bajaLanding = (port: LedgerPort, assetId: string) =>
  listLanding(port, (list) => bajaLanded(list, assetId));

export const descriptorLanding =
  (port: LedgerPort, assetId: string, sequence: number): LandingCheck =>
  async () => {
    const read = await provisionalCall(
      port,
      "ledger.actividad-asset.timeline",
      { asset_id: assetId },
      false,
    );
    return read.kind === "done"
      ? descriptorLanded(read.result.events, sequence)
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
    const read = await provisionalCall(
      port,
      "ledger.actividad-asset.plan",
      { asset_id: assetId },
      false,
    );
    return read.kind === "done" ? claimLanded(read.result.rows, sent) : null;
  };

/** An add landed if the register lists the id the window minted. */
export function elementLanded(list: AssetListResult, assetId: string): Landing {
  return list.rows.some((row) => row.asset_id === assetId)
    ? "saved"
    : "not_saved";
}

/** A correction landed if the element stands at the revision it would have
 * made; an element the register no longer lists cannot be told. */
export function correctionLanded(
  list: AssetListResult,
  assetId: string,
  revision: number,
): Landing {
  const found = list.rows.find((row) => row.asset_id === assetId);
  if (!found) return "untold";
  return found.revision_number >= revision ? "saved" : "not_saved";
}

/** A description landed if the element has as many descriptors as the
 * sequence the write would have taken. */
export function descriptorLanded(
  events: readonly TimelineEvent[],
  sequence: number,
): Landing {
  const described = events.filter(
    (event) => event.type_key === "description_added",
  ).length;
  return described >= sequence ? "saved" : "not_saved";
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
      claim.from === sent.from &&
      claim.until === sent.until &&
      claim.amount !== null &&
      sameDecimal(claim.amount.decimal, sent.amount),
  )
    ? "saved"
    : "not_saved";
}

/** A baja landed if the register lists the element with a baja. */
export function bajaLanded(list: AssetListResult, assetId: string): Landing {
  const found = list.rows.find((row) => row.asset_id === assetId);
  if (!found) return "untold";
  return found.baja ? "saved" : "not_saved";
}

/** The effective claims that no longer match the schedule, with their year:
 * the ones a correction can record again in the same write. */
export function staleClaims(
  rows: readonly PlanRow[],
): { year: number; claim: PlanClaim }[] {
  return rows.flatMap((row) =>
    row.claims
      .filter((claim) => claim.effective && !claim.matches_current_schedule)
      .map((claim) => ({ year: row.tax_year, claim })),
  );
}

// ---- How a write ended -----------------------------------------------------------

/** The backend's refusal codes this tab treats apart. */
export const INCOMPLETE = "REFUSED_ACTIVIDAD_ASSET_INCOMPLETE";
export const CONFLICT = "REFUSED_ACTIVIDAD_ASSET_CLAIM_CONFLICT";

export type Refusal = {
  code: string | null;
  reasonKey: string | null;
  /** The fields the backend says are still to fill in. */
  missing: string[];
  /** The claim a new claim overlaps. */
  conflict: ClaimConflict | null;
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
  const existing = asRecord(result?.conflicting_claim);
  const amount = asRecord(existing?.amount);
  return {
    code: typeof refusal?.code === "string" ? refusal.code : null,
    reasonKey:
      typeof refusal?.reason_key === "string" ? refusal.reason_key : null,
    missing,
    conflict:
      existing &&
      typeof existing.claim_id === "string" &&
      typeof existing.from === "string" &&
      typeof existing.until === "string"
        ? {
            claim_id: existing.claim_id,
            from: existing.from,
            until: existing.until,
            amount:
              amount && typeof amount.decimal === "string"
                ? { decimal: amount.decimal }
                : null,
          }
        : null,
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

export const createReused = (result: unknown) =>
  asRecord(result)?.reused_existing_element === true;
export const claimReused = (result: unknown) =>
  asRecord(result)?.reused_existing_claim === true;
export const neverReused = () => false;

// ---- Words for a refusal ---------------------------------------------------------

/** The sub-reasons the backend gives, each to the line that says it. */
const REASON: Record<string, string> = {
  asset_not_found: "desktop.ledger.assets.reason.asset_not_found",
  already_disposed: "desktop.ledger.assets.reason.already_disposed",
  baja_before_service: "desktop.ledger.assets.reason.baja_before_service",
  option_not_offered: "desktop.ledger.assets.reason.option_not_offered",
  reason_not_offered: "desktop.ledger.assets.reason.option_not_offered",
  acquisition_not_found: "desktop.ledger.assets.reason.acquisition_not_found",
  asset_exists: "desktop.ledger.assets.reason.asset_exists",
  revision_stale: "desktop.ledger.assets.reason.revision_stale",
  nothing_changed: "desktop.ledger.assets.reason.nothing_changed",
  span_crosses_years: "desktop.ledger.assets.reason.span_crosses_years",
  year_not_in_plan: "desktop.ledger.assets.reason.year_not_in_plan",
  projected_authority: "desktop.ledger.assets.reason.projected_authority",
  opening_history_unknown:
    "desktop.ledger.assets.reason.opening_history_unknown",
  claim_not_found: "desktop.ledger.assets.reason.claim_not_found",
  claim_not_effective: "desktop.ledger.assets.reason.claim_not_effective",
};

/** The refusal codes whose own line exists, by lower-cased code. */
const CODE: Record<string, string> = {
  refused_actividad_asset_accelerated_da18_depreciation_not_computed:
    "desktop.ledger.assets.refusal.refused_actividad_asset_accelerated_da18_depreciation_not_computed",
  refused_actividad_asset_claim_conflict:
    "desktop.ledger.assets.refusal.refused_actividad_asset_claim_conflict",
  refused_actividad_asset_incomplete:
    "desktop.ledger.assets.refusal.refused_actividad_asset_incomplete",
  refused_actividad_asset_unsupported:
    "desktop.ledger.assets.refusal.refused_actividad_asset_unsupported",
  refused_actividad_asset_validation:
    "desktop.ledger.assets.refusal.refused_actividad_asset_validation",
};

/** A refusal in words, by its backend keys: the sub-reason's line, else the
 * code's, else null where the tab has none and the caller shows the token. */
export function refusalWord(
  t: Translate,
  refusal: Pick<Refusal, "code" | "reasonKey">,
): string | null {
  if (refusal.reasonKey !== null && Object.hasOwn(REASON, refusal.reasonKey))
    return t(REASON[refusal.reasonKey]!);
  const code = refusal.code?.toLowerCase();
  if (code !== undefined && Object.hasOwn(CODE, code)) return t(CODE[code]!);
  return null;
}

/** The fields still to fill in, by their labels. */
export function missingLabels(
  t: Translate,
  options: FormOptions | null,
  keys: readonly string[],
): string {
  return keys
    .map((key) => {
      const found = options?.fields.find((field) => field.key === key);
      return found ? t(found.label_key) : fieldWord(t, key);
    })
    .join(", ");
}
