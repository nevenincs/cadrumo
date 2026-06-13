---
tags:
  - '#audit'
  - '#secure-storage-production-hardening'
date: '2026-06-04'
modified: '2026-06-04'
related:
  - '[[2026-05-22-secure-storage-production-hardening-refactor-plan]]'
  - '[[2026-06-04-secure-storage-production-hardening-W12-P26-S175]]'
---

# `secure-storage-production-hardening` `W12.P26.S175` Review

## S175-001 | PASS | Idle timeout no longer constructs settings at import

`_idle_timeout.py` no longer imports or constructs `Settings` at module import time to resolve `DEFAULT_IDLE_LOCK_MINUTES`. The module keeps the documented default value as a constant and leaves runtime configured idle windows to callers that already pass manifest/settings-derived values into `evaluate_idle`.

## S175-002 | PASS | Validation failures use AEAT storage errors

`evaluate_idle` continues to be a pure evaluator over a `BucketSession`, a timestamp, and a configured idle window. Non-positive `configured_minutes` now raises `StorageValidationError` with the shared `errors.integrity.integrity_storage_validation` translated message key.

## S175-003 | PASS | Tests cover real evaluator behavior

The focused tests exercise the default constant, not-expired and expired outcomes, exact-deadline expiry, sealed-session expiry, touch-driven deadline movement, translated validation failures, evaluator purity, strict pydantic record validation, and absence of direct `Settings(...)` construction. They do not use fake/stub classes, mocks, monkeypatching, skip, or xfail shortcuts.

The source-read assertion imports the centralized `UTF_8_ENCODING` constant instead of carrying a local encoding literal.

Validation:

- `uv run --no-sync pytest -q src/aeat/adapters/persistence/storage/master_key/test_idle_timeout.py src/aeat/adapters/persistence/storage/master_key/test_bucket_session.py src/aeat/adapters/persistence/storage/test_runtime.py` passed with 53 tests.
- `uv run --no-sync ruff check src/aeat/adapters/persistence/storage/master_key/_idle_timeout.py src/aeat/adapters/persistence/storage/master_key/test_idle_timeout.py src/aeat/adapters/persistence/storage/master_key/test_bucket_session.py src/aeat/adapters/persistence/storage/test_runtime.py` passed.
- `uv run --no-sync -q python -m aeat.locales audit` passed for `ca.yml`, `en.yml`, `es.yml`, and `hu.yml`.
- Touched-surface hygiene scan found no broad exception suppressions, direct settings construction, naked environment access, fake/stub/monkeypatch markers, skipped/xfail tests, or direct output.

Review-agent note: spawning `vaultspec-code-reviewer` failed with `agent thread limit reached`, so the supervisor completed the same checklist locally.

Disposition: close `AFR-073` as `bootstrap-custody`.
