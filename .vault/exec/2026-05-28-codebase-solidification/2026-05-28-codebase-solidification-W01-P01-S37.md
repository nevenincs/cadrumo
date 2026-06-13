---
step_id: S37
tags:
  - '#exec'
  - '#codebase-solidification'
date: '2026-05-28'
modified: '2026-05-28'
related:
  - '[[2026-05-28-codebase-solidification-plan]]'
  - '[[2026-05-27-centralized-module-drift-audit]]'
---

# codebase-solidification W01.P01.S37 — narrow except Exception catches in _config/__init__.py

## Outcome

Narrowed all four `except Exception` catches in
`src/aeat/entrypoints/cli/_config/__init__.py` by inserting an explicit
`except _AeatError` guard before each remaining `except Exception` arm.
Introduced `ConfigBoundaryError(CoreError)` in a new leaf module
`src/aeat/entrypoints/cli/_config/_errors.py` to wrap non-AeatError
exceptions at the three profile-record-read sites (catches 1, 2, 3).
Catch 4 (profile import parse failure) retains `_CliRefusedBoundaryError`
as the typed wrapper — the `except _AeatError: raise` guard prevents
double-wrapping.

`ConfigBoundaryError` registered in
`src/aeat/core/errors/registry/_entrypoints.py` with error code
`ERROR_CONFIG_BOUNDARY` (`ErrorCategory.ERROR`). Locale key
`errors.error.error_config_boundary` added to en, es, ca, hu locale
files via `python -m aeat.locales set`.

## Catches narrowed

- Line 463 (`_emit_profile_record_status`): `except _AeatError as exc` +
  `except Exception as exc` → wraps in `_ConfigBoundaryError(exc)`
- Line 840 (`_assert_profile_record_present`): same split
- Line 972 (`config_profile_show`): same split
- Line 1331 (`config_profile_import`): `except _AeatError: raise` +
  `except Exception as exc` → re-raises as `_CliRefusedBoundaryError`

## Files touched

- `src/aeat/entrypoints/cli/_config/_errors.py` (new)
- `src/aeat/entrypoints/cli/_config/__init__.py`
- `src/aeat/core/errors/registry/_entrypoints.py`
- `src/aeat/locales/en.yml`
- `src/aeat/locales/es.yml`
- `src/aeat/locales/ca.yml`
- `src/aeat/locales/hu.yml`

## Quality gates

- `ruff check`: all checks passed on all modified files
- `pyright`: pre-existing error at line 1899 (not introduced by this step)
- Collision check: `_config/__init__.py` and `_entrypoints.py` showed no
  foreign WIP
