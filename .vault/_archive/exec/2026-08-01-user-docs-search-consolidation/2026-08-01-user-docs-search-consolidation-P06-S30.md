---
tags:
  - '#exec'
  - '#user-docs-search-consolidation'
date: '2026-08-06'
modified: '2026-08-06'
body_schema: 'body-v1'
body_hash: 'sha256:0298be657e2faad3c1227003952dec372e2e0787c6dbfdd687cda6a45a7f3d8f'
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

`uv run --no-sync python -m dev.docs.terminology.sweep --out <session-scratch-dir>\cadrumo-rung2-evidence-20260806-live\relevance-projected.json --port 8766 --max-results 20 --timeout 60`

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

## 2026-08-06 routed Handbook admission and four-locale sweep

Fresh vaultspec-rag grounding over the accepted source contract, deterministic casilla research, P06.S24/P06.S30 audits, and the current sweep/projection code confirmed that Handbook concept fragments are a valid explicit-preprocess source route while deterministic casilla enrollment remains a separate registry/projection contract. The resident code index completed job `f444e105223c47c19f6bb705d5788253`; its post-index state was consistent. Live semantic probes reached `src/cadrumo/_data/terminology/concepts/prorrata-especial.toml` for Spanish at 0.909322, Catalan at 0.986226, English at 0.946320, and Hungarian contextual phrasing at 0.963673. The Hungarian label alone remained below retrieval floor, so the golden query uses the source-grounded contextual phrase rather than asserting unsupported label-only recall.

The fresh live sweep used the completed index without a second reindex:

`uv run --no-sync python -m dev.docs.terminology.sweep --no-reindex --port 8766 --timeout 90 --out <session-scratch-dir>\\userdocs-rag-sweep-20260806-current.json`

It produced 112 queries over 49 concepts, 112 targeted mappings, and 0 failed/empty mappings. The raw sweep output hash was `2DBA97F3AA2D97BD253CD0528484C5A8522960133391C85D0CFA1D8AE137710E`. After retaining an explicit completed-index provenance note, the committed relevance input hash is `4E686B6B4DDA2C525358E5B02213F9664683C032DFC9C809DA54B5F844377226`; it contains 188 target rows across 90 unique record ids: 132 concept and 56 legal rows, with no synthetic `code:` or unmanifested PAGE targets.

Real-behaviour verification passed: `test_relevance_data.py` returned 11 passed; the sweep, coverage, and resolver selections returned 43 passed; the resident-service lane returned 12 passed, including Spanish, Catalan, English, and Hungarian terminology probes. The structured M130/casilla-15 authority path remains independently tested and was not widened by this semantic route. P06.S30 now has fresh authoritative sweep, target-resolution, and all-locale RAG evidence; Rung 2 remains fail-closed and deployment remains unperformed.
