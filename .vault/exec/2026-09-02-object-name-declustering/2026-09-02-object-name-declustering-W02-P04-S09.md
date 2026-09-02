---
tags:
  - '#exec'
  - '#object-name-declustering'
date: '2026-09-02'
modified: '2026-09-02'
body_schema: 'body-v2'
body_hash: 'sha256:2e736fb2dd0c49b11def97594290503b4a6e553ed011aaa7c7ad68bc6fb86225'
step_id: 'S09'
related:
  - "[[2026-09-02-object-name-declustering-plan]]"
---

# Implement bounded syntax-aware rename transformations with byte-precondition and allowlist enforcement

## Scope

- `dev/quality/object_name_transform.py`

## Changes

- `A` `dev/quality/object_name_transform.py`
- `verify:` `uv run --no-sync ruff check dev/quality/object_name_transform.py` -> `pass`
- `verify:` `uv run --no-sync ty check dev/quality/object_name_transform.py` -> `pass`
- `verify:` `uv run --no-sync python -m py_compile dev/quality/object_name_transform.py` -> `pass`
