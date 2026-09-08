---
tags:
  - '#audit'
  - '#reachability-burndown'
date: '2026-09-08'
modified: '2026-09-08'
body_schema: 'body-v2'
body_hash: 'sha256:6a1dc98a67f2bdccca05ec7b612b219bab6ea78ed88b44fb98fa5f801c188b54'
related:
  - "[[2026-09-04-reachability-burndown-plan]]"
  - "[[2026-09-04-reachability-burndown-W05-P12-S190]]"
---

# `reachability-burndown` audit: `S190 inventory facade deduplication implementation review`

## Scope

Independent review of `W05.P12.S190` against the plan row, Step Record, complete current `inventory.py`, focused test migrations, shared runtime-attached repository proofs, live application inventory service, aggregation resolver composition, and the exact reachability detector.

The three removed functions were pure convenience wrappers around `InventoryLedgerRepository`: `create_inventory_ledger` delegated to `create`, `load_inventory` projected `load().ledgers`, and `save_inventory` wrapped a tuple in `InventoryLedgerDocument` before `save`. Current tests and runtime proofs now call the repository directly with the same document and tuple projections. No compatibility alias, baseline, threshold, disposition list, or second persistence owner was introduced.

Live ownership remains intact. `InventoryService` constructs bucket-bound `InventoryLedgerRepository` instances and drives create, load, save, remove, movement, and closing-authority behavior. Modelo calculation composition injects `inventory_ledger_repository_for_bucket` into `InventorySourceResolver`, while aggregation retains its repository protocol. The secure namespace and repository class are unchanged.

Independent verification reproduced the Step Record: Ruff passed; the focused command passed 7 tests; the exact detector reports 338 unused symbols and 18 orphan tests, confirming the stated 341-to-338 reduction. The broad runtime failures described by the record concern workflow-envelope validation, verification-report registry provenance, M303 carry ingress provenance, and borrador snapshot provenance; they are peer-owned and unrelated to the three facade removals.

## Findings

### inventory-facade-doc-residue | low | Two docstrings still name the deleted save_inventory path

The implementation and imports contain no remaining use of `create_inventory_ledger`, `load_inventory`, or `save_inventory`, but `test_inventory_actividad_year_uniqueness.py` and the production `InventoryLedgerDocument` docstring in `domain.contribuyente.inventory.records` still describe a `save / save_inventory` path. After S190 there is no `save_inventory` callable. These statements now misdescribe the owning write surface and leave semantic residue for the duplicate facade that this step claims to remove. Runtime behavior is correct, but closure is withheld until both references name only the canonical repository `save` path.

### inventory-facade-doc-residue-resolution | low | Canonical repository wording replaces both stale facade references

Both affected docstrings now name `InventoryLedgerRepository.save` as the write path. An exact scan finds none of the deleted callable identities; the only substring match is the legitimate locale key `load_inventory_ledger_failed`, which names a repository load failure rather than the removed `load_inventory` facade. The original finding is resolved.

### final-disposition | low | Approved with no open S190 findings

The expanded focused scope passes 36 tests and Ruff is clean. The Step Record includes both repaired docstring paths and exact commands. Repository ownership, live application and aggregation wiring, secure namespace behavior, and the 341-to-338 signal reduction remain verified. Independent review approves closing `W05.P12.S190`.

## Recommendations

Approve `W05.P12.S190` for closure. No S190 remediation remains.

Continue the reachability campaign from the live exact signal of 338 unused symbols and 18 orphan tests; do not absorb the peer-owned broad runtime failures into this step.
