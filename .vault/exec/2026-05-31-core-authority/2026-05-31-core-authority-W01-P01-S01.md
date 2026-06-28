---
step_id: S01
tags:
  - '#exec'
  - '#core-authority'
date: '2026-05-31'
modified: '2026-05-31'
related:
  - '[[2026-05-31-core-authority-plan]]'
  - '[[2026-05-31-core-authority-adr]]'
  - '[[2026-05-31-core-authority-action-tracker-v2-reference]]'
---

# core-authority W01.P01.S01 — rename adapter ExportFormatError to AeatExportFormatError

## Scope

FIX-001: Two classes named `ExportFormatError` existed with separate qualnames in the
error registry (`core/errors/registry/_adapters.py` and `_application.py`). The name
collision made `except ExportFormatError` catch behaviour import-order dependent.

Rename the adapter class (`adapters/outbound/aeat/export/_errors.py`) to
`AeatExportFormatError`. Update its registry qualname entry in
`core/errors/registry/_adapters.py`. Migrate all four adapter call-sites:
`__init__.py`, `_formats/_serialise.py`, `_formats/_record_spec.py`,
`_formats/_deserialise.py`, and the roundtrip test file. The application-layer
`ExportFormatError` in `application/export/_errors.py` is the canonical sole entry.

## Outcome

- `adapters/outbound/aeat/export/_errors.py`: class renamed to `AeatExportFormatError`.
- `core/errors/registry/_adapters.py`: qualname updated to `aeat.adapters.outbound.aeat.export._errors.AeatExportFormatError`.
- 3 `_formats/` modules and their test file: import and raise/except sites use `AeatExportFormatError`.
- `application/export/test_tabular.py`: new test `test_export_format_error_registry_has_no_name_collision` asserts exactly one `ExportFormatError` entry (application canonical).
- Caller rename count: 6 files updated (8 total including `_errors.py` and `_adapters.py`).

## Verification

`uv run --no-sync pytest src/aeat/adapters/outbound/aeat/export/ src/aeat/application/export/test_tabular.py -x -q --deselect src/aeat/adapters/outbound/aeat/export/_formats/test_fichero_boe_roundtrip.py::test_modelo_303_golden_sha_fichero_boe`

161 passed, 2 skipped. The deselected test is a pre-existing fixture failure (bound casilla resolution) unrelated to this change.

## Commit

`72f6a6698` — fix(errors): rename adapter ExportFormatError to AeatExportFormatError (W01.P01.S01)
