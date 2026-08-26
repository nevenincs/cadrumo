---
tags:
  - '#exec'
  - '#cli-root-verb-homes'
date: '2026-08-26'
modified: '2026-08-26'
body_schema: 'body-v2'
body_hash: 'sha256:3672d664e42c4ee56172281e1a548bcbe17bcac9a9d66fc36c7e5ae8ebf73a52'
step_id: 'S25'
related:
  - "[[2026-08-26-cli-root-verb-homes-plan]]"
---

# Make app modelo readiness revision-id optional with law-determined resolution

## Scope

- `src/cadrumo/entrypoints/cli/_modelo_readiness_command_specs.py`

## Changes

- `M` `src/cadrumo/entrypoints/cli/_modelo_readiness_cli.py`
- `M` `src/cadrumo/entrypoints/cli/_modelo_readiness_command_specs.py`
- `verify:` `pytest test_modelo_audit_command_specs parameter-contract gate` -> `pass`
