---
tags:
  - '#research'
  - '#modelo-parity-rollup'
date: '2026-08-05'
modified: '2026-08-05'
body_schema: 'body-v1'
body_hash: 'sha256:0024c5964145d37d5fd0d2dd66270bb2a23561abdd068b40368c02fd3d4a99ff'
related:
  - '[[2026-08-05-modelo-parity-rollup-s16-s18-candidate-contract-matrix-research]]'
  - '[[2026-08-05-modelo-parity-rollup-s16-s18-evidence-research]]'
  - '[[2026-08-05-modelo-parity-rollup-semantic-decision-boundary-audit]]'
  - '[[2026-08-05-modelo-parity-rollup-five-domain-contract-adr]]'
  - '[[2026-08-05-modelo-parity-rollup-plan]]'
---
# `modelo-parity-rollup` research: `S18 1481 activity oracle addendum`

## Decision boundary

The 2025 `1481` row must remain manual/open. The new oracle proves a necessary M131 source capabilityâ€”activity identity and annual-base stabilityâ€”but it does not prove an annual M100 `1481` producer or authorize a cross-model relation.

## Findings

### Activity-level 2025 M131 capability is now independently exercised

The new Luna Max/XHigh test at `src/cadrumo/domain/calculations/registry/tests/test_modelo_131_2025_activity_oracle.py` runs the real 2025 M131 registry runtime for epigraphs `972.1` and `721.2` across `1T`, `2T`, `3T`, and `4T`.

It preserves separate activity keys and reproduces the independently grounded annual-base values `22,473.79` for `972.1` and `8,987.09` for `721.2` in every quarter. The test passed its focused pytest, Ruff, format, and basedpyright checks. It does not sum the activities and does not write or read an M100 `1481` relation.

### The 2025 official dictionary confirms the per-activity versus aggregate boundary

The bundled 2025 Modelo 100 individual declaration dictionary identifies `E4AR` as field `1481`, Rendimiento neto reducido, under the repeated `RegEstimaObj/ActividadEstObj` activity path; it identifies `E4SUMA` as field `1482`, the result-level sum of the `1481` values; and it identifies `E4TOTAL` as field `1484`, `1482 - 1483`. Source: `src/cadrumo/_data/corpus/aeat_official/disenos_registro/modelo_100/files/01-100-diccionario-declaracion-individual-ejercicio-2025-actualizado-14-04-2026-416-kb-otros-fi.properties:369-374`.

That official layout evidence strengthens the required activity-preserving contract: a proposed M131 handoff cannot collapse multiple activities into one annual `1481`, and it must distinguish repeated activity rows from the `1482` aggregate. The dictionary does not identify M131 casilla `01` as the source, does not settle quarterly-to-annual period alignment, and does not establish a relation-prefill rule.

### The M100 mapping remains unproved

The oracle proves that the 2025 M131 engine can preserve activity identity and that its annual-base value is stable across quarterly runtime selections. It does not prove that M131 casilla `01` is legally equivalent to M100 `1481`, that a quarterly sum is valid, or that a relation can populate repeated M100 activity rows. The existing 2025 semantic guard still confirms that no relation targets `1481`.

## Sources

- New real-runtime oracle: `src/cadrumo/domain/calculations/registry/tests/test_modelo_131_2025_activity_oracle.py`.
- Independent coefficient/support tables: `src/cadrumo/domain/calculations/registry/tests/_modelo_131_modulos_engine_support.py`.
- 2025 M131 engine tests: `src/cadrumo/domain/calculations/registry/tests/test_modelo_131_modulos_engine.py`.
- Bundled M131 instructions: `src/cadrumo/_data/corpus/aeat_official/instructions/modelo_131/files/modelo-131-instrucciones.html:74`.
- 2025 official M100 declaration dictionary: `src/cadrumo/_data/corpus/aeat_official/disenos_registro/modelo_100/files/01-100-diccionario-declaracion-individual-ejercicio-2025-actualizado-14-04-2026-416-kb-otros-fi.properties:369-374`.
- Existing M100 fold-in evidence: `src/cadrumo/application/modelo/tests/test_modelo_100_m131_modulos_fold_in_live.py`.
- Current 2025 M100 relation guard: `src/cadrumo/domain/calculations/registry/tests/test_modelo_100_2025_semantic_boundaries.py`.

## Required implementation gates

Before SOL can authorize a 2025 `1481` producer, the evidence must define:

- the authoritative annual M100 mÃ³dulos producer and its relationship to M131;
- activity-preserving transfer or recomputation for multiple activities, seasonal operation, commencement, and cessation;
- the distinction between repeated per-activity `1481` and aggregate `1482`;
- a canonical relation only if official evidence proves the transfer, with period/activity provenance and reverse wiring;
- an independent 2025 M131-to-M100 runtime oracle.

The new test and the official field-layout evidence close only source and layout prerequisites. They do not change production schema or wiring.
