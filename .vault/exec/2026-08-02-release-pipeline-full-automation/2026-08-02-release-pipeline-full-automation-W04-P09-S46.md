---
tags:
  - '#exec'
  - '#release-pipeline-full-automation'
date: '2026-08-02'
modified: '2026-08-02'
body_schema: 'body-v1'
body_hash: 'sha256:d5a839e1275385dbc74e67956c1a1f86b481ace51eeb948aa99f1be65eda4e7a'
step_id: 'S46'
related:
  - "[[2026-08-02-release-pipeline-full-automation-plan]]"
---
# Fix the promoter report-only shell guard which tests the variable for emptiness rather than truth

## Scope

- `.github/workflows/release-soak-promoter.yml`
- `dev/release/tests/test_soak_promoter_workflow.py`

## Description

- Replace `${REPORT_ONLY:+--report-only}` with an explicit equality test building an argument array.
- Add two tests: one forbidding the emptiness-test form and requiring the truth test, one pinning the input as a boolean defaulting to false.

## Outcome

`uv run --no-sync pytest dev/release/tests/test_soak_promoter_workflow.py -q` reports 9 passed.

## Notes

`${VAR:+flag}` expands whenever VAR is non-empty, and a boolean dispatch input renders as the literal string `false`, which is non-empty. So the flag was passed on EVERY manual dispatch and a manual promoter run could never promote anything.

The reason it survived review is worth naming: a scheduled tick leaves the input unset, so `${VAR:+flag}` correctly expands to nothing there. The bug was invisible in the path that runs hourly and present only in the path a human takes deliberately - so the automated evidence all looked right, and the failure would have appeared the first time someone tried to promote by hand and could not work out why nothing happened.

The two assertions are pinned as a pair because a default of `true` would reproduce the same never-promotes outcome through configuration rather than through shell semantics.
