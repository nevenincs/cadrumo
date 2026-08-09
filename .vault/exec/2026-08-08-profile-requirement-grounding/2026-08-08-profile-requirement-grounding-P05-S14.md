---
tags:
  - '#exec'
  - '#profile-requirement-grounding'
date: '2026-08-09'
modified: '2026-08-09'
body_schema: 'body-v1'
body_hash: 'sha256:b50b26d25a8648e35f66e07b28f21dd499c29cc2c2ed55f642e6caf2bf31adbb'
step_id: 'S14'
related:
  - "[[2026-08-08-profile-requirement-grounding-plan]]"
---

# Replace test_preflight_returns_ready_when_no_modelo_selectors_match, which encodes the current defect as the contract, with a regression asserting a profile declaring no facts is never reported ready for a modelo

## Scope

- `src/cadrumo/application/user_profile/tests/test_services.py`

## Description

Renamed `test_preflight_returns_ready_when_no_modelo_selectors_match` to `test_preflight_ready_with_no_modelo_selectors_matched_is_not_assessed` and added an assertion that `report.per_operation_requirements_assessed is False` alongside the existing `ready is True` assertion, so the test now honestly documents that this `ready=True` reflects zero schema-required fields examined rather than a complete profile. Added a new test, `test_create_work_unit_service_refuses_profile_declaring_no_facts_whatsoever`, at the work-creation gate layer proving a `UserProfileRecord` with `facts=()` is refused via `ModeloProfileReadinessError` (caught by `_FILING_BASELINE_PROFILE_PATHS`, which the amendment's ruling 3 explicitly keeps in force).

## Outcome

Landed as scoped. The original test was renamed and strengthened rather than deleted, since it correctly documents `ProfilePreflightService.report()`'s own scope (that service has no knowledge of `_FILING_BASELINE_PROFILE_PATHS`, which lives one layer up in `_profile_readiness_gate.py`) - deleting it would have removed real coverage of that service's documented boundary. The stronger "never ready with zero facts" guarantee the amendment asks for was added as a separate test at the correct layer (the gate), where it is actually true.

## Verification

`pytest src/cadrumo/application/user_profile/tests/test_services.py src/cadrumo/application/modelo/tests/test_profile_readiness_gate.py -n 0 -m "unit or integration"` - all pass, including both the renamed test and the new zero-facts regression.

## Notes

Grounded in the ADR amendment's exact worked example ("Driven against a real UserProfileRecord declaring no facts whatsoever, report(modelo='303', ...) returns ready=True with missing=()") and ruling 3 (baseline paths not retired by this amendment).
