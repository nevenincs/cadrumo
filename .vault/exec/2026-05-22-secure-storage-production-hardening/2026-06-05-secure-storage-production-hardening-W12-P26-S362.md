---
tags:
  - '#exec'
  - '#secure-storage-production-hardening'
date: '2026-06-05'
modified: '2026-06-05'
step_id: 'S362'
related:
  - '[[2026-05-22-secure-storage-production-hardening-refactor-plan]]'
---

# W12.P26.S362 - Close AFR-260 for submission models

Scope: close `AFR-260` for `src/aeat/domain/submission/_models.py` with scanner
signal `remote-provider`, target `remote-mirror`, and owner `W12.P24.S98`.

## Description

- Audited `_models.py` for remote-provider, secure-storage, active-profile, settings,
  environment, filesystem, and runtime repository behavior.
- Confirmed the module defines strict/frozen pydantic records and closed status enums
  for historical submission attempts only.
- Confirmed `Path` fields are model values (`browser_trace_path`,
  `justificante_pdf_path`) and the module does not read, write, create, or inspect
  those filesystem paths.
- Confirmed encrypted persistence for these records is owned by
  `src/aeat/domain/submission/_repository.py` and covered by real secure-storage
  roundtrip tests.
- Fixed a relocated test import in
  `src/aeat/domain/submission/tests/test_secure_storage_roundtrip.py`; after moving
  under `tests/`, `...adapters` resolved to `aeat.domain.adapters`, so the test now
  imports `....adapters`.
- Closed `W12.P26.S362` through `vaultspec-core vault plan step check` and updated
  the `AFR-260` register status to `closed`.

## Outcome

`AFR-260` is closed. `_models.py` is not a remote provider or storage owner; it is a
typed historical-submission data contract. The only code change repairs the focused
secure-storage test gate after package relocation.

Validation passed:

- `uv run --no-sync -q python -m aeat.locales audit`
- `uv run --no-sync ruff check src/aeat/domain/submission/_models.py src/aeat/domain/submission/tests/test_secure_storage_roundtrip.py src/aeat/domain/submission/tests/test_repository.py`
- `uv run --no-sync pytest -q src/aeat/domain/submission/tests/test_secure_storage_roundtrip.py src/aeat/domain/submission/tests/test_repository.py`
- `uv run --no-sync pytest -q src/aeat/adapters/persistence/storage/tests/test_runtime_migrated_repositories.py -k "submission"`

## Notes

The plan's `remote-provider` signal is retained as scanner provenance. The closeout
disposition is that `_models.py` is a model-only historical remote-result record
surface; remote acquisition and persistence are outside this file.
