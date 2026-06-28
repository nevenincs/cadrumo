---
tags:
  - '#exec'
  - '#live-iva-compensation-wallet'
date: '2026-05-26'
modified: '2026-05-26'
step_id: 'S01'
related:
  - '[[2026-05-19-live-iva-compensation-wallet-plan]]'
---



# `live-iva-compensation-wallet` `W10.P01.S01`

Added the first convention-regrounding implementation slice for SecureStorage
exceptions and user-facing localisation.

- Modified: `src/aeat/adapters/persistence/storage/errors.py`
- Modified: `src/aeat/adapters/persistence/storage/__init__.py`
- Modified: `src/aeat/adapters/persistence/storage/bucket/_errors.py`
- Modified: `src/aeat/adapters/persistence/storage/bucket/test_bucket_errors.py`
- Modified: `src/aeat/core/errors/registry/_adapters.py`
- Modified: `src/aeat/locales/en.yml`
- Modified: `src/aeat/locales/es.yml`
- Modified: `src/aeat/locales/ca.yml`
- Modified: `src/aeat/locales/hu.yml`
- Created: `src/aeat/adapters/persistence/storage/test_errors.py`
- Modified: `.vault/plan/2026-05-19-live-iva-compensation-wallet-plan.md`

## Description

The storage exception hierarchy now has a named `SecureStorageError` base that
derives from the central `AeatError` registry pattern. `StorageError` and the
per-bucket lifecycle base inherit through this new base, so encrypted
persistence, secret-store, bucket-session, and bucket lifecycle failures can be
caught as one governed SecureStorage family without bypassing the central
registry.

Representative SecureStorage and bucket errors were changed to render through
registry locale keys rather than raw positional detail strings. Raw recovery or
legacy details remain internal attributes where useful, but they no longer
override the operator-facing locale message. The registry gained a
`FAIL_SECURE_STORAGE` code, and all locale files gained the corresponding
translation plus the missing repair-plan help text exposed by locale parity.

The wallet plan gained Wave W10 for the broader codebase convention
regrounding work requested by the operator: localised user-facing errors,
central exception inheritance, exception swallowing diagnostics, centralized
settings/env handling, shared model/enum reuse, and non-tautological tests.

The official plan-step CLI could not close `W10.P01.S01`; it returned `Step
'W10.P01.S01' does not exist in this plan`. The row is checked in the plan
because this plan currently has known L3 display-path parsing issues tracked in
the vault gate results.

## Tests

Passed:

- `uv run pytest src/aeat/adapters/persistence/storage/test_errors.py src/aeat/adapters/persistence/storage/bucket/test_bucket_errors.py src/aeat/core/errors/test_registry_enforcement.py src/aeat/locales/test_parity.py src/aeat/locales/test_locale_translation_honesty.py -q --disable-warnings`
- `uv run ruff check src/aeat/adapters/persistence/storage/errors.py src/aeat/adapters/persistence/storage/__init__.py src/aeat/adapters/persistence/storage/bucket/_errors.py src/aeat/adapters/persistence/storage/bucket/test_bucket_errors.py src/aeat/adapters/persistence/storage/test_errors.py src/aeat/core/errors/registry/_adapters.py`
