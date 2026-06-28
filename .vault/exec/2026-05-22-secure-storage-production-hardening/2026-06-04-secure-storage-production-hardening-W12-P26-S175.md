---
tags:
  - '#exec'
  - '#secure-storage-production-hardening'
date: '2026-06-04'
modified: '2026-06-04'
step_id: 'S175'
related:
  - '[[2026-05-22-secure-storage-production-hardening-refactor-plan]]'
  - '[[2026-06-04-secure-storage-production-hardening-w12-p26-s175-review-audit]]'
---

# `secure-storage-production-hardening` `W12.P26.S175`

Closed `AFR-073` for idle-timeout evaluation.

## Description

- Reviewed `src/aeat/adapters/persistence/storage/master_key/_idle_timeout.py` against the `manifest-bucket` and `master-key` scanner signals.
- Removed import-time `Settings` construction from the default idle-lock constant.
- Localized non-positive configured idle-window failures with the shared storage validation translated message key.
- Added real-behavior tests for translated validation failures and absence of direct `Settings(...)` construction.
- Routed the test module's source read through the centralized `UTF_8_ENCODING` constant.
- Validated evaluator behavior remains pure and does not mutate `BucketSession`.

## Outcome

`AFR-073` is closed as a `bootstrap-custody` idle-timeout implementation row.

Validation passed:

- `uv run --no-sync pytest -q src/aeat/adapters/persistence/storage/master_key/test_idle_timeout.py src/aeat/adapters/persistence/storage/master_key/test_bucket_session.py src/aeat/adapters/persistence/storage/test_runtime.py`
- `uv run --no-sync ruff check src/aeat/adapters/persistence/storage/master_key/_idle_timeout.py src/aeat/adapters/persistence/storage/master_key/test_idle_timeout.py src/aeat/adapters/persistence/storage/master_key/test_bucket_session.py src/aeat/adapters/persistence/storage/test_runtime.py`
- `uv run --no-sync -q python -m aeat.locales audit`
- Touched-surface hygiene scan found no broad exception suppressions, direct settings construction, naked environment access, fake/stub/monkeypatch markers, skipped/xfail tests, or direct output.

## Notes

Runtime callers still pass configured idle windows from manifest/settings-owned paths. This row only removes the import-time settings read and hardens validation diagnostics.
