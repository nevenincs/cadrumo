---
tags:
  - '#exec'
  - '#reachability-burndown'
date: '2026-09-08'
modified: '2026-09-09'
body_schema: 'body-v2'
body_hash: 'sha256:25de341ed9a039a29fe81b10eb2d330631a90f3dab4d75afc509838d65e0118d'
step_id: 'S251'
related:
  - "[[2026-09-04-reachability-burndown-plan]]"
---

# Move the export-renderer encoding aliases out of the shipped registry package

## Scope

- `Delete the unreachable record-spec module and its self-tests`
- `keep the alias map local to the development renderer that consumes it`
- `remove its obsolete import census`
- `run the renderer gate`
- `remeasure exact reachability`
- `update the cadence reference`
- `and write the Step Record`

## Changes

- `M` `dev/registry/pipeline/_export_tree.py`
- `M` `dev/registry/tests/test_export_tree.py`
- `D` `src/cadrumo/domain/calculations/registry/record_spec.py`
- `D` `src/cadrumo/domain/calculations/registry/tests/test_record_spec.py`
- `M` `.vault/reference/2026-09-04-reachability-burndown-reference.md`
- `verify:` `uv run --no-sync ruff check dev/registry/pipeline/_export_tree.py dev/registry/tests/test_export_tree.py` -> `pass`
- `verify:` `uv run --no-sync pytest -q dev/registry/tests/test_export_tree.py` -> `pass`
- `verify:` `uv run --no-sync python -m dev.audit.unreachable_code --confidence exact` -> `fail`
