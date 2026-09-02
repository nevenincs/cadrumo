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

# Build deterministic hard-edge operation-to-file components and explainable risk ordering from installed analyzer signals

## Scope

- `dev/quality/object_name_graph.py`

## Changes

- `A` `dev/quality/object_name_graph.py`
- `verify:` `uv run --no-sync ruff check dev/quality/object_name_graph.py` -> `pass`
- `verify:` `uv run --no-sync ty check dev/quality/object_name_graph.py` -> `pass`
- `verify:` `uv run --no-sync python -m py_compile dev/quality/object_name_graph.py` -> `pass`
- `verify:` `git diff --check -- dev/quality/object_name_graph.py` -> `pass`
