---
tags:
  - '#exec'
  - '#secure-storage-production-hardening'
date: '2026-06-04'
modified: '2026-06-04'
step_id: 'S244'
related:
  - '[[2026-05-22-secure-storage-production-hardening-refactor-plan]]'
  - '[[2026-06-04-secure-storage-production-hardening-w12-p26-s244-review-audit]]'
---

# W12.P26.S244 Overview Runtime Storage Disposition

Scope: close `AFR-142` for `src/aeat/application/overview/__init__.py`; supporting hardening touched `src/aeat/core/decimal/_coerce.py`.

## Description

- Reclassified `AFR-142` from stale `remote-mirror` ownership to `runtime-default`.
- Verified overview status delegates persisted state reads to the canonical runtime-backed `OperatorStateProjection`.
- Verified calendar assembly remains local and pure over supplied profile/deadline inputs.
- Added debug diagnostics for narrow graceful-degradation paths in calendar and filing-obligation advisory handling.
- Removed the unused package-level `render_overview_status_lines` export.
- Fixed the central decimal coercion helper so malformed values are logged by type/default/error metadata, not by raw value.
- Added real behavior tests for overview debug diagnostics and central decimal redaction.
- Closed `S244` through `vaultspec-core vault plan step check`.

## Outcome

`AFR-142` is closed as `runtime-default`. Overview does not contact AEAT or create a remote mirror; when status needs persisted state, it routes through the already-enrolled runtime projection and secure-object repositories. Graceful degradation paths are now observable at debug level without leaking malformed profile values.

Validation passed:

- `uv run --no-sync ruff check src/aeat/core/decimal/_coerce.py src/aeat/core/decimal/test_coerce.py src/aeat/application/overview/__init__.py src/aeat/application/overview/test_calendar.py src/aeat/entrypoints/cli/test_overview_rendering.py src/aeat/entrypoints/cli/test_overview_verbs.py`
- `uv run --no-sync pytest -q src/aeat/core/decimal/test_coerce.py src/aeat/application/overview/test_calendar.py src/aeat/entrypoints/cli/test_overview_rendering.py src/aeat/entrypoints/cli/test_overview_verbs.py`
- `$env:PYTHONPATH='src'; uv run --no-sync -q python -m aeat.locales audit`

## Notes

The central decimal logging fix is recorded here because S244 exposed the privacy issue while hardening overview advisory parsing. It is intentionally centralized rather than bypassed locally.
