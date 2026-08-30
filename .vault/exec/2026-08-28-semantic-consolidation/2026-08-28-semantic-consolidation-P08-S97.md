---
tags:
  - '#exec'
  - '#semantic-consolidation'
date: '2026-08-30'
modified: '2026-08-30'
body_schema: 'body-v2'
body_hash: 'sha256:f25a2f67c3cf3dccdebcfce2fc886b6c4d50ca60c5e2fe615d6d2ea282411ba8'
step_id: 'S97'
related:
  - "[[2026-08-28-semantic-consolidation-plan]]"
---

# Rehome the censal no-write-surface scan and its anti-tautology guard off the sede facade onto the censal module, so emptying a namespace cannot turn a guard green by emptiness

## Scope

- `src/cadrumo/adapters/outbound/aeat/sede/tests/`

## Changes

- `M` `src/cadrumo/adapters/outbound/aeat/sede/tests/test_censal_no_write_surface.py`
- `verify:` `pytest src/cadrumo/adapters/outbound/aeat/sede/tests/test_censal_no_write_surface.py -n 0 -m ""` -> `pass`
