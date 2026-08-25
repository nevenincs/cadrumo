---
tags:
  - '#exec'
  - '#tui-architecture'
date: '2026-08-24'
modified: '2026-08-25'
body_schema: 'body-v1'
body_hash: 'sha256:bf67caecc698eaad8c7911eaf564943ee67573789ce84c4b6f5259f3113f3ac6'
step_id: 'S123'
related:
  - "[[2026-08-11-tui-architecture-plan]]"
---
# Implement TuiOperationObservationDependencyReceiptV1 and its sole live-tree validator, proving strict round trips, atomic interleaving, progress and replay, registered REVIEW non-authority, restart refresh, digest drift refusal, production DI, sentinel non-retention, current-only deletion, and a semantic-plus-exact producer census that fails duplicate operation state or projection authorities

## Scope

- `src/cadrumo/application/operations/tests/test_public_operation_dependency_receipt.py`

## Description

Implemented the strict frozen C0 receipt schema and the sole live-tree validator in the mandated test-owned module. The receipt binds accepted/rejected ADR provenance, producing commit, source-tree digest, exact public contract set, definition/schema/export/capability manifests, canonical real-behavior proof sources, and source-tree-bound Vaultspec RAG semantic evidence.

The validator independently recomputes production DI parity, document ancestry, proof source digests, public exports, exact AST authority/constructor ownership, and semantic-census tool/query/schema/result digests. Semantic evidence is captured explicitly by the S124 producer; test execution never silently substitutes a local index when the RAG service is unavailable.

## Outcome

- Strict JSON round-trip and closed-model validation pass.
- Required proof inventory covers atomic interleaving, current-only refusal, digest drift, production composition, progress/replay, restart refresh, REVIEW non-authority, sentinel non-retention, and anchored materialization.
- Exact AST census fails displaced or duplicate operation state, registry, projection, fold, and composition authorities.
- Semantic evidence rejects missing canonical authorities, unexpected competing authorities, stale source-tree digests, altered query/tool/schema identity, and non-reproducing result digests.
- S124 remains the sole clean-commit receipt producer.

## Verification

- `uv run pytest -q -m integration src/cadrumo/application/operations/tests/test_public_operation_dependency_receipt.py`: 6 passed.
- `uv run ruff check src/cadrumo/application/operations/tests/test_public_operation_dependency_receipt.py`: passed.
- Vaultspec RAG was driven separately for the canonical producer census; runtime service unavailability is a hard capture refusal, never a silent validator downgrade.

## Notes

The repository worktree is intentionally dirty during implementation, so S123 validates receipt mechanics with `require_clean_tree=False`. S124 alone may emit and validate the clean-commit artifact.
