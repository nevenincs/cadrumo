---
tags:
  - '#exec'
  - '#reachability-burndown'
date: '2026-09-08'
modified: '2026-09-08'
body_schema: 'body-v2'
body_hash: 'sha256:6fb3233eb43c3df4a4ea93ae2568ab72909ba0d2e4b56b584716bf276c224327'
step_id: 'S214'
related:
  - "[[2026-09-04-reachability-burndown-plan]]"
---

<!-- Machine-owned: the filename, the frontmatter, the title heading and the
     Scope list are all filled by `vaultspec-core vault add exec` from the
     originating Step row; never hand-edit them. Add no frontmatter fields.
     Wiki-links belong in `related:` only, never in the body. -->

# Delete the wholly unused CSV_EXTENSIONS constant and export from local-observation spreadsheet parsing while retaining the live XLSX discriminator and CSV/TXT fallback behavior in both decimal and lexical parsers.

## Scope

- `Local-observation spreadsheet parser and focused CSV/XLSX tests`
- `exact reachability signal`
- `focused gates`
- `Step Record`
- `and independent code review.`

## Changes

- `M` `.vault/plan/2026-09-04-reachability-burndown-plan.md`
- `M` `src/cadrumo/application/modelo/local_observation_spreadsheet.py`
- `A` `.vault/exec/2026-09-04-reachability-burndown/2026-09-04-reachability-burndown-W05-P12-S214.md`
- `verify:` `uv run --no-sync pytest -q src/cadrumo/application/modelo/tests/test_local_observation_spreadsheet.py src/cadrumo/entrypoints/cli/tests/test_modelo_local_observation_spreadsheet_cli.py` -> `pass (32 passed)`
- `verify:` `uv run --no-sync ruff check src/cadrumo/application/modelo/local_observation_spreadsheet.py src/cadrumo/application/modelo/tests/test_local_observation_spreadsheet.py src/cadrumo/entrypoints/cli/tests/test_modelo_local_observation_spreadsheet_cli.py` -> `pass`
- `verify:` `uv run --no-sync python -m dev.quality.production_metastate` -> `pass`
- `verify:` `rg -n "CSV_EXTENSIONS" src/cadrumo/application/modelo src/cadrumo/entrypoints --glob '*.py'` -> `pass (no matches)`
- `verify:` `uv run --no-sync python -m dev.audit.unreachable_code --confidence exact` -> `pass (expected nonzero with live findings: 63 unreachable modules, 312 exact unused symbols, 15 orphaned tests, 2028/2092 shipped modules reachable)`
