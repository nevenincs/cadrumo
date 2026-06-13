---
tags:
  - '#audit'
  - '#secure-storage-production-hardening'
date: '2026-05-26'
modified: '2026-05-26'
related:
  - '[[2026-05-22-secure-storage-production-hardening-refactor-plan]]'
  - '[[2026-05-22-secure-storage-production-hardening-architecture-research]]'
---



# `secure-storage-production-hardening` audit: `tr-backed storage messages`

## Scope

Audited secure-storage and adjacent operator paths for user-facing messages that should resolve through `tr()` and locale catalog keys instead of raw exception text.

## Existing Convention

The central error renderer in `src/aeat/core/errors/_registry.py` resolves `translated_message` through `tr(...)`, otherwise falls back to the registered error-code `message_key`. This is the project convention for user-facing `AeatError` output.

Bucket lifecycle errors in `src/aeat/adapters/persistence/storage/bucket/_errors.py` already follow the convention by setting `translated_message` keys such as `errors.refused.refused_storage_bucket_no_active` and `errors.locked.locked_storage_bucket_session`.

`SecureObjectUnreadableError` in `src/aeat/adapters/persistence/storage/errors.py` now uses `translated_message="errors.integrity.integrity_storage_secure_object_unreadable"` and structured context, so it is aligned with the convention.

## Findings

- High: secure-storage exceptions that pass a literal `message` bypass locale rendering. `resolve_error_message()` returns `error.args[0]` before using the registry `message_key`, so raise sites such as `StorageValidationError("...")`, `StorageError("...")`, `RepositoryError("...")`, `KeyringUnavailableError(f"...")`, and `MasterKeyUnavailableError("...")` can surface untranslated text to operators.
- High: runtime-readiness errors added in `src/aeat/adapters/persistence/storage/runtime.py` currently build literal remediation text, including `aeat config profile switch NAME`, inside `StorageValidationError` messages. These should become locale-backed messages with structured readiness context.
- Medium: `src/aeat/adapters/persistence/storage/master_key/_active_session.py` raises `NoActiveBucketSessionError` with literal operator guidance. This should use the registered storage no-active-session locale key or a dedicated translated message key.
- Medium: `src/aeat/adapters/persistence/storage/sql/engine.py` raises raw `StorageError` messages for empty database URLs and engine creation failures. The empty-url wording references direct environment mutation and should be replaced by settings-route language.
- Medium: multiple storage internals raise literal validation messages for programmer/data invariants. Some are acceptable internal diagnostics, but the audit cannot currently distinguish internal-only from operator-facing surfaces; W11 should either convert operator-facing branches or document why an internal invariant may remain raw.

## Disposition

- `W11.P18.S71` owns conversion of user-facing secure-storage messages to `tr()`/locale-backed keys and must validate with `uv run python -m aeat.locales audit`.
- `W11.P18.S72` owns any exception-constructor changes needed to preserve AEAT registry semantics while avoiding raw message overrides.
- `W11.P18.S73` owns logging or typed degradation for branches where low-level failures are intentionally hidden from the operator.
- `W11.P19.S74` owns the storage-route wording cleanup where messages currently instruct direct environment variable mutation instead of centralized `Settings` configuration.

## Validation

`uv run python -m aeat.locales audit` reported `ok` for `ca.yml`, `en.yml`, `es.yml`, and `hu.yml` before this audit step.
