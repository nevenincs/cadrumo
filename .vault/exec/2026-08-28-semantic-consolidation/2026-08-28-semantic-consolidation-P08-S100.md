---
tags:
  - '#exec'
  - '#semantic-consolidation'
date: '2026-08-30'
modified: '2026-08-30'
body_schema: 'body-v2'
body_hash: 'sha256:f76133c84b5d20a19267da4d3a8a4527e139774333a46acc5e5e74e981876aee'
step_id: 'S100'
related:
  - "[[2026-08-28-semantic-consolidation-plan]]"
---

# Promote the post-retirement checks into a single reusable sweep covering all five stale-reference classes, so each retirement runs a written-down pass rather than ad-hoc checks

## Scope

- `dev/quality/namespace_retirement_sweep.py`

## Changes

- `A` `dev/quality/namespace_retirement_sweep.py`
- `verify:` `python dev/quality/namespace_retirement_sweep.py` -> `pass`
