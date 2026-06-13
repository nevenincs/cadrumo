---
tags:
  - '#exec'
  - '#repo-health-triage'
date: '2026-06-05'
modified: '2026-06-05'
step_id: 'S76'
related:
  - '[[2026-06-04-repo-health-triage-plan]]'
---

# W06.P19.S76 ledger projection complexity reduction

Scope: `W06.P19.S76` - Reduce ledger list and review projection cognitive
complexity.

## Description

- Extract `ledger review` filter parsing, backend query construction, detail
  payloads, list payloads, and text-line rendering into private helpers.
- Extract `ledger rule apply` dry-run candidate selection, matching-rule lookup,
  dry-run rendering, and live-result rendering into private helpers because it
  was the remaining ledger function above the Complexipy threshold.
- Repair local `_ledger.py` typing around output schema classes, ledger-link
  evidence payloads, stale filed revision mappings, and mutable evidence payloads.

## Outcome

Completed. `ledger_review` moved to Radon A (1) and Complexipy 0. `rule_apply`
moved to Radon A (4) and Complexipy 2. `ledger_list` was already low and remains
Radon A (2), Complexipy 1. `_ledger.py` now passes the path-scoped Ty check.

Verification:

- `uv run --no-sync ruff check src/aeat/entrypoints/cli/_ledger.py` passed.
- `uv run --no-sync ty check src/aeat/entrypoints/cli/_ledger.py --output-format concise`
  passed.
- `uv run --no-sync radon cc src/aeat/entrypoints/cli/_ledger.py -s` captured
  the reduced command grades.
- `uv run --no-sync complexipy src/aeat/entrypoints/cli/_ledger.py --max-complexity-allowed 20`
  passed.
- `uv run --no-sync pytest src/aeat/entrypoints/cli/test_ledger_bulk_classify.py src/aeat/entrypoints/cli/test_ledger_list_filter.py -q`
  passed with 23 tests.
- `uv run --no-sync pytest src/aeat/entrypoints/cli/test_cli_surface.py::test_app_ledger_import_reimport_review_round_trips_state src/aeat/entrypoints/cli/test_backend_boundary.py::test_manual_ledger_import_and_review_boundaries_stay_backend_owned src/aeat/entrypoints/cli/test_backend_boundary.py::test_manual_ledger_review_help_exposes_backend_filter_vocabulary -q`
  passed the review round-trip and backend ownership tests, with the help
  vocabulary residual noted below.

## Notes

Two review-prefix UX tests still fail during import setup with
`Storage runtime is not ready for profile-bound storage: The database route does
not match the active bucket session`. The backend help-vocabulary test still
fails because `ledger review --help` does not include the expected
`classification` filter token. These failures were not hidden or bypassed by
the complexity extraction.
