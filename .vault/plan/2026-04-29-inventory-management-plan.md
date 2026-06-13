---
tags:
  - '#plan'
  - '#inventory-management'
date: '2026-04-29'
modified: '2026-04-29'
related:
  - '[[2026-04-29-inventory-management-research]]'
  - '[[2026-04-29-inventory-management-adr]]'
---

# `inventory-management` `implementation` plan

Implement a profile-owned inventory and amortization tracking surface for
autonomo activities, grounded in the M100 foundations and BOE-verified LIS,
LIRPF, and RIRPF rules.

## Proposed Changes

Create public profile APIs for long-lived assets and short-lived inventory,
persisted as schema-versioned JSON under the config profile root. Add strict
models, computations, structured errors, and CLI commands. Add a small Anexo D
derivation helper that overlays ledger-derived `0155` and `0173` while leaving
existing aggregate callers compatible.

## Tasks

- Foundation artifacts and legal verification
  1. Record BOE findings and #216 Path A decision.
  1. Add tests that lock the representative LIS art. 12.1.a coefficients.
- Assets ledger
  1. Add strict `AssetRecord` and `AmortizationLedger` models.
  1. Add JSON load/save and record-amortization helpers.
  1. Enforce cost-basis caps and optional libertad de amortizacion.
- Inventory ledger
  1. Add strict `InventoryLedger` and `MovementRecord` models.
  1. Add JSON load/save and movement helpers.
  1. Compute FIFO, PMP, and coste medio variation and explicitly refuse LIFO.
- CLI and M100 integration
  1. Create `aeat profile assets` and `aeat profile inventory`.
  1. Register JSON output schemas.
  1. Add Anexo D overlay helper for `0155` and `0173`.
- Documentation and review
  1. Add concept documentation and Kent capability coverage.
  1. Write execution records and run the formal code review.
- Continuation audit loops
  1. Run a full Kent UX experience audit loop for the inventory-management CLI:
     command discovery, add/list/show/record flows, JSON/plain output, error
     copy, trilingual behavior, and capability/coverage alignment.
  1. Run a persistence-adherence audit loop against the #216 storage layer now
     merged into this worktree: compare Path A JSON ledgers with the governed
     persistence substrate, classify the data, document migration criteria, and
     identify any immediate security gaps.
  1. Run a data-security opt-in and adherence support loop: define operator
     opt-in boundaries, unsafe/plaintext warnings, storage-root controls, and
     future migration hooks for encrypted profile ledgers.

## Parallelization

Assets and inventory code can be developed independently after the error
registry entries exist. CLI work depends on both public APIs. M100 helper tests
depend on both computations.

## Verification

Run focused unit tests for assets, inventory, M100 helper, and CLI commands.
Run `just lint`, `just typecheck`, `just test`, and `just hooks` if time and
environment allow. The review gate must verify the ten issue invariants:
strict models, enum reuse, BOE coefficient lock, basis cap, LIFO refusal,
inventory variation, backwards compatibility, Path A JSON persistence,
multi-actividad behavior, and #398 error registration.

Continuation verification must add UX transcript evidence, persistence-layer
classification evidence against #216, and security opt-in/adherence evidence
before any future PR claims those loops as complete.
