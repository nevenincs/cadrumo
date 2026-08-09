---
tags:
  - '#exec'
  - '#m303-carry-reconciliation'
date: '2026-08-09'
modified: '2026-08-09'
body_schema: 'body-v1'
body_hash: 'sha256:0d53ef6213800cae9b563ea8f13ba045073626c95962275d3872e24c844c33c3'
step_id: 'S05'
related:
  - "[[2026-08-07-m303-carry-reconciliation-plan]]"
---
# DEFERRED - report a refunded basis rather than resultado once disposition recovery from the justificante Tipo de declaracion makes the branch reachable

## Scope

- `src/cadrumo/application/calculations/_m303_carry_ingress.py`
- `src/cadrumo/application/calculations/_observations_repository.py`
- `src/cadrumo/application/modelo/_filed_revision_observation.py`
- `src/cadrumo/application/live/_filed_observation_persistence.py`
- `src/cadrumo/domain/iva_compensation/_filed_derivation.py`

## Description

- Add typed envelope-level Modelo 303 result-disposition projection with source provenance.
- Normalize both official AEAT and app-filing ingress through the canonical carry resolver.
- Preserve raw submitted header facts and reject missing, duplicate, invalid, contradictory, and sign-incompatible inputs.
- Carry a refunded basis through the filed-derivation domain branch.
- Leave the IVA history consumers on their raw pre-S05 inputs for the deferred S07 migration.

## Outcome

- Persisted filing observations recover a typed disposition for all C, D, V, X, I, N, U, and G declaration codes.
- Casilla registry observations remain casilla-only while envelope metadata owns result disposition and provenance.
- The resolver fails closed before persistence when the submitted evidence is incomplete or inconsistent.

## Verification

`uv run --no-sync pytest src/cadrumo/application/calculations/tests/test_m303_carry_ingress.py -q`

`26 passed in 17.49s`

`uv run --no-sync pytest src/cadrumo/application/live/tests/test_filed_header_facts_reach_storage.py src/cadrumo/application/live/tests/test_filed_capture_calculation_history.py src/cadrumo/domain/iva_compensation/tests/test_filed_derivation_disposition.py -q`

`57 passed in 27.56s`

`uv run --no-sync pytest -m integration src/cadrumo/adapters/outbound/aeat/sede/tests/test_submitted_file_header_facts.py -q`

`19 passed in 16.17s`

`uv run --no-sync basedpyright src/cadrumo/application/calculations/_m303_carry_ingress.py src/cadrumo/application/calculations/_observations_repository.py src/cadrumo/application/modelo/_filed_revision_observation.py src/cadrumo/application/modelo/_revision_persistence.py src/cadrumo/application/modelo/_filing_actions.py src/cadrumo/application/live/_filed_observation_persistence.py`

`0 errors, 0 warnings, 0 notes`

## Notes

- S06, S07, and S08 remain deferred in the amended ADR sequence.
- The formal S05 review completed without open findings after restoring both history consumers to their raw inputs and adding the exported-bytes recovery proof.
