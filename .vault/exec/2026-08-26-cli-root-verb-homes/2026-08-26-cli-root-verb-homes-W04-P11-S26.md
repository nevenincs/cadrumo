---
tags:
  - '#exec'
  - '#cli-root-verb-homes'
date: '2026-08-26'
modified: '2026-08-26'
body_schema: 'body-v2'
body_hash: 'sha256:74eb1ddfd38c0ef6329f6b39e2c59368f0a106bf30cfbbf050724ceb069eca7f'
step_id: 'S26'
related:
  - "[[2026-08-26-cli-root-verb-homes-plan]]"
---

# Adopt the exit-2 missing-field contract on app modelo readiness

## Scope

- `src/cadrumo/entrypoints/cli/`

## Changes

- `M` `src/cadrumo/entrypoints/cli/_modelo_readiness_cli.py`
- `verify:` `handler raises typer.Exit(code=2) when not ready` -> `pass`
