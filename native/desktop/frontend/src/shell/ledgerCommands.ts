// The Ledger page's commands that several controls reach: one definition
// each, so a group header, a shortcut, the palette and the inspector cannot
// do the same thing in different ways. A command decides here what it would
// stage and why it cannot; the page asks the person for what is missing,
// stages the cells it returns and says what it staged. Nothing here writes.

import type { LedgerRow } from "./ledger";
import { parsePercent, type GrammarRefusal } from "./ledgerGrammar";
import {
  effectiveFacts,
  storedFieldValue,
  type StageCell,
  type StageEvent,
  type StagedContent,
} from "./ledgerStage";
import { isSpendingCategory, takesShare } from "./ledgerVocabulary";

export const CLASSIFY_KINDS = ["business", "personal", "mixed"] as const;
export type ClassifyKind = (typeof CLASSIFY_KINDS)[number];

/** The stored classification each classify command sets. */
export const CLASSIFICATION_OF: Record<ClassifyKind, string> = {
  business: "BUSINESS",
  personal: "PERSONAL",
  mixed: "MIXED",
};

/** The movements a classify command is asked to act on: the selection, or
 * a group's movements, in the order they are drawn. */
export type ClassifyTarget = {
  ids: readonly string[];
  /** How many of them filters, the search or a folded group hide. */
  hidden: number;
  /** The window they come from is read only in part, so a selection of
   * "everything" covers the loaded rows only. */
  partial: boolean;
};

/** Why a classify command cannot run on its target. */
export type ClassifyBlock =
  | { kind: "nothing_selected" }
  /** Some named movements are not drawn: the person chooses first whether
   * to show them or keep only the visible ones. */
  | { kind: "hidden"; hidden: number; selected: number }
  /** Every named movement is a transfer, which is Personal or unclassified
   * only. */
  | { kind: "transfers_only" }
  /** None of the named movements is active, and only active movements
   * take a change. */
  | { kind: "inactive_only" };

export type ClassifyAvailability =
  | {
      kind: "ready";
      /** The movements it will stage a change on. */
      ids: string[];
      /** Named movements left as they are: transfers, for Business and
       * Mixed, and movements that are not active. */
      skipped: number;
      partial: boolean;
    }
  | { kind: "blocked"; block: ClassifyBlock };

const TRANSFER = "INTERNAL_TRANSFER";

/**
 * Whether a movement takes a spending category: an expense, or an income
 * that refunds one, carrying a purchase invoice. A spending category says
 * what a business expense is; pure income is classified by its direction
 * alone and never reads one, as the product's readiness check holds. With
 * `staged`, the movement is read as it would be once saved: its staged
 * direction, and a purchase invoice staged to be attached.
 */
export function takesExpenseCategory(
  row: LedgerRow,
  staged?: StagedContent,
): boolean {
  const id = row.transaction.transaction_id;
  const direction = staged
    ? effectiveFacts(row, staged.rows[id]).direction
    : row.transaction.direction;
  const evidence =
    row.transaction.purchase_invoice_evidence_id !== null ||
    (staged?.actions.some(
      (action) =>
        (action.kind === "attach" &&
          action.transactionId === id &&
          action.evidenceId !== null) ||
        (action.kind === "attach_file" && action.transactionId === id),
    ) ??
      false);
  return direction === "OUTGOING" || (direction === "INCOMING" && evidence);
}

/** How the movements a classify command stages split by what they take: a
 * spending category, or none, being income. */
export function categorySplit(
  ids: readonly string[],
  rows: ReadonlyMap<string, LedgerRow>,
  staged?: StagedContent,
): { expenses: number; income: number } {
  let expenses = 0;
  let income = 0;
  for (const id of ids) {
    const row = rows.get(id);
    if (!row) continue;
    if (takesExpenseCategory(row, staged)) expenses += 1;
    else income += 1;
  }
  return { expenses, income };
}

/** Whether `kind` can classify `target`, and on which movements. */
export function classifyAvailability(
  kind: ClassifyKind,
  target: ClassifyTarget,
  rows: ReadonlyMap<string, LedgerRow>,
): ClassifyAvailability {
  if (target.hidden > 0) {
    if (!target.ids.some((id) => rows.has(id)))
      return { kind: "blocked", block: { kind: "nothing_selected" } };
    return {
      kind: "blocked",
      block: {
        kind: "hidden",
        hidden: target.hidden,
        selected: target.ids.length,
      },
    };
  }
  const named = target.ids.filter((id) => rows.has(id));
  if (named.length === 0)
    return { kind: "blocked", block: { kind: "nothing_selected" } };
  const active = named.filter(
    (id) => rows.get(id)!.transaction.lifecycle_state === "ACTIVE",
  );
  if (active.length === 0)
    return { kind: "blocked", block: { kind: "inactive_only" } };
  const ids =
    kind === "personal"
      ? active
      : active.filter((id) => rows.get(id)!.transaction.direction !== TRANSFER);
  if (ids.length === 0)
    return { kind: "blocked", block: { kind: "transfers_only" } };
  return {
    kind: "ready",
    ids,
    skipped: target.ids.length - ids.length,
    partial: target.partial,
  };
}

/** The categories with a business-use ratio configured, by year, as
 * `ledger.ratios.list` answers them: a configured category is the usage
 * ratio a Mixed movement of that year names. A year absent was not read
 * yet; null where its ratios could not be read or the censo withholds
 * them. */
export type ConfiguredRatios = ReadonlyMap<number, ReadonlySet<string> | null>;

/** The movement's year, which its usage ratio is configured for. */
const yearOf = (row: LedgerRow) => Number(row.transaction.date.slice(0, 4));

/** How Mixed with `category` stands on the movements that take one: those
 * whose year has a ratio configured for it, those whose year has none,
 * and those whose year's ratios were not read. */
export type RatioCoverage = { staged: number; missing: number; unread: number };
export function ratioCoverage(
  ids: readonly string[],
  rows: ReadonlyMap<string, LedgerRow>,
  category: string,
  ratios: ConfiguredRatios | undefined,
  staged?: StagedContent,
): RatioCoverage {
  const out: RatioCoverage = { staged: 0, missing: 0, unread: 0 };
  for (const id of ids) {
    const row = rows.get(id);
    if (!row || !takesExpenseCategory(row, staged)) continue;
    const configured = ratios?.get(yearOf(row));
    if (configured === undefined || configured === null) out.unread += 1;
    else if (configured.has(category)) out.staged += 1;
    else out.missing += 1;
  }
  return out;
}

/** What the person supplied with the command: Business names a category
 * where a movement takes one, Mixed a business share, typed as a
 * percentage, and the category where a movement takes one. `ratios` are
 * the configured usage ratios Mixed names with its category. */
export type ClassifyRequest = {
  kind: ClassifyKind;
  ids: readonly string[];
  category?: string | null;
  share?: string | null;
  ratios?: ConfiguredRatios;
  /** What is staged already: a movement is read as it would be saved. */
  staged?: StagedContent;
};

export type ClassifyOutcome =
  /** Asked for again with the field filled in. */
  | { kind: "needs"; field: "category" | "share" }
  | { kind: "refused"; field: "share"; refusal: GrammarRefusal }
  | {
      kind: "staged";
      /** The one stage event that stages it, undone as one step. */
      event: Extract<StageEvent, { type: "stage" }>;
      /** How many movements it stages a change on. */
      movements: number;
    };

/**
 * The cells that classify `request.ids` as asked: the classification, the
 * share with Mixed and a clear of a stored share where the movement stops
 * being Mixed, and the category with Business or Mixed on the movements
 * that take a spending category; income takes none. Mixed takes only a
 * category a share applies to. Where a movement takes a category and none
 * was given, the category is asked for. A category already stored is left
 * as it is for Personal, and for income. Mixed names the category as its
 * usage ratio where the movement's year has a ratio configured for it, as
 * the product's readiness check asks of every Mixed movement; elsewhere
 * none is staged, and the step says so. Movements the rows do not hold are
 * left out.
 */
export function classifyCells(
  request: ClassifyRequest,
  rows: ReadonlyMap<string, LedgerRow>,
): ClassifyOutcome {
  let category: string | null = null;
  let share: string | null = null;
  if (request.kind === "mixed") {
    const parsed = parsePercent(request.share ?? "");
    if (parsed.kind === "empty") return { kind: "needs", field: "share" };
    if (parsed.kind === "refused")
      return { kind: "refused", field: "share", refusal: parsed.refusal };
    share = parsed.value;
  }
  if (request.kind !== "personal") {
    const expenses = categorySplit(request.ids, rows, request.staged).expenses;
    const given = request.category ?? null;
    const fits =
      given !== null &&
      isSpendingCategory(given) &&
      (request.kind === "business" || takesShare(given));
    if (expenses > 0 && !fits) return { kind: "needs", field: "category" };
    if (expenses > 0) category = given;
  }
  const cells: StageCell[] = [];
  let movements = 0;
  for (const id of request.ids) {
    const row = rows.get(id);
    if (!row) continue;
    movements += 1;
    cells.push({
      id,
      field: "business_classification",
      value: { kind: "set", value: CLASSIFICATION_OF[request.kind] },
      stored: storedFieldValue(row, "business_classification"),
    });
    const storedShare = storedFieldValue(row, "business_pct");
    if (share !== null)
      cells.push({
        id,
        field: "business_pct",
        value: { kind: "set", value: share },
        stored: storedShare,
      });
    else if (storedShare !== null && storedShare !== undefined)
      cells.push({
        id,
        field: "business_pct",
        value: { kind: "clear" },
        stored: storedShare,
      });
    if (category !== null && takesExpenseCategory(row, request.staged)) {
      cells.push({
        id,
        field: "category_id",
        value: { kind: "set", value: category },
        stored: storedFieldValue(row, "category_id"),
      });
      if (
        request.kind === "mixed" &&
        request.ratios?.get(yearOf(row))?.has(category)
      )
        cells.push({
          id,
          field: "usage_ratio_id",
          value: { kind: "set", value: category },
          stored: storedFieldValue(row, "usage_ratio_id"),
        });
    }
  }
  return {
    kind: "staged",
    event: { type: "stage", label: "bulk_set", cells },
    movements,
  };
}

/**
 * The page's one way to classify movements as Business, Personal or Mixed.
 * The inspector, Alt+B, Alt+P and Alt+M, the palette and a group header's
 * buttons all call it. Without `ids` it acts on the selection; a group
 * header names its own movements. The page asks for the category or share
 * the kind needs, then stages what `classifyCells` returns.
 */
export type ClassifySelection = (
  kind: ClassifyKind,
  scope?: ClassifyScope,
) => void;
/** What a classify command acts on, where not the selection, and what the
 * control already asked for: a field beside the control that holds the
 * category or the share is not asked for again. */
export type ClassifyScope = {
  ids?: readonly string[];
  answer?: { category?: string; share?: string };
};

/** The classifications a category belongs to: a category says what a
 * business expense is, so it is set only where the movement is Business or
 * Mixed. */
const TAKES_CATEGORY = ["BUSINESS", "MIXED"];

/**
 * The cells that set `category` on those of `ids` that are active,
 * classified Business or Mixed and take a spending category; the others
 * are counted as skipped, since a movement still to classify is classified
 * first, with its category, and income takes none.
 */
export function categoryCells(
  ids: readonly string[],
  category: string,
  rows: ReadonlyMap<string, LedgerRow>,
  staged?: StagedContent,
):
  | {
      kind: "staged";
      event: Extract<StageEvent, { type: "stage" }>;
      movements: number;
      skipped: number;
    }
  | { kind: "nothing"; skipped: number } {
  const cells: StageCell[] = [];
  let skipped = 0;
  for (const id of ids) {
    const row = rows.get(id);
    if (
      !row ||
      row.transaction.lifecycle_state !== "ACTIVE" ||
      !TAKES_CATEGORY.includes(row.transaction.business_classification) ||
      !takesExpenseCategory(row, staged) ||
      !isSpendingCategory(category)
    ) {
      skipped += 1;
      continue;
    }
    cells.push({
      id,
      field: "category_id",
      value: { kind: "set", value: category },
      stored: storedFieldValue(row, "category_id"),
    });
  }
  return cells.length
    ? {
        kind: "staged",
        event: { type: "stage", label: "bulk_set", cells },
        movements: cells.length,
        skipped,
      }
    : { kind: "nothing", skipped };
}

/** What a rule made from a selection or a group starts from: the
 * movements it was made from. */
export type RuleSeed = { ids: readonly string[] };
/**
 * Opens the rule dialog over the page, prefilled from what the movements
 * share. A group header, the inspector and the palette call it; nothing is
 * saved until the person saves the rule.
 */
export type OpenRuleFromSelection = (seed: RuleSeed) => void;
