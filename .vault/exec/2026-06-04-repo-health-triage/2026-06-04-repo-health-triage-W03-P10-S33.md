---
tags:
  - '#exec'
  - '#repo-health-triage'
date: '2026-06-04'
modified: '2026-06-04'
step_id: 'W03.P10.S33'
related:
  - '[[2026-06-04-repo-health-triage-plan]]'
---

# W03.P10.S33 - Extract ledger review-filter projection service

Scope: execute the ledger decomposition step for review-row filtering and projection.

## Description

- Add `_review_projection.py` as the application-layer owner for ledger review filtering.
- Move review-status classification, review-row projection, filter-label rendering, transaction-id filter validation, and import/issue event matching into the new module.
- Keep `_actions.py` responsible for transaction repository loading and delegate `query_ledger_review_rows` to the projection module.
- Preserve the public application API used by CLI list/review commands and tests.

## Outcome

- `_actions.py` dropped the review-filter helper cluster and now calls `project_ledger_review_query`.
- `_review_projection.py` landed as a focused 206-line module.
- Review-row behavior remains covered through existing application and CLI tests.

## Notes

- Verification:
  - `uv run --no-sync ruff check src/aeat/application/ledger/_actions.py src/aeat/application/ledger/_review_projection.py src/aeat/application/ledger/test_actions.py src/aeat/entrypoints/cli/test_ledger_list_filter.py`
  - `uv run --no-sync pytest src/aeat/application/ledger/test_actions.py::test_query_ledger_review_rows_filters_exact_period_and_projects_rows src/aeat/application/ledger/test_actions.py::test_query_ledger_review_rows_filters_by_direction src/aeat/application/ledger/test_actions.py::test_query_ledger_review_rows_filters_quarter_import_and_issue_events src/aeat/entrypoints/cli/test_ledger_list_filter.py -q`
  - `uv run --no-sync pytest src/aeat/application/ledger/test_actions.py -q`
