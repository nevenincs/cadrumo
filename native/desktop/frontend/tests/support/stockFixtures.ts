import type { InventoryMovementProjection } from "../../src/shell/ledgerInventoryContract";
import { fixtureDay } from "../../src/dev/fixtureDates";

/** A sale of stock as the inventory reads serve a movement. */
export const movement = (
  id: string,
  quantity: string,
): InventoryMovementProjection => ({
  movement_id: id,
  movement_date: fixtureDay(11, 20, -1),
  kind: "cogs",
  sku: "papel-a3",
  quantity: { decimal: quantity },
  unit_cost: null,
  taxable_base: null,
  iva_rate: { decimal: "0.21" },
  iva_amount: null,
  deductible_iva_ratio: { decimal: "1" },
  acquisition_cost: null,
  schema_version: "1",
  acquisition_detail: null,
  ledger_row: "unstated",
  claimed_transaction_id: null,
});
