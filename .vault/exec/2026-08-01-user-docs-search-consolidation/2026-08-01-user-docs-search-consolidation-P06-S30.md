---
tags:
  - '#exec'
  - '#user-docs-search-consolidation'
date: '2026-08-06'
modified: '2026-08-06'
body_schema: 'body-v1'
body_hash: 'sha256:b3997f198bb51bb6a80653df6391b57f339c2adfb7716fe6ab9dac07e5a24811'
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

### 2026-08-06 sweep projection optimization

Fresh vaultspec-rag grounding over the accepted ADR, source contract, P06 sweep audit, and the current sweep/projection code confirmed that the complete authoritative Pagefind/Rung-2 projection is the only admissible manifest. The safe remediation therefore reuses one materialized projection between run_sweep() and TargetResolver; it does not narrow CLI coverage, add synthetic targets, change structured casilla authority, or modify the relevance bytes.

The bounded implementation changed only dev/docs/terminology/_sweep.py, dev/docs/terminology/_resolution.py, and dev/docs/terminology/tests/test_sweep.py. The focused real suite returned 13 passed in 41.04s; scoped Ruff, basedpyright (0 errors, 0 warnings, 0 notes), and git diff --check passed. A seven-query live default sweep measured seven targeted mappings, zero empty mappings, and 47.4 seconds wall time.

A current full 112-query live rerun timed out at 244.4 seconds, and its marked live-service test failed after 43.19 seconds because the prorrata mapping had no targets. The previous successful 112-query artifact remains the standing relevance evidence. This optimization therefore removes the former focused test_sweep.py timeout boundary but does not prove a fresh complete laundering run or justify closing P06.S30. The committed relevance artifact remains unchanged and Rung 2 remains fail-closed.

The adjacent resolver regression run then returned 24 passed in 130.87s, covering the real registry-backed resolver behavior after the projection-injection seam. The Rung-2 contract suite independently returned 33 passed in 0.87s.
