---
tags:
  - '#exec'
  - '#cli-root-verb-homes'
date: '2026-08-26'
modified: '2026-08-26'
body_schema: 'body-v2'
body_hash: 'sha256:82936703874291877d4c87acbd6b2f7578a0d6d555a336dd99713bbaf11b21b3'
step_id: 'S06'
related:
  - "[[2026-08-26-cli-root-verb-homes-plan]]"
---

<!-- Machine-owned: the filename, the frontmatter, the title heading and the
     Scope list are all filled by `vaultspec-core vault add exec` from the
     originating Step row; never hand-edit them. Add no frontmatter fields.
     Wiki-links belong in `related:` only, never in the body. -->

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
