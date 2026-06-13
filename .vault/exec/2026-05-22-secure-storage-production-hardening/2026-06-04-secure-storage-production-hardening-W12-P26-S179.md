---
tags:
  - '#exec'
  - '#secure-storage-production-hardening'
date: '2026-06-04'
modified: '2026-06-04'
step_id: 'S179'
related:
  - '[[2026-05-22-secure-storage-production-hardening-refactor-plan]]'
  - '[[2026-06-04-secure-storage-production-hardening-w12-p26-s179-review-audit]]'
---

# `secure-storage-production-hardening` `W12.P26.S179`

Closed `AFR-077` for the typed recovery facade.

## Description

- Reviewed `src/aeat/adapters/persistence/storage/master_key/_recovery_facade.py` against the `manifest-bucket`, `master-key`, and `plain-file` scanner signals.
- Wrapped recovery-envelope base64 and strict blob validation failures as `RecoveryVerificationError`.
- Reclassified lower-level storage validation during recovery unwrap as recovery verification failure.
- Added real facade coverage for a strict `RecoveryRecord` whose base64 decodes but fails encrypted-blob shape validation.
- Asserted the typed recovery error envelope does not echo malformed envelope payloads.

## Outcome

`AFR-077` is closed as a `bootstrap-custody` recovery-facade implementation row.

Validation passed:

- `uv run --no-sync pytest -q src/aeat/adapters/persistence/storage/master_key/test_recovery_facade.py src/aeat/adapters/persistence/storage/master_key/test_recovery.py`
- `uv run --no-sync ruff check src/aeat/adapters/persistence/storage/master_key/_recovery_facade.py src/aeat/adapters/persistence/storage/master_key/test_recovery_facade.py src/aeat/adapters/persistence/storage/master_key/test_recovery.py`
- `uv run --no-sync -q python -m aeat.locales audit`
- Touched-surface hygiene scan found no broad exception suppressions, pragma/noqa/type-ignore suppressions, direct settings construction, naked environment access, fake/stub/monkeypatch markers, skipped/xfail tests, direct output, or naked encoding literals.

## Notes

The facade remains a typed composition layer over `_recovery.py` and `BucketSession.open`; it does not persist mnemonics or recovery bytes, and it preserves the same HKDF/AAD contract.
