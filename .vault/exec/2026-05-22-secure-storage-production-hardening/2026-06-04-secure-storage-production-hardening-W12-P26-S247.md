---
tags:
  - '#exec'
  - '#secure-storage-production-hardening'
date: '2026-06-04'
modified: '2026-06-04'
step_id: 'S247'
related:
  - '[[2026-05-22-secure-storage-production-hardening-refactor-plan]]'
  - '[[2026-06-04-secure-storage-production-hardening-w12-p26-s247-review-audit]]'
---

# `secure-storage-production-hardening` `W12.P26.S247`

Closed `AFR-145` for the repair-integrity application service.

## Description

- Reviewed `src/aeat/application/repair_integrity.py` as a runtime-default secure-object integrity and repair-remediation boundary.
- Verified repair decisions persist through the active bucket secure-object repository under the registered repair decision namespace.
- Verified repair reports expose key digests and metadata only, not plaintext secure-object payloads.
- Removed the namespace-listing exception swallow that could report an empty clean integrity result after a repository/storage failure.
- Added a regression test proving namespace enumeration failures are not converted into false-ok integrity reports.
- Added real repository tests for localized repair decision and repair-list refusal paths.
- Converted repair-list and repair-remediation refusal errors to structured localized messages with explicit context.
- Reconciled additional modelo CLI locale keys exposed by the canonical `aeat.locales` audit.
- Closed `S247` through `vaultspec-core vault plan step check`.

## Outcome

`AFR-145` is closed as `runtime-default` with `secure-object, secure-bound, active-profile, manifest-bucket, master-key` signals. The repair-integrity surface now fails closed when namespace enumeration fails instead of silently downgrading to an empty report.

Validation passed:

- `uv run --no-sync ruff check src/aeat/application/repair_integrity.py src/aeat/application/test_repair_integrity.py`
- `uv run --no-sync pytest -q src/aeat/application/test_repair_integrity.py`
- `$env:PYTHONPATH='src'; uv run --no-sync -q python -m aeat.locales audit`

## Notes

No deprecated config-init surface was introduced. The focused repair-integrity suite passed with 13 real-behavior tests. The remaining active-bucket session fallback logs at debug level and intentionally yields so diagnostics can still report bootstrap/readiness failures from the secure-object probes.
