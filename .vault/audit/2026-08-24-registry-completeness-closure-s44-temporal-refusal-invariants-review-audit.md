---
tags:
  - '#audit'
  - '#registry-completeness-closure'
date: '2026-08-24'
modified: '2026-08-24'
body_schema: 'body-v1'
body_hash: 'sha256:e2faa475d27ab374548467e9e94fd6d02a5f205002f3bf7cb181d0fcdf3e70e2'
related:
  - "[[2026-08-24-registry-completeness-closure-plan]]"
---

# `registry-completeness-closure` audit: `s44 temporal refusal invariants review`

## Scope

Reviewed commit `2ca6889244` and the current public application-registry surface. The review checked whether every `TemporalRevisionCoverage` refusal shape matches the actual composer boundary, whether direct construction and deserialised frozen-row mutations are refused when contradictory, and whether the public facade remains compatible with the temporal and source-connectivity composers.

## Findings

### undeclared-grade-guard-unproven | medium | The no-declared-grade invariant lacks a direct and mutation bite proof

`TemporalRevisionCoverage` correctly refuses an `undeclared_authority_grade` row that carries a declared grade, but the new negative-construction and revalidated-mutation cases only corrupt that branch's `selected_revision`. An external in-memory mutation that removes only the non-null-grade guard leaves all fourteen S44 direct-shape and mutation tests green. This leaves a public deserialisation path unguarded by the required anti-regression proof: a future removal of that condition would accept a contradictory refusal that claims both no declared grade and a declared grade.

All other reviewed branch shapes agree with the composer: law-selection refusal carries no selected revision; the two mismatch codes carry a conflicting selected revision; undeclared-grade and declared-grade-snapshot refusals retain the registered selection; and only the latter requires a declared grade. The model remains publicly exported through `cadrumo.application.registry` and current source-connectivity composition does not consume or conflict with its fields.

## Recommendations

Add a targeted follow-up that supplies both a direct contradictory `undeclared_authority_grade` payload with a declared grade and a `model_copy` plus `model_validate` mutation of that field. Run the focused temporal-coverage test module and demonstrate that removing only this guard makes the new proof fail.
