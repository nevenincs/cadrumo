---
tags:
  - '#exec'
  - '#profile-requirement-grounding'
date: '2026-08-09'
modified: '2026-08-09'
body_schema: 'body-v1'
body_hash: 'sha256:8d3f98774ac5942965bb23f585f4a39a3a076be49363bf3410280058d9bab941'
step_id: 'S13'
related:
  - "[[2026-08-08-profile-requirement-grounding-plan]]"
---

# Surface the not-assessed signal as a CLI notice on config profile preflight and app modelo readiness, never as a clean bill of health

## Scope

- `src/cadrumo/entrypoints/cli/_config_payloads.py`
- `src/cadrumo/entrypoints/cli/_modelo_payloads.py`

## Description

Added `per_operation_requirements_assessed: bool` (no default) to `ProjectionModeloReadiness` (`state_projection.py`) and `ConfigProfilePreflightResult` (`_config_payloads.py`), threaded from the underlying `ProfilePreflightReport` at both construction sites (`state_projection.py`'s `_build_modelo_readiness`, `_profile_inspect.py`'s `preflight` command). Added a WARNING `Notice` on both `app modelo readiness` and `config profile preflight` firing whenever the flag is `False`, stating plainly that `ready`/`profile_ready` reflects only the export-identity and conditional checks, not a per-modelo assessment.

## Outcome

Landed as scoped by the ADR amendment's ruling 1. First verification run found two real regressions from the new required field and the new notice: a positional `notices[0]` assertion in `test_modelo_100_readiness_missing_bindings.py` broke because the new notice can now appear alongside the pre-existing ledger notice, and `test_app_quickfile.py`'s hand-built `ProjectionModeloReadiness` test fixture lacked the new required field. Both fixed same-iteration: the positional test now looks up notices by code (a more robust fix than reordering, since a third notice would have re-broken a positional assumption), and the fixture gained the field.

## Verification

`pytest src/cadrumo/entrypoints/cli/tests/test_modelo_100_readiness_missing_bindings.py src/cadrumo/entrypoints/cli/tests/test_app_quickfile.py src/cadrumo/application/tests/test_state_projection.py src/cadrumo/entrypoints/cli/tests/test_config_profile_preflight_scope.py src/cadrumo/entrypoints/cli/tests/test_config_preflight_revision_default.py src/cadrumo/entrypoints/cli/tests/test_modelo_work_readiness_ux.py src/cadrumo/application/user_profile/tests/ src/cadrumo/application/modelo/tests/test_profile_readiness_gate.py -n 0 -m "unit or integration"` - 600 passed, sequential, after both fixes.

## Notes

Since no shipped schema field currently declares a `modelo_` selector, this notice fires on essentially every real preflight/readiness call today - by design, per the amendment. It should stop firing organically once P05.S16 populates real `modelo_` selectors and the axis starts contributing for at least the modelos that inventory covers.
