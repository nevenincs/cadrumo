---
tags:
  - '#exec'
  - '#secure-storage-production-hardening'
date: '2026-06-03'
step_id: 'S154'
related:
  - '[[2026-05-22-secure-storage-production-hardening-refactor-plan]]'
  - '[[2026-06-03-secure-storage-production-hardening-W12-P26-S154-review]]'
---

# `secure-storage-production-hardening` `W12.P26.S154`

Closed `AFR-052` for the blob-store secret materialisation helpers.

## Description

- Reviewed `src/aeat/adapters/persistence/storage/blob_store/_materialisation.py` against the `master-key` and `plain-file` scanner signals.
- Classified the temp-file materialisation as an explicit plaintext bridge for path-only third-party consumers.
- Verified secret bytes originate from `SecretStore` and the encrypted blob substrate, not from a separate plaintext persistence backend.
- Verified the singleton factory uses centralized settings via `load_settings()` or a caller-supplied settings object and does not read environment variables directly.
- Verified the narrow `FileNotFoundError` suppressions only make cleanup idempotent after `mkstemp` materialisation.
- Closed `W12.P26.S154` through `vaultspec-core vault plan step check`.

## Outcome

`AFR-052` is closed as `plaintext-exception`.

Validation passed:

- `uv run --no-sync pytest -q src/aeat/adapters/persistence/storage/blob_store/test_materialisation.py`
- `uv run --no-sync ruff check src/aeat/adapters/persistence/storage/blob_store/_materialisation.py src/aeat/adapters/persistence/storage/blob_store/test_materialisation.py`
- Case-sensitive touched-file hygiene scan found no broad exception catches, fake/stub/monkeypatch markers, skipped/xfail tests, direct output, raw UTF-8 literals, local secure-object marker construction, direct settings construction, or direct environment access.
- Suppression scan found only `FileNotFoundError` cleanup suppressions after `mkstemp` materialisation paths.

## Notes

No source edit was required. Plaintext exists only for the lifetime requested by the caller and is removed by context exit or the returned cleanup callback.

The 2026-06-03 export/parity ADRs were re-read during closure. They do not change this storage classification: temp-file materialisation remains an interop bridge only. Future modelo export work must still derive export content from the encrypted `CalculationRevision`/evidence envelope, keep offline and Sheets materialisers on one typed plan, refuse ledger-derived exports without bundled or resolvable evidence, and avoid using this bridge as a separate export authority.
