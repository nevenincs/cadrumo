---
tags:
  - '#exec'
  - '#cli-root-verb-homes'
date: '2026-08-26'
modified: '2026-08-26'
body_schema: 'body-v2'
body_hash: 'sha256:9fabcf9fe2a7ba0502c12aa2c4db20c0395c85b363a7d9027eeb37881a5ccfe6'
step_id: 'S16'
related:
  - "[[2026-08-26-cli-root-verb-homes-plan]]"
---

# Update the bootstrap-exempt and login-gated verb paths and resolve the stale config profile export entry

## Scope

- `src/cadrumo/entrypoints/cli/_bootstrap_exempt.py`

## Changes

- `M` `src/cadrumo/entrypoints/cli/_bootstrap_exempt.py`
- `M` `src/cadrumo/entrypoints/cli/tests/test_login_gated_verbs_never_exempt.py`
- `verify:` `pytest bootstrap-exempt + login-gated gates` -> `pass`
