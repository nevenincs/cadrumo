---
tags:
  - '#exec'
  - '#object-name-declustering'
date: '2026-09-03'
modified: '2026-09-03'
body_schema: 'body-v2'
body_hash: 'sha256:24c0d1184b2790b083a3ca373be5b96c6ff8ff18d846e1b1eec522b633a69470'
step_id: 'S25'
related:
  - "[[2026-09-02-object-name-declustering-plan]]"
---

<!-- Machine-owned: the filename, the frontmatter, the title heading and the
     Scope list are all filled by `vaultspec-core vault add exec` from the
     originating Step row; never hand-edit them. Add no frontmatter fields.
     Wiki-links belong in `related:` only, never in the body. -->

# Reuse a receipt-local verified graph cache

## Scope

- `dev/quality/object_name_graph.py`
- `dev/quality/object_name_rehearsal.py`
- `dev/quality/tests/test_object_name_graph.py`
- `dev/quality/tests/test_object_name_rehearsal.py`

## Changes

- `M` `dev/quality/object_name_graph.py`
- `M` `dev/quality/object_name_rehearsal.py`
- `M` `dev/quality/tests/test_object_name_rehearsal.py`
- `verify:` `uv run --no-sync pytest -q -n0 dev/quality/tests/test_object_name_graph.py dev/quality/tests/test_object_name_rehearsal.py` -> `pass`
- `verify:` `uv run --no-sync pytest -q -n0 dev/quality/tests/test_object_name_rehearsal.py -k "shared_hard_edge or receipt_binds_only_declared or post_copy_byte_corruption or unsafe_system_temp"` -> `pass`
- `verify:` `uv run --no-sync ruff format --check dev/quality/object_name_graph.py dev/quality/object_name_rehearsal.py dev/quality/tests/test_object_name_graph.py dev/quality/tests/test_object_name_rehearsal.py` -> `pass`
- `verify:` `uv run --no-sync ruff check dev/quality/object_name_graph.py dev/quality/object_name_rehearsal.py dev/quality/tests/test_object_name_graph.py dev/quality/tests/test_object_name_rehearsal.py` -> `pass`
- `verify:` `uv run --no-sync ty check dev/quality/object_name_graph.py dev/quality/object_name_rehearsal.py dev/quality/tests/test_object_name_rehearsal.py` -> `pass`
