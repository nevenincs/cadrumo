---
tags:
  - '#exec'
  - '#object-name-declustering'
date: '2026-09-02'
modified: '2026-09-02'
body_schema: 'body-v2'
body_hash: 'sha256:486f8b09080445a5ccdd1867635136236e6509c5e74a020ff3d2485a270555f8'
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
