---
tags:
  - '#exec'
  - '#reachability-burndown'
date: '2026-09-09'
modified: '2026-09-09'
body_schema: 'body-v2'
body_hash: 'sha256:abc77ef15a3fbb3bcf4117c85a36d45f6e1510e1a847c8c1c04b50bf76130172'
step_id: 'S312'
related:
  - "[[2026-09-04-reachability-burndown-plan]]"
---

<!-- Machine-owned: the filename, the frontmatter, the title heading and the
     Scope list are all filled by `vaultspec-core vault add exec` from the
     originating Step row; never hand-edit them. Add no frontmatter fields.
     Wiki-links belong in `related:` only, never in the body. -->

# Remove import-gate development metastate and retain strict live import resolution

## Scope

- `src/cadrumo/tests/test_cross_module_imports_resolve.py and signal-burndown cadence guidance`

## Changes

- `M` `src/cadrumo/tests/test_cross_module_imports_resolve.py`
- `M` `.vault/reference/2026-09-04-reachability-burndown-reference.md`
- `verify:` `uv run --no-sync pytest -q src/cadrumo/tests/test_cross_module_imports_resolve.py` -> `fail`

## Notes

The retained live import-resolution check reaches a peer-owned syntax error in `src/cadrumo/application/operations/supervisor.py:358` (`IndentationError: unexpected unindent`). The import gate itself collected and began resolving the live source tree successfully; this Step does not absorb the concurrent production edit.
