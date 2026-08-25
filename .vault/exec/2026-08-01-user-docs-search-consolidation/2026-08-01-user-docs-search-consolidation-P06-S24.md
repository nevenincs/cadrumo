---
tags:
  - '#exec'
  - '#user-docs-search-consolidation'
date: '2026-08-04'
modified: '2026-08-06'
body_schema: 'body-v1'
body_hash: 'sha256:24e333d4fc89d64ba145335aff3213c58a579085289070721f48088bf44ef916'
step_id: 'S24'
related:
  - "[[2026-08-01-user-docs-search-consolidation-plan]]"
---

# Add real-behaviour search gates for M130 casilla 15 exact resolution, projection parity, localized definition completeness, and target resolvability

## Scope

- `dev/docs/tests/`

## Description

- Add real-authority census and projection parity gates for the deterministic casilla surfaces.
- Assert M130/casilla 15 registry definition parity and individual registry-section resolution.
- Assert localized definition fields and shared generated target/anchor parity for the worked casilla.

## Outcome

Commit `390c33b5e1` adds the focused real-behavior gate file. The gate uses the validated bundled registry authority, the production casilla projection, census, resolver, unified-record funnel, and reference renderer. It proves the M130/casilla-15 identity and definition are enrolled deterministically, the exact source-section hit resolves to one canonical target, and the rendered entry contains the localized fields and shared deep-link anchor.

## Notes

RAG grounding used vault search and full-file retrieval for the accepted ADR, plan, research, P06 records, and implementation/test analogues. The configured semantic code-search route rejected its `codebase` alias with `unknown_source_type`; no reindex or bypass was attempted. The implementation passed AST syntax and `git diff --check`; the focused formal review returned PASS with no findings. No tests, builds, Pagefind compilation, sweeps, live probes, or deployment were run. P06.S24 remains open until the user authorizes the real gate run and the post-change sweep/coverage evidence is recorded.

### 2026-08-05 current source re-audit

Fresh vaultspec-rag grounding for the M130/casilla-15 enrollment contract found the production registry projection, localized definition propagation, individual registry-section resolver, shared target/anchor funnel, and focused real-authority gate already present. Exact source inspection confirms the gate names the validated bundled authority and the real `2019-y-siguientes` casilla source section; it does not invent a search vocabulary or substitute semantic relevance for deterministic enrollment.

This re-audit establishes source readiness only. The gate has not been executed, so projection parity, localized-definition completeness, target resolvability, and post-change coverage remain unproven. P06.S24 stays open. No tests, builds, Pagefind compilation, sweeps, live probes, generated artifacts, reindexing, model downloads, or deployment were run.

### 2026-08-06 authorized execution

Fresh `vaultspec-rag` grounding and the authorized marker-aware run now prove the owned casilla/legal source gates: `uv run --no-sync pytest -q -m "unit or (integration and not serial)" -n0 dev/docs/tests/test_casilla_enrollment_consolidation.py dev/docs/terminology/tests/test_casilla_projection.py dev/docs/terminology/tests/test_coverage.py dev/docs/tests/test_legal_anchor_parity.py dev/docs/terminology/tests/test_resolution.py dev/docs/terminology/tests/test_relevance_data.py dev/docs/terminology/tests/test_rung2_evaluation.py` returned `63 passed in 180.00s (0:03:00)`.

The authoritative projection contains 8,496 records: 6,359 casillas, 1,494 CLI records, 49 concepts, and 594 legal records. The exact M130/casilla-15 record is `casilla-record:63300419eb4c0e5119307cfc` at `_generated/casillas/130.html#casilla-15`; the ES/EN/CA/HU labels and localized help fields are present.

A real full English Pagefind build produced 2,094 pages and 8,496 injected term/casilla/legal/CLI records. An independent Pagefind capture resolved the structured query to the canonical M130/casilla-15 record and stable target. The four-language source projection is green, but strict Sphinx builds for en/es/ca/hu remain red on the same five known sequence/product divergences; this is not a claim of four deployed locale artifacts.

The broader `test_sweep.py` selection timed out at 184 seconds while materializing the four-language CLI projection and is recorded as unverified. Rung 2 remains fail-closed and deployment remains outside this gate.
