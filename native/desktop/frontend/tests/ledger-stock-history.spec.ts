import { expect, test } from "@playwright/test";
import { historyRows } from "../src/components/ledger/assets/stockHistory";
import type {
  InventoryLedgerProjection,
  InventoryHistoryEntryProjection,
} from "../src/shell/ledgerInventoryContract";
import { fixtureDay, fixtureYear } from "../src/dev/fixtureDates";
import { movement } from "./support/stockFixtures";

const PRIOR = fixtureYear - 1;

// The Stock panel's history of a book: the newest change first, with what each
// displaced and what took its place. No page is opened.

const change = (
  id: string,
  day: string,
  kind: InventoryHistoryEntryProjection["kind"],
  facts: Partial<InventoryHistoryEntryProjection> = {},
): InventoryHistoryEntryProjection => ({
  correction_id: id,
  kind,
  recorded_at: `${day}T09:30:00Z`,
  actor: "runtime",
  correction_reason: null,
  retirement_reason: null,
  superseded_movement: null,
  replacement_movement_id: null,
  prior_opening_stock: null,
  prior_valuation_method: null,
  prior_descriptor: null,
  ...facts,
});

const ledgerOf = (
  history: InventoryHistoryEntryProjection[],
): InventoryLedgerProjection => ({
  actividad_id: "Papelería",
  year: PRIOR,
  valuation_method: "pmp",
  opening_stock: { decimal: "400" },
  opening_layers: [],
  period_movements: [movement("current", "60")],
  closing_authority_fingerprints: null,
  schema_version: "1",
  bucket_event_ids: [],
  descriptor: { label: "Tienda", description: null },
  retired: false,
  retirement_reason: null,
  history,
  advisories: [],
});

test("the history lists the newest change first, with what each displaced and what took its place", () => {
  const rows = historyRows(
    ledgerOf([
      change("a", fixtureDay(2, 10, -1), "opening_corrected", {
        correction_reason: "keying_error",
        prior_opening_stock: { decimal: "308" },
      }),
      change("b", fixtureDay(3, 1, -1), "opening_corrected", {
        correction_reason: "keying_error",
        prior_opening_stock: { decimal: "380" },
        prior_valuation_method: "fifo",
      }),
      change("c", fixtureDay(11, 24, -1), "movement_corrected", {
        correction_reason: "source_document_corrected",
        superseded_movement: movement("old", "50"),
        replacement_movement_id: "current",
      }),
      change("d", fixtureDay(11, 25, -1), "movement_reversed", {
        correction_reason: "duplicate_entry",
        superseded_movement: movement("gone", "5"),
      }),
      change("e", fixtureDay(12, 1, -1), "described", {
        prior_descriptor: { label: "Papel", description: "Antes" },
      }),
      change("f", fixtureDay(12, 31, -1), "retired", {
        retirement_reason: "activity_ceased",
      }),
    ]),
  );

  expect(rows.map((row) => row.kind)).toEqual([
    "retired",
    "described",
    "movement_reversed",
    "movement_corrected",
    "opening_corrected",
    "opening_corrected",
  ]);
  expect(rows[0]).toMatchObject({
    day: fixtureDay(12, 31, -1),
    reason: { family: "retirement", token: "activity_ceased" },
    before: [],
    after: [],
  });
  // Each opening value is found in the next change of it, else in the book.
  const second = rows[4];
  const first = rows[5];
  expect(first?.before).toEqual([{ kind: "opening", value: "308" }]);
  expect(first?.after).toEqual([{ kind: "opening", value: "380" }]);
  expect(second?.before).toEqual([
    { kind: "opening", value: "380" },
    { kind: "method", value: "fifo" },
  ]);
  expect(second?.after).toEqual([
    { kind: "opening", value: "400" },
    { kind: "method", value: "pmp" },
  ]);
  // What replaced a movement is the movement the book holds under its reference.
  expect(rows[3]?.after).toEqual([
    { kind: "movement", value: movement("current", "60") },
  ]);
  expect(rows[2]?.after).toEqual([{ kind: "removed" }]);
  expect(rows[1]?.before).toEqual([
    { kind: "label", value: "Papel" },
    { kind: "description", value: "Antes" },
  ]);
  expect(rows[1]?.after).toEqual([
    { kind: "label", value: "Tienda" },
    { kind: "description", value: null },
  ]);
});

test("a book never changed has no history, and the history carries no reference to show", () => {
  expect(historyRows(ledgerOf([]))).toEqual([]);
  const rows = historyRows(
    ledgerOf([
      change("secret-reference", fixtureDay(2, 10, -1), "opening_corrected", {
        prior_opening_stock: { decimal: "308" },
      }),
    ]),
  );
  expect(JSON.stringify(rows)).not.toContain("secret-reference");
});
