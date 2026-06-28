---
step_id: S108
tags:
  - '#exec'
  - '#core-authority'
date: '2026-05-31'
modified: '2026-05-31'
related:
  - "[[2026-05-31-core-authority-plan]]"
  - "[[2026-05-31-core-authority-adr]]"
  - "[[2026-05-31-core-authority-audit]]"
---

# core-authority W13.P32.S108 step record

## Step

Rename `domain/user_profile/_values::ProfileFactValue` to `UserProfileFactValue` to
eliminate the name collision with `domain/calculations/registry/_schema::ProfileFactValue`.
Migrate all callers.

## Rationale

Two distinct types shared the name `ProfileFactValue`:
- `domain/user_profile/_values.py`: 6-member union (str|bool|int|Decimal|date|None) — the
  user profile fact value type used for storing and retrieving profile facts.
- `domain/calculations/registry/_schema.py:944`: 3-member union (bool|int|str) — the
  registry binding value type for profile-sourced calculation inputs.

These are different domain concepts. The user-profile copy is renamed to `UserProfileFactValue`
to eliminate ambiguity. The registry `ProfileFactValue` retains its name as it is the
domain-canonical calculation concept.

## Files touched

- `src/aeat/domain/user_profile/_values.py` — renamed type alias
- `src/aeat/domain/user_profile/__init__.py` — updated re-export
- `src/aeat/application/user_profile/__init__.py` — updated import and re-export
- `src/aeat/application/modelo/_profile_binding.py` — updated all 7 usage sites

## Verification

`domain/user_profile/` test suite: 28 passed in 19.05s (no regressions).
