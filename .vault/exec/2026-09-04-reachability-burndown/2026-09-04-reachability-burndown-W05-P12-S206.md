---
tags:
  - '#exec'
  - '#reachability-burndown'
date: '2026-09-08'
modified: '2026-09-09'
body_schema: 'body-v2'
body_hash: 'sha256:d815f2c1f1c5627910ff0f653c807cfec084683da615236bd560065e0a6f630e'
step_id: 'S206'
related:
  - "[[2026-09-04-reachability-burndown-plan]]"
---

# Delete the test-only calendar_censo_enrolment_profile_keys census accessor and its export from production calendar warnings, and rewrite focused calendar tests around externally observable required-key behavior while retaining the private live enrolment-key authority and production applicability computation.

## Scope

- `Overview calendar warning owner and focused calendar tests`
- `exact reachability signal`
- `focused gates`
- `cadence reference`
- `Step Record`
- `and independent code review.`

## Changes

- `M` `.vault/reference/2026-09-04-reachability-burndown-reference.md`
- `M` `src/cadrumo/application/overview/calendar_warnings.py`
- `M` `src/cadrumo/application/overview/tests/test_calendar.py`
- `verify:` `uv run --no-sync ruff check src/cadrumo/application/overview/calendar_warnings.py src/cadrumo/application/overview/tests/test_calendar.py` -> `pass`
- `verify:` `uv run --no-sync pytest -q -n0 -m "" --basetemp <isolated-workspace-temp> <four focused censo enrolment tests>` -> `pass` (4 passed)
- `verify:` `rg -n "calendar_censo_enrolment_profile_keys" src/cadrumo --glob '*.py'` -> `pass` (no matches)
- `verify:` `uv run --no-sync python -m dev.quality.production_metastate` -> `pass`
- `verify:` `uv run --no-sync python -m dev.audit.unreachable_code --confidence exact` -> `findings` (target absent; live graph measured)

## Notes

The live post-change graph measured 65 unreachable modules, 322 exact unused symbols, 18 orphaned tests, and 2028/2094 shipped modules reachable. The exact `calendar_censo_enrolment_profile_keys` finding is absent. Concurrent peer edits changed both module totals and the aggregate unused-symbol count during this step, so no aggregate reduction is attributed to S206.
