---
tags:
  - '#exec'
  - '#ci-lane-deconflation'
date: '2026-08-31'
modified: '2026-08-31'
body_schema: 'body-v2'
body_hash: 'sha256:4d7e2bb014fa92afaf35f468296142a68a94e5c81c6eca73e3cf95aa9b206717'
step_id: 'S123'
related:
  - "[[2026-08-05-ci-lane-deconflation-plan]]"
---
# Refactor the size-budget subjects in calc_sheets_pull.py into cohesive siblings without raising any threshold.

## Scope

- `src/cadrumo/adapters/outbound/google/calc_sheets_pull.py`

## Changes

- `M` `src/cadrumo/adapters/outbound/google/calc_sheets_pull.py`
- `A` `src/cadrumo/adapters/outbound/google/calc_sheets_pull_records.py`
- `A` `src/cadrumo/adapters/outbound/google/calc_sheets_pull_coverage.py`
- `M` `src/cadrumo/adapters/outbound/google/tests/test_calc_sheets_pull_typing.py`
- `M` `src/cadrumo/adapters/outbound/google/tests/test_calc_sheets_typed_outcomes.py`
- `M` `src/cadrumo/adapters/outbound/google/tests/test_compute_from_pull.py`
- `M` `src/cadrumo/adapters/outbound/google/tests/test_package_module_allowlist.py`
- `M` `src/cadrumo/adapters/outbound/google/tests/test_pull_adapter_helpers.py`
- `M` `src/cadrumo/adapters/outbound/google/tests/test_pull_result_roundtrip.py`
- `M` `src/cadrumo/adapters/outbound/google/tests/test_verify_pull_coverage.py`
- `M` `src/cadrumo/adapters/outbound/google/tests/test_worksheet_export_pull_roundtrip.py`
- `M` `src/cadrumo/application/calculations/tests/test_detail_record_round_trip.py`
- `M` `src/cadrumo/application/calculations/tests/test_row_set_assembly.py`
- `M` `src/cadrumo/application/storage/calc_sheets/tests/test_row_set_assembly.py`
- `M` `src/cadrumo/application/storage/calc_sheets/tests/test_row_set_calculation_roundtrip.py`
- `M` `src/cadrumo/entrypoints/cli/_modelo_spreadsheet_cli.py`
- `M` `src/cadrumo/entrypoints/cli/tests/test_google_payloads.py`
- `M` `src/cadrumo/entrypoints/cli/tests/test_modelo_spreadsheet_pull_observations.py`
- `M` `src/cadrumo/adapters/outbound/aeat/sede/declarations_observations.py`
- `verify:` `uv run --no-sync pytest -n0 -q src/cadrumo/adapters/outbound/google/tests/test_calc_sheets_pull_typing.py src/cadrumo/adapters/outbound/google/tests/test_calc_sheets_typed_outcomes.py src/cadrumo/adapters/outbound/google/tests/test_compute_from_pull.py src/cadrumo/adapters/outbound/google/tests/test_pull_adapter_helpers.py src/cadrumo/adapters/outbound/google/tests/test_pull_result_roundtrip.py src/cadrumo/adapters/outbound/google/tests/test_verify_pull_coverage.py src/cadrumo/adapters/outbound/google/tests/test_worksheet_export_pull_roundtrip.py src/cadrumo/adapters/outbound/google/tests/test_package_module_allowlist.py` -> `pass (87 passed, exit 0)`
- `verify:` `uv run --no-sync pytest -n0 --collect-only -q src/cadrumo/adapters/outbound/google/tests/test_calc_sheets_pull_typing.py src/cadrumo/adapters/outbound/google/tests/test_calc_sheets_typed_outcomes.py src/cadrumo/adapters/outbound/google/tests/test_compute_from_pull.py src/cadrumo/adapters/outbound/google/tests/test_pull_adapter_helpers.py src/cadrumo/adapters/outbound/google/tests/test_pull_result_roundtrip.py src/cadrumo/adapters/outbound/google/tests/test_verify_pull_coverage.py src/cadrumo/adapters/outbound/google/tests/test_worksheet_export_pull_roundtrip.py src/cadrumo/adapters/outbound/google/tests/test_package_module_allowlist.py` -> `pass (87 collected, exit 0)`
- `verify:` `uv run --no-sync ruff check <S123 paths>` -> `pass (exit 0)`
- `verify:` `uv run --no-sync ruff format --check <S123 paths>` -> `pass (exit 0)`
- `verify:` `uv run --no-sync python -c "from cadrumo.tests import measure_module_lines; key='src/cadrumo/adapters/outbound/google/calc_sheets_pull.py'; actual=measure_module_lines()[key]; limit=1250; print(f'{key}: {actual}/{limit}'); assert actual <= limit"` -> `pass (1228 <= 1250, exit 0)`

## Notes

Predecessor exception: shared-worktree commit `0b578b3458c40279cd68ee765ccdc1b0b997a93a` captured the typed-record extraction and its direct consumer moves during the S123 validation run; its source-target diff is verified above. This step's remaining commit records the coverage extraction and traceability close. The target measured 1,369 source lines before the extraction and 1,228 under the canonical budget measurer after it. An earlier 13-module diagnostic run exited 1 with 133 passed and four unrelated existing failures: strict list-vs-tuple CLI references, missing expected pull observation, withholding `'0'` versus `0` identity drift, and an empty atribucion `clave`; the focused S123 evidence is green. No baseline was changed.
