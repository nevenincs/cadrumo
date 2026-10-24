// What the movement inspector works out without drawing: where its jump
// index stands and how much of it fits, what a selection has in common,
// which selected movements a field set for all reaches and which it skips,
// the parts of a split, a split's cohort, what approving a model's
// suggestion writes, and whether a date moves a movement to another
// quarter. Nothing here reads or writes the ledger.

import type {
  LedgerLlmSuggestion,
  LedgerRow,
  LedgerTransaction,
} from "../../../shell/ledger";
import {
  parseDecimal,
  periodOf,
  samePeriod,
  AMOUNT_RULE,
  type LedgerPeriod,
} from "../../../shell/ledgerGrammar";
import {
  effectiveFacts,
  storedFieldValue,
  type StageCell,
  type StageField,
  type StagedAction,
  type StagedContent,
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
 * most first. */
export function selectionCounts(
  rows: readonly LedgerRow[],
  issues: ReadonlyMap<string, readonly string[]>,
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
      issues.get(t.transaction_id)?.length ?? 0,
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
  "not_active" | "sealed" | "transfer" | "personal" | "unclassified";

const TAX_SETS: ReadonlySet<SetForAllField> = new Set([
  "category_id",
  "iva_category",
  "irpf_category",
]);
const DECIDED_WITH_TAX = ["BUSINESS", "MIXED"];

/** Why `field` set on `row` would be skipped, judged on the movement as it
 * will be once what is staged on it is saved. */
export function setSkip(
  field: SetForAllField,
  row: LedgerRow,
  content: StagedContent,
  sealed: ReadonlySet<string>,
): SkipReason | null {
  const id = row.transaction.transaction_id;
  if (row.transaction.lifecycle_state !== "ACTIVE") return "not_active";
  if (sealed.has(id)) return "sealed";
  if (!TAX_SETS.has(field)) return null;
  const facts = effectiveFacts(row, content.rows[id]);
  if (facts.direction === "INTERNAL_TRANSFER") return "transfer";
  if (facts.business_classification === "PERSONAL") return "personal";
  if (!DECIDED_WITH_TAX.includes(facts.business_classification ?? ""))
    return "unclassified";
  return null;
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
    content: StagedContent;
    sealed: ReadonlySet<string>;
    visible: ReadonlySet<string>;
  },
): SetForAll {
  const out: SetForAll = { cells: [], visible: 0, hidden: 0, skipped: {} };
  for (const id of ids) {
    const row = rows.get(id);
    if (!row) continue;
    const skip = setSkip(field, row, context.content, context.sealed);
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

/** Whether a lifecycle action can be staged on `row`. */
export function lifecycleTakes(
  kind: LifecycleAction,
  row: LedgerRow,
  sealed: ReadonlySet<string>,
): boolean {
  const t = row.transaction;
  if (sealed.has(t.transaction_id)) return false;
  if (kind === "restore")
    return t.lifecycle_state === "ARCHIVED" || t.lifecycle_state === "STASHED";
  if (t.lifecycle_state !== "ACTIVE") return false;
  return !(
    kind === "exclude" && t.business_classification === "REVIEWED_EXCLUDED"
  );
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
  const parts = objectIds.filter(
    (id) => rows.get(id)?.transaction.lifecycle_state === "ACTIVE",
  );
  return (
    parts.length >= 2 &&
    parts.length === selected.length &&
    parts.every((id) => selected.includes(id))
  );
}

// ---- Split ---------------------------------------------------------------------

type Cents = bigint;
function centsOf(text: string): Cents | null {
  const parsed = parseDecimal(text, AMOUNT_RULE);
  if (parsed.kind !== "value") return null;
  const [whole, fraction = ""] = parsed.value.split(".");
  return BigInt(whole!) * 100n + BigInt(fraction.padEnd(2, "0"));
}
function textOfCents(value: Cents): string {
  const whole = value / 100n;
  const fraction = value % 100n;
  if (fraction === 0n) return whole.toString();
  const digits = fraction.toString().padStart(2, "0").replace(/0$/, "");
  return `${whole}.${digits}`;
}

/** The part that makes the parts add up to the movement's amount: what is
 * left once the others are taken, in shortest canonical form, or null when
 * the others are not all amounts or leave nothing. */
export function splitRemainder(
  total: string,
  others: readonly string[],
): string | null {
  const whole = centsOf(total);
  if (whole === null) return null;
  let left = whole;
  for (const other of others) {
    const part = centsOf(other);
    if (part === null) return null;
    left -= part;
  }
  return left > 0n ? textOfCents(left) : null;
}

export type SplitProblem =
  | { kind: "count" }
  | { kind: "amount"; index: number }
  | { kind: "description"; index: number }
  | { kind: "duplicate"; index: number }
  | { kind: "sum"; difference: string; over: boolean };

/** The most parts one split makes. */
export const SPLIT_PARTS_MAX = 128;

/** Whether the parts make a split the ledger takes: two or more, each a
 * positive amount with a description, no two alike, adding up to the
 * movement's amount exactly. The amounts come back in shortest form. */
export function checkSplit(
  total: string,
  parts: readonly { amount: string; description: string }[],
):
  | { ok: true; children: { amount: string; description: string }[] }
  | { ok: false; problem: SplitProblem } {
  if (parts.length < 2 || parts.length > SPLIT_PARTS_MAX)
    return { ok: false, problem: { kind: "count" } };
  const whole = centsOf(total);
  let sum = 0n;
  const seen = new Set<string>();
  const children: { amount: string; description: string }[] = [];
  for (const [index, part] of parts.entries()) {
    const amount = centsOf(part.amount);
    if (amount === null)
      return { ok: false, problem: { kind: "amount", index } };
    const description = part.description.trim();
    if (description === "")
      return { ok: false, problem: { kind: "description", index } };
    const key = `${amount}␟${description}`;
    if (seen.has(key))
      return { ok: false, problem: { kind: "duplicate", index } };
    seen.add(key);
    sum += amount;
    children.push({ amount: textOfCents(amount), description });
  }
  if (whole === null || sum !== whole) {
    const difference = whole === null ? 0n : sum - whole;
    return {
      ok: false,
      problem: {
        kind: "sum",
        difference: textOfCents(difference < 0n ? -difference : difference),
        over: difference > 0n,
      },
    };
  }
  return { ok: true, children };
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
  if (suggestion.classification === "MIXED")
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
  suggestion.classification === "MIXED" &&
  suggestion.business_pct === null;

// ---- Dates ---------------------------------------------------------------------

/** The quarter a movement leaves and the one it moves to when its staged
 * dates change its effective date across a quarter, or null. */
export function quarterMove(
  transaction: LedgerTransaction,
  facts: ReturnType<typeof effectiveFacts>,
): { from: LedgerPeriod; to: LedgerPeriod } | null {
  const from = periodOf(transaction.date, "quarter");
  const to = periodOf(facts.value_date ?? facts.booked_date ?? "", "quarter");
  if (!from || !to || samePeriod(from, to)) return null;
  return { from, to };
}
