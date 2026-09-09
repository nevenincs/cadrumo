---
tags:
  - '#exec'
  - '#reachability-burndown'
date: '2026-09-09'
modified: '2026-09-09'
body_schema: 'body-v2'
body_hash: 'sha256:b28b0ab0a56b759fc0d5bd68ae0ddc450fec5cd7d1a6b17834b1807ec4efbdd3'
step_id: 'S358'
related:
  - "[[2026-09-04-reachability-burndown-plan]]"
---

<!-- Machine-owned: the filename, the frontmatter, the title heading and the
     Scope list are all filled by `vaultspec-core vault add exec` from the
     originating Step row; never hand-edit them. Add no frontmatter fields.
     Wiki-links belong in `related:` only, never in the body. -->

# Delete the test-only flow back-page navigation verb left after removal of its sole frontend.

## Scope

- `flow engine API and tests`
- `exact unused-symbol signal`

## Changes

- `M` `src/cadrumo/application/flows/engine.py`
- `M` `src/cadrumo/application/flows/tests/test_engine.py`
- `M` `.vault/reference/2026-09-04-reachability-burndown-reference.md`
- `verify:` `uv run --no-sync pytest -n0 -m "" src/cadrumo/application/flows/tests/test_engine.py -q` -> `pass (16 passed)`
- `verify:` `uv run --no-sync ruff check src/cadrumo/application/flows/engine.py src/cadrumo/application/flows/tests/test_engine.py` -> `pass`
- `verify:` `uv run --no-sync python -m dev.audit.unreachable_code --confidence exact` -> `pass (263 unused symbols; down from 264)`
