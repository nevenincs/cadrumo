---
tags:
  - '#exec'
  - '#reachability-burndown'
date: '2026-09-09'
modified: '2026-09-09'
body_schema: 'body-v2'
body_hash: 'sha256:215a3e72df5e5d89c1d4d1ad235466778b344dc0acfc7fb08cc4853ad4e9de79'
step_id: 'S287'
related:
  - "[[2026-09-04-reachability-burndown-plan]]"
---

# Delete the test-only visible and exact workflow-resume convenience resolvers, migrate retained coverage to the live unified resume owner, run focused gates, classify the shared envelope-schema red, update cadence, and remeasure exact reachability.

## Scope

- `workflow resume production surface and focused resume tests`

## Changes

- `M` `src/cadrumo/application/workflow/resume.py`
- `M` `src/cadrumo/application/workflow/tests/test_resume.py`
- `M` `.vault/reference/2026-09-04-reachability-burndown-reference.md`
- `verify:` exact search for visible/exact convenience resolvers -> `no matches`
- `verify:` focused Ruff check -> `pass`
- `verify:` focused resume tests -> `6 passed, 7 peer-owned envelope-schema failures`
- `verify:` exact reachability -> `251 unused symbols, 31 unreachable modules, 0 orphaned tests`

## Notes

All seven focused failures terminate in the existing workflow envelope-header validation defect: `written_at`, `payload`, and `encryption` are rejected as extra fields while loading rows saved by the same suite. Both deleted wrappers and the live unified resolver reached that identical persistence path; the migration introduced no distinct failure.
