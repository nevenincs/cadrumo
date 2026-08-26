---
tags:
  - '#exec'
  - '#cli-root-verb-homes'
date: '2026-08-26'
modified: '2026-08-26'
body_schema: 'body-v2'
body_hash: 'sha256:16a977f25b970e1a7ac81b999a270d388cb62f54c6cfd4e4548bb47e27e578b0'
step_id: 'S17'
related:
  - "[[2026-08-26-cli-root-verb-homes-plan]]"
---

# Rename app ledger doclink to app ledger evidence pull, retaining the source enum

## Scope

- `src/cadrumo/entrypoints/cli/`

## Changes

- `M` `src/cadrumo/entrypoints/cli/_app_ledger_operations_command_specs.py`
- `M` `src/cadrumo/entrypoints/cli/_ledger.py`
- `M` `src/cadrumo/entrypoints/cli/_ledger_lifecycle_cli.py`
- `M` `src/cadrumo/entrypoints/cli/_ledger_payloads.py`
- `M` `src/cadrumo/locales/en/cli.yml`
- `M` `src/cadrumo/locales/es/cli.yml`
- `M` `src/cadrumo/locales/ca/cli.yml`
- `M` `src/cadrumo/locales/hu/cli.yml`
- `verify:` `COMMAND_GRAPH rebuild + pytest locus/placement/operator-surface gates` -> `pass`
