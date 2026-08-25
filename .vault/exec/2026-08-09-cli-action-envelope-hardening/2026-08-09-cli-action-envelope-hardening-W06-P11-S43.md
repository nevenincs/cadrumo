---
tags:
  - '#exec'
  - '#cli-action-envelope-hardening'
date: '2026-08-25'
modified: '2026-08-25'
body_schema: 'body-v1'
body_hash: 'sha256:1ce84161933a0dc0423dee581328fba446b76ae0f52a924143500df2d1b3f45f'
step_id: 'S43'
related:
  - "[[2026-08-09-cli-action-envelope-hardening-plan]]"
---




# Replace scenario-owned expected actions with observed production condition and action assertions

## Scope

- `dev/agent_eval/_models.py`

## Description

- Remove evaluator-owned expected action and continuation fields without compatibility aliases.
- Select scenarios by the S42 leaf-condition-scenario identity.
- Compare observed production verdict condition, action, and no-recovery outcome to the resolved production profile.

## Outcome

Commit `66c6957713` replaces authored expectations with strict production observations. Legacy fields are forbidden, actionable and terminal outcomes are discriminated, and the result carries the observation rather than copied action authority.

Eight focused tests pass; Ruff and diff checks pass. Independent review confirmed the remaining runner references are exclusively S44 consumer work.

## Notes

- `TYPE_CHECKING` imports avoid eager operator-surface materialization while retaining exact model typing.
