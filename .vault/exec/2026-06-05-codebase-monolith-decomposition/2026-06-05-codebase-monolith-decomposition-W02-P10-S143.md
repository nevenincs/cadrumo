---
tags:
  - '#exec'
  - '#codebase-monolith-decomposition'
date: '2026-06-05'
modified: '2026-06-05'
step_id: 'S143'
related:
  - '[[2026-06-05-codebase-monolith-decomposition-plan]]'
---

# W02.P10.S143 Config Custody Split

Scope: split residual config custody command registration into focused transport helpers without moving custody policy into CLI.

## Description

- Split secret-store custody verbs from `_custody.py` into `_custody_secret.py`.
- Kept `_custody.py` as the unlock and root custody registrar facade.
- Preserved application-owned custody operations through `aeat.application.user_profile` calls.
- Verified the split modules stay below callable and module size budgets.

## Outcome

The config custody CLI surface remains transport-only and no longer concentrates unlock, lock, rekey, recovery, and recovery verification handlers in one file.

## Notes

Ruff passed for the changed config custody modules. Focused config CLI tests passed across 57 real-behavior tests. The root custody module is 93 lines and the focused secret custody module is 266 lines, with no callable over the 180-line default.
