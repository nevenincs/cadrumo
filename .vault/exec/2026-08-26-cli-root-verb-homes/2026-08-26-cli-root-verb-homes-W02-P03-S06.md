---
tags:
  - '#exec'
  - '#cli-root-verb-homes'
date: '2026-08-26'
modified: '2026-08-26'
body_schema: 'body-v2'
body_hash: 'sha256:734f3f720ff089b0f88626e222e54a13db9e092db45e59b46dbd42ba8f8a025e'
step_id: 'S06'
related:
  - "[[2026-08-26-cli-root-verb-homes-plan]]"
---

# Move the four sync calc leaves to app modelo spreadsheet with push and calculate renames

## Scope

- `src/cadrumo/entrypoints/cli/`

## Changes

- `R` `src/cadrumo/entrypoints/cli/_config/_google_sync_calc.py` -> `src/cadrumo/entrypoints/cli/_modelo_spreadsheet_cli.py`
- `A` `src/cadrumo/entrypoints/cli/_modelo_spreadsheet_payloads.py`
- `A` `src/cadrumo/entrypoints/cli/_modelo_spreadsheet_command_specs.py`
- `M` `src/cadrumo/entrypoints/cli/_config/_google_payloads.py`
- `M` `src/cadrumo/entrypoints/cli/_config/_google_command_specs.py`
- `M` `src/cadrumo/entrypoints/cli/_command_specs.py`
- `verify:` `COMMAND_GRAPH rebuild (294 leaves, 4 spreadsheet leaves mounted)` -> `pass`
