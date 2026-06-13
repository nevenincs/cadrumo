---
step_id: S44
date: 2026-05-28
modified: '2026-05-28'
tags:
  - "#exec"
  - "#codebase-solidification"
related:
  - "[[2026-05-28-codebase-solidification-plan]]"
  - "[[2026-05-27-centralized-module-drift-audit]]"
---

# codebase-solidification W01.P01.S44 - real-behavior tests for AggregationConfigError

## Outcome

Created `src/aeat/application/aggregation/test_service.py` with 12 real-behavior
tests covering the registry enrollment, envelope round-trip, and all 9 replaced
raise sites.

## Test inventory

- `test_aggregation_config_error_is_in_error_registry` — asserts `ERROR_AGGREGATION_CONFIG` in `ERROR_REGISTRY`
- `test_aggregation_config_error_registered_code_accessible_from_instance` — `get_registered_error_code` returns correct code from instance
- `test_aggregation_config_error_round_trips_through_build_error_envelope` — `build_error_envelope` produces code=`ERROR_AGGREGATION_CONFIG`, category=`ERROR`
- `test_site1_provider_contract_rejects_duplicate_modelos` — site 1
- `test_site2_contract_rejects_duplicate_providers` — site 2
- `test_site3_contract_rejects_modelo_owned_by_multiple_providers` — site 3
- `test_site4_contract_rejects_wrong_source_kind_taxonomy` — site 4
- `test_site5_command_rejects_cross_family_observations` — site 5
- `test_site6_result_rejects_duplicate_source_kinds` — site 6
- `test_site7_result_rejects_modelo_mismatch` — site 7
- `test_site8_result_rejects_period_mismatch` — site 8
- `test_site9_result_rejects_provider_payload_type_mismatch` — site 9

## Pytest outcome

`12 passed in 1.47s` — all tests pass. Existing `test_per_modelo_service.py`
`11 passed` — no regressions.

## Collision signal

No WIP on any target Python file at session start. Locale/registry files had
pre-landed changes from parallel S27/S28 campaign commit `fb551c34` — those
changes are compatible and were already correct for this step's needs.

## Commit SHA

`e3cf65e5d` (same commit as S43)
