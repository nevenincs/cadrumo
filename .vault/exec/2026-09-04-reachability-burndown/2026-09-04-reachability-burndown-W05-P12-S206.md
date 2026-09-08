---
tags:
  - '#exec'
  - '#reachability-burndown'
date: '2026-09-08'
modified: '2026-09-08'
body_schema: 'body-v2'
body_hash: 'sha256:fcb2ea4b2f821061aa9aaafd76d47f96342d885b325061cdc464792b8c577daf'
step_id: 'S206'
related:
  - "[[2026-09-04-reachability-burndown-plan]]"
---

<!-- Machine-owned: the filename, the frontmatter, the title heading and the
     Scope list are all filled by `vaultspec-core vault add exec` from the
     originating Step row; never hand-edit them. Add no frontmatter fields.
     Wiki-links belong in `related:` only, never in the body. -->

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
