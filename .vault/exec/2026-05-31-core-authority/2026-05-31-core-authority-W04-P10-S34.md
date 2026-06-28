---
step_id: S34
tags:
  - '#exec'
  - '#core-authority'
date: '2026-05-31'
modified: '2026-05-31'
related:
  - '[[2026-05-31-core-authority-plan]]'
  - '[[2026-05-31-core-authority-adr]]'
  - '[[2026-05-31-core-authority-action-tracker-v2-reference]]'
---

# core-authority W04.P10.S34 — _ProfileFactValue alias in application/overview/_explain.py (BLOCKED)

## Status

**BLOCKED.** Depends on S33 which is blocked. `_ProfileFactValue` in `_explain.py` is `str | bool | int` — identical to the registry schema's `bool | int | str`. If S33 is resolved by renaming the user_profile version rather than deleting it, S34 can proceed by aliasing `_ProfileFactValue` to `domain/calculations/registry/_schema.py:ProfileFactValue` directly (which it already effectively mirrors). Deferred to the same follow-up plan as S33.

## Files touched

None.
