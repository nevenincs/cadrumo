---
tags:
  - '#exec'
  - '#arch-remediation-engine-lifecycle'
date: '2026-07-02'
modified: '2026-07-17'
step_id: 'S08'
related:
  - "[[2026-07-02-arch-remediation-engine-lifecycle-plan]]"
---

# Add a regression asserting an in-process profile switch cannot observe the prior bucket engine, via an engine-identity assertion across a switch

## Scope

- `src/aeat/adapters/persistence/storage/tests/test_engine_session_lifecycle.py`

## Description

- Add `test_profile_switch_cannot_observe_prior_bucket_engine`: opening bucket A then switching to B disposes A's engine,
  so re-resolving A's route yields a fresh engine handle, never the pre-switch one.

## Outcome

Regression pins that an in-process profile switch cannot observe the prior bucket's engine.

Landed in commit `38e62c216`.

## Notes
