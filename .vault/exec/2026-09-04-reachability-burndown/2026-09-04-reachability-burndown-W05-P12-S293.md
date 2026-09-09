---
tags:
  - '#exec'
  - '#reachability-burndown'
date: '2026-09-09'
modified: '2026-09-09'
body_schema: 'body-v2'
body_hash: 'sha256:96c0514eee2c6bedbb4b914c8bd7ddb78e8f183b33c46340432f427979ce3722'
step_id: 'S293'
related:
  - "[[2026-09-04-reachability-burndown-plan]]"
---

<!-- Machine-owned: the filename, the frontmatter, the title heading and the
     Scope list are all filled by `vaultspec-core vault add exec` from the
     originating Step row; never hand-edit them. Add no frontmatter fields.
     Wiki-links belong in `related:` only, never in the body. -->

# Withdraw the unshipped offline XLSX/JSON calc-sheets transport atomically after its test-only facade exposed test-only serializers; move Guide and Evidencia tables to the live Google owner and retain direct plan/apply behavior tests.

## Scope

- `offline workbook materializer and synthetic/parity tests`
- `live export tables and Google apply adapter`
- `calc-sheets prose`
- `exact reachability`
- `cadence reference`
- `and Step Record`

## Changes

- `D` `src/cadrumo/application/storage/calc_sheets/workbook_export.py`
- `A` `src/cadrumo/application/storage/calc_sheets/export_tables.py`
- `D` `src/cadrumo/application/storage/calc_sheets/tests/test_workbook_export_evidence.py`
- `D` `src/cadrumo/application/storage/calc_sheets/tests/test_workbook_evidence_digest_contract.py`
- `D` `src/cadrumo/application/storage/calc_sheets/tests/test_row_set_calculation_roundtrip.py`
- `D` `src/cadrumo/adapters/outbound/google/tests/test_calc_sheets_offline_online_conformance.py`
- `D` `src/cadrumo/adapters/outbound/google/tests/test_calc_sheets_transport_facet_parity.py`
- `D` `src/cadrumo/entrypoints/cli/tests/test_modelo_export_evidence.py`
- `M` `src/cadrumo/adapters/outbound/google/_calc_sheets_apply_values.py`
- `M` `src/cadrumo/adapters/outbound/google/_calc_sheets_apply_formatting.py`
- `M` `src/cadrumo/adapters/outbound/google/tests/test_calc_sheets_apply_evidence.py`
- `M` `src/cadrumo/application/storage/__init__.py`
- `M` `src/cadrumo/application/storage/calc_sheets/__init__.py`
- `M` `src/cadrumo/application/storage/calc_sheets/_styling.py`
- `M` `src/cadrumo/application/storage/calc_sheets/engine.py`
- `M` `src/cadrumo/application/storage/calc_sheets/records.py`
- `M` `src/cadrumo/application/storage/calc_sheets/theme.py`
- `M` `src/cadrumo/application/storage/calc_sheets/tests/test_engine_evidence_threading.py`
- `M` `src/cadrumo/application/storage/calc_sheets/tests/test_modelo_export_formatting.py`
- `M` `src/cadrumo/application/storage/calc_sheets/tests/test_modelo_export_styling.py`
- `M` `dev/docs/preprocess/_workbook.py`
- `M` `.vault/reference/2026-09-04-reachability-burndown-reference.md`
- `verify:` `rg -n "workbook_export|offline workbook|offline XLSX|offline xls|offline export|OfflineWorkbook|serialize_offline|openpyxl_argb" src dev -g "*.py"` -> `pass`
- `verify:` `uv run --no-sync ruff check <focused calc-sheets and Google apply paths>` -> `pass`
- `verify:` `uv run --no-sync pytest -q <focused live plan and Google Evidencia tests>` -> `pass`
- `verify:` `uv run --no-sync python -m dev.audit.unreachable_code --confidence exact` -> `pass`
