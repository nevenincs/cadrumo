---
tags:
  - '#exec'
  - '#secure-storage-production-hardening'
date: '2026-06-04'
modified: '2026-06-04'
step_id: 'S231'
related:
  - '[[2026-05-22-secure-storage-production-hardening-refactor-plan]]'
  - '[[2026-06-04-secure-storage-production-hardening-w12-p26-s231-review-audit]]'
---

# `secure-storage-production-hardening` `W12.P26.S231`

Closed `AFR-129` for the live verify observation service.

## Description

- Reviewed `src/aeat/application/live/_verify.py` against the live
  remote-mirror and secure-object contracts.
- Reclassified the affected-file row from stale `manifest-discovery` /
  `plain-file` metadata to `remote-mirror` with secure-object,
  manifest-bucket, and remote-provider signals.
- Localized blank bucket id, blank observation id, not-found,
  ambiguous-prefix, bucket-mismatch, and observation-id-mismatch refusal paths.
- Hardened lookup refusals so bucket ids and matched full observation ids are
  not embedded in the primary error message.
- Changed `VerifyObservationRepository.list_observations()` to fail closed on
  decrypted payload bucket contamination instead of silently filtering the row.
- Updated real-runtime tests to assert secure-object persistence, raw SQLite
  non-leakage for the NIF witness, legacy JSONL absence, locale metadata,
  bounded error context, and contaminated-row refusal.
- Closed `S231` through `vaultspec-core vault plan step check`.

## Outcome

`AFR-129` is closed as `remote-mirror`. Live verify durable state remains an
encrypted bucket-local audit mirror of authenticated AEAT read checks, and the
reviewed error boundaries now follow the locale-backed no-leak convention.

Validation passed:

- `uv run --no-sync ruff check src/aeat/application/live/_verify.py src/aeat/application/live/test_verify.py`
- `uv run --no-sync pytest -q src/aeat/application/live/test_verify.py`
- `uv run --no-sync pytest -q src/aeat/adapters/persistence/storage/test_runtime_migrated_repositories.py -k "verify or s85_runtime"`
- `$env:PYTHONPATH='src'; uv run --no-sync -q python -m aeat.locales audit`
- `uv run --no-sync vaultspec-core vault plan check .vault/plan/2026-05-22-secure-storage-production-hardening-refactor-plan.md`

## Notes

Locale catalogue updates were performed through `python -m aeat.locales`
(`scaffold`, `set`, and `audit`). No naked environment access, settings
bypass, silent exception swallowing, `noqa`, `pragma`, monkeypatch, fake,
mock, skip, xfail, or tautological test was introduced.
