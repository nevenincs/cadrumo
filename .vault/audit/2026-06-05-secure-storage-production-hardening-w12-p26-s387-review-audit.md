---
tags:
  - '#audit'
  - '#secure-storage-production-hardening'
date: '2026-06-05'
modified: '2026-06-05'
related:
  - '[[2026-05-22-secure-storage-production-hardening-refactor-plan]]'
  - '[[2026-06-05-secure-storage-production-hardening-W12-P26-S387]]'
---

# `secure-storage-production-hardening` `W12.P26.S387` Review

## S387-001 | FIXED | Review queue invoice and draft adapters used ambient repository defaults

Reviewed the S387 scope as `vaultspec-code-reviewer`. `_review.py` delegates queue
loading to `project_review_queue()` and does not own storage directly, but the
application queue path was only partially bucket-explicit: `ReviewQueue.collect()` sent
its bucket id to transaction loading while invoice and draft loading still constructed
their repositories through defaults.

`invoices_pending()` and `drafts_pending()` now require `bucket_id` for repository
loading, and `ReviewQueue.collect()` passes its resolved bucket id to every source
adapter.

## S387-002 | PASS | Review CLI stays localized and exception-owned

The review CLI still renders through localized text helpers and projects
`ReviewError` through the shared CLI error resolver. The slice did not introduce raw
`typer.BadParameter` storage messages, ad hoc exception classes, or broad catch blocks.

## S387-003 | PASS | Locale audit stayed clean for the staged review queue slice

The review queue change did not introduce locale keys. The local shared worktree
contains an untracked ledger-rule split with its own locale requirement; that repair was
performed through `python -m aeat.locales set` but remains unstaged with its owning
source split.

## S387-004 | PASS | Validation

- Focused ruff passed for the review CLI, review application modules, and focused tests.
- Focused application review tests passed with 34 selected tests.
- Focused review CLI integration tests passed with 5 tests.
- `python -m aeat.locales audit` passed for all locale catalogs in the shared worktree.

Reviewer note: no critical, high, medium, or low findings remain for the S387 slice.

Disposition: close `AFR-285` as `manifest-discovery`.
