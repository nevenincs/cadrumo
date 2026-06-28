---
step_id: S06
date: 2026-05-27
modified: '2026-05-27'
tags:
  - "#exec"
  - "#cross-domain-continuity"
related:
  - "[[2026-05-26-cross-domain-continuity-plan]]"
commit: c940ffb67
---

# cross-domain-continuity P01.S06 — command_error_boundary discrimination

## Deliverables

- `src/aeat/entrypoints/cli/_errors.py` — added `StoredProfileDriftError` discriminator arm in `command_error_boundary`, placed before the broad `AeatError` catch. Routes `StoredProfileDriftError` → `CliStoredDataValidationBoundaryError(error.original_exception)`. Bare `ValidationError` remains on its own arm (input-time path). Updated docstring to document 4 exception families.

## Outcome

`StoredProfileDriftError` is dispatched by typed exception, not field-path introspection. The two CLI boundary messages (stored-data repair vs input-time validation) are distinct. Linter and type-checker clean.
