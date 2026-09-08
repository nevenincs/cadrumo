---
tags:
  - '#exec'
  - '#reachability-burndown'
date: '2026-09-04'
modified: '2026-09-07'
body_schema: 'body-v2'
body_hash: 'sha256:e25bf76e19120360c6ad07bbc4e1872870a0e958d63ecaca61b93f2c8dbb4f27'
step_id: 'S141'
related:
  - "[[2026-09-04-reachability-burndown-plan]]"
---

# Delete the complexity audit's empty-baseline compatibility model and metastate vocabulary, projecting live cyclomatic, maintainability, and cognitive findings directly into the audit report with no new/regressed/allowed/resolved partitions, strict flag, retained path parameter, or baseline-shaped output

## Scope

- `dev audit complexity collector and report projection`
- `focused detector and report tests`
- `CLI output contract`

## Changes

- `M` `dev/audit/complexity.py`
- `M` `dev/audit/report.py`
- `D` `dev/audit/tests/test_complexity_classification.py`
- `A` `dev/audit/tests/test_complexity_scan.py`
- `verify:` `uv run pytest -q -n 0 --confcutdir=dev/audit/tests -m unit dev/audit/tests/test_complexity_scan.py` -> `pass (4 passed)`
- `verify:` `uv run ruff check dev/audit/complexity.py dev/audit/report.py dev/audit/tests/test_complexity_scan.py` -> `pass`
- `verify:` exact complexity ghost-API scan across `dev/audit`, `dev/tests`, and `justfile` -> `pass (zero matches)`
- `verify:` live `scan_complexity()` -> `pass (664 current findings: 545 cyclomatic, 21 maintainability, 98 cognitive)`
