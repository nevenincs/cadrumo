---
tags:
  - '#exec'
  - '#object-name-declustering'
date: '2026-09-02'
modified: '2026-09-02'
body_schema: 'body-v2'
body_hash: 'sha256:7a258c8725120b228d90045f9ba9c0a30cd7b6648df750a0f89eb06b71c4b455'
step_id: 'S14'
related:
  - "[[2026-09-02-object-name-declustering-plan]]"
---

# Test stale receipts, unexpected paths, failed gates, interrupted writes, and successful replay

## Scope

- `dev/quality/tests/test_object_name_replay.py`

## Changes

- `A` `dev/quality/tests/test_object_name_replay.py`
- `M` `dev/quality/object_name_replay.py`
- `verify:` `uv run --no-sync pytest -q -n0 dev/quality/tests/test_object_name_replay.py` -> `pass` (`52 passed`)
- `verify:` `uv run --no-sync ruff format --check dev/quality/tests/test_object_name_replay.py dev/quality/object_name_replay.py` -> `pass`
- `verify:` `uv run --no-sync ruff check dev/quality/tests/test_object_name_replay.py dev/quality/object_name_replay.py` -> `pass`
- `verify:` `uv run --no-sync ty check dev/quality/object_name_replay.py dev/quality/tests/test_object_name_replay.py` -> `pass`
- `verify:` `uv run --no-sync basedpyright dev/quality/object_name_replay.py dev/quality/tests/test_object_name_replay.py` -> `pass`
- `verify:` `uv run --no-sync python -m compileall -q dev/quality/object_name_replay.py dev/quality/tests/test_object_name_replay.py` -> `pass`
- `verify:` `git diff --check -- dev/quality/object_name_replay.py dev/quality/tests/test_object_name_replay.py` -> `pass`
- `verify:` `independent S14 transaction-integrity re-review` -> `pass`

## Notes

Shared-tree commits `8f9c2ededc` and `a2b9aa24fa` materially landed S14
before Step closure. Commit `8f9c2ededc` also contains unrelated unreachable-
code audit changes; this record claims only the replay implementation and test
paths above. S14 proves in-process `BaseException` rollback and retained orphan
evidence; it does not claim process-crash recovery.
