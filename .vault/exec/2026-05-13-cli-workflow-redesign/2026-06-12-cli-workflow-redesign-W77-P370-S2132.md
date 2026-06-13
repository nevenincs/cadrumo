---
tags:
  - '#exec'
  - '#cli-workflow-redesign'
date: '2026-06-12'
modified: '2026-06-12'
step_id: 'S2132'
related:
  - '[[2026-05-13-cli-workflow-redesign-epic-plan]]'
  - '[[2026-05-12-cli-workflow-redesign-bucket-adr]]'
---

# W77.P370.S2132 - bucket-maintenance command and result contracts

## Scope

- `src/aeat/application/bucket_maintenance/_contracts.py`
- `src/aeat/application/bucket_maintenance/_service.py`
- `src/aeat/application/bucket_maintenance/tests/test_service_delete.py`
- `src/aeat/application/bucket_maintenance/tests/test_service_import_export.py`

## Description

- Verified strict Pydantic command/result contracts for browse, delete, export, import, rename, and namespace inventory rows.
- Verified destructive bucket delete is refused at the service boundary unless `DeleteBucketCommand.confirmed` is true.
- Verified import collision protection is enforced unless `ImportBucketCommand.force_replace` is true.
- Verified recovery archives require `ImportBucketCommand.recovery_wrap_passphrase`.

## Outcome

S2132 is complete. The service boundary carries the explicit yes/confirmed safeguards and typed command/result contracts; no CLI-only flag handling is the sole enforcement point.

## Checks

- `uv run --no-sync pytest src/aeat/application/bucket_maintenance/tests src/aeat/adapters/persistence/storage/bucket/tests -m "unit or integration" -q --basetemp Y:/tmp/pytest-w77-bucket-maintenance-full-2`
- `uv run --no-sync ruff check src/aeat/application/bucket_maintenance src/aeat/adapters/persistence/storage/bucket`
