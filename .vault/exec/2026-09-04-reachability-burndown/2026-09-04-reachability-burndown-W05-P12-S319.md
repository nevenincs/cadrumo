---
tags:
  - '#exec'
  - '#reachability-burndown'
date: '2026-09-09'
modified: '2026-09-09'
body_schema: 'body-v2'
body_hash: 'sha256:75c6de8cbf280ca53e8a140cb917351c568547374db2b4fa8055768a2e8461c5'
step_id: 'S319'
related:
  - "[[2026-09-04-reachability-burndown-plan]]"
---

<!-- Machine-owned: the filename, the frontmatter, the title heading and the
     Scope list are all filled by `vaultspec-core vault add exec` from the
     originating Step row; never hand-edit them. Add no frontmatter fields.
     Wiki-links belong in `related:` only, never in the body. -->

# Delete displaced projection version and digest-adapter declarations from the facade

## Scope

- `operation projection facade`
- `focused projection contracts`
- `exact reachability`
- `cadence reference`
- `and Step Record`

## Changes

- `M` `src/cadrumo/application/operations/projection_services.py`
- `M` `.vault/reference/2026-09-04-reachability-burndown-reference.md`
- `verify:` `uv run --no-sync python -m py_compile src/cadrumo/application/operations/projection_services.py` -> `pass`
- `verify:` `uv run --no-sync pytest -q src/cadrumo/application/operations/tests/test_projection_services.py src/cadrumo/application/operations/tests/test_cancellation_cleanup.py` -> `pass`
