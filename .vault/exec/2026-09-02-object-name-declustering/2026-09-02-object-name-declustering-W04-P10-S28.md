---
tags:
  - '#exec'
  - '#object-name-declustering'
date: '2026-09-07'
modified: '2026-09-07'
body_schema: 'body-v2'
body_hash: 'sha256:4895cc2c6a7ed1c7165c18c9d0796a2dfdc2be4eddababe41df7d63166b2c05e'
step_id: 'S28'
related:
  - "[[2026-09-02-object-name-declustering-plan]]"
---

# Require replay to compare the receipt inventory against a freshly scanned current inventory and the exact manifest digest, without also equating current inventory to the authored value, so unrelated declaration churn no longer invalidates a leaf operation whose own bytes and graph evidence are unchanged (Terra xhigh fixes and refactors)

## Scope

- `dev/quality/object_name_replay.py`

## Changes

- `M` `dev/quality/object_name_replay.py`
- `M` `dev/quality/tests/test_object_name_replay.py`
- `A` `.vault/audit/2026-09-07-object-name-declustering-s28-implementation-review-audit.md`
- `verify:` `uv run --no-sync pytest dev/quality/tests/test_object_name_replay.py -q` -> `pass`
- `verify:` `uv run --no-sync ruff check dev/quality/object_name_replay.py dev/quality/tests/test_object_name_replay.py` -> `pass`
- `verify:` `uv run --no-sync ruff format --check dev/quality/object_name_replay.py dev/quality/tests/test_object_name_replay.py` -> `pass`
- `verify:` `uv run --no-sync basedpyright dev/quality/object_name_replay.py dev/quality/tests/test_object_name_replay.py` -> `pass`
- `verify:` `uv run --no-sync ty check dev/quality/object_name_replay.py dev/quality/tests/test_object_name_replay.py` -> `pass`
- `verify:` `uv run --no-sync python -m py_compile dev/quality/object_name_replay.py dev/quality/tests/test_object_name_replay.py` -> `pass`
- `verify:` `git diff --check -- dev/quality/object_name_replay.py dev/quality/tests/test_object_name_replay.py` -> `pass`
