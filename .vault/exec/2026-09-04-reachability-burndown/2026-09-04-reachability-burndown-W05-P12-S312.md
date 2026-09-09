---
tags:
  - '#exec'
  - '#reachability-burndown'
date: '2026-09-09'
modified: '2026-09-09'
body_schema: 'body-v2'
body_hash: 'sha256:7c5e695136ed411245824b977ccd2c9f7c0c3d36246c70c3f129ee4697e50b9e'
step_id: 'S312'
related:
  - "[[2026-09-04-reachability-burndown-plan]]"
---

# Remove import-gate development metastate and retain strict live import resolution

## Scope

- `src/cadrumo/tests/test_cross_module_imports_resolve.py and signal-burndown cadence guidance`

## Changes

- `M` `src/cadrumo/tests/test_cross_module_imports_resolve.py`
- `M` `.vault/reference/2026-09-04-reachability-burndown-reference.md`
- `verify:` `uv run --no-sync pytest -q src/cadrumo/tests/test_cross_module_imports_resolve.py` -> `fail`

## Notes

The retained live import-resolution check reaches a peer-owned syntax error in `src/cadrumo/application/operations/supervisor.py:358` (`IndentationError: unexpected unindent`). The import gate itself collected and began resolving the live source tree successfully; this Step does not absorb the concurrent production edit.
