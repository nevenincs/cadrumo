---
tags:
  - '#exec'
  - '#reachability-burndown'
date: '2026-09-04'
modified: '2026-09-07'
body_schema: 'body-v2'
body_hash: 'sha256:b379c4ef64c0422819d5e48900f5a539b6dd0766cf9a6640d22a671c0d7d70c5'
step_id: 'S162'
related:
  - "[[2026-09-04-reachability-burndown-plan]]"
---

# Delete the empty undeclared-directory exemption mechanism from the storage grammar agreement gate so every derived unmatched directory is reported directly, while retaining planted rename and undeclared-run detector proof.

## Scope

- `storage path directory agreement gate`
- `focused detector tests`
- `live reachability detector`

## Changes

- `M` `src/cadrumo/adapters/persistence/storage/tests/test_storage_path_directory_agreement_gate.py`
- `verify:` `rg -n "UNDECLARED_DIRECTORY_EXEMPTIONS" src/cadrumo --glob '*.py'` -> `pass` (zero matches)
- `verify:` `uv run ruff check src/cadrumo/adapters/persistence/storage/tests/test_storage_path_directory_agreement_gate.py` -> `pass`
- `verify:` `uv run pytest -q src/cadrumo/adapters/persistence/storage/tests/test_storage_path_directory_agreement_gate.py` -> `pass` (9 passed)
- `verify:` `uv run python -m dev.quality.unused_symbol_coverage` -> `fail` (367 exact symbols and 18 orphaned test modules, unchanged)
