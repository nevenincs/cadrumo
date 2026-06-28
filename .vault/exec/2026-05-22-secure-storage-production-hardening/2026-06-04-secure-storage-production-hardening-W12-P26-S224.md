---
tags:
  - '#exec'
  - '#secure-storage-production-hardening'
date: '2026-06-04'
modified: '2026-06-04'
step_id: 'S224'
related:
  - '[[2026-05-22-secure-storage-production-hardening-refactor-plan]]'
  - '[[2026-06-04-secure-storage-production-hardening-w12-p26-s224-review-audit]]'
---

# `secure-storage-production-hardening` `W12.P26.S224`

Closed `AFR-122` for ledger usage-ratio application commands.

## Description

- Reviewed `src/aeat/application/ledger/_ratios.py` against the usage-ratio
  secure-object runtime contract.
- Reclassified the row from `manifest-discovery` to `runtime-default` because
  the application commands load and save the bucket usage-ratio profile through
  `load_usage_ratios` and `save_usage_ratios`, whose default path resolves a
  runtime-owned secure-object repository for the requested bucket.
- Added real runtime facade tests proving the application wrappers round-trip
  through the active runtime bucket and fail closed for an inactive bucket route.
- Closed `S224` through `vaultspec-core vault plan step check` and aligned
  `AFR-122` to closed.

## Outcome

`AFR-122` is closed as `runtime-default`. The implementation already delegated
storage to the secure-object domain service; the added application tests lock
the public facade against future plain-file or ambient-route regressions.

Validation passed:

- `uv run --no-sync ruff check src/aeat/application/ledger/_ratios.py src/aeat/application/ledger/test_ratios.py`
- `uv run --no-sync pytest -q src/aeat/application/ledger/test_ratios.py`
- `$env:PYTHONPATH='src'; uv run --no-sync -q python -m aeat.locales audit`
- `uv run --no-sync vaultspec-core vault plan check .vault/plan/2026-05-22-secure-storage-production-hardening-refactor-plan.md` returned only the existing monotonic-order warning.

## Notes

No direct production `SecureObjectRepository` construction, naked environment
access, settings bypass, silent exception swallowing, `noqa`, `pragma`,
monkeypatch, fake, mock, skip, xfail, or tautological test was introduced.
