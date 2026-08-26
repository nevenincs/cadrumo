---
tags:
  - '#exec'
  - '#cli-root-verb-homes'
date: '2026-08-26'
modified: '2026-08-26'
body_schema: 'body-v2'
body_hash: 'sha256:855075faac6dbb0ed70e8b28e5d78c77be7d49703349717072ab09fd3fcd5072'
step_id: 'S05'
related:
  - "[[2026-08-26-cli-root-verb-homes-plan]]"
---

# Gate that a path-bearing or handle-bearing parameter without a declared locus cannot be constructed, and prove it bites

## Scope

- `src/cadrumo/entrypoints/cli/tests/`

## Changes

- `A` `src/cadrumo/entrypoints/cli/tests/test_transport_locus_declared.py`
- `verify:` `pytest test_transport_locus_declared.py` -> `pass`
