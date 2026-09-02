---
tags:
  - '#exec'
  - '#object-name-declustering'
date: '2026-09-02'
modified: '2026-09-02'
body_schema: 'body-v2'
body_hash: 'sha256:6b71f6deb28a16c2bc72ef5f92a6ad229c86e89b8a9f6478a72de210fc54aedb'
step_id: 'S05'
related:
  - "[[2026-09-02-object-name-declustering-plan]]"
---

<!-- Machine-owned: the filename, the frontmatter, the title heading and the
     Scope list are all filled by `vaultspec-core vault add exec` from the
     originating Step row; never hand-edit them. Add no frontmatter fields.
     Wiki-links belong in `related:` only, never in the body. -->

# Build deterministic hard-edge operation-to-file components and explainable risk ordering from installed analyzer signals

## Scope

- `dev/quality/object_name_graph.py`

## Changes

- `A` `dev/quality/object_name_graph.py`
- `verify:` `uv run --no-sync ruff check dev/quality/object_name_graph.py` -> `pass`
- `verify:` `uv run --no-sync ty check dev/quality/object_name_graph.py` -> `pass`
- `verify:` `uv run --no-sync python -m py_compile dev/quality/object_name_graph.py` -> `pass`
- `verify:` `git diff --check -- dev/quality/object_name_graph.py` -> `pass`
