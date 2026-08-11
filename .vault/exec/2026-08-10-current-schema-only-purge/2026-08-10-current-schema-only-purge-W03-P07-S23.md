---
tags:
  - '#exec'
  - '#current-schema-only-purge'
date: '2026-08-10'
modified: '2026-08-11'
body_schema: 'body-v1'
body_hash: 'sha256:89ff8044c603a813d299a24da9ec1728d5dc0f0d145c1597ddc2b9d01081c433'
step_id: 'S23'
related:
  - "[[2026-08-10-current-schema-only-purge-plan]]"
---
# Prove under-declared Modelo 303 observations are refused and current dispositions round trip

## Scope

- `src/cadrumo/application/calculations/tests/test_m303_carry_ingress.py`

## Description

- Exercise the canonical carry-normalization ingress with real encrypted persistence.
- Prove official evidence without `declaration_type` is refused before mutation.
- Prove application-filing evidence without a typed result disposition is refused before mutation.
- Round-trip distinct official `C` and application-filing `D` carry projections under strict equality.

## Outcome

The restored current-contract proof covers both under-declared refusal populations and the two disposition-bearing success populations without reinstating the withdrawn generic runtime screen.

All four focused tests pass, Ruff is clean, and basedpyright reports no errors, warnings, or notes for the proof file.

## Notes

The prior Step Record described the superseded pre-amendment design. The accepted current-schema ADR assigns normalization to canonical ingress and requires explicit policy at callers, so this proof invokes `normalize_m303_carry=True` and verifies repository state directly.
