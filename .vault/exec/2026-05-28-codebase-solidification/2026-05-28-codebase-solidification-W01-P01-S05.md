---
step_id: S05
tags:
  - '#exec'
  - '#codebase-solidification'
date: '2026-05-28'
modified: '2026-05-28'
related:
  - '[[2026-05-28-codebase-solidification-plan]]'
  - '[[2026-05-27-centralized-module-drift-audit]]'
---

# codebase-solidification W01.P01.S05 — ExportFormatError + ExportFieldError hierarchy

## Outcome

Created `src/aeat/application/export/_errors.py` with two new domain exception classes:

- `ExportFormatError(CoreError)` — raised when an unsupported export serialization format is requested.
- `ExportFieldError(CoreValidationError)` — raised when a field validation invariant is violated during tabular export. Inherits `ValueError` via `CoreValidationError` so pydantic field validators continue to satisfy pydantic's exception contract.

Migrated all seven bare `ValueError` / `raise` sites in `_tabular.py`:
- 2 sites in `TabularExportResult._validate_fieldnames` (pydantic field validator): blank names, duplicates → `ExportFieldError`.
- 3 sites in `_normalize_fieldnames`: empty sequence, blank names, duplicates → `ExportFieldError`.
- 1 site in `_normalize_row`: unknown field keys → `ExportFieldError`.
- 1 site in `serialize_tabular_rows` (unsupported format guard): → `ExportFormatError`.

Registered both error codes in `src/aeat/core/errors/registry/_application.py`:
- `REFUSED_EXPORT_FORMAT` (`ErrorCategory.REFUSED`, `message_key="errors.refused.refused_export_format"`).
- `REFUSED_EXPORT_FIELD` (`ErrorCategory.REFUSED`, `message_key="errors.refused.refused_export_field"`).

Added locale keys to all four locale files (en, es, ca, hu) via `python -m aeat.locales set`.

## Files touched

- `src/aeat/application/export/_errors.py` (created)
- `src/aeat/application/export/_tabular.py` (7 raise sites migrated)
- `src/aeat/core/errors/registry/_application.py` (2 error codes registered)
- `src/aeat/locales/en.yml`, `es.yml`, `ca.yml`, `hu.yml` (locale keys added via CLI)

## Commit

`7beb7c114` — solidification(W01.P01.S05+S06): ExportFormatError + ExportFieldError hierarchy and tests
