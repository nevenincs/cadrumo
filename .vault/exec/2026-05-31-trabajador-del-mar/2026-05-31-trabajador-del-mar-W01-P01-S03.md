---
step_id: "S03"
tags:
  - "#exec"
  - "#trabajador-del-mar"
date: "2026-05-31"
modified: '2026-05-31'
related:
  - "[[2026-05-31-trabajador-del-mar-plan]]"
  - "[[2026-05-31-trabajador-del-mar-adr]]"
---

# trabajador-del-mar W01.P01.S03 step record

## Step

Write a registry-load test asserting the new profile facts appear in the validated snapshot without schema error.

## Files Touched

- `src/aeat/domain/calculations/registry/test_trabajador_del_mar_profile.py` — created with 8 profile-load tests (S03 surface).

## Commit

`1c1a68a3b` — test(maritime-worker): registry profile load tests for maritime_worker section (S03)

## Tests Added (S03 surface)

- `test_user_profile_schema_loads_with_maritime_worker_section` — section presence
- `test_worker_class_fact_is_enum_with_trabajador_del_mar` — enum type, values, predicates
- `test_worker_class_carries_legal_refs_for_all_three_maritime_axes` — all five BOE citations
- `test_vessel_flag_fact_is_enum_with_es_and_foreign` — flag enum + legal_refs
- `test_waters_type_fact_is_enum_with_national_and_international` — waters enum + legal_refs
- `test_vessel_registry_fact_is_enum_covering_rebeca_variants` — REBECA enum variants
- `test_retmar_registered_fact_is_boolean_with_schedule_predicate` — boolean + predicate + legal_refs
- `test_no_da24_reference_in_maritime_worker_section` — DA 24 contamination guard

## Outcome

8/8 tests pass. Profile schema loads without error with the new maritime_worker section.
