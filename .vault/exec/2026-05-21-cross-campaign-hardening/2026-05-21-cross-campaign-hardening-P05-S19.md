---
tags: ["#exec", "#cross-campaign-hardening"]
date: '2026-05-21'
modified: '2026-05-21'
step_id: 'P05.S19'
related:
  - '[[2026-05-21-cross-campaign-hardening-plan]]'
  - '[[2026-05-21-cross-campaign-hardening-audit]]'
---

# `cross-campaign-hardening` `P05.S19`

Closed PERS-4: decrypted secure-object records now expose
`object_key` as a string, matching `SecureObjectWrite.object_key`.

- Modified: `src/aeat/adapters/persistence/storage/sql/secure_objects.py`
- Modified: `src/aeat/adapters/persistence/storage/sql/test_secure_objects.py`
- Modified: `.vault/plan/2026-05-21-cross-campaign-hardening-plan.md`

## Description

Changed `SecureObjectRecord.object_key` and
`SecureObjectUnreadable.object_key` from raw bytes to strings. Direct
`load()` calls preserve the natural object key supplied by the caller;
namespace iteration still cannot recover natural keys from the HMAC
lookup column, so it reports the digest as a hex string. Raw archive
surfaces continue to expose `SecureObjectRawRow.object_key` as bytes
because that path mirrors the storage row.

Updated the strict secure-object record roundtrip to assert the loaded
record carries the natural object key, while separately proving SQLite
stores only a non-reversible 32-byte HMAC digest and not the natural
key.

No fakes, mocks, monkeypatches, skipped tests, or copied business logic
were introduced.

## Tests

`uv run ruff check src/aeat/adapters/persistence/storage/sql/secure_objects.py src/aeat/adapters/persistence/storage/sql/test_secure_objects.py` passed.

`uv run pytest -q src/aeat/adapters/persistence/storage/sql/test_secure_objects.py` passed with 13 tests in 2.60s.

`uv run pytest -q src/aeat/adapters/persistence/storage/sql/test_archive_bundle_roundtrip.py` passed with 1 test in 1.13s.

`uv run vaultspec-core vault plan step check .vault/plan/2026-05-21-cross-campaign-hardening-plan.md S19` closed the row.

`uv run vaultspec-core vault plan check .vault/plan/2026-05-21-cross-campaign-hardening-plan.md` passed.

The first locale gate run found two missing repair-profile keys in all locales. Per the locale-work constraint, this was repaired with `uv run python -m aeat.locales scaffold`.

`uv run python -m aeat.locales audit` then passed for `ca.yml`, `en.yml`, `es.yml`, and `hu.yml`.

`uv run python -m aeat.locales scaffold --check` then passed for `ca.yml`, `en.yml`, `es.yml`, and `hu.yml`.

`git diff --check -- .vault/plan/2026-05-21-cross-campaign-hardening-plan.md .vault/exec/2026-05-21-cross-campaign-hardening/2026-05-21-cross-campaign-hardening-P05-S19.md src/aeat/adapters/persistence/storage/sql/secure_objects.py src/aeat/adapters/persistence/storage/sql/test_secure_objects.py src/aeat/locales/ca.yml src/aeat/locales/en.yml src/aeat/locales/es.yml src/aeat/locales/hu.yml` passed with only existing CRLF normalization warnings.
