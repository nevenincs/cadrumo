---
tags:
  - '#exec'
  - '#secure-storage-production-hardening'
date: '2026-06-04'
modified: '2026-06-04'
step_id: 'S203'
related:
  - '[[2026-05-22-secure-storage-production-hardening-refactor-plan]]'
  - '[[2026-06-04-secure-storage-production-hardening-w12-p26-s203-review-audit]]'
---

# `secure-storage-production-hardening` `W12.P26.S203`

Closed `AFR-101` for application diagnostics.

## Description

- Reviewed `src/aeat/application/diagnostics.py` against the `runtime-default`
  classification for secure-object, active-profile, manifest-bucket, master-key,
  SQL route, and plain-file signals.
- Added real-behavior tests for diagnostics secure-object aggregate degradation
  when the active bucket session is missing.
- Added real-behavior tests for diagnostics secure-object aggregate degradation
  when the active storage session belongs to a different bucket.
- Verified both degradation paths emit debug logs for the storage runtime
  failure, including route-specific details, instead of silently swallowing it.
- Added explicit migrated-runtime diagnostics degradation cases beside the
  runtime refusal matrix for missing-session and route-mismatch routes.
- Preserved the prior S203 review finding that diagnostics profile identifiers
  are redacted through the shared CLI placeholder and that plain-file exposure is
  limited to diagnostic log path reporting.

## Outcome

`AFR-101` is closed. Diagnostics secure-object aggregate reads remain
runtime-bound and now have explicit coverage for logged degradation under missing
or mismatched active bucket storage. Existing quarantine preview/mutation tests
continue to cover the bootstrap-exempt repair-session behavior.

Validation passed:

- `uv run --no-sync ruff check src/aeat/application/diagnostics.py src/aeat/application/test_diagnostics.py src/aeat/adapters/persistence/storage/test_runtime_migrated_repositories.py`
- `uv run --no-sync pytest src/aeat/application/test_diagnostics.py -k "secure_object_unreadable_total or quarantine" -q`
- `uv run --no-sync pytest src/aeat/adapters/persistence/storage/test_runtime_migrated_repositories.py -k "diagnostic or auth_diagnostics or s85_runtime" -q`
- `$env:PYTHONPATH='src'; uv run --no-sync -q pytest -q src/aeat/application/test_diagnostics.py src/aeat/adapters/persistence/storage/test_runtime_migrated_repositories.py -k "auth_diagnostics or secure_objects or diagnostics or migrated_runtime_defaults_refuse"` (prior committed S203 validation)
- `$env:PYTHONPATH='src'; uv run --no-sync -q python -m aeat.locales audit`

## Notes

No production files were changed for S203. No direct secure-object repository
construction, naked environment access, unlogged exception swallowing, raw
user-facing strings, `noqa`, `pragma`, monkeypatches, fakes, mocks, skips, or
xfails were introduced.
