---
tags:
  - '#exec'
  - '#reachability-burndown'
date: '2026-09-04'
modified: '2026-09-04'
body_schema: 'body-v2'
body_hash: 'sha256:ff1c42d6564ce8403151c0e40a733a022b903a4084531d01c79150440573a5ca'
step_id: 'S21'
related:
  - "[[2026-09-04-reachability-burndown-plan]]"
---

# Extend the constant-agreement screen to detect a canonical value restated under a related name, with detector-teeth proof for both noise guards

## Scope

- `dev/quality/constant_value_agreement.py`

## Changes

- `M` `dev/quality/constant_value_agreement.py`
- `M` `dev/quality/tests/test_constant_value_agreement.py`
- `verify:` `uv run --no-sync pytest dev/quality/tests/test_constant_value_agreement.py -q` -> `pass`
- `verify:` `uv run --no-sync python -m dev.quality.constant_value_agreement --kind stem_restatement` -> `pass`
