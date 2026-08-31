---
tags:
  - '#exec'
  - '#test-reconciliation-sweep'
date: '2026-08-28'
modified: '2026-08-28'
body_schema: 'body-v2'
body_hash: 'sha256:e59270ef7a7ca33632beddd29808db34d4cf3c31343e6772b717f09af56560b8'
step_id: 'S09'
related:
  - "[[2026-08-28-test-reconciliation-sweep-plan]]"
---

# Widen the coverage predicate to the post-split transport vocabulary, govern every leaf it newly selects, and delete the stale row in the same change

## Scope

- `src/cadrumo/application/repair_integrity.py`

## Changes

- `M` `src/cadrumo/application/repair_integrity.py`
- `M` `src/cadrumo/entrypoints/cli/tests/test_repair_policy_coverage.py`
- `verify:` `pytest src/cadrumo/entrypoints/cli/tests/test_repair_policy_coverage.py -m integration` -> `pass`
- `verify:` `pytest src/cadrumo/application/tests/test_repair_integrity.py` -> `pass`
