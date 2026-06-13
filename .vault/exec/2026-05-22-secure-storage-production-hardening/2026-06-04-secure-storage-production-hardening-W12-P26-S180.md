---
tags:
  - '#exec'
  - '#secure-storage-production-hardening'
date: '2026-06-04'
modified: '2026-06-04'
step_id: 'S180'
related:
  - '[[2026-05-22-secure-storage-production-hardening-refactor-plan]]'
  - '[[2026-06-04-secure-storage-production-hardening-w12-p26-s180-review-audit]]'
---

# `secure-storage-production-hardening` `W12.P26.S180`

Closed stale duplicate `AFR-078` for the master-key ClassVar guard.

## Description

- Reviewed `src/aeat/adapters/persistence/storage/master_key/test_no_classvar_state.py` against the `master-key` and `plain-file` scanner signals.
- Confirmed it duplicated the canonical consolidated guard in `src/aeat/adapters/persistence/storage/master_key/test_master_key_no_classvars.py`.
- Removed the duplicate guard rather than keeping two overlapping AST tests for the same invariant.
- Reclassified `AFR-078` as `retired` in the affected-file ledger and closed `W12.P26.S180`.

## Outcome

`AFR-078` is closed as a retired duplicate. The master-key provider ClassVar invariant remains enforced by `test_master_key_no_classvars.py`.

Validation passed:

- `uv run --no-sync pytest -q src/aeat/adapters/persistence/storage/master_key/test_master_key_no_classvars.py src/aeat/adapters/persistence/storage/master_key/test_bucket_session.py`
- `uv run --no-sync ruff check src/aeat/adapters/persistence/storage/master_key/test_master_key_no_classvars.py src/aeat/adapters/persistence/storage/master_key/test_bucket_session.py`
- `uv run --no-sync -q python -m aeat.locales audit`
- `uv run --no-sync vaultspec-core vault plan check .vault/plan/2026-05-22-secure-storage-production-hardening-refactor-plan.md`

## Notes

An earlier parallel locale-audit invocation failed to import `aeat`; rerunning the canonical `python -m aeat.locales audit` command directly passed for all locale files. Plan check still reports the known `PLAN022` monotonic-order warning only.
