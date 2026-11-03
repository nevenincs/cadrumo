// What each classification takes, as the backend serves it with
// `ledger.entry-options`. This is the one place the window holds it, and only
// while the Ledger page is open: there is no copy to fall back on, so with
// nothing served each answer is null, which is not a no. A caller acts on a
// served true or false alone, and a refusal stays the ledger's to give.

import { useSyncExternalStore } from "react";
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

/** Whether a rule deciding it may name a spending category; null where it is
 * not served. */
export const ruleMayNameCategory = (id: string): boolean | null =>
  classificationRule(id)?.rule_may_name_category ?? null;

/** Whether a split part so classified is advised to name a spending category.
 * It is advice: no write refuses a part without one. Null where it is not
 * served. */
export const splitPartAdvisedCategory = (id: string): boolean | null =>
  classificationRule(id)?.split_part_requires_category ?? null;
