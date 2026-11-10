// What each classification takes, as the backend serves it with
// `ledger.entry-options`. This is the one place the window holds it, and only
// while the Ledger page is open: there is no copy to fall back on, so with
// nothing served each answer is null, which is not a no. A caller acts on a
// served true or false alone, and a refusal stays the ledger's to give.

import { useSyncExternalStore } from "react";
import { FIELDS_DROPPED_BY_PERSONAL } from "./ledgerContract";
import type { LedgerEntryClassification } from "./ledgerSetup";

let held: readonly LedgerEntryClassification[] | null = null;
const listeners = new Set<() => void>();

/** Holds what the backend served, or null where it has served nothing. */
export function holdLedgerClassifications(
  rows: readonly LedgerEntryClassification[] | null,
): void {
  if (held === rows) return;
  held = rows;
  for (const listener of listeners) listener();
}

function subscribe(listener: () => void): () => void {
  listeners.add(listener);
  return () => listeners.delete(listener);
}

/** The rows served, drawing again when they arrive or go. A control that asks
 * below calls this once, so that it draws again with the answer. */
export const useLedgerClassifications = ():
  readonly LedgerEntryClassification[] | null =>
  useSyncExternalStore(subscribe, () => held);

/** The served row of a classification, or null where it is not served: the
 * Ledger page is closed, the backend has not answered, or it names no such
 * classification. */
export const classificationRule = (
  id: string,
): LedgerEntryClassification | null =>
  held?.find((row) => row.classification === id) ?? null;

/** Whether a movement so classified carries a business share; null where it
 * is not served. */
export const takesBusinessShare = (id: string): boolean | null =>
  classificationRule(id)?.takes_business_share ?? null;

/** Whether a movement so classified carries a usage ratio; null where it is
 * not served. */
export const takesUsageRatio = (id: string): boolean | null =>
  classificationRule(id)?.takes_usage_ratio ?? null;

/** Whether a movement so classified carries business figures; null where it
 * is not served. */
export const carriesBusinessFigures = (id: string): boolean | null =>
  classificationRule(id)?.carries_business_figures ?? null;

/** Whether a movement so classified keeps the spending category it names;
 * null where it is not served. */
export const keepsCategory = (id: string): boolean | null =>
  classificationRule(id)?.keeps_category ?? null;

/** The classifications served as carrying business figures, in the
 * backend's order; null where none are served. */
export const classificationsCarryingBusinessFigures = ():
  readonly string[] | null =>
  held === null
    ? null
    : held
        .filter((row) => row.carries_business_figures)
        .map((row) => row.classification);

/** Whether a rule deciding it may name a spending category; null where it is
 * not served. */
export const ruleMayNameCategory = (id: string): boolean | null =>
  classificationRule(id)?.rule_may_name_category ?? null;

/** Whether a split part so classified is advised to name a spending category.
 * It is advice: no write refuses a part without one. Null where it is not
 * served. */
export const splitPartAdvisedCategory = (id: string): boolean | null =>
  classificationRule(id)?.split_part_requires_category ?? null;

/**
 * The stored fields a write of `id` drops from a movement, from what the
 * backend serves of the classification: the share where it takes none, the
 * usage ratio where it takes none, and the business figures, category
 * included, where it carries none. Only the fields the ledger lists as
 * dropped are named; nothing is named for a classification that is not
 * served.
 */
export const fieldsDroppedBy = (id: string): readonly string[] =>
  FIELDS_DROPPED_BY_PERSONAL.filter((field) =>
    field === "business_pct"
      ? takesBusinessShare(id) === false
      : field === "usage_ratio_id"
        ? takesUsageRatio(id) === false
        : carriesBusinessFigures(id) === false,
  );
