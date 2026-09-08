---
tags:
  - '#exec'
  - '#reachability-burndown'
date: '2026-09-08'
modified: '2026-09-08'
body_schema: 'body-v2'
body_hash: 'sha256:93aa3affb607f266eaec1c0170e92ecb55d373e65495f26034525c7d91a17727'
step_id: 'S251'
related:
  - "[[2026-09-04-reachability-burndown-plan]]"
---

<!-- Machine-owned: the filename, the frontmatter, the title heading and the
     Scope list are all filled by `vaultspec-core vault add exec` from the
     originating Step row; never hand-edit them. Add no frontmatter fields.
     Wiki-links belong in `related:` only, never in the body. -->

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
