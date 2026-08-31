---
tags:
  - '#exec'
  - '#test-reconciliation-sweep'
date: '2026-08-28'
modified: '2026-08-28'
body_schema: 'body-v2'
body_hash: 'sha256:8b37bf77eb86907033d004e82defa8713e45d3c0ef923a4486283bbd0c8e3d70'
step_id: 'S01'
related:
  - "[[2026-08-28-test-reconciliation-sweep-plan]]"
---

# Narrow the CLASSIFIED_BY_MANUAL constants gate to its defining modules, since a package-namespace assertion demands the re-export the inert-namespace boundary forbids

## Scope

- `src/cadrumo/core/tests/`

## Changes

- `M` `src/cadrumo/core/tests/test_external_constants_centralisation_part1.py`
- `verify:` `pytest src/cadrumo/core/tests/test_external_constants_centralisation_part1.py` -> `pass`
