---
step_id: S06
tags:
  - '#exec'
  - '#codebase-solidification'
date: '2026-05-28'
modified: '2026-05-28'
related:
  - '[[2026-05-28-codebase-solidification-plan]]'
  - '[[2026-05-27-centralized-module-drift-audit]]'
---

# codebase-solidification W01.P01.S06 — export error envelope and i18n tests

## Outcome

Extended `src/aeat/application/export/test_tabular.py` with 14 new real-behavior tests covering:

- Registry membership: `REFUSED_EXPORT_FORMAT` and `REFUSED_EXPORT_FIELD` are in `ERROR_REGISTRY`.
- Code attribute assertions: `code`, `message_key`, `retryable` fields match the registry declaration.
- Envelope round-trips: `build_error_envelope` succeeds for both error classes; envelope carries `code`, `category == "REFUSED"`, `retryable is False`, `schema_version == "1"`.
- Locale catalogue presence: `errors.refused.refused_export_format` and `errors.refused.refused_export_field` keys are non-empty in all four locale files (en, es, ca, hu), verified by loading the YAML with UTF-8 encoding.
- Real raise sites: all seven replaced sites exercised through the real `serialize_tabular_rows` entry point and `TabularExportResult` model construction — no mocks, no xfail, no tautological assertions.

Existing tests (CSV payload, JSONL payload, unknown fields) updated to assert `ExportFieldError` rather than the now-removed bare `ValueError` match.

## Verification

`uv run --no-sync pytest src/aeat/application/export/test_tabular.py -xvs`: 17 passed.

## Files touched

- `src/aeat/application/export/test_tabular.py` (14 new tests, 3 existing tests updated)

## Commit

`7beb7c114` — solidification(W01.P01.S05+S06): ExportFormatError + ExportFieldError hierarchy and tests
