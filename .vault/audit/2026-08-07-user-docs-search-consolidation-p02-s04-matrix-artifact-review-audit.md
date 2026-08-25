---
tags:
  - '#audit'
  - '#user-docs-search-consolidation'
date: '2026-08-07'
modified: '2026-08-07'
body_schema: 'body-v1'
body_hash: 'sha256:e2f0394c72cbddc51cbc50e3fe50513548a1296264f7b59f26728b79323fd999'
related:
  - "[[2026-08-01-user-docs-search-consolidation-plan]]"
  - "[[2026-08-01-user-docs-search-consolidation-adr]]"
  - "[[2026-08-01-user-docs-search-consolidation-P02-S04]]"
  - "[[2026-08-04-user-docs-search-consolidation-rung-2-static-embedding-boundary-research]]"
---

# `user-docs-search-consolidation` audit: `P02.S04 matrix artifact review`

## Scope

Review the generated P02.S04 static-embedding matrix, its pinned provider/tokenizer/model provenance, loader and byte-contract compatibility, and the boundaries preventing it from being treated as an accepted or shipped Rung-2 bundle.

## Findings

### matrix-contract | low | Matrix artifact matches the pinned static-matrix contract

The independently inspected artifact carries schema version 4, 114 vocabulary rows, 153 query-token rows, dimension 256, serialized size 257,393 bytes, and canonical artifact SHA-256 `d102c30db0a589854ac6ee4d0f1609d689a9dd5e5b23b61fe5063e3a1f6bbfda`. Its file SHA-256 is `cfd853a4473c4c7c0ea2bf27efae36291b7d338c7a0fa64ea5db15669024218`. The model repository/revision/licence, model2vec 0.8.2 provider identity, and tokenizers 0.23.1 identity match the current RAG-grounded provenance. No contract defect was found in this inspection.

### artifact-lifecycle | medium | Matrix exists only as uncommitted shared-worktree WIP

The artifact is present at `src/cadrumo/_data/terminology/evaluation/rung2-matrix.json` but is untracked in the shared worktree. It therefore cannot yet be described as committed reviewable data or as a shipped input. P02.S04 must remain open until the intended artifact is separately staged and committed under an authorized clean-worktree handoff.

### full-bundle-projection | high | Authoritative bundle assembly remains blocked by unrelated peer WIP

The project compiler still fails before the authoritative Pagefind manifest is assembled because `StopIteration` occurs while resolving `CalculationSourceDiagnostic` in `src/cadrumo/application/aggregation/_modelo_bindings.py`. That file is peer-owned WIP and was not modified. The matrix alone is not evidence of a complete Rung-2 search bundle.

### runtime-acceptance | high | Browser enablement and accepted remeasurement remain unproven

The current diagnostic replay remains 22/32 semantic hits (miss rate 0.3125) and 93/123 composed coverage (0.7560975609756098), with ten insufficient-coverage misses. No accepted browser configuration, locale/kind acceptance, built-site replay, or deployment artifact follows from this matrix. The browser tier must remain fail-closed and P02.S04/P02.S06/P02.S07 must remain open.

### 2026-08-07 full-bundle projection follow-up | low | Earlier assembly blocker cleared; acceptance remains open

The prior `StopIteration` finding is cleared by the current shared-worktree state: `build_rung2_compilation_inputs()` now returns the authoritative 114-query/114-vocabulary/153-token/8,505-record input set with two ratified alias-authority entries and zero failed queries, and the pinned-provider compiler writes a loader-valid schema-v3 temporary bundle of 2,138,574 canonical bytes. The matrix, bridge, manifest, provenance, and bundle hash links are therefore assembled successfully for this diagnostic run.

This follow-up does not promote the temporary bundle or erase the original lifecycle finding. The matrix remains untracked WIP, the standing semantic replay is 22/32 with 10 insufficient-coverage misses and aggregate coverage 93/123 (`0.7560975609756098`), the independently captured Pagefind observations are not freshly hash-linked to this bundle, and locale/kind/browser/deployment acceptance remains unproven. The earlier high-severity assembly blocker is closed as a source-state finding; P02.S04/P02.S06/P02.S07 remain open under the existing fail-closed boundary.

## Recommendations

- Preserve the matrix as uncommitted WIP until the shared tree has a scoped handoff; do not stage peer files.
- Resolve the unrelated Pagefind projection failure in its owning work before attempting the authoritative full-bundle compile.
- Re-run the held-out, locale/kind, browser, and deployment gates only after the exact bundle is compiled and independently reviewed.
- Keep the browser configuration disabled and do not close P02.S04, P02.S06, or P02.S07 on matrix-only evidence.
