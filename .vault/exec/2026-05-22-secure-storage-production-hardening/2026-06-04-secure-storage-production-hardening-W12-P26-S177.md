---
tags:
  - '#exec'
  - '#secure-storage-production-hardening'
date: '2026-06-04'
modified: '2026-06-04'
step_id: 'S177'
related:
  - '[[2026-05-22-secure-storage-production-hardening-refactor-plan]]'
  - '[[2026-06-04-secure-storage-production-hardening-w12-p26-s177-review-audit]]'
---

# `secure-storage-production-hardening` `W12.P26.S177`

Closed `AFR-075` for the file/keyring master-key provider boundary.

## Description

- Reviewed `src/aeat/adapters/persistence/storage/master_key/_master_key.py` against the `secure-object`, `active-profile`, `manifest-bucket`, `master-key`, `sql-route`, and `plain-file` scanner signals.
- Added localized helper constructors for master-key unavailable and passphrase-mismatch failures.
- Removed local path details from malformed KDF, wrapped master-key, bucket-DEK document, bucket-DEK authentication, and passphrase mismatch error messages.
- Routed bucket-DEK authentication failures through storage `DecryptionError` instead of cryptography internals.
- Logged atomic-write tempfile cleanup failures instead of suppressing them silently.
- Narrowed the unsecured-profile decrypt proof catch and updated tests to avoid monkeypatch parameters and local encoding literals.
- Added real persisted-artefact tests for tampered bucket DEK, tampered master key, malformed KDF JSON, translated message keys, and no path leakage in error envelopes.

## Outcome

`AFR-075` is closed as a `bootstrap-custody` master-key provider implementation row.

Validation passed:

- `uv run --no-sync pytest -q src/aeat/adapters/persistence/storage/master_key/test_master_key.py`
- `uv run --no-sync ruff check src/aeat/adapters/persistence/storage/master_key/_master_key.py src/aeat/adapters/persistence/storage/master_key/test_master_key.py`
- `uv run --no-sync -q python -m aeat.locales audit`
- Touched-surface hygiene scan found only intentional existing patterns documented in the review record.

## Notes

The accepted export evidence and workbook parity ADRs reinforce that encrypted revision storage must remain custody-preserving: this row keeps master-key and bucket-DEK failures typed, localized, and non-leaky while preserving the secure-object boundary that evidence-bearing exports depend on.
