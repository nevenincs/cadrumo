---
tags:
  - '#exec'
  - '#reachability-burndown'
date: '2026-09-09'
modified: '2026-09-09'
body_schema: 'body-v2'
body_hash: 'sha256:7e28650fe6d541f9ca32921bb110425b3a4fed4c717c7f926063221fba421fbc'
step_id: 'S340'
related:
  - "[[2026-09-04-reachability-burndown-plan]]"
---

<!-- Machine-owned: the filename, the frontmatter, the title heading and the
     Scope list are all filled by `vaultspec-core vault add exec` from the
     originating Step row; never hand-edit them. Add no frontmatter fields.
     Wiki-links belong in `related:` only, never in the body. -->

# Remove the namespace-registry source census and its pinned repository vocabulary while retaining direct registry behavior tests.

## Scope

- `namespace registry tests and reachability cadence reference`

## Changes

- `M` `src/cadrumo/adapters/persistence/storage/tests/test_namespace_registry.py`
- `M` `.vault/reference/2026-09-04-reachability-burndown-reference.md`
- `verify:` `uv run --no-sync pytest -q src/cadrumo/adapters/persistence/storage/tests/test_namespace_registry.py` -> `pass`
- `verify:` `uv run --no-sync ruff check src/cadrumo/adapters/persistence/storage/tests/test_namespace_registry.py` -> `pass`
- `verify:` `uv run --no-sync python -m dev.audit.unreachable_code --confidence exact` -> `pass`
