---
tags:
  - '#exec'
  - '#source-casilla-integration'
date: '2026-08-25'
modified: '2026-08-25'
body_schema: 'body-v1'
body_hash: 'sha256:a693050fc4df52cb8882c84902a660313cd11472b5407b57319e3956b777a7e3'
step_id: 'S88'
related:
  - "[[2026-08-22-source-casilla-integration-plan]]"
---

# route Google Sheets pull output into the governed calculation input boundary

## Scope

- `src/cadrumo/entrypoints/cli/_config/_google_sync_calc.py`

## Description

- Delegate populated Google Sheets row sets through the snapshot-owned `assemble_observations_for_snapshot` command.
- Preserve the pull payload projection and localized refusal boundary.
- Prove the exact public-command call with an injected dispatcher guard and assemble a live Modelo 190 row through the selected snapshot.

## Outcome

Google Sheets pull now passes each populated row set and its law-selected registry snapshot through the governed calculation input command introduced by S87. The route neither persists an observation nor creates row identity, fingerprints, bindings, source ownership, or a calculation revision.

## Notes

Focused verification passed: `pytest -n 0 src/cadrumo/entrypoints/cli/_config/tests/test_google_sync_calc_pull_observations.py -q` (2 passed) and scoped Ruff for the production and test modules. Scoped code review found no issue. S89 through S91 remain intentionally open.
