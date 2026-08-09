---
tags:
  - '#exec'
  - '#profile-requirement-grounding'
date: '2026-08-09'
modified: '2026-08-09'
body_schema: 'body-v1'
body_hash: 'sha256:0d1b53067d610d6401bd0e99a05bd704c7939493cfe96b05abcc624bc9298d38'
step_id: 'S07'
related:
  - "[[2026-08-08-profile-requirement-grounding-plan]]"
---

# Add a grounded regression proving the blocking-gate message text changes for a known missing field

## Scope

- `src/cadrumo/application/modelo/tests/`

## Description

Added `test_create_work_unit_service_refuses_profile_missing_activity` assertions (already existing test, extended) proving the blocking-gate `ModeloProfileReadinessError.context["missing"]` changed from a raw dotted path to a resolved label. Also extended `test_config_profile_preflight_scope.py` and `test_modelo_work_readiness_ux.py` with equivalent assertions on the `config profile preflight` and `app modelo readiness` CLI surfaces, including a JSON-mode check that `preflight` and `readiness` return matching `label`/`legal_refs` for the same underlying gap.

## Outcome

The regression genuinely bites: it failed against the pre-enrichment code (raw dotted path) and against an interim state (schema-description label instead of the catalogue label), and was updated each time the underlying rendering changed, most recently to assert the catalogue label rather than a hardcoded translated string (see Notes).

## Verification

`pytest src/cadrumo/application/modelo/tests/test_profile_readiness_gate.py src/cadrumo/entrypoints/cli/tests/test_config_profile_preflight_scope.py src/cadrumo/entrypoints/cli/tests/test_modelo_work_readiness_ux.py -n 0 -m "unit or integration"` - all pass.

## Notes

The P04.S11 honesty review flagged (`localized-prose-hardcoded-in-the-p03-regression`) that `test_create_work_unit_service_refuses_profile_missing_activity` originally pinned a hardcoded Spanish catalogue string, coupling a modelo-gate test to the `es` locale catalogue's exact text. Fixed same-session: the expected value is now computed via `profile_field_label("activities", schema.field("activities.description"))`, so a legitimate translation edit no longer reds this test.
