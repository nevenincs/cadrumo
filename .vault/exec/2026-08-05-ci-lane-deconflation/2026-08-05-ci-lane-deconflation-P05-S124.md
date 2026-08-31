---
tags:
  - '#exec'
  - '#ci-lane-deconflation'
date: '2026-08-31'
modified: '2026-08-31'
body_schema: 'body-v2'
body_hash: 'sha256:26116fc6316f8dc3c64ed6dc9f118e9f079d875546667c2c4046bc032eaa025d'
step_id: 'S124'
related:
  - "[[2026-08-05-ci-lane-deconflation-plan]]"
---
# Refactor the size-budget subjects in _google_drive.py into cohesive siblings without raising any threshold.

## Scope

- `src/cadrumo/adapters/outbound/storage/_google_drive.py`

## Changes

- `M` `src/cadrumo/adapters/outbound/storage/_google_drive.py`
- `A` `src/cadrumo/adapters/outbound/storage/_google_drive_metadata.py`
- `M` `src/cadrumo/adapters/outbound/storage/tests/test_google_drive.py`
- `M` `src/cadrumo/adapters/outbound/storage/tests/test_google_drive_failure_preconditions.py`
- `M` `src/cadrumo/adapters/outbound/storage/tests/test_google_drive_metadata_contract.py`
- `verify:` `uv run --no-sync pytest -n0 -q src/cadrumo/adapters/outbound/storage/tests/test_google_drive.py src/cadrumo/adapters/outbound/storage/tests/test_google_drive_metadata_contract.py src/cadrumo/adapters/outbound/storage/tests/test_google_drive_failure_preconditions.py src/cadrumo/adapters/outbound/storage/tests/test_validation_preconditions.py src/cadrumo/adapters/outbound/storage/tests/test_provider_conformance_parity.py` -> `pass (85 passed, exit 0)`
- `verify:` `uv run --no-sync ruff check src/cadrumo/adapters/outbound/storage/_google_drive.py src/cadrumo/adapters/outbound/storage/_google_drive_metadata.py src/cadrumo/adapters/outbound/storage/tests/test_google_drive.py src/cadrumo/adapters/outbound/storage/tests/test_google_drive_metadata_contract.py src/cadrumo/adapters/outbound/storage/tests/test_google_drive_failure_preconditions.py` -> `pass (exit 0)`
- `verify:` `uv run --no-sync ruff format --check src/cadrumo/adapters/outbound/storage/_google_drive.py src/cadrumo/adapters/outbound/storage/_google_drive_metadata.py src/cadrumo/adapters/outbound/storage/tests/test_google_drive.py src/cadrumo/adapters/outbound/storage/tests/test_google_drive_metadata_contract.py src/cadrumo/adapters/outbound/storage/tests/test_google_drive_failure_preconditions.py` -> `pass (exit 0)`
- `verify:` `uv run --no-sync python -c "from cadrumo.tests._size_budget import measure_module_lines; subject='src/cadrumo/adapters/outbound/storage/_google_drive.py'; lines=measure_module_lines()[subject]; print(f'{subject}: {lines}/1250'); raise SystemExit(lines > 1250)"` -> `pass (1139/1250, exit 0)`
