---
tags:
  - '#exec'
  - '#registry-dated-validity'
date: '2026-08-27'
modified: '2026-08-27'
body_schema: 'body-v2'
body_hash: 'sha256:b12b2a73d274be5eb40ccb81bae060df1f7c188e0b0f4a8e90201a5094c4782d'
step_id: 'S02'
related:
  - "[[2026-08-27-registry-dated-validity-plan]]"
---

# Add the closed ValidityWindow primitive as a public canonical core module, with both bounds required, no default and no open end, a from-before-to invariant, and year-coverage derivation over a group of windows, plus real-behaviour tests including a refusal proof for an omitted bound

## Scope

- `src/cadrumo/core/validity_window.py and src/cadrumo/core/tests/`

## Changes

- `A` `src/cadrumo/core/validity_window.py`
- `A` `src/cadrumo/core/tests/test_validity_window.py`
- `verify:` `pytest src/cadrumo/core/tests/test_validity_window.py` -> `pass`
