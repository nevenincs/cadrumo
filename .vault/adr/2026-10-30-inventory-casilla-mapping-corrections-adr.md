---
tags:
  - '#adr'
  - '#inventory-casilla-mapping'
date: '2026-10-30'
modified: '2026-10-30'
body_schema: 'body-v2'
body_hash: 'sha256:6d882e97a2d0928615de44c8048f8e54e40a5f979765a5ae9a51a811e7f2d15f'
related:
  - "[[2026-08-23-inventory-casilla-mapping-adr]]"
  - '[[2026-08-23-inventory-casilla-grounding-research]]'
---

# `inventory-casilla-mapping` adr: `Inventory corrections and retirement` | (**status:** `accepted`)

Authorization basis: the operator instructed that inventory items can be added, edited and removed in a Ledger tab, and on 2026-10-30 instructed that known blockers be fixed. Both instructions were relayed in this work's assignment, and they ask for this decision to be made from the law and the ledger invariants without asking.

## Problem Statement

Inventory had create, movement add, valuation preview and closing-authority operations, and no way to edit or remove. Stock facts feed FIFO and weighted-average valuation, the Anexo D projection and the next year's opening, so edit and remove need a meaning that does not rewrite evidence or move a calculated period silently.

## Considerations

- Orden HAC/773/2019 art. 11 (BOE-A-2019-10487): an error in a register is rectified by a further annotation, so each quarter's totals remain determinable.
- Código de Comercio art. 29.1 and art. 30 (BOE-A-1885-6627): no erasure, and six-year retention. RIRPF art. 68.1 retains documents through prescription.
- LIRPF art. 28 and LIS art. 17 keep valuation method and stock as tax facts, not display data.
- The ledger rule: corrections preserve revision or reversal evidence rather than erase history; amounts are magnitudes.
- `CalculationRevision.row_source_identities` already stores each inventory row's activity and projection fingerprint, which is a drift anchor needing no new revision shape.
- A movement added after a closing authority moved the movement-derived closing with no refusal. That is the same hole a correction would open.

## Considered options

- Effective set plus append-only history, chosen. `period_movements` stays the effective set, so no valuation or projection consumer filters anything.
- Status flags on movements in `period_movements`, rejected. Every consumer would have to filter, and one that forgot would value a cancelled movement.
- Negative reversing movements, rejected. They encode direction in the sign, against the magnitude rule, and quantity is `gt=0`.
- Physical delete of an empty ledger, rejected. Retirement covers it, and one removal meaning is simpler than two. The unreleased physical `remove` verbs, reached only by tests, are deleted.

## Constraints

- Nothing a correction displaces is lost: the superseded movement, prior opening, prior method and prior descriptor stay in `InventoryLedger.history`. A superseded movement id is never reissued.
- Every change carries a caller-chosen `correction_id`. The same id with the same content is an exact replay with no write and no event. The same id with other content refuses.
- Stock facts freeze once consumed. A recorded closing authority, or the next year's closing authority for the same activity, refuses movement add, opening or method correction, movement correction, reversal and retirement. Descriptive facts never enter valuation or fingerprints and stay editable, including on a retired ledger.
- Retirement keeps every fact. A retired ledger refuses stock changes until restored. A retired ledger still holding stock facts makes the Anexo D cohort unresolved rather than dropping them; one without facts leaves the cohort.
- A cohort that differs from a draft's recorded inventory rows blocks that draft through the existing drift route, `_ledger_drift_gate.py`. A filed revision stays immutable; its correction runs through the amendment route.
- Refusals are typed reasons with catalogue keys and facts.
- Weighted-average valuation now refuses a count above stock, as FIFO already did.

## Implementation

We will add `ledger.inventory.inspect`, `describe`, `correct`, `movement.correct`, `movement.reverse`, `retire` and `restore` as registered operations reaching CLI, TUI and MCP as the other inventory operations do. The pure transforms live in `src/cadrumo/domain/contribuyente/inventory/corrections.py` and run inside the repository's revision guard. The persisted schema version stays 3, because the two new ledger fields are additive defaults.

## Rationale

The effective set plus history satisfies the rectification and retention rules with no change to any valuation consumer. Freezing consumed facts is stricter than the law requires, and it is what makes silent movement of a calculated period impossible: the only ledgers a correction can reach have no authority, and the Anexo D projection cannot exist without one.

## Consequences

- An operator who needs to correct stock after recording a closing authority has no route yet. Replacing a recorded authority is a separate decision, and this refusal is its visible trigger.
- A ledger with no closing authority never reached a calculation, so the drift finding fires only for cohort changes: another activity's authority, or a retirement. It stays as the guard against a stored document changing beneath a draft.
- Reversing a movement can make a valuation refuse; the operator then corrects in date order. The history keeps every step.
- Events and ledger writes share no transaction, as with the other inventory verbs. A crash between them followed by a replay leaves the change recorded in history with no event.
