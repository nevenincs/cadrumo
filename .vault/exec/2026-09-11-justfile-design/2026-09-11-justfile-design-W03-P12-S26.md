---
tags:
  - '#exec'
  - '#justfile-design'
date: '2026-09-11'
modified: '2026-09-11'
body_schema: 'body-v2'
body_hash: 'sha256:211265abb6869e53e6fc1d6f352a7866b2206d6d73f2edf14322a5985e15be90'
step_id: 'S26'
related:
  - "[[2026-09-11-justfile-design-plan]]"
---

# Replace test-all with product registry tooling packaging and capability-qualified aggregates

## Scope

- `justfile`

## Changes

- `M` `justfile`
- `M` `dev/tests/test_lane_reachability.py`
- `verify:` `just --dry-run test-product test-registry test-tooling` -> `pass`
