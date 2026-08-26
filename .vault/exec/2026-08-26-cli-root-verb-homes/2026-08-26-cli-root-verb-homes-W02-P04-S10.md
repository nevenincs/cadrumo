---
tags:
  - '#exec'
  - '#cli-root-verb-homes'
date: '2026-08-26'
modified: '2026-08-26'
body_schema: 'body-v2'
body_hash: 'sha256:e7370049941b2ff2dd3d808eee6a04616113e115d20cbc5c82eff63a4ab18044'
step_id: 'S10'
related:
  - "[[2026-08-26-cli-root-verb-homes-plan]]"
---

# Fold app maintenance reconcile into config repair and retire the family

## Scope

- `src/cadrumo/entrypoints/cli/`

## Changes

- `R` `src/cadrumo/entrypoints/cli/_app_maintenance.py` -> `src/cadrumo/entrypoints/cli/_config/_repair_prepared_exports.py`
- `R` `src/cadrumo/entrypoints/cli/_app_maintenance_payloads.py` -> `src/cadrumo/entrypoints/cli/_config/_repair_prepared_exports_payloads.py`
- `D` `src/cadrumo/entrypoints/cli/_app_maintenance_command_specs.py`
- `M` `src/cadrumo/entrypoints/cli/_command_specs.py`
- `M` `src/cadrumo/entrypoints/cli/_config/_repair_command_specs.py`
- `M` `src/cadrumo/locales/en/cli.yml`
- `M` `src/cadrumo/locales/es/cli.yml`
- `M` `src/cadrumo/locales/ca/cli.yml`
- `M` `src/cadrumo/locales/hu/cli.yml`
- `verify:` `dev.locales scaffold --check` -> `pass`
- `verify:` `COMMAND_GRAPH rebuild (294 leaves, policy preserved)` -> `pass`
