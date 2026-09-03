---
tags:
  - '#exec'
  - '#duplication-burndown'
date: '2026-09-03'
modified: '2026-09-03'
body_schema: 'body-v2'
body_hash: 'sha256:bfc2b02fc213f64f6bbdf8c3dc68c8a4dbcd758cb5f08461cbcf5995cc492898'
step_id: 'S02'
related:
  - "[[2026-09-03-duplication-burndown-plan]]"
---

# Restore and run the deleted duplication instrument tests against the current typed runner

## Scope

- `src/cadrumo/tests/test_dev_audit_report.py`

## Changes

- `A` `dev/audit/tests/_duplication_support.py`
- `A` `dev/audit/tests/test_duplication.py`
- `A` `dev/audit/tests/test_duplication_scan.py`
- `verify:` `uv run --no-sync pytest -q -m "unit or integration" dev/audit/tests/test_duplication.py dev/audit/tests/test_duplication_scan.py` -> `pass`
- `verify:` `uv run --no-sync ruff check dev/audit/tests` -> `pass`

## Notes

Three gates from the deleted originals were not restored as written. Two asserted the
production tree carries zero clones; that was true when they were authored and is false
today (52 groups), so restoring them would gate the dashboard on a frozen corpus count,
which `aeat-quality-gates` bans. The health-report gate was rewritten to assert the
mapping instead: GREEN reachable only via `observed_zero`, clones AMBER carrying the
measured count, neither verdict honest without proof of inspection.

The third (`test_dispositions_arithmetic_reconciles`) and the live coverage gate
(`test_every_observed_clone_group_has_a_recorded_disposition`) take the disposition
RECORD as their subject, which `W01.P01.S04` fills and `W01.P01.S05` proves. They are
deferred to S05 rather than restored here, where they would red the tree on debt this
Step does not own.

`dev/audit/tests` carries 17 pre-existing failures unrelated to this Step:
`test_vacuity_screen` (16) runs `git ls-files` inside a non-repository `tmp_path` and
gets exit 128, and one timing-sensitive semgrep timeout case in `test_security_scan`.
Neither module imports the restored files.
