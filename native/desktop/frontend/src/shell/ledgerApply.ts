// Runs a planned apply over the ledger port, one step at a time and in the
// plan's order. Nothing is ever sent twice: a refusal stays staged with its
// reason, and a write whose outcome was not observed pauses every later
// write until the page reads the ledger again. Before it writes, the apply
// reads the period again and names every staged movement that changed or
// left since the page read it.

import {
  ledgerFailure,
  type JsonObject,
  type JsonValue,
  type LedgerAddResult,
  type LedgerBulkClassifyResult,
  type LedgerClassifyResult,
  type LedgerErrorDetail,
  type LedgerFailureCode,
  type LedgerOutcome,
  type LedgerPort,
  type LedgerRow,
  type LedgerUpdateResult,
} from "./ledger";
import type { LedgerPlan, PlanStep } from "./ledgerPlan";
import {
  actionRows,
  stagedMovements,
  storedFieldValue,
  unchangedBy,
  type StageEvent,
  type StageField,
  type StageKeep,
  type StagedContent,
} from "./ledgerStage";
import type { LedgerPeriod } from "./ledgerGrammar";
import { readWindow, rowsById, type LedgerReadFailure } from "./ledgerWindow";

/** Why a step was not sent. */
export type NotSentWhy =
  /** A write before it has an unknown outcome. */
  | "paused"
  /** The session or the host went away. */
  | "stopped"
  /** An earlier step for the same movement did not save. */
  | "after_refusal"
  /** An earlier part of the same bulk was refused whole. */
  | "after_part";

/** Where one step, or one row of a bulk part, stands after the apply. */
export type StepOutcome =
  | { kind: "applied"; newId: string | null }
  /** Settled with nothing to change: the stored value is read again before
   * the staged one is dropped. */
  | { kind: "unchanged" }
  /** Saved or already so; the bulk counts do not say which row was which. */
  | { kind: "settled" }
  | {
      kind: "refused";
      reason: string | null;
      messages: string[];
      detail: LedgerErrorDetail | null;
    }
  /** It may have saved. Never sent again before a re-read. */
  | { kind: "unknown"; operationId: string | null }
  /** Saved, but its result was not read. */
  | { kind: "saved_unread"; operationId: string | null }
  | { kind: "not_sent"; why: NotSentWhy };

export type RowResult = { transactionId: string; outcome: StepOutcome };
export type StepReport = {
  index: number;
  step: PlanStep;
  /** For a bulk part, `refused` means nothing in the part was saved. */
  outcome: StepOutcome;
  rows: RowResult[];
};

export type ApplyReport = {
  steps: StepReport[];
  /** The step whose outcome is unknown; writes stay paused until a re-read. */
  paused: { index: number; operationId: string | null } | null;
  /** The session or host failure that stopped the run. */
  stopped: LedgerFailureCode | null;
  /** Movements that took a new id, in the order they did. */
  rekeys: { from: string; to: string }[];
  /** Movements to read again: what was saved, unchanged or unknown. */
  reread: string[];
  /** How many changes were saved. */
  saved: number;
};

const refused = (
  reason: string | null,
  messages: string[] = [],
  detail: LedgerErrorDetail | null = null,
): StepOutcome => ({ kind: "refused", reason, messages, detail });

/** The movements a step writes. */
export function stepRows(step: PlanStep): string[] {
  switch (step.kind) {
    case "bulk":
      return step.rows.map((row) => row.transactionId);
    case "classify":
    case "update":
      return [step.transactionId];
    case "add":
      return [];
    case "action":
    case "answer":
      return actionRows(step.action);
  }
}

const object = (value: JsonValue | undefined): JsonObject | null =>
  value !== null && typeof value === "object" && !Array.isArray(value)
    ? value
    : null;
const texts = (value: JsonValue | undefined): string[] =>
  Array.isArray(value)
    ? value.filter((item): item is string => typeof item === "string")
    : [];

/** The refusal a settled result carries in its own outcome, if any. */
function validationOf(result: JsonObject): StepOutcome | null {
  for (const candidate of [
    result,
    object(result.result),
    object(result.projection),
  ]) {
    if (candidate?.outcome !== "validation_error") continue;
    const validation = object(candidate.validation);
    const messages = [
      ...texts(candidate.validation_messages),
      ...texts(validation?.messages),
    ];
    const code =
      typeof candidate.validation_code === "string"
        ? candidate.validation_code
        : typeof candidate.validation_kind === "string"
          ? candidate.validation_kind
          : "validation_error";
    return refused(code, messages);
  }
  return null;
}

/** What a settled result says happened, row by row. */
function settledOutcome(
  step: PlanStep,
  result: JsonObject,
): { outcome: StepOutcome; rows: RowResult[] } {
  const ids = stepRows(step);
  const each = (outcome: StepOutcome) => ({
    outcome,
    rows: ids.map((transactionId) => ({ transactionId, outcome })),
  });
  const validation = validationOf(result);
  if (validation) return each(validation);
  switch (step.kind) {
    case "bulk": {
      const batch = (result as unknown as LedgerBulkClassifyResult).projection
        .result;
      if (!batch) return each(refused("validation_error"));
      const failed = new Map(
        batch.failures.map((failure) => [failure.row_index, failure.reason]),
      );
      // The counts say how many rows changed, not which.
      const saved: StepOutcome =
        batch.skipped === 0
          ? { kind: "applied", newId: null }
          : batch.applied === 0
            ? { kind: "unchanged" }
            : { kind: "settled" };
      return {
        outcome: failed.size === ids.length ? refused(null) : saved,
        rows: ids.map((transactionId, at) => ({
          transactionId,
          outcome: failed.has(at) ? refused(null, [failed.get(at)!]) : saved,
        })),
      };
    }
    case "classify": {
      const written = (result as unknown as LedgerClassifyResult).result;
      return each(
        written?.bucket_event_ids.length
          ? { kind: "applied", newId: null }
          : { kind: "unchanged" },
      );
    }
    case "update": {
      const written = (result as unknown as LedgerUpdateResult).result;
      if (!written?.bucket_event_ids.length) return each({ kind: "unchanged" });
      const after = written.transaction?.transaction_id ?? null;
      return each({
        kind: "applied",
        newId: after && after !== step.transactionId ? after : null,
      });
    }
    case "add": {
      const written = (result as unknown as LedgerAddResult).result;
      // A replay of the same add returns the row it stored and writes
      // nothing.
      return each(
        written?.bucket_event_ids.length
          ? {
              kind: "applied",
              newId: written.transaction?.transaction_id ?? null,
            }
          : { kind: "unchanged" },
      );
    }
    case "action":
    case "answer":
      return each({ kind: "applied", newId: null });
  }
}

function outcomeOf(
  step: PlanStep,
  outcome: LedgerOutcome,
): { outcome: StepOutcome; rows: RowResult[] } {
  if (outcome.kind === "settled") return settledOutcome(step, outcome.result);
  const found: StepOutcome =
    outcome.kind === "refused"
      ? refused(outcome.reason, [], outcome.detail)
      : // Still running or waiting: its settlement was not observed.
        { kind: "unknown", operationId: outcome.operation_id };
  return {
    outcome: found,
    rows: stepRows(step).map((transactionId) => ({
      transactionId,
      outcome: found,
    })),
  };
}

function thrownOutcome(error: unknown): StepOutcome {
  const failure = ledgerFailure(error);
  switch (failure.code) {
    case "unknown":
      return { kind: "unknown", operationId: failure.operation_id };
    case "saved_unread":
      return { kind: "saved_unread", operationId: failure.operation_id };
    case "unavailable":
    case "not_signed_in":
      // The host's own answer before anything reached the ledger.
      return { kind: "not_sent", why: "stopped" };
    default:
      return refused(failure.reason ?? failure.code);
  }
}

/** The step's request under the ids earlier steps gave its movements. */
function rekeyed(
  step: PlanStep,
  current: (id: string) => string,
): JsonObject | null {
  if (step.kind !== "action") return null;
  const request = { ...step.request };
  if (typeof request.transaction_id === "string")
    request.transaction_id = current(request.transaction_id);
  if (Array.isArray(request.child_ids))
    request.child_ids = request.child_ids.map((id) =>
      typeof id === "string" ? current(id) : id,
    );
  return request;
}

async function send(
  port: LedgerPort,
  step: PlanStep,
  current: (id: string) => string,
): Promise<LedgerOutcome> {
  switch (step.kind) {
    case "bulk":
      return port.submit("ledger.classify.bulk", step.request);
    case "classify":
      return port.submit("ledger.classify.single", step.request);
    case "update":
      return port.submit("ledger.update", step.request);
    case "add":
      return port.submit("ledger.add", step.request);
    case "action":
      return port.submit(step.definition, rekeyed(step, current)!);
    case "answer":
      return port.answer(
        step.action.operationId,
        step.action.reviewDigest,
        step.action.decision,
      );
  }
}

const DONE: ReadonlySet<StepOutcome["kind"]> = new Set([
  "applied",
  "unchanged",
  "settled",
  "saved_unread",
]);

/**
 * Runs `plan`'s steps in order. Each is sent once. A refused step keeps its
 * movement's later steps back; an unknown one keeps every later step back;
 * a session that went away stops the run. `onStep` hears each step settle.
 */
export async function runPlan(
  port: LedgerPort,
  plan: LedgerPlan,
  onStep?: (report: StepReport) => void,
): Promise<ApplyReport> {
  const ids = new Map<string, string>();
  const current = (id: string) => ids.get(id) ?? id;
  const failedRows = new Set<string>();
  const steps: StepReport[] = [];
  let paused: ApplyReport["paused"] = null;
  let stopped: LedgerFailureCode | null = null;
  let partRefused = false;
  for (const [index, step] of plan.steps.entries()) {
    const rows = stepRows(step);
    let settled: { outcome: StepOutcome; rows: RowResult[] };
    const hold = (why: NotSentWhy) => {
      const outcome: StepOutcome = { kind: "not_sent", why };
      return {
        outcome,
        rows: rows.map((transactionId) => ({ transactionId, outcome })),
      };
    };
    if (paused) settled = hold("paused");
    else if (stopped) settled = hold("stopped");
    else if (step.kind === "bulk" && partRefused) settled = hold("after_part");
    else if (rows.some((id) => failedRows.has(id)))
      settled = hold("after_refusal");
    else {
      try {
        settled = outcomeOf(step, await send(port, step, current));
      } catch (error) {
        const outcome = thrownOutcome(error);
        if (outcome.kind === "not_sent") stopped = ledgerFailure(error).code;
        settled = {
          outcome,
          rows: rows.map((transactionId) => ({ transactionId, outcome })),
        };
      }
      const outcome = settled.outcome;
      // A part refused whole, not row by row, stops the parts after it.
      if (
        step.kind === "bulk" &&
        outcome.kind === "refused" &&
        settled.rows.every((row) => row.outcome === outcome)
      )
        partRefused = true;
      if (outcome.kind === "unknown" || outcome.kind === "saved_unread")
        paused = { index, operationId: outcome.operationId };
      if (step.kind === "update" && outcome.kind === "applied" && outcome.newId)
        ids.set(step.transactionId, outcome.newId);
    }
    for (const row of settled.rows)
      if (!DONE.has(row.outcome.kind)) failedRows.add(row.transactionId);
    const report: StepReport = { index, step, ...settled };
    steps.push(report);
    onStep?.(report);
  }
  const reread = new Set<string>();
  let saved = 0;
  for (const report of steps)
    for (const row of report.rows) {
      const kind = row.outcome.kind;
      if (DONE.has(kind) || kind === "unknown")
        reread.add(current(row.transactionId));
      if (kind === "applied" || kind === "settled" || kind === "saved_unread")
        saved += 1;
    }
  for (const report of steps)
    if (report.step.kind === "add" && DONE.has(report.outcome.kind)) saved += 1;
  return {
    steps,
    paused,
    stopped,
    rekeys: [...ids].map(([from, to]) => ({ from, to })),
    reread: [...reread],
    saved,
  };
}

/** What stays staged after an apply: refused, unknown and not-sent work,
 * and everything the plan held back. */
export function keepAfterApply(
  content: StagedContent,
  report: ApplyReport,
): StageKeep {
  const rows = new Map<string, Set<StageField>>(
    Object.entries(content.rows).map(([id, changes]) => [
      id,
      new Set(Object.keys(changes) as StageField[]),
    ]),
  );
  const drafts = new Set(content.drafts.map((draft) => draft.key));
  const actions = new Set(content.actions.map((action) => action.id));
  const drop = (id: string, fields: StageField[]) =>
    fields.forEach((field) => rows.get(id)?.delete(field));
  for (const { step, outcome, rows: results } of report.steps) {
    if (step.kind === "bulk") {
      for (const [at, row] of step.rows.entries())
        if (DONE.has(results[at]!.outcome.kind))
          drop(row.transactionId, row.fields);
      continue;
    }
    if (!DONE.has(outcome.kind)) continue;
    if (step.kind === "classify") {
      drop(step.transactionId, step.fields);
      if (step.m210Action) actions.delete(step.m210Action);
    } else if (step.kind === "update") drop(step.transactionId, step.fields);
    else if (step.kind === "add") drafts.delete(step.draftKey);
    else actions.delete(step.action.id);
  }
  return {
    rows: Object.fromEntries(
      [...rows]
        .filter(([, fields]) => fields.size > 0)
        .map(([id, fields]) => [id, [...fields]]),
    ),
    drafts: [...drafts],
    actions: [...actions],
  };
}

/** The stage events that settle the stage after an apply: keep what did not
 * save, then follow every new id. */
export function stageAfterApply(
  content: StagedContent,
  report: ApplyReport,
): StageEvent[] {
  return [
    { type: "rebase", keep: keepAfterApply(content, report) },
    ...report.rekeys.map(({ from, to }): StageEvent => ({
      type: "rekey",
      from,
      to,
    })),
  ];
}

// ---- Before and after an apply ---------------------------------------------

/** A staged movement that is not as the page read it. */
export type SinceReadConflict =
  | {
      kind: "changed";
      transactionId: string;
      before: LedgerRow;
      after: LedgerRow;
    }
  | {
      /** Removed, or moved out of the period, since the page read it. */
      kind: "gone";
      transactionId: string;
      before: LedgerRow | null;
    };

/** Compares every staged movement's id and `modified_at` between the read
 * the page staged against and the read at the apply. */
export function changedSinceRead(
  content: StagedContent,
  read: ReadonlyMap<string, LedgerRow>,
  fresh: ReadonlyMap<string, LedgerRow>,
): SinceReadConflict[] {
  const conflicts: SinceReadConflict[] = [];
  for (const id of stagedMovements(content)) {
    const before = read.get(id) ?? null;
    const after = fresh.get(id);
    if (!after) conflicts.push({ kind: "gone", transactionId: id, before });
    else if (
      before &&
      before.transaction.modified_at !== after.transaction.modified_at
    )
      conflicts.push({ kind: "changed", transactionId: id, before, after });
  }
  return conflicts;
}

/** Reads the period again before an apply and names what changed since the
 * page read it. The plan is built from the rows this returns. */
export async function prepareApply(
  port: LedgerPort,
  period: LedgerPeriod | null,
  content: StagedContent,
  read: ReadonlyMap<string, LedgerRow>,
): Promise<
  | {
      kind: "ready";
      rows: Map<string, LedgerRow>;
      conflicts: SinceReadConflict[];
    }
  | { kind: "failed"; failure: LedgerReadFailure }
> {
  const answer = await readWindow(port, period);
  if (answer.kind === "failed") return answer;
  const rows = rowsById(answer.rows);
  return {
    kind: "ready",
    rows,
    conflicts: changedSinceRead(content, read, rows),
  };
}

export type UnknownResolution = "saved" | "not_saved" | "undetermined";

/**
 * What a re-read says about a step whose outcome was unknown, per movement:
 * found saved, found not saved, or not told by the read. An add is never
 * told: it stays staged with its key, so sending it again is the same add.
 */
export function resolveUnknown(
  step: PlanStep,
  content: StagedContent,
  fresh: ReadonlyMap<string, LedgerRow>,
): Map<string, UnknownResolution> {
  const found = new Map<string, UnknownResolution>();
  const fieldsSaved = (id: string, fields: StageField[]): UnknownResolution => {
    const row = fresh.get(id);
    if (!row) return "undetermined";
    const changes = content.rows[id] ?? {};
    let undetermined = false;
    for (const field of fields) {
      const stored = storedFieldValue(row, field);
      const change = changes[field];
      if (!change || stored === undefined) undetermined = true;
      else if (!unchangedBy(field, stored, change)) return "not_saved";
    }
    return undetermined ? "undetermined" : "saved";
  };
  switch (step.kind) {
    case "bulk":
      for (const row of step.rows)
        found.set(
          row.transactionId,
          fieldsSaved(row.transactionId, row.fields),
        );
      break;
    case "classify":
      found.set(
        step.transactionId,
        fieldsSaved(step.transactionId, step.fields),
      );
      break;
    case "update":
      // A new id leaves the old one behind whether or not it saved.
      found.set(
        step.transactionId,
        step.newIdentity
          ? fresh.has(step.transactionId)
            ? "not_saved"
            : "undetermined"
          : fieldsSaved(step.transactionId, step.fields),
      );
      break;
    case "add":
      found.set(step.draftKey, "undetermined");
      break;
    case "answer":
      found.set(step.action.transactionId, "undetermined");
      break;
    case "action": {
      const action = step.action;
      const row =
        action.kind === "merge" ? undefined : fresh.get(action.transactionId);
      const state = row?.transaction.lifecycle_state;
      const verdict = (saved: boolean): UnknownResolution =>
        saved ? "saved" : "not_saved";
      let resolution: UnknownResolution = "undetermined";
      if (action.kind === "remove")
        resolution = verdict(!fresh.has(action.transactionId));
      else if (row)
        switch (action.kind) {
          case "archive":
            resolution = verdict(state === "ARCHIVED");
            break;
          case "stash":
            resolution = verdict(state === "STASHED");
            break;
          case "restore":
            resolution = verdict(state === "ACTIVE");
            break;
          case "exclude":
            resolution = verdict(
              row.transaction.business_classification === "REVIEWED_EXCLUDED",
            );
            break;
          case "link":
            resolution = verdict(
              row.transaction.invoice_id === action.invoiceId,
            );
            break;
          case "attach":
            resolution = verdict(
              action.attachmentIds.every((id) =>
                row.transaction.attachment_ids.includes(id),
              ) &&
                (action.evidenceId === null ||
                  row.transaction.purchase_invoice_evidence_id ===
                    action.evidenceId),
            );
            break;
          case "detach":
            resolution = verdict(
              action.attachmentIds.every(
                (id) => !row.transaction.attachment_ids.includes(id),
              ),
            );
            break;
          case "split":
            resolution = verdict(state === "SPLIT");
            break;
        }
      for (const id of actionRows(action)) found.set(id, resolution);
      break;
    }
  }
  return found;
}
