---
tags:
  - '#exec'
  - '#modelo-parity-rollup'
date: '2026-08-05'
modified: '2026-08-05'
body_schema: 'body-v1'
body_hash: 'sha256:bfb37de543b1bd6c1205a2bc171c0cc232086a3a502f4a7edb16a30cf0c50229'
step_id: 'S30'
related:
  - "[[2026-08-05-modelo-parity-rollup-plan]]"
---
# Acquire an authoritative independent 2025 0613 cap and rounding oracle matrix, including per-child effective spend and profile-to-calculate evidence without changing 2025 schema or formula wiring

## Scope

- `src/cadrumo/domain/contribuyente/tests/test_guarderia_2025_facts.py`
- `src/cadrumo/_data/corpus/manuals/renta/2025/part1/source.pdf.extracted.md:54989-55004`
- `src/cadrumo/_data/corpus/manuals/renta/2025/part1/source.pdf.extracted.md:55073-55088`
- `.vault/research/2026-08-05-modelo-parity-rollup-s17-0613-cap-rounding-research.md`

## Description

- The Luna Max worker ran VaultSpec-RAG before discovery and used the bundled 2025 manual examples as the evidence boundary.
- Added two real source-capability cases for the official two- and six-qualifying-month input shapes. The test exercises the production `RentaFamilyProfile.gastos_guarderia_reales()` aggregation path for raw month-level spend and separate effective annual custody spend.
- Corrected the initial worker patch because direct read-back of assigned fields was tautological. The final test asserts production aggregation results and deliberately does not calculate or assert the unresolved `0613` cap.
- Kept the 2025 casilla manual and did not add profile fields, cap facts, formula, binding, reverse wiring, or schema changes.

## Outcome

The authorized source-capability tranche is complete: five focused tests pass. The full 0613 promotion gate remains open because the official authority still does not provide the complete independent matrix for 0, 2, 6, 7, 8, and 12 months, effective-spend reductions, turning-three, and unequal per-child caps with one executable rounding stage.

## Verification

- `uv run --no-sync pytest -q -n 0 src/cadrumo/domain/contribuyente/tests/test_guarderia_2025_facts.py`: `5 passed`.
- Ruff check passed.
- Ruff format check passed.
- No production or unrelated test files were modified by the Luna worker. The final local refinement remained within the same exclusive test file.

## Notes

- Official 2025 manual values used as input evidence: 2 months -> `166.67` cap and `2,290` effective spend (`:54989-55004`); 6 months -> `500` cap and `2,290` effective spend (`:55073-55088`). The test does not encode those cap outputs.
- SOL remains authoritative: no 2025 `0613` formula, binding, profile schema, or manual-to-computed change is authorized.
