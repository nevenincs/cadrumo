---
tags:
  - '#exec'
  - '#history-onboarding'
date: '2026-08-08'
modified: '2026-08-08'
body_schema: 'body-v1'
body_hash: 'sha256:e8acfd6320862cbf8f7274d9a566ef5d84e15c6d1f545e7a7caf9612b138dfbd'
step_id: 'S10'
related:
  - "[[2026-08-07-history-onboarding-plan]]"
---

# enroll app live filed pull-all in PROFILE_BOUND_WRITE_VERB_PATHS, verified by the existing write-policy guard test asserting the new path is recognised as profile-bound

## Scope

- `src/cadrumo/application/storage_write_policy.py`

## Description

- Enroll `app live filed pull-all` in `PROFILE_BOUND_WRITE_VERB_PATHS`.

## Outcome

`pull-all` persists, so it is profile-bound. `discover` is deliberately NOT
enrolled: it reads the register's option lists and persists nothing, and enrolling
a read-only verb would put a write guard in front of a verb that cannot write.

## Verification

uv run --no-sync pytest src/cadrumo/application/live/tests/ src/cadrumo/application/overview/tests/ \
      src/cadrumo/entrypoints/cli/tests/test_app_live_filed_discover.py \
      src/cadrumo/entrypoints/cli/tests/test_filed_history_onboarding_result.py \
      src/cadrumo/entrypoints/cli/tests/test_json_schema_conformance.py \
      src/cadrumo/entrypoints/cli/tests/test_documented_command_conformance.py \
      src/cadrumo/agent/tests/test_rule_surface_conformance.py -q -n0 -m "unit or integration"
    1147 passed, 2 deselected in 155.20s (0:02:35)

## Notes

The enrolment and the verb it names were authored in the same working tree and
landed together, so the allowlist never referenced a verb that did not exist and
the verb was never reachable without its guard.
