---
tags:
  - '#exec'
  - '#audits-resolution'
date: '2026-05-13'
modified: '2026-05-13'
related:
  - "[[2026-05-13-audits-resolution-plan]]"
  - "[[2026-05-13-eliminate-shims-audit]]"
---

# audits-resolution group-a step-5

## scope

Plan row A5: remove the four `del path` ignored-parameter shims and
update every caller.

## changes

Helpers de-pathed:

- `load_usage_ratios` (`src/aeat/domain/usage_ratios/_service.py`)
  loses its `path: Path` parameter and its `del path`.
- `save_usage_ratios` (same file) loses its `path: Path` parameter.
- `_load_transaction_catalogue` (`src/aeat/application/filing/_review.py`)
  loses its `path: Path | None` parameter.
- `_read_transaction_catalogue` (same file) loses its `path: Path`
  parameter.

Callers updated:

- `_load_profile` and `_save_profile` in
  `src/aeat/entrypoints/cli/financial/profile.py` no longer pass
  `_usage_ratios_path()`.
- The three public `_review.py` entrypoints
  (`compute_current_approval_basis`, `approval_stale_reasons`,
  `approve_draft`, `refresh_review_status`) drop the
  `transaction_catalogue_path: Path | None` keyword and the internal
  threading. The pathlib import in `_review.py` is no longer needed.

Their bodies remain unchanged — `del path` was the only path-aware
line and the SQL-backed
`SecureObjectRepository` / `TransactionCatalogueRepository` calls
were already path-free.

## verification

`grep -rn 'del path\b' src/aeat/` returns only the legitimate
local-rotation pattern in
`adapters/persistence/storage/blob_store/_blob_store.py:329` (audit
allowlist).

`pytest src/aeat/application/filing/test_filing.py
src/aeat/application/filing/test_review_describe_stale_reason.py
src/aeat/domain/usage_ratios/` returns 62 passed.

Eleven pre-existing failures in the broader filing/financial test
surface (file-backed test fixtures that expected pre-A5 behaviour the
audit explicitly flagged as already ignored, plus four concurrent-
agent registry-calculation drifts) reproduce on a clean checkout
without the A5 changes and are not in audits-resolution scope.
