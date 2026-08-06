---
tags:
  - '#exec'
  - '#user-docs-search-consolidation'
date: '2026-08-06'
modified: '2026-08-06'
body_schema: 'body-v1'
body_hash: 'sha256:a317564706ef293d2482b07f9dbb5819a9cfc185d5b73feda98ec3eda7e5bdd9'
step_id: 'S30'
related:
  - "[[2026-08-01-user-docs-search-consolidation-plan]]"
---

# Prove the RAG sweep composition emits only authoritative injected record targets while preserving deterministic structured casilla enrollment, then refresh the manifest-admissible relevance input

## Scope

- `dev/docs/terminology/_sweep.py`
- `dev/docs/terminology/tests/test_sweep.py`
- `src/cadrumo/_data/terminology/relevance/`

## Description

- Ground the sweep composition and manifest boundary with `vaultspec-rag` searches over the accepted ADR, source contract, and current projection code.
- Run the resident `vaultspec-rag` service sweep with an explicit timeout and preserve the returned laundered mapping.
- Materialize the authoritative unified projection used by Pagefind and Rung 2, then reject resolver-only synthetic targets.
- Promote the byte-identical sweep result to the committed relevance input and inspect structured Modelo/casilla enrollment.

## Outcome

The live sweep produced 112 queries across 49 concepts with 0 failed queries and 0 empty mappings. The committed relevance artifact contains 169 target rows across 91 unique record ids; its target kinds are 112 concept rows and 57 legal rows, with no synthetic `code:` targets. The authoritative projection contains 8,496 records: 6,359 casillas, 1,494 CLI records, 49 concepts, and 594 legal records, with no PAGE records.

The deterministic structured path remains independent of semantic relevance. Modelo 130 casilla 15 resolves to `casilla-record:63300419eb4c0e5119307cfc` and `_generated/casillas/130.html#casilla-15`, with Spanish, English, Catalan, and Hungarian labels and localized help present.

## Verification

`uv run --no-sync python -m dev.docs.terminology.sweep --out C:\Users\hello\AppData\Local\Temp\cadrumo-rung2-evidence-20260806-live\relevance-projected.json --port 8766 --max-results 20 --timeout 60`

`112 queries, 49 concepts, 112 with targets, 0 empty`

Artifact SHA-256: `2885f9206ff2f2d7a0979745d7c7964fe85a9b335121748b88765b414c5f9e44`. The promoted repository file is byte-identical to this result.

`uv run --no-sync pytest -q -m "unit or (integration and not serial)" -n0 dev/docs/tests/test_casilla_enrollment_consolidation.py dev/docs/terminology/tests/test_casilla_projection.py dev/docs/terminology/tests/test_coverage.py dev/docs/tests/test_legal_anchor_parity.py dev/docs/terminology/tests/test_resolution.py dev/docs/terminology/tests/test_relevance_data.py dev/docs/terminology/tests/test_rung2_evaluation.py`

`63 passed in 180.00s (0:03:00)`

The broader `test_sweep.py` selection timed out at 184 seconds while materializing the four-language CLI projection; it is unverified rather than treated as green. The live endpoint was reachable on port 8766. No synthetic fallback was added.

## Notes

All discovery claims were grounded through the `vaultspec-rag` CLI because the MCP codebase alias remains rejected as `unknown_source_type` and is tracked in vaultspec-rag issue #350. Rung 2 remains fail-closed: this step refreshed the R1/relevance input and did not promote or enable a semantic bundle. Deployment was not performed.
