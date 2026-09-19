---
tags:
  - '#exec'
  - '#object-name-declustering'
date: '2026-09-02'
modified: '2026-09-02'
body_schema: 'body-v2'
body_hash: 'sha256:165b4a4c623a0a3ce9a03295bbe77b533af5ce5f031cd20c7050fb665b67e7db'
step_id: 'S06'
related:
  - "[[2026-09-02-object-name-declustering-plan]]"
---

# Test component isolation, shared-file coupling, stable ordering, and risk-evidence rendering

## Scope

- `dev/quality/tests/test_object_name_graph.py`

## Changes

- `M` `dev/quality/object_name_graph.py`
- `A` `dev/quality/tests/test_object_name_graph.py`
- `verify:` `uv run --no-sync pytest -q -n0 dev/quality/tests/test_object_name_graph.py` -> `pass`
- `verify:` `uv run --no-sync ruff check dev/quality/object_name_graph.py dev/quality/tests/test_object_name_graph.py` -> `pass`
- `verify:` `uv run --no-sync ty check dev/quality/object_name_graph.py dev/quality/tests/test_object_name_graph.py` -> `pass`
- `verify:` `independent combined S05/S06 CRITICAL/HIGH review` -> `pass`
