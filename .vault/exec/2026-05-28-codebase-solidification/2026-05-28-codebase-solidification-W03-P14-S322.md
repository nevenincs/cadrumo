---
step_id: S322
tags:
  - '#exec'
  - '#codebase-solidification'
date: '2026-05-30'
modified: '2026-05-30'
related:
  - '[[2026-05-28-codebase-solidification-plan]]'
---

# codebase-solidification W03.P14.S322 — project_answers registration slot in aeat.core

## Outcome

Introduced a registration slot in `src/aeat/core/profile.py`:

- `_PROJECT_ANSWERS_SLOT: list[ProjectAnswersFn]` mutable singleton list
- `register_project_answers(fn)` / `get_project_answers()` / `project_answers()` shim
- `ProjectAnswersNotRegisteredError` raised when slot empty
- `ProjectAnswersFn` Protocol type alias for the callable signature

`src/aeat/application/wizard/_persistence.py` imports `register_project_answers`
at the top of the file (alongside other core imports) and calls it after
`project_answers` is defined, at module-level before `__all__`. This means
importing `_persistence` registers the concrete implementation in the slot so
domain consumers get the real callable.

## Files touched

- `src/aeat/core/profile.py`
- `src/aeat/application/wizard/_persistence.py`

## Verification

`test_project_answers_raises_before_registration` and
`test_project_answers_registered_after_persistence_import` in
`src/aeat/core/test_profile.py` pass. Ruff zero errors.
