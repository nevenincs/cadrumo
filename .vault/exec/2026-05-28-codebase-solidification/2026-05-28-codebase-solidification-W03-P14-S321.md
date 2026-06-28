---
step_id: S321
tags:
  - '#exec'
  - '#codebase-solidification'
date: '2026-05-30'
modified: '2026-05-30'
related:
  - '[[2026-05-28-codebase-solidification-plan]]'
---

# codebase-solidification W03.P14.S321 — SetupAnswers canonical home in aeat.core

## Outcome

Introduced `SetupAnswers` as a pydantic `BaseModel` in `src/aeat/core/profile.py`.
The class carries all wizard-flow typed-answer fields with lazy-accessor validators
(`_m()`, `_p()`, `_ccaa()` via `importlib.import_module`) to resolve
`aeat.domain.deadlines._models` types at runtime, avoiding a circular import at
module load time.

`ProfileAnswerTypeError` added to `src/aeat/core/errors/__init__.py` and registered
in `src/aeat/core/errors/registry/_core.py` as `INTEGRITY_PROFILE_ANSWER_TYPE`.
Locale key `integrity_profile_answer_type` added to en/es/ca/hu.

`WizardAnswerTypeError` in `src/aeat/application/wizard/_errors.py` changed base
class from `CoreValidationError` to `ProfileAnswerTypeError` for backward compat.

## Files touched

- `src/aeat/core/profile.py` (new)
- `src/aeat/core/errors/__init__.py`
- `src/aeat/core/errors/registry/_core.py`
- `src/aeat/application/wizard/_errors.py`
- `src/aeat/locales/en.yml`
- `src/aeat/locales/es.yml`
- `src/aeat/locales/ca.yml`
- `src/aeat/locales/hu.yml`

## Verification

12 tests in `src/aeat/core/test_profile.py` pass. Ruff zero errors. Committed in
`098da3776` (swept by W03.P18 peer commit).
