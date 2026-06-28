---
tags:
  - '#exec'
  - '#user-profile-lazy-import'
date: '2026-06-04'
modified: '2026-06-04'
step_id: 'S05'
related:
  - "[[2026-06-03-user-profile-lazy-import-plan]]"
---

# Strip the top-level domain import and Pydantic declarations

## Scope

- `src/aeat/application/user_profile/__init__.py`

## Description

- Remove the top-level `from ...domain.user_profile import (...)`
  block; the four domain records are now resolved on demand via
  `__getattr__`.
- Remove the 17 Pydantic class declarations and the
  `_PROFILE_SNAPSHOT_HASH_KWARGS` constant from the module body; they
  live in `_commands.py`.
- Keep the module docstring (extended to document the lazy contract
  and the producer-side probe sibling).
- Keep the `_register_language_resolver()` call (the resolver itself
  is cheap and defers its workflow / orchestration imports).
- Keep `ProfileId` as a top-level re-export (it is a cheap core-layer
  alias that every consumer expects without going through `__getattr__`).
- Keep `__all__` unchanged; the public surface is the same.

## Outcome

- Landed as part of commit `e78b32be0` together with S04 and S06.
- After the strip, importing `aeat.application.user_profile` in a
  fresh interpreter places zero registry submodules into `sys.modules`
  (down from 69).

## Notes

- The `TYPE_CHECKING` block was extended to import the four domain
  records and the relocated commands so static type-checkers still
  resolve names at the boundary.
