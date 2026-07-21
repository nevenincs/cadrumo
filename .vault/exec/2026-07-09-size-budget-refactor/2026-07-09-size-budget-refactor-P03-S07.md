---
tags:
  - '#exec'
  - '#size-budget-refactor'
date: '2026-07-09'
modified: '2026-07-17'
step_id: 'S07'
related:
  - "[[2026-07-09-size-budget-refactor-plan]]"
---

# Read taxpayer_profile_from_mapping in full and identify a cohesive extraction boundary (e.g. per-axis mapping helpers) that shrinks it under its override

## Scope

- `src/aeat/domain/deadlines/_profiles.py`

## Description

- Read `taxpayer_profile_from_mapping` in full (196 lines against the 180-line default budget).
- Identified two cohesive, self-contained sub-steps as the extraction boundary: the values-to-canonical-token stringification plus IVARegime normalisation and identity/activity default padding (`_canonicalize_and_pad`), and the 12-field estimacion objetiva (modulos) kwarg group (`_objective_estimation_fields`).
- Chose a `TypedDict` return shape for the modulos field group (not a loosely-typed dict) so `ty`/`pyright` continue verifying each field against `TaxpayerProfile` construction through the `**` splice.

## Outcome

Extraction boundary confirmed: two private helpers preserving the caller's exact locals and forwarding semantics, executed by coder-perf under commit `ccd5e2057`.

## Notes

Landed by coder-perf (parallel P03 assignment per the plan's Parallelization section); this record documents the completed Step for plan-closure purposes per `plan-closure-requires-exec-records`.
