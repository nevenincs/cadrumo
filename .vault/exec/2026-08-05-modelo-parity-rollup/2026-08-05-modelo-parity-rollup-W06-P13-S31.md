---
tags:
  - '#exec'
  - '#modelo-parity-rollup'
date: '2026-08-05'
modified: '2026-08-05'
body_schema: 'body-v1'
body_hash: 'sha256:ad172c661b53325d2f4fec7b574a4d8752b96a0ea482a4018e68e3c4c71347e7'
step_id: 'S31'
related:
  - "[[2026-08-05-modelo-parity-rollup-plan]]"
---
# Ground the annual shared-engine 2025 per-activity path for M100 1481 and produce only an independent oracle or research artifact without adding an M131 casilla-01 relation

## Scope

- `src/cadrumo/domain/calculations/registry/tests/test_modelo_131_2025_activity_oracle.py`
- `src/cadrumo/domain/calculations/registry/tests/test_modelo_100_2025_semantic_boundaries.py`
- `src/cadrumo/_data/corpus/aeat_official/disenos_registro/modelo_100/files/01-100-diccionario-declaracion-individual-ejercicio-2025-actualizado-14-04-2026-416-kb-otros-fi.properties`
- `.vault/research/2026-08-05-modelo-parity-rollup-s18-1481-oracle-addendum-research.md`

## Description

- Ran VaultSpec-RAG code searches for the annual M100/M131 handoff and the activity-preserving rental/module source boundaries. The current code index matched the relation handoff models, the 2025 no-relation semantic guard, the existing live M100 fold-in, and the M131 activity oracle.
- The real 2025 M131 activity oracle remains green for two distinct epigraphs across all four quarters and deliberately retains activity-keyed annual-base values without aggregating them.
- Added the 2025 official declaration-dictionary evidence to the S18 research addendum: `E4AR` is repeated activity-level casilla `1481`, `E4SUMA` is the result-level sum into `1482`, and `E4TOTAL` is `1484` after `1483`.
- SOL's boundary is respected: official 2025 evidence does not prove M131 casilla `01` to M100 `1481`, the source casilla is activity-collapsed, and no relation, binding, formula, or casilla declaration was added.

## Outcome

The authorized evidence and oracle tranche is complete. S18 adjudication remains open and deferred; this is not M100 parity certification.

## Verification

- Focused M131 activity oracle: `1 passed`.
- Existing M100 2025 semantic-boundary guard remains the negative guard for `1481` relation absence.
- No production registry, relation, binding, formula, aggregation, or M131 code was changed.

## Notes

- RAG code request references: `8be4666d04d443ccb2f99916907e0e76`, `c81c6a7b49e94822928fc66875abc03f`.
- Official dictionary locator: `...2025...properties:369-374`.
- Allowed production-file set under SOL is empty.
