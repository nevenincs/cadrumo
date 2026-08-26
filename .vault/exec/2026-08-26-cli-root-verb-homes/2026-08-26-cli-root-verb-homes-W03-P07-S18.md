---
tags:
  - '#exec'
  - '#cli-root-verb-homes'
date: '2026-08-26'
modified: '2026-08-26'
body_schema: 'body-v2'
body_hash: 'sha256:d56e6f9f44824609255e80ad2a05434a1bf3e64acfafbb3e4b0550334c43c6ed'
step_id: 'S18'
related:
  - "[[2026-08-26-cli-root-verb-homes-plan]]"
---

# Rename app ledger pull-folder to app ledger evidence pull-all

## Scope

- `src/cadrumo/entrypoints/cli/`

## Changes

- `M` `src/cadrumo/entrypoints/cli/_app_ledger_management_command_specs.py`
- `verify:` `COMMAND_GRAPH rebuild (evidence pull-all mounted)` -> `pass`
