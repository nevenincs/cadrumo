---
tags:
  - '#exec'
  - '#object-name-declustering'
date: '2026-09-02'
modified: '2026-09-02'
body_schema: 'body-v2'
body_hash: 'sha256:9e53249adbee242e085d33375d1e263f009630f187bca6a69e20833d8f8f4eaf'
step_id: 'S24'
related:
  - "[[2026-09-02-object-name-declustering-plan]]"
---

# Bind rehearsal receipts and replay drift checks to the reviewed component

## Scope

- `dev/quality/object_name_rehearsal.py`
- `dev/quality/object_name_replay.py`
- `dev/quality/tests/test_object_name_rehearsal.py`
- `dev/quality/tests/test_object_name_replay.py`

## Changes

- `M` `dev/quality/object_name_rehearsal.py`
- `M` `dev/quality/object_name_replay.py`
- `M` `dev/quality/tests/test_object_name_rehearsal.py`
- `M` `dev/quality/tests/test_object_name_replay.py`
- `verify:` `uv run --no-sync pytest -q -n0 dev/quality/tests/test_object_name_manifest.py dev/quality/tests/test_object_name_rehearsal.py` -> `pass`
- `verify:` `uv run --no-sync pytest -q -n0 dev/quality/tests/test_object_name_replay.py` -> `pass`
- `verify:` `uv run --no-sync ruff check dev/quality/object_name_manifest.py dev/quality/object_name_rehearsal.py dev/quality/object_name_replay.py dev/quality/tests/test_object_name_manifest.py dev/quality/tests/test_object_name_rehearsal.py dev/quality/tests/test_object_name_replay.py` -> `pass`
