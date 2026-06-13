---
tags:
  - '#exec'
  - '#secure-storage-production-hardening'
date: '2026-06-05'
modified: '2026-06-05'
step_id: 'S387'
related:
  - '[[2026-05-22-secure-storage-production-hardening-refactor-plan]]'
---

# W12.P26.S387 - Close AFR-285 for review queue

Scope: close `AFR-285` for `src/aeat/entrypoints/cli/_review.py` with signal
`manifest-bucket`, target `manifest-discovery`, and owner `W12.P22.S90`.

## Description

- Audited `_review.py` as a thin CLI facade over the application review operator.
- Confirmed `_review.py` does not construct storage repositories, resolve raw SQL
  routes, inspect environment variables, or swallow review exceptions.
- Traced `project_review_queue()` through `ReviewQueue.collect()` and found that the
  active bucket id reached the transaction adapter but not the invoice and draft
  adapters.
- Made `invoices_pending()` and `drafts_pending()` require an explicit `bucket_id` when
  repository loading is needed.
- Updated `ReviewQueue.collect()` to pass its `bucket_id` to the invoice and draft
  adapters.
- Updated review adapter tests to persist invoice and draft fixtures through
  bucket-bound repositories.
- Added a real secure-storage isolation regression for invoice review loading across
  neighboring buckets.
- Closed `W12.P26.S387` through `vaultspec-core vault plan step check` and updated the
  `AFR-285` register status to `closed`.

## Outcome

`AFR-285` is closed as `manifest-discovery`. The review CLI remains an application-owned
facade, and the review queue no longer lets invoice or filing-draft source adapters
fall back to ambient active-bucket repository construction.

Validation passed:

- `uv run --no-sync ruff check src/aeat/entrypoints/cli/_review.py src/aeat/application/review/_operator.py src/aeat/application/review/_aggregator.py src/aeat/application/review/_adapters.py src/aeat/application/review/tests/test_adapters.py src/aeat/application/review/tests/test_aggregator.py src/aeat/application/review/tests/test_operator.py src/aeat/entrypoints/cli/tests/test_review_operator_errors.py src/aeat/entrypoints/cli/tests/test_review_payloads_roundtrip.py`
- `uv run --no-sync pytest -q src/aeat/application/review/tests/test_adapters.py src/aeat/application/review/tests/test_aggregator.py src/aeat/application/review/tests/test_operator.py src/aeat/entrypoints/cli/tests/test_review_operator_errors.py src/aeat/entrypoints/cli/tests/test_review_payloads_roundtrip.py`
- `uv run --no-sync pytest -q -m integration src/aeat/entrypoints/cli/tests/test_review_operator_errors.py src/aeat/entrypoints/cli/tests/test_review_payloads_roundtrip.py`
- `uv run --no-sync -q python -m aeat.locales audit`

## Notes

The local shared worktree contains an untracked ledger-rule split that requires a
separate locale update. That intersecting translation repair was performed through
`python -m aeat.locales set` in the worktree, but it is not part of this S387 commit
because the owning source split is not tracked in this slice.
