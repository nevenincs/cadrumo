---
tags:
  - '#exec'
  - '#tui-architecture'
date: '2026-08-25'
modified: '2026-08-25'
body_schema: 'body-v1'
body_hash: 'sha256:89cfa1c1c5b02e7d868b5353945e8a5b5fbeaf5e5c1b63b348e05c03c99b175d'
step_id: 'S169'
related:
  - "[[2026-08-11-tui-architecture-plan]]"
---

# Hard-move WorkUnitCatalogueRepositoryProtocol from the private domain/modelos/_protocols.py definition into the sole public semantically named domain/modelos/work_unit_repository.py defining module, atomically migrate the exact 20 application consumers plus every adapter, development, test, fixture, annotation, registration, and dynamic caller to direct defining-module imports, delete the package re-export, old definition, alias, shim, fallback, and compatibility surfaces, retain the one-record atomic bare-and-enveloped profile singleton contract by collapsing the hand decoder in modelos_work_units into the shared secure-document kernel, make load project load_revisioned, remove every second load and bare raw preflight while preserving exactly one adapter exception translation, rehome replay-guard persistence in its adapter owner and delete the adapter-package bridge and parallel reader, prove with real encrypted-SQL present/absent interleavings that each observation performs one SELECT and returns the singleton plus revision from the same SecureObjectRecord with encryption, CAS, and lineage intact, and enforce exact AST plus Vaultspec-RAG fixed-point gates for direct imports and zero remnant or parallel decoder/reader authority

## Scope

- `src/cadrumo/domain/modelos/work_unit_repository.py`
- `retired WorkUnitCatalogueRepositoryProtocol definition in src/cadrumo/domain/modelos/_protocols.py`
- `src/cadrumo/domain/modelos/__init__.py`
- `the exact 20 application consumers under src/cadrumo/application/ledger`
- `src/cadrumo/application/calculations`
- `and src/cadrumo/application/modelo`
- `src/cadrumo/adapters/persistence/profile/_secure_enveloped_document.py`
- `src/cadrumo/adapters/persistence/profile/_secure_model_document.py`
- `src/cadrumo/adapters/persistence/profile/modelos_work_units.py`
- `adapter-owned replay-guard persistence and retired application/adapter bridge and parallel-reader sites`
- `every affected adapter/dev/test/fixture/annotation/dynamic caller`
- `focused real encrypted-SQL interleaving`
- `one-SELECT`
- `CAS`
- `lineage`
- `and encryption tests`
- `dev/quality/import_hygiene_scan.py`
- `dev/tests/test_import_hygiene_gate.py`
- `and exact AST/Vaultspec-RAG zero-remnant tests`

## Description

- Reconciled the shared-history hard move of `WorkUnitCatalogueRepositoryProtocol` to its public defining module and retained only direct defining-module consumers.
- Made both secure singleton kernels project `load` from a one-record `load_revisioned` observation, with the bare raw preflight and secondary-read helpers absent.
- Collapsed the work-unit decoder onto the enveloped kernel; preserved its structured inner-envelope integrity context at the one adapter translation boundary.
- Reconciled the adapter-owned recipient replay guard, deleting retired accounting/allowlist references and retaining its governed bare-kernel mutation path.
- Added real encrypted-SQL absent and present interleaving proofs for bare and enveloped singleton observations, asserting one read and payload/revision cohesion.
- Ran direct-import AST, exact source, and semantic discovery fixed-point checks; rebuilt the semantic code index before the final query.

## Outcome

Shared commit `49577a525c` delivered the principal hard move, both singleton-kernel changes, the work-unit decoder collapse, and the replay-guard relocation. This S169 closure commit carries the remaining integrity-context preservation, stale documentation correction, relocation-accounting changes, and encrypted-SQL observation tests.

The one-record proofs run against real encrypted SQL for both wire shapes. Each present-row interleaving returns the first payload with its own revision despite a write after the read; each absent-row read reports the absent sentinel after exactly one repository load. Existing encrypted roundtrip, CAS, and lineage coverage remains on the same governed secure-object routes.

Scoped Ruff passed. The AST fixed point found twenty direct application consumers, no old protocol definition or package re-export, no retired replay module, and no singleton secondary-read helper. The source code semantic index was refreshed before its final discovery check.

## Notes

The first focused test run exposed loss of the pre-existing structured classification and version contexts after decoder collapse; the adapter translation now preserves those kernel-supplied contexts while storage-column failures retain their existing generic translation.

The initial rerun was briefly blocked by an unrelated concurrent absence of `cadrumo.core.resources.errors`; the module settled without S169 edits. Earlier active-bucket coverage also names concurrent custody and authentication relocation entries outside S169 ownership; they are not included here.

The shared index contained an unrelated staged quality configuration file before S169 staging. This commit is made with explicit paths only, leaving that index entry untouched. The plan remains open for independent review.
