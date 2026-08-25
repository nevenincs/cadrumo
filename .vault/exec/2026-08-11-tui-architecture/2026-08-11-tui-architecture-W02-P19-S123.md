---
tags:
  - '#exec'
  - '#tui-architecture'
date: '2026-08-24'
modified: '2026-08-25'
body_schema: 'body-v1'
body_hash: 'sha256:60a8d01b8e432e7f7909990109aeb599db7407fb166e318a7f89791bf829c15b'
step_id: 'S123'
related:
  - "[[2026-08-11-tui-architecture-plan]]"
---
# Implement TuiOperationObservationDependencyReceiptV1 and its sole live-tree validator, proving strict round trips, atomic interleaving, progress and replay, registered REVIEW non-authority, restart refresh, digest drift refusal, production DI, sentinel non-retention, current-only deletion, and a semantic-plus-exact producer census that fails duplicate operation state or projection authorities

## Scope

- `src/cadrumo/application/operations/tests/test_public_operation_dependency_receipt.py`
- `conftest.py`
- `dev/docs/conftest.py` (deleted after moving the shared fixture to its canonical repository-wide home)
- `justfile`

## Description

Implemented the strict frozen C0 receipt schema and sole live-tree validator in the mandated test-owned module. The receipt binds accepted/rejected ADR provenance, producing commit, source-tree digest, exact public contract set, definition/schema/export/capability manifests, canonical real-behavior proof sources, and source-tree-bound Vaultspec RAG semantic evidence.

The validator independently recomputes production DI parity, document ancestry, proof source digests, public exports, exact AST authority/constructor ownership, and semantic-census tool/query/schema/result digests. The census runs the real resident Vaultspec RAG service on explicit port 8766 and refuses service failure; no local-index fallback exists.

The resident-service environment fixture was moved from the docs subtree to the repository-root pytest authority so every marked test shares one implementation. The obsolete narrow conftest was deleted. The canonical resident-service recipe now enrolls this receipt module and runs serially against the singleton service.

## Outcome

- Strict JSON round-trip and closed-model validation pass.
- Required proof inventory covers atomic interleaving, current-only refusal, digest drift, production composition, progress/replay, restart refresh, REVIEW non-authority, sentinel non-retention, and anchored materialization.
- Exact AST census fails displaced or duplicate operation state, registry, projection, fold, and composition authorities.
- Real semantic evidence rejects missing canonical authorities, unexpected competing authorities, stale source-tree digests, altered query/tool/schema identity, and non-reproducing results.
- One canonical resident-service fixture and one canonical resident test recipe own the shared process contract.
- S124 remains the sole clean-commit receipt producer.

## Verification

- `just test-resident-service`: 17 passed, 228 deselected.
- `uv run --no-sync pytest -q -n0 -m "resident_service" src/cadrumo/application/operations/tests/test_public_operation_dependency_receipt.py`: 5 passed, 1 deselected.
- `uv run --no-sync pytest -q -n0 -m "integration and not resident_service" src/cadrumo/application/operations/tests/test_public_operation_dependency_receipt.py`: 1 passed, 5 deselected.
- `uv run ruff check conftest.py src/cadrumo/application/operations/tests/test_public_operation_dependency_receipt.py`: passed.
- Independent Vaultspec code review: approved; exact live RAG capture returned seven canonical operation paths, with no fallback, mocks, fakes, patches, skips, or xfails.

## Notes

The shared repository contains unrelated concurrent work, so S123 validates receipt mechanics with `require_clean_tree=False`. S124 alone may emit and validate the exact clean-commit artifact.
