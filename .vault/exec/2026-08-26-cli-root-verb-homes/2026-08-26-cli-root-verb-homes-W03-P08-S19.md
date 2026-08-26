---
tags:
  - '#exec'
  - '#cli-root-verb-homes'
date: '2026-08-26'
modified: '2026-08-26'
body_schema: 'body-v2'
body_hash: 'sha256:3fb52c114763140cde9cbb2a63fefc6ec5791e30a7160621cce631ef9a55936d'
step_id: 'S19'
related:
  - "[[2026-08-26-cli-root-verb-homes-plan]]"
---

# Rename app modelo reconcile file to reconcile import

## Scope

- `src/cadrumo/entrypoints/cli/`

## Changes

- `M` `src/cadrumo/entrypoints/cli/_modelo_nonwork_reconcile_command_specs.py`
- `M` `src/cadrumo/entrypoints/cli/_modelo_reconcile_cli.py`
- `M` `src/cadrumo/locales/en/cli.yml`
- `M` `src/cadrumo/locales/es/cli.yml`
- `M` `src/cadrumo/locales/ca/cli.yml`
- `M` `src/cadrumo/locales/hu/cli.yml`
- `verify:` `COMMAND_GRAPH rebuild` -> `pass`
