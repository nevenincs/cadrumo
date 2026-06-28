---
tags:
  - '#exec'
  - '#secure-storage-production-hardening'
date: '2026-06-03'
modified: '2026-06-03'
step_id: 'S141'
related:
  - '[[2026-05-22-secure-storage-production-hardening-refactor-plan]]'
  - '[[2026-06-03-secure-storage-production-hardening-w12-p26-s141-review-audit]]'
---

# `secure-storage-production-hardening` `W12.P26.S141`

Closed `AFR-039` for the outbound storage error hierarchy.

## Description

- Reviewed `src/aeat/adapters/outbound/storage/_errors.py` against the `remote-provider` scanner signal and the project exception-hierarchy mandate.
- Confirmed outbound provider and remote-mirror failures derive from `AeatError` through `OutboundStorageError`.
- Confirmed `StorageCorruptionError` derives from `CoreError` by design because sidecar schema corruption is not a remote-provider transport, quota, permission, or mirror failure.
- Repaired the module docstring so it no longer overclaims that every backend failure is an `OutboundStorageError`.
- Added real hierarchy coverage proving outbound leaves remain under `OutboundStorageError` and `AeatError`, while `StorageCorruptionError` remains a `CoreError` outside the outbound provider hierarchy.
- Closed `W12.P26.S141` through `vaultspec-core vault plan step check` and aligned the AFR register row to `closed`.

## Outcome

`AFR-039` is closed as `remote-mirror`.

Validation passed:

- `uv run --no-sync pytest -q src/aeat/adapters/outbound/storage/test_foundation.py src/aeat/adapters/outbound/storage/test_local.py -k "storage_error_hierarchy_unified or every_leaf_carries or corruption"`
- `uv run --no-sync ruff check src/aeat/adapters/outbound/storage/_errors.py src/aeat/adapters/outbound/storage/test_foundation.py`
- `rg -n "Settings\(|PROJECT_ROOT|os\.environ|print\(|typer\.echo|# noqa|pragma|type: ignore|except Exception|except BaseException" src/aeat/adapters/outbound/storage/_errors.py src/aeat/adapters/outbound/storage/test_foundation.py`

## Notes

The source scan intentionally returned no matches for direct settings construction, project-root constants, direct environment access, print/echo output, suppression pragmas, or broad exception catches in the S141 slice.

The CLI-facing message localization surface is registry-backed for this hierarchy; no new locale key was added in this step.
