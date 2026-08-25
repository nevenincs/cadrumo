---
tags:
  - '#exec'
  - '#aeat-export-fragment-generator-authority'
date: '2026-08-10'
modified: '2026-08-25'
body_schema: 'body-v1'
body_hash: 'sha256:bf9e8a1993065cf8095a77fb39a3bae6bd028cbecaac43a631c4f8a202919237'
step_id: 'S94'
related:
  - "[[2026-08-10-aeat-export-fragment-generator-authority-plan]]"
---
# Author the core projection types for Modelo 200 design-numbered detail rows

## Scope

- `src/cadrumo/core/_filing_projection_ref.py`
- `src/cadrumo/core/tests/test_filing_projection_ref.py`
- `src/cadrumo/domain/calculations/registry/tests/test_modelo_200_registry.py`

## Description

- Confirm the core filing-projection union already contains the fourteen Modelo 200 design-numbered row families and their closed field vocabularies.
- Derive every family slot cap from the live Modelo 200 design endpoint declarations rather than a second handwritten table.
- Prove all 578 endpoints fit their exact typed upper bounds and every cap-plus-one value refuses through the canonical compiler.
- Prove the five shipped Modelo 303 projection kinds named by the Step remain explicitly casilla-free.

## Outcome

The production boundary was already present in commits `8461ac8e53` and `d0b320e87c`; this reconciliation added only the missing design-derived acceptance proof in `01b5d15bea`. Thirty focused core tests and eleven Modelo 200 registry tests pass. Scoped Ruff formatting and linting and the diff check are clean.

## Notes

No production code changed. The proof imports the canonical compiler and live selected snapshot, so it neither redeclares slot caps nor invents casilla identities.
