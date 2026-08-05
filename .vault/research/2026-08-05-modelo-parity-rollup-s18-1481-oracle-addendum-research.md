---
tags:
  - '#research'
  - '#modelo-parity-rollup'
date: '2026-08-05'
modified: '2026-08-05'
body_schema: 'body-v1'
body_hash: 'sha256:7803250a1975c3dd98d8adb7631322ea8b559659e66c3c2f636e36432fd3c39e'
related:
  - '[[2026-08-05-modelo-parity-rollup-s16-s18-candidate-contract-matrix-research]]'
  - '[[2026-08-05-modelo-parity-rollup-s16-s18-evidence-research]]'
  - '[[2026-08-05-modelo-parity-rollup-semantic-decision-boundary-audit]]'
  - '[[2026-08-05-modelo-parity-rollup-five-domain-contract-adr]]'
  - '[[2026-08-05-modelo-parity-rollup-plan]]'
---
# `modelo-parity-rollup` research: `S18 1481 activity oracle addendum`

## Decision boundary

The 2025 `1481` row must remain manual/open. The new oracle proves a necessary M131 source capability—activity identity and annual-base stability—but it does not prove an annual M100 `1481` producer or authorize a cross-model relation.

## Findings

### Activity-level 2025 M131 capability is now independently exercised

The new Luna Max/XHigh test at `src/cadrumo/domain/calculations/registry/tests/test_modelo_131_2025_activity_oracle.py` runs the real 2025 M131 registry runtime for epigraphs `972.1` and `721.2` across `1T`, `2T`, `3T`, and `4T`.

It preserves separate activity keys and reproduces the independently grounded annual-base values `22,473.79` for `972.1` and `8,987.09` for `721.2` in every quarter. The test passed its focused pytest, Ruff, format, and basedpyright checks. It does not sum the activities and does not write or read an M100 `1481` relation.

### The M100 mapping remains unproved

The oracle proves that the 2025 M131 engine can preserve activity identity and that its annual-base value is stable across quarterly runtime selections. It does not prove that M131 casilla `01` is legally equivalent to M100 `1481`, that a quarterly sum is valid, or that a relation can populate repeated M100 activity rows. The existing 2025 semantic guard still confirms that no relation targets `1481`.

## Sources

- New real-runtime oracle: `src/cadrumo/domain/calculations/registry/tests/test_modelo_131_2025_activity_oracle.py`.
- Independent coefficient/support tables: `src/cadrumo/domain/calculations/registry/tests/_modelo_131_modulos_engine_support.py`.
- 2025 M131 engine tests: `src/cadrumo/domain/calculations/registry/tests/test_modelo_131_modulos_engine.py`.
- Bundled M131 instructions: `src/cadrumo/_data/corpus/aeat_official/instructions/modelo_131/files/modelo-131-instrucciones.html:74`.
- Existing M100 fold-in evidence: `src/cadrumo/application/modelo/tests/test_modelo_100_m131_modulos_fold_in_live.py`.
- Current 2025 M100 relation guard: `src/cadrumo/domain/calculations/registry/tests/test_modelo_100_2025_semantic_boundaries.py`.

## Required implementation gates

Before SOL can authorize a 2025 `1481` producer, the evidence must define:

- the authoritative annual M100 módulos producer and its relationship to M131;
- activity-preserving transfer or recomputation for multiple activities, seasonal operation, commencement, and cessation;
- the distinction between repeated per-activity `1481` and aggregate `1482`;
- a canonical relation only if official evidence proves the transfer, with period/activity provenance and reverse wiring;
- an independent 2025 M131-to-M100 runtime oracle.

The new test closes only the activity-source prerequisite. It does not change production schema or wiring.
