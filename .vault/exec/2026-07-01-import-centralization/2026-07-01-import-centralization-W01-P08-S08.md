---
tags:
  - '#exec'
  - '#import-centralization'
date: '2026-07-01'
modified: '2026-07-08'
step_id: 'S08'
related:
  - "[[2026-07-01-import-centralization-plan]]"
---

# Promote `CarriedSecureObject`, `CoverageManifest`, `ProfileExportError`, `UserProfileError`, `UserProfileValidationError`, `utc_now` to `aeat.domain.user_profile.__all__` with eager re-exports so the 10 existing cross-package consumer site(s) can import from the facade

## Scope

- `src/aeat/domain/user_profile/__init__.py`

## Description

- Located the defining modules for all six named symbols: `UserProfileError`,
  `UserProfileValidationError`, `ProfileExportError` in `_errors.py`;
  `CarriedSecureObject`, `CoverageManifest` in `_portable_export.py`; `utc_now`
  in `_values.py` (an alias-import of `aeat.core.time.now`).
- Confirmed `_portable_export.py` is the exact module the package already keeps
  lazy for `UserProfilePortableExport`, because its top-level imports cascade
  into `aeat.domain.modelos`, `aeat.domain.transactions`, and the calculation
  registry. Added `CarriedSecureObject` and `CoverageManifest` through the same
  existing module-level `__getattr__` (PEP 562) rather than eager imports, so
  the promotion does not reintroduce the cascade cost the existing lazy design
  exists to avoid.
- Added `UserProfileError`, `UserProfileValidationError`, `ProfileExportError` to
  the existing eager `_errors` import, and `utc_now` to the existing eager
  `_values` import (both modules are already imported eagerly at package init,
  so these four additions are free).
- Updated `__all__` and the module docstring to name the new exports and the
  lazy-resolution rationale for the two portable-export types.
- Verified with a probe script that accessing `up.CarriedSecureObject` after
  package import is the first point `aeat.domain.modelos._calculation_revision`
  enters `sys.modules` (lazy behaviour preserved, not merely asserted).
- Ran `ruff check --fix` and `ruff format --diff` (clean), `pytest --collect-only
  -q src/aeat` (clean), `pytest -q src/aeat/domain/user_profile/tests` (passed),
  and the two pre-existing architecture-boundary gates (passed).

## Outcome

- `src/aeat/domain/user_profile/__init__.py` exports all six named symbols;
  `CarriedSecureObject`/`CoverageManifest` are lazy, the remaining four are
  eager. Re-scanned with `dev/import_hygiene_scan.py`: all six now report
  `already_in_facade: true`.
- Committed as `7c885ced3`.

## Notes

- No incidents. No consumer files were touched (Wave 2 scope); the six
  cross-package consumer sites the Step names still import from the private
  submodules and will be rewired in Wave 2.
