// What the movement inspector works out without drawing: where its jump
// index stands and how much of it fits, what a selection has in common,
// which selected movements a field set for all reaches and which it skips,
// the parts of a split, a split's cohort, what approving a model's
// suggestion writes, and whether a date moves a movement to another
// quarter. Nothing here reads or writes the ledger.

import type { LedgerLlmSuggestion } from "../../../shell/ledgerMovementOperations";
import type { LedgerStagedRowAnswer } from "../../../shell/ledgerMovementCheckContract";
import type { LedgerRow, LedgerTransaction } from "../../../shell/ledger";
import {
  FIELDS_DROPPED_BY_PERSONAL,
  takesChanges,
} from "../../../shell/ledgerContract";
import { takesBusinessShare } from "../../../shell/ledgerClassifications";
import { periodsHolding } from "../../../shell/ledgerPeriods";
import type { StagedCheck } from "../../../shell/ledgerStagedCheck";
import { samePeriod, type LedgerPeriod } from "../../../shell/ledgerGrammar";
import {
  effectiveFacts,
  storedFieldValue,
  type StageCell,
  type StageField,
  type StagedAction,
} from "../../../shell/ledgerStage";
import { statusWord, type StatusWord } from "../movements/movementWords";

// ---- The jump index ------------------------------------------------------------

/** The inspector's sections, in the order its one scroll shows them. */
export const INSPECTOR_SECTIONS = [
  "classify",
  "documents",
  "invoice",
  "details",
  "history",
] as const;
export type InspectorSection = (typeof INSPECTOR_SECTIONS)[number];
export const isInspectorSection = (id: string): id is InspectorSection =>
  (INSPECTOR_SECTIONS as readonly string[]).includes(id);

/**
 * How many of the index's entries fit in `available` beside one another,
 * `gap` apart. When they do not all fit, the rest go into a More menu
 * whose button takes `more`, so fewer fit beside it; at least one entry is
 * always shown.
 */
export function fittingEntries(
  widths: readonly number[],
  more: number,
  available: number,
  gap = 0,
): number {
  const span = (count: number) =>
    widths.slice(0, count).reduce((sum, width) => sum + width, 0) +
    gap * Math.max(0, count - 1);
  if (span(widths.length) <= available) return widths.length;
  for (let count = widths.length - 1; count >= 1; count -= 1)
    if (span(count) + gap + more <= available) return count;
  return 1;
}

/**
 * The section the reader is in: the last whose heading has scrolled to
 * within `offset` of the top, or the last section once the scroll is at
 * its end, so a short final section can still be current.
 */
export function currentSection<Id extends string>(
  tops: readonly { id: Id; top: number }[],
  scroll: { top: number; height: number; content: number },
  offset: number,
): Id | null {
  if (tops.length === 0) return null;
  if (scroll.top + scroll.height >= scroll.content - 2)
    return tops[tops.length - 1]!.id;
  let current = tops[0]!.id;
  for (const entry of tops)
    if (entry.top - scroll.top <= offset) current = entry.id;
  return current;
}

// ---- Many movements at once ----------------------------------------------------

/** What the selected movements hold for one field: one value, empty
 * included, or several. */
export type CommonValue =
  { kind: "one"; value: string | null } | { kind: "mixed"; count: number };
export function commonValue(
  values: readonly (string | null | undefined)[],
): CommonValue {
  const distinct = new Set(values.map((value) => value ?? null));
  if (distinct.size === 1)
    return { kind: "one", value: [...distinct][0] ?? null };
  return { kind: "mixed", count: distinct.size };
}

/** How many of the movements hold each classification and each status,
 * most first. `issues` is null while readiness is not measured, so a
 * reviewed movement counts as not measured rather than done. */
export function selectionCounts(
  rows: readonly LedgerRow[],
  issues: ReadonlyMap<string, readonly string[]> | null,
): {
  classifications: [string, number][];
  statuses: [StatusWord, number][];
} {
  const classifications = new Map<string, number>();
  const statuses = new Map<StatusWord, number>();
  for (const row of rows) {
    const t = row.transaction;
    classifications.set(
      t.business_classification,
      (classifications.get(t.business_classification) ?? 0) + 1,
    );
    const word = statusWord(
      row.review_status,
      issues === null ? null : (issues.get(t.transaction_id)?.length ?? 0),
    );
    statuses.set(word, (statuses.get(word) ?? 0) + 1);
  }
  const order = <K>(entries: Map<K, number>) =>
    [...entries].sort((a, b) => b[1] - a[1]);
  return {
    classifications: order(classifications),
    statuses: order(statuses),
  };
}

/** Whether the ledger answers that none of the movements is, or is staged to
 * be, classified: the tax fields take nothing until one is. With no answer the
 * tax fields wait too. */
export function noneClassified(
  rows: readonly LedgerRow[],
  check: StagedCheck | null,
): boolean {
  return rows.every(
    (row) => !check?.rows.get(row.transaction.transaction_id)?.classified,
  );
}

/** The fields the selection inspector sets on every selected movement. */
export const SET_FOR_ALL_FIELDS = [
  "category_id",
  "iva_category",
  "irpf_category",
  "group_label",
  "notes",
] as const;
export type SetForAllField = (typeof SET_FOR_ALL_FIELDS)[number];

/** Why a movement is left out of a change set for all. */
export type SkipReason =
  "not_active" | "sealed" | "sealed_unread" | "transfer" | "personal";

const TAX_SETS: ReadonlySet<SetForAllField> = new Set([
  "category_id",
  "iva_category",
  "irpf_category",
]);
/** Why `field` set on `row` would be skipped, judged on the movement as it
 * will be once what is staged on it is saved. */
export function setSkip(
  field: SetForAllField,
  row: LedgerRow,
  check: StagedCheck,
  sealed: ReadonlySet<string>,
  /** Movements whose sealed state the page could not read. */
  unread?: ReadonlySet<string>,
): SkipReason | null {
  const id = row.transaction.transaction_id;
  if (!takesChanges(row.transaction.lifecycle_state)) return "not_active";
  if (sealed.has(id)) return "sealed";
  if (unread?.has(id)) return "sealed_unread";
  if (!TAX_SETS.has(field)) return null;
  const skip = check.rows.get(id)?.tax_set_skip ?? null;
  return skip === "personal" &&
    !(FIELDS_DROPPED_BY_PERSONAL as readonly string[]).includes(field)
    ? null
    : skip;
}

export type SetForAll = {
  cells: StageCell[];
  /** Movements it reaches, drawn and not drawn. */
  visible: number;
  hidden: number;
  skipped: Partial<Record<SkipReason, number>>;
};

/** The cells that set `field` to `value` on each of `ids` that takes it,
 * and what it leaves out and why. */
export function setForAll(
  field: SetForAllField,
  value: string,
  ids: readonly string[],
  rows: ReadonlyMap<string, LedgerRow>,
  context: {
    check: StagedCheck;
    sealed: ReadonlySet<string>;
    unread?: ReadonlySet<string>;
    visible: ReadonlySet<string>;
  },
): SetForAll {
  const out: SetForAll = { cells: [], visible: 0, hidden: 0, skipped: {} };
  for (const id of ids) {
    const row = rows.get(id);
    if (!row) continue;
    const skip = setSkip(
      field,
      row,
      context.check,
      context.sealed,
      context.unread,
    );
    if (skip) {
      out.skipped[skip] = (out.skipped[skip] ?? 0) + 1;
      continue;
    }
    if (context.visible.has(id)) out.visible += 1;
    else out.hidden += 1;
    out.cells.push({
      id,
      field,
      value: { kind: "set", value },
      stored: storedFieldValue(row, field),
    });
  }
  return out;
}

/** The lifecycle actions the inspector offers. */
export const LIFECYCLE_KINDS = [
  "archive",
  "stash",
  "restore",
  "exclude",
] as const;
export type LifecycleAction = (typeof LIFECYCLE_KINDS)[number];

/** Whether a lifecycle action can be staged on a movement, as the ledger
 * answers; with no answer it waits. */
export function lifecycleTakes(
  kind: LifecycleAction,
  answer: LedgerStagedRowAnswer | undefined,
  sealed: boolean,
): boolean {
  return !sealed && (answer?.lifecycle_actions.includes(kind) ?? false);
}

/** The staged action of one lifecycle change, by a stable id, so staging
 * it again replaces it. */
export function lifecycleAction(
  kind: LifecycleAction,
  transactionId: string,
  reason: string,
): StagedAction {
  return { id: `${kind}:${transactionId}`, kind, transactionId, reason };
}

/** Whether the selected movements are every active part of one split: the
 * movement's split siblings, as its history names them, that the window
 * holds. */
export function completeCohort(
  selected: readonly string[],
  objectIds: readonly string[],
  rows: ReadonlyMap<string, LedgerRow>,
): boolean {
  const parts = objectIds.filter((id) => {
    const state = rows.get(id)?.transaction.lifecycle_state;
    return state !== undefined && takesChanges(state);
  });
  return (
    parts.length >= 2 &&
    parts.length === selected.length &&
    parts.every((id) => selected.includes(id))
  );
}

// ---- The model's suggestion ----------------------------------------------------

export type SuggestionWrite = {
  field: StageField;
  value: string | null;
  derived?: true;
};

/**
 * What approving `suggestion` writes, field by field: the classification,
 * the business share a Mixed one carries, the category and the IVA
 * category it names, and, where the registry's rate works them out, the
 * base, rate and IVA, marked as worked out by Cadrumo. A split writes its
 * parts instead, which the review lists.
 */
export function suggestionWrites(
  suggestion: LedgerLlmSuggestion["suggestion"],
): SuggestionWrite[] {
  if (suggestion.kind === "split") return [];
  const writes: SuggestionWrite[] = [];
  if (suggestion.classification)
    writes.push({
      field: "business_classification",
      value: suggestion.classification,
    });
  if (
    suggestion.classification &&
    takesBusinessShare(suggestion.classification) === true
  )
    writes.push({ field: "business_pct", value: suggestion.business_pct });
  if (suggestion.category)
    writes.push({ field: "category_id", value: suggestion.category });
  if (suggestion.iva_category)
    writes.push({ field: "iva_category", value: suggestion.iva_category });
  if (suggestion.rate_derivable)
    for (const field of ["taxable_base", "iva_rate", "iva_amount"] as const)
      if (suggestion[field] !== null)
        writes.push({ field, value: suggestion[field], derived: true });
  return writes;
}

/** Whether a suggestion can be approved as it stands: a Mixed one needs a
 * share, which only a new review asked with it can carry. */
export const needsShare = (suggestion: LedgerLlmSuggestion["suggestion"]) =>
  suggestion.kind !== "split" &&
  !!suggestion.classification &&
  takesBusinessShare(suggestion.classification) === true &&
  suggestion.business_pct === null;

// ---- Dates ---------------------------------------------------------------------

/** The day a movement's staged dates make its effective one: its value date,
 * else its booking date; empty where neither is held. */
export const effectiveDay = (facts: ReturnType<typeof effectiveFacts>) =>
  facts.value_date ?? facts.booked_date ?? "";

/** The quarter a movement leaves and the one it moves to when its staged
 * dates change its effective date across a quarter, or null. */
export function quarterMove(
  transaction: LedgerTransaction,
  facts: ReturnType<typeof effectiveFacts>,
): { from: LedgerPeriod; to: LedgerPeriod } | null {
  const from = periodsHolding(transaction.date)?.quarterly;
  const to = periodsHolding(effectiveDay(facts))?.quarterly;
  // A quarter not served is not known to differ, so no move is reported.
  if (!from || !to || samePeriod(from, to)) return null;
  return { from, to };
}
