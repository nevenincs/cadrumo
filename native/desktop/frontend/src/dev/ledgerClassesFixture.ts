// What each admitted ledger definition may do to the profile's records, as
// the host classes it: a read declares no effect that changes records, a
// write may change them, and a review may change them after the person
// answers it. The browser cannot read the host's manifest, so the two lists
// below copy its write and review families; a unit test compares them with
// the shipped manifest and the host's admitted list, definition by
// definition. Every other admitted definition is a read.

import type { LedgerDefinitionId } from "../shell/ledger";

export const LEDGER_WRITES: readonly string[] = [
  "ledger.actividad-asset.claim",
  "ledger.actividad-asset.correct",
  "ledger.actividad-asset.create",
  "ledger.actividad-asset.describe",
  "ledger.actividad-asset.dispose",
  "ledger.add",
  "ledger.allocate",
  "ledger.archive",
  "ledger.attach",
  "ledger.bienes_inversion.declare",
  "ledger.classify.bulk",
  "ledger.classify.iva-derive",
  "ledger.classify.single",
  "ledger.counterparty",
  "ledger.detach",
  "ledger.evidence.add",
  "ledger.evidence.batch",
  "ledger.evidence.confirm",
  "ledger.evidence.extract",
  "ledger.evidence.remove",
  "ledger.evidence.update",
  "ledger.exclude",
  "ledger.export",
  "ledger.import",
  "ledger.inventory.closing-authority.record",
  "ledger.inventory.closing-value.record",
  "ledger.inventory.correct",
  "ledger.inventory.create",
  "ledger.inventory.describe",
  "ledger.inventory.evidence.add",
  "ledger.inventory.movement.add",
  "ledger.inventory.movement.claim",
  "ledger.inventory.movement.correct",
  "ledger.inventory.movement.reverse",
  "ledger.inventory.restore",
  "ledger.inventory.retire",
  "ledger.inventory.valuation.preview",
  "ledger.invoice.add",
  "ledger.invoice.attach_document",
  "ledger.invoice.import",
  "ledger.invoice.remove",
  "ledger.invoice.update",
  "ledger.invoice.wizard",
  "ledger.link",
  "ledger.merge",
  "ledger.own_account",
  "ledger.participation.rebuild",
  "ledger.prorrata.declare_gross",
  "ledger.prorrata.declare_sector",
  "ledger.prorrata.elect_especial",
  "ledger.prorrata.elect_general",
  "ledger.prorrata.remove_gross",
  "ledger.prorrata.revoke_especial",
  "ledger.prorrata.seed",
  "ledger.prorrata.seed_sector",
  "ledger.prorrata.settle_sector",
  "ledger.ratios.set",
  "ledger.ratios.unset",
  "ledger.remove",
  "ledger.reset",
  "ledger.restore",
  "ledger.retencion_soportada.attest_absence",
  "ledger.retencion_soportada.record",
  "ledger.retencion_soportada.remove",
  "ledger.retencion_soportada.withdraw_absence",
  "ledger.rule.add",
  "ledger.rule.apply",
  "ledger.rule.remove",
  "ledger.split.manual",
  "ledger.stash",
  "ledger.update",
];

export const LEDGER_REVIEWS: readonly string[] = [
  "ledger.classify.review",
  "ledger.split.review",
];

export type LedgerClass = "read" | "write" | "review";

export function ledgerClassOf(definition: LedgerDefinitionId): LedgerClass {
  if (LEDGER_REVIEWS.includes(definition)) return "review";
  return LEDGER_WRITES.includes(definition) ? "write" : "read";
}
