---
step_id: S09
tags:
  - '#exec'
  - '#codebase-solidification'
date: '2026-05-28'
modified: '2026-05-28'
related:
  - '[[2026-05-28-codebase-solidification-plan]]'
  - '[[2026-05-27-centralized-module-drift-audit]]'
---

# codebase-solidification W01.P01.S09 — WorkflowInputMismatchError

## Outcome

Introduced `WorkflowInputMismatchError(CoreValidationError)` in
`src/aeat/application/modelo/_actions.py`. Replaced the bare
`ValueError("workflow input request does not match calculation revision")`
at `_RevisionInputsProvider.load_inputs` with a structured envelope
carrying `expected_modelo`, `expected_period`, `requested_modelo`, and
`requested_period` context keys. Registered `REFUSED_WORKFLOW_INPUT_MISMATCH`
in `src/aeat/core/errors/registry/_application.py`. Exported the error
class from `src/aeat/application/modelo/__init__.py`.

## Files touched

- `src/aeat/application/modelo/_actions.py` (CoreValidationError import, class declaration, raise replaced)
- `src/aeat/application/modelo/__init__.py` (import + __all__ entry)
- `src/aeat/core/errors/registry/_application.py` (ErrorCode entry added)
- `src/aeat/locales/en.yml`, `ca.yml`, `es.yml`, `hu.yml` (locale key scaffolded and set)

## Collision check

`git diff` on all target files returned empty before authoring.

## Commit

`07378f2c0`
