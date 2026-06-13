---
tags:
  - '#exec'
  - '#secure-storage-production-hardening'
date: '2026-06-04'
modified: '2026-06-04'
step_id: 'S192'
related:
  - '[[2026-05-22-secure-storage-production-hardening-refactor-plan]]'
  - '[[2026-06-04-secure-storage-production-hardening-w12-p26-s192-review-audit]]'
---

# `secure-storage-production-hardening` `W12.P26.S192`

Closed `AFR-090` for the Renta ledger aggregation repository-boundary module.

## Description

- Reviewed `src/aeat/application/aggregation/_renta_ledger.py` against the
  `manifest-discovery` manifest-bucket classification and the export ADR
  direction that ledger-derived filing data must remain bucket-scoped and
  evidence-ready.
- Bound the default invoice repository to the requested Renta ledger
  `bucket_id`.
- Added fail-closed validation for injected invoice repositories whose
  `bucket_id` is missing or differs from the requested bucket.
- Added the locale key
  `aggregation.renta_ledger.errors.invoice_bucket_mismatch` through
  `python -m aeat.locales set` for `ca`, `en`, `es`, and `hu`.
- Added real secure-storage regression coverage for default invoice repository
  binding, invoice bucket mismatch, and unbound invoice repository refusal.

## Outcome

`AFR-090` is closed as a bucket-scoping hardening slice. Repository-backed Renta
expense aggregation now reads both transaction and invoice catalogues from the
requested bucket unless explicit, matching scoped repositories are supplied.

Validation passed:

- `uv run --no-sync ruff check src/aeat/application/aggregation/_renta_ledger.py src/aeat/application/aggregation/test_renta_ledger.py`
- `uv run --no-sync pytest -q src/aeat/application/aggregation/test_renta_ledger.py`
- `$env:PYTHONPATH='src'; uv run --no-sync -q python -m aeat.locales audit`

Reviewer pass:

- Initial review found an unbound injected invoice repository bypass and a
  misleading transaction-repository locale key reuse.
- Re-review after fixes reported no findings and no remaining critical or high
  issues.

## Notes

No pragma/noqa suppressions, monkeypatches, fakes, or naked environment access
were added.
