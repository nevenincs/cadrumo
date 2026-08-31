---
tags:
  - '#exec'
  - '#test-reconciliation-sweep'
date: '2026-08-28'
modified: '2026-08-28'
body_schema: 'body-v2'
body_hash: 'sha256:6b02b2fe58520d065aa7e9209383acdd6c8b45460cd1f532e651a862fd319a37'
step_id: 'S08'
related:
  - "[[2026-08-28-test-reconciliation-sweep-plan]]"
---

# Govern the four writers this campaign's renames pulled into the coverage predicate

## Scope

- `src/cadrumo/application/repair_integrity.py`

## Changes

- `M` `src/cadrumo/application/repair_integrity.py`
- `verify:` `pytest src/cadrumo/entrypoints/cli/tests/test_repair_policy_coverage.py -m integration` -> `pass`
