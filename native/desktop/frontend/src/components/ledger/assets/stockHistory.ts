import type {
  InventoryBook,
  InventoryHistoryKind,
  InventoryMovement,
  ValuationMethod,
} from "../../../shell/ledgerSetup";

// ---- The history of a book ------------------------------------------------------------

/** A fact a change displaced or left in its place. */
export type HistoryFact =
  | { kind: "opening"; value: string }
  | { kind: "method"; value: ValuationMethod }
  | { kind: "label"; value: string }
  | { kind: "description"; value: string | null }
  | { kind: "movement"; value: InventoryMovement }
  | { kind: "removed" };

/** One change, with what it displaced and what stood in its place. */
export type HistoryRow = {
  /** Where the change stands in the history, oldest first. */
  position: number;
  /** The day it was made, year-month-day. */
  day: string;
  kind: InventoryHistoryKind;
  reason:
    | { family: "correction"; token: string }
    | { family: "retirement"; token: string }
    | null;
  before: HistoryFact[];
  after: HistoryFact[];
};

/**
 * The changes of a book, newest first, each with what it displaced and what
 * took its place. What took its place is found in what was kept: the next
 * change of the same fact states what that change displaced, else the book
 * as it stands. Nothing is worked out.
 */
export function historyRows(ledger: InventoryBook): HistoryRow[] {
  const entries = ledger.history ?? [];
  const movements = [
    ...ledger.period_movements,
    ...entries.flatMap((entry) =>
      entry.superseded_movement ? [entry.superseded_movement] : [],
    ),
  ];
  const rows = entries.map((entry, position): HistoryRow => {
    const later = entries.slice(position + 1);
    const before: HistoryFact[] = [];
    const after: HistoryFact[] = [];
    if (entry.prior_opening_stock !== null) {
      before.push({
        kind: "opening",
        value: entry.prior_opening_stock.decimal,
      });
      const next = later.find((found) => found.prior_opening_stock !== null);
      after.push({
        kind: "opening",
        value: (next?.prior_opening_stock ?? ledger.opening_stock).decimal,
      });
    }
    if (entry.prior_valuation_method !== null) {
      before.push({ kind: "method", value: entry.prior_valuation_method });
      const next = later.find((found) => found.prior_valuation_method !== null);
      after.push({
        kind: "method",
        value: next?.prior_valuation_method ?? ledger.valuation_method,
      });
    }
    if (entry.kind === "described") {
      // The first description displaced nothing, so it has no "before".
      if (entry.prior_descriptor !== null) {
        before.push({ kind: "label", value: entry.prior_descriptor.label });
        before.push({
          kind: "description",
          value: entry.prior_descriptor.description,
        });
      }
      const next = later.find((found) => found.kind === "described");
      const now = next?.prior_descriptor ?? ledger.descriptor ?? null;
      if (now !== null) {
        after.push({ kind: "label", value: now.label });
        after.push({ kind: "description", value: now.description });
      }
    }
    if (entry.superseded_movement !== null) {
      before.push({ kind: "movement", value: entry.superseded_movement });
      const replacement = movements.find(
        (found) => found.movement_id === entry.replacement_movement_id,
      );
      // A reversal takes the movement out and puts none in its place.
      if (entry.replacement_movement_id === null)
        after.push({ kind: "removed" });
      else if (replacement)
        after.push({ kind: "movement", value: replacement });
    }
    return {
      position,
      day: entry.recorded_at.slice(0, 10),
      kind: entry.kind,
      reason: entry.correction_reason
        ? { family: "correction", token: entry.correction_reason }
        : entry.retirement_reason
          ? { family: "retirement", token: entry.retirement_reason }
          : null,
      before,
      after,
    };
  });
  return rows.reverse();
}
