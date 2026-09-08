---
tags:
  - '#exec'
  - '#reachability-burndown'
date: '2026-09-08'
modified: '2026-09-08'
body_schema: 'body-v2'
body_hash: 'sha256:141dec6dbfee7520feb4e2c7f910ad54ce804dbfe2c96fefc95efb26f93f0ca1'
step_id: 'S232'
related:
  - "[[2026-09-04-reachability-burndown-plan]]"
---

<!-- Machine-owned: the filename, the frontmatter, the title heading and the
     Scope list are all filled by `vaultspec-core vault add exec` from the
     originating Step row; never hand-edit them. Add no frontmatter fields.
     Wiki-links belong in `related:` only, never in the body. -->

# Delete the test-only BORRADOR_100_SNAPSHOT_NAMESPACE string alias and export from the live Modelo 100 snapshot service; make the retained secure-storage boundary tests read the canonical LIVE_BORRADOR_100_SNAPSHOT_NAMESPACE definition directly while preserving encrypted namespace, schema-version, and lifecycle behavior.

## Scope

- `Borrador 100 live snapshot service and focused storage tests`
- `accepted live snapshot persistence authority`
- `exact symbol signal`
- `focused gates`
- `cadence reference`
- `Step Record`
- `and independent code review.`

## Changes

- `M` `src/cadrumo/application/live/borrador_100.py`
- `M` `src/cadrumo/application/live/tests/test_borrador_100.py`
- `M` `src/cadrumo/application/live/tests/test_borrador_100_roundtrip.py`
- `M` `.vault/reference/2026-09-04-reachability-burndown-reference.md`
- `verify:` `uv run --no-sync ruff check src/cadrumo/application/live/borrador_100.py src/cadrumo/application/live/tests/test_borrador_100.py src/cadrumo/application/live/tests/test_borrador_100_roundtrip.py` -> `pass`
- `verify:` `uv run --no-sync pytest -q -n 0 --basetemp .tmp/pytest-s232 src/cadrumo/application/live/tests/test_borrador_100.py src/cadrumo/application/live/tests/test_borrador_100_roundtrip.py` -> `pass`
- `verify:` `uv run --no-sync python -m dev.audit.unreachable_code --confidence exact` -> `fail`
