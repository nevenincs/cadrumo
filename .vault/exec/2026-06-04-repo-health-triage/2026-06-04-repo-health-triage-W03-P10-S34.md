---
tags:
  - '#exec'
  - '#repo-health-triage'
date: '2026-06-04'
modified: '2026-06-04'
step_id: 'W03.P10.S34'
related:
  - '[[2026-06-04-repo-health-triage-plan]]'
---

# W03.P10.S34 - Split ledger list CLI parsing and rendering

Scope: execute the ledger CLI decomposition step for `ledger list` parsing, filtering projection, paging, grouping, and row rendering.

## Description

- Add `_ledger_list.py` as the CLI-side helper for `ledger list` filter parsing and output projection.
- Move list filter application, shared review-query matching, group filtering, group ordering, paging, truncation footer construction, row payload construction, and text-line rendering out of `_ledger.py`.
- Keep `_ledger.py` responsible for Typer option wiring, active repository resolution, parse-error translation, and envelope emission.
- Wrap pre-existing long `ledger classify` and `ledger doclink` lines in `_ledger.py` so the touched-file Ruff gate is clean.

## Outcome

- `ledger list` continues to use the shared `LedgerReviewFilterSpec` and `query_ledger_review_rows` backend filter contract.
- The Typer command body is now orchestration only; the list-specific projection is isolated for the next complexity burn-down pass.
- No command grammar, JSON payload shape, text output shape, paging semantics, or group-filter behavior was intentionally changed.

## Notes

- Verification:
  - `uv run --no-sync ruff check src/aeat/entrypoints/cli/_ledger.py src/aeat/entrypoints/cli/_ledger_list.py`
  - `uv run --no-sync pytest src/aeat/entrypoints/cli/test_ledger_list_filter.py -q`
  - `uv run --no-sync pytest src/aeat/entrypoints/cli/test_cold_start_no_profile.py -q`
  - `uv run --no-sync pytest src/aeat/entrypoints/cli/test_workflow_surface.py::test_review_filter_help_lists_supported_filter_keys -q`
  - Targeted `complexipy` probe on `_ledger.py` and `_ledger_list.py`
- Complexity signal:
  - `_ledger_list.py` has no functions over cognitive-complexity threshold 12.
  - Remaining `_ledger.py` functions over threshold are `rule_apply`, `ledger_classify`, and `ledger_link`; those are outside this list-command slice.
- One broader lifecycle node, `src/aeat/entrypoints/cli/test_cli_surface.py::test_app_ledger_create_manual_transaction_persists_in_active_bucket`, currently fails before this slice's list path on an unrelated `ledger update` taxable-base plus IVA gross-validation refusal.
