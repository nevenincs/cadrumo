---
tags:
  - '#exec'
  - '#cli-root-verb-homes'
date: '2026-08-26'
modified: '2026-08-26'
body_schema: 'body-v2'
body_hash: 'sha256:1e5d199d0334447cf4b3868afafc5eb732862f0ee5bb7b690ed832eb1ccc5cee'
step_id: 'S08'
related:
  - "[[2026-08-26-cli-root-verb-homes-plan]]"
---

# Re-key the four envelope command identifiers and their result schemas

## Scope

- `src/cadrumo/entrypoints/cli/`

## Changes

- `M` `src/cadrumo/entrypoints/cli/_modelo_spreadsheet_cli.py`
- `M` `src/cadrumo/entrypoints/cli/_modelo_spreadsheet_payloads.py`
- `verify:` `pytest operator_surface/tests + transport locus gate` -> `pass`
