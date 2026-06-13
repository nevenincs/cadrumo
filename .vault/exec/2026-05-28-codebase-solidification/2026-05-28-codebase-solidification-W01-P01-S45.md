---
step_id: S45
tags:
  - '#exec'
  - '#codebase-solidification'
date: '2026-05-28'
modified: '2026-05-28'
related:
  - '[[2026-05-28-codebase-solidification-plan]]'
  - '[[2026-05-27-centralized-module-drift-audit]]'
---

# codebase-solidification W01.P01.S45 — DiagnosticModelError invariant replacement

## Outcome

Created `src/aeat/application/_errors.py` with `DiagnosticModelError(CoreValidationError)`.
Replaced all three bare `ValueError` raises inside
`DiagnosticCheck._enforce_actionable_contract` (lines 128, 131-134, 137 of
`src/aeat/application/diagnostics.py`) with `DiagnosticModelError(...)`.
Added `from ._errors import DiagnosticModelError` import to `diagnostics.py`.

Registered `REFUSED_DIAGNOSTIC_MODEL_INVARIANT` (`ErrorCategory.REFUSED`) in
`src/aeat/core/errors/registry/_application.py` with
`message_key="errors.refused.refused_diagnostic_model_invariant"`.

Added locale key `refused_diagnostic_model_invariant` to all four locale
files (en.yml translated, ca/es/hu with fallback key pattern) in alphabetical
order within the `refused:` section.

`uv run --no-sync python -m aeat.locales audit` passes all four locales.

## Files

- `src/aeat/application/_errors.py` (created)
- `src/aeat/application/diagnostics.py` (ValueError → DiagnosticModelError; import added)
- `src/aeat/core/errors/registry/_application.py` (registry entry added)
- `src/aeat/locales/en.yml` (key added)
- `src/aeat/locales/ca.yml` (fallback key added)
- `src/aeat/locales/es.yml` (fallback key added)
- `src/aeat/locales/hu.yml` (fallback key added)
