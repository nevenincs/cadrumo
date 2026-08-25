---
tags:
  - '#exec'
  - '#tui-architecture'
date: '2026-08-24'
modified: '2026-08-25'
body_schema: 'body-v1'
body_hash: 'sha256:8ce5f476e36de0dc7195d97422eb7a1e0016dbda75f938d622ea46ad2986fdff'
step_id: 'S123'
related:
  - "[[2026-08-11-tui-architecture-plan]]"
---
# Implement TuiOperationObservationDependencyReceiptV1 and its sole live-tree validator, proving strict round trips, atomic interleaving, progress and replay, registered REVIEW non-authority, restart refresh, digest drift refusal, production DI, sentinel non-retention, current-only deletion, and a semantic-plus-exact producer census that fails duplicate operation state or projection authorities

## Scope

- `src/cadrumo/application/operations/tests/test_public_operation_dependency_receipt.py`

## Description

Implemented the strict frozen C0 receipt schema and sole live-tree validator in the mandated test-owned module. The receipt binds accepted/rejected ADR provenance, implementation commit A, source-tree digest, exact public contract set, definition/schema/export/capability manifests, canonical real-behavior proof sources, and source-tree-bound Vaultspec RAG semantic evidence.

Applied the accepted D13 amendment as a current-only breaking change: the receipt has `implementation_commit` and no `producing_commit` alias or dual parser. The public builder captures only a clean implementation commit A. The durable validator derives clean current HEAD B, checks A ancestry and the B source-tree digest from committed Git bytes, requires the working artifact bytes equal `git show B:<receipt path>`, and parses those committed bytes only. B is never stored in the receipt.

The private `_in_memory_for_test` builder and validator exercise S123 mechanics without artifact attestation and cannot open C0. The public durable path remains the only artifact-attestation path.

## Outcome

- Strict JSON round-trip and closed-model validation pass, including rejection of legacy top-level `producing_commit` input.
- Required proof inventory covers atomic interleaving, current-only refusal, digest drift, production composition, progress/replay, restart refresh, REVIEW non-authority, sentinel non-retention, and anchored materialization.
- Exact AST census fails displaced or duplicate operation state, registry, projection, fold, and composition authorities.
- Real semantic evidence rejects missing canonical authorities, unexpected competing authorities, stale source-tree digests, altered query/tool/schema identity, and non-reproducing results.
- Durable D13 attestation refuses a non-ancestor implementation commit, B source-digest drift, artifact byte mismatch, uncommitted artifact bytes, and staged artifact bytes.
- S124 remains the sole clean-commit receipt producer and C0 opener.

## Verification

- `uv run --no-sync pytest -q -n0 -m integration src/cadrumo/application/operations/tests/test_public_operation_dependency_receipt.py`: 11 passed.
- `uv run --no-sync pytest -q -n0 -m resident_service src/cadrumo/application/operations/tests/test_public_operation_dependency_receipt.py`: 5 passed, 6 deselected.
- `uv run --no-sync pytest -q -n0 -m "integration and not resident_service" src/cadrumo/application/operations/tests/test_public_operation_dependency_receipt.py`: 6 passed, 5 deselected.
- `uv run --no-sync ruff check src/cadrumo/application/operations/tests/test_public_operation_dependency_receipt.py`: passed.
- `uv run --no-sync ruff format --check src/cadrumo/application/operations/tests/test_public_operation_dependency_receipt.py`: passed.

## Notes

The shared repository contains unrelated concurrent work, so the durable C0 artifact validator is intentionally not invoked by S123's in-memory receipt tests. S124 alone supplies clean A/B artifact evidence.

The scoped `ty check` retains eleven pre-existing diagnostics in the receipt's unchanged query-literal and broadly typed contract-manifest helpers; the D13 amendment adds none.
