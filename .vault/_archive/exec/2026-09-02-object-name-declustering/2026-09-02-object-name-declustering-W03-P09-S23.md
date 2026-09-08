---
tags:
  - '#exec'
  - '#object-name-declustering'
date: '2026-09-02'
modified: '2026-09-02'
body_schema: 'body-v2'
body_hash: 'sha256:aa2480444b1cd0d6235bdde9b4d938f6ddf6ec8c9f03d950f4e87ca379d9a72e'
step_id: 'S23'
related:
  - "[[2026-09-02-object-name-declustering-plan]]"
---

# Bind manifest staleness to selected identities and declared bytes

## Scope

- `dev/quality/object_name_manifest.py`
- `dev/quality/tests/test_object_name_manifest.py`

## Changes

- `M` `dev/quality/object_name_manifest.py`
- `M` `dev/quality/tests/test_object_name_manifest.py`
- `verify:` `uv run --no-sync pytest -q -n0 dev/quality/tests/test_object_name_manifest.py` -> `pass`
- `verify:` `uv run --no-sync ruff check dev/quality/object_name_manifest.py dev/quality/tests/test_object_name_manifest.py` -> `pass`
