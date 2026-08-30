---
tags:
  - '#exec'
  - '#semantic-consolidation'
date: '2026-08-30'
modified: '2026-08-30'
body_schema: 'body-v2'
body_hash: 'sha256:a34d97e22f0663d15949a96ed7b141ac8ea6068b1b9d10222a4dd5582337c4f5'
step_id: 'S102'
related:
  - "[[2026-08-28-semantic-consolidation-plan]]"
---

# Adopt the canonical filing-year bounds in the work-lifecycle CLI, which redeclared FILING_YEAR_MIN and FILING_YEAR_MAX as local literals

## Scope

- `src/cadrumo/entrypoints/cli/_modelo_work_lifecycle_cli.py`

## Changes

- `M` `src/cadrumo/entrypoints/cli/_modelo_work_lifecycle_cli.py`
- `verify:` `pytest src/cadrumo/core/tests/test_filing_year_single_declaration.py -n 0 -m ""` -> `pass`
