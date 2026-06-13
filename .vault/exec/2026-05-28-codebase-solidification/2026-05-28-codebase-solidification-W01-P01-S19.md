---
step_id: S19
tags:
  - '#exec'
  - '#codebase-solidification'
date: '2026-05-28'
modified: '2026-05-28'
related:
  - '[[2026-05-28-codebase-solidification-plan]]'
  - '[[2026-05-27-centralized-module-drift-audit]]'
---

# codebase-solidification W01.P01.S19 — AuthDiagnosticPhoneStateError introduction

## Outcome

Created `src/aeat/application/auth/_errors.py` introducing
`AuthDiagnosticPhoneStateError(CoreValidationError)`. Registered it in
`src/aeat/core/errors/registry/_application.py` with code
`REFUSED_AUTH_DIAGNOSTIC_PHONE_STATE` (`ErrorCategory.REFUSED`), message key
`errors.refused.refused_auth_diagnostic_phone_state`, suggestion
`aeat app auth diagnostics --help`. Added the locale message key to en, es, ca,
and hu locale files via `python -m aeat.locales set`. Replaced
`raise ValueError(phone_state)` at line 141 of
`src/aeat/application/auth/_diagnostics.py` with
`raise AuthDiagnosticPhoneStateError(phone_state, context={"phone_state": phone_state})`.

## Files touched

- `src/aeat/application/auth/_errors.py` (created)
- `src/aeat/application/auth/_diagnostics.py`
- `src/aeat/core/errors/registry/_application.py`
- `src/aeat/locales/en.yml`
- `src/aeat/locales/es.yml`
- `src/aeat/locales/ca.yml`
- `src/aeat/locales/hu.yml`

## Verification

3/3 tests in `src/aeat/application/auth/test_diagnostics.py` pass. Ruff clean.
Commit SHA: a184582de.
