---
tags:
  - '#exec'
  - '#registry-dated-validity'
date: '2026-08-27'
modified: '2026-08-27'
body_schema: 'body-v2'
body_hash: 'sha256:b02f585ecdc8f15a32b2c7aedec45659a7f88200cb9cadadbd56cbcc6431769c'
step_id: 'S21'
related:
  - "[[2026-08-27-registry-dated-validity-plan]]"
---

# Wire the LIRPF art. 30.2.5.a insured-person counts into the shipped aggregation so both cap limbs reach production

## Scope

- `src/cadrumo/application/aggregation/tests/test_seguro_enfermedad_cap_reaches_production.py`

## Changes

- `R` `src/cadrumo/domain/contribuyente/_seguro_enfermedad_insured.py` -> `src/cadrumo/domain/contribuyente/seguro_enfermedad_insured.py`
- `M` `src/cadrumo/domain/contribuyente/seguro_enfermedad_insured.py`
- `M` `src/cadrumo/domain/contribuyente/__init__.py`
- `M` `src/cadrumo/domain/contribuyente/tests/test_seguro_enfermedad_insured.py`
- `M` `src/cadrumo/application/user_profile/projections.py`
- `M` `src/cadrumo/application/modelo/profile_binding.py`
- `M` `src/cadrumo/application/modelo/_autonomic_deduccion_advisory.py`
- `M` `src/cadrumo/application/modelo/_required_binding_gate.py`
- `M` `src/cadrumo/application/modelo/_profile_export_binding.py`
- `M` `src/cadrumo/application/modelo/tests/test_autonomic_deduccion_advisory.py`
- `M` `src/cadrumo/application/modelo/tests/test_modelo_100_2024_profile_coverage.py`
- `M` `src/cadrumo/application/modelo/tests/test_profile_binding_real_path.py`
- `M` `src/cadrumo/application/aggregation/_renta_ledger.py`
- `A` `src/cadrumo/application/aggregation/tests/test_seguro_enfermedad_cap_reaches_production.py`
- `verify:` `pytest src/cadrumo/application/aggregation/tests/test_seguro_enfermedad_cap_reaches_production.py` -> `pass`
- `verify:` `pytest test_profile_binding_real_path test_autonomic_deduccion_advisory test_modelo_100_2024_profile_coverage test_profile_binding test_seguro_enfermedad_insured test_seguro_cap_sums_both_limbs` -> `pass`

## Notes

Two relocations were required to reach production and are recorded here because
each deleted a name rather than aliasing it. `count_seguro_enfermedad_insured`
moved off the `RentaFamilyProfile` assembler onto a plain descendant sequence and
gained `seguro_enfermedad_insured_counts_from_facts`, so the whole count sits
below both application packages; the first attempt routed through
`application/modelo` and hit the existing modelo-imports-aggregation cycle.
`profile_fact_index` and its type guard moved from
`application/modelo/profile_binding.py` to `application/user_profile/projections.py`
for the same reason, with all seven consumers updated in the same change.

Nineteen tests are red in the affected suites and NONE are caused by this Step.
Attribution: `application/wizard` no longer registers the profile keys on import,
which reds the registration-order, fact-write-door and cleared-path gates, and
traces to the peer relocation commit `f3d439a8bf`; the M100 2025 relief bindings
added by `6c0b795c8d` and `e13a909b5a` red the source-mesh binding-set
assertions; and the modelo 200 `calculation` authority grade reds three borrador
and lifecycle tests from `1d1b203114`. All sit in paths this Step did not touch
and are left for their owners.
