---
tags:
  - '#exec'
  - '#profile-requirement-grounding'
date: '2026-08-09'
modified: '2026-08-09'
body_schema: 'body-v1'
body_hash: 'sha256:a5526b43c4d0c1fed99e67c9862fc771357d4535aaf34f13099cb644061325da'
step_id: 'S05'
related:
  - "[[2026-08-08-profile-requirement-grounding-plan]]"
---

# Add label, legal_refs, and modelos to ModeloReadinessMissingRequirementPayload and its construction site

## Scope

- `src/cadrumo/entrypoints/cli/_modelo_payloads.py`

## Description

Added `label: str`, `legal_refs: list[str]`, `modelos: list[str]` to `ModeloReadinessMissingRequirementPayload` in `_modelo_payloads.py`, and populated them at the construction site in `_modelo_readiness_cli.py`'s `readiness` command. Threaded `authority=resources().modelos.authority` into `state_projection.py`'s call to `modelo_work_profile_preflight_report(...)` so this surface also receives the registry-binding grounding union. Later extended (post-review) to append a `modelos` column to the command's text-line output.

## Outcome

Same pattern as `P02.S04`: JSON delivered as specified, text-line `modelos` column added afterward by the P04.S10 review fix, outside this Step's originally-scoped file list.

## Verification

`pytest src/cadrumo/entrypoints/cli/tests/test_config_profile_preflight_scope.py src/cadrumo/application/tests/test_state_projection.py -m integration -n 0` - all pass, including an assertion that `app modelo readiness`'s JSON `missing[].label`/`legal_refs` agree with `config profile preflight`'s for the same underlying gap on a real fixture.

## Notes

None.
