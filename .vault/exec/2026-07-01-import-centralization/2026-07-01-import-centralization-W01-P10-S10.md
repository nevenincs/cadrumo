---
tags:
  - '#exec'
  - '#import-centralization'
date: '2026-07-01'
modified: '2026-07-08'
step_id: 'S10'
related:
  - "[[2026-07-01-import-centralization-plan]]"
---

# Promote `FiscalResidency`, `compute_deduccion_maternidad_0611`, `modelo100_ecivil_export_code`, `register_profile_keys` to `aeat.domain.contribuyente.__all__` with eager re-exports so the 5 existing cross-package consumer site(s) can import from the facade

## Scope

- `src/aeat/domain/contribuyente/__init__.py`

## Description

- Located the four named symbols' defining modules: `FiscalResidency` and
  `modelo100_ecivil_export_code` in `_renta_codes.py` (both cheap, no heavy
  imports); `compute_deduccion_maternidad_0611` in `_deduccion_maternidad.py`
  (pure arithmetic, only depends on `aeat.core.external_constants`);
  `register_profile_keys` in `_keys.py` (already imported eagerly for
  `ProfileKey`/`ProfileKeyRequirement`/etc.).
- Added all four to the package's existing eager import statements
  (`_renta_codes`, `_deduccion_maternidad`, `_keys`) and to `__all__`.
- Ran `ruff check --fix` and `ruff format --diff` (clean), `pytest
  --collect-only -q src/aeat` (clean), `pytest -q
  src/aeat/domain/contribuyente/tests` (passed), and the two pre-existing
  architecture-boundary gates (passed).

## Outcome

- `src/aeat/domain/contribuyente/__init__.py` now exports `FiscalResidency`,
  `compute_deduccion_maternidad_0611`, `modelo100_ecivil_export_code`,
  `register_profile_keys`. Re-scanned with `dev/import_hygiene_scan.py`: all
  four report `already_in_facade: true`.
- Committed together with the S11 disposition as `fc3e9a6ee` (both Steps land
  in the same package facade file and were verified together).

## Notes

- No incidents. Consumer rewrites (Wave 2) are out of this Step's scope; the
  five named cross-package consumer sites still import from the private
  submodules.
