---
tags:
  - '#exec'
  - '#object-name-declustering'
date: '2026-09-02'
modified: '2026-09-02'
body_schema: 'body-v2'
body_hash: 'sha256:0d28a47154cedc613c300cd635ada1fc390c18eb6167e290ad4fc99c61568dde'
step_id: 'S04'
related:
  - "[[2026-09-02-object-name-declustering-plan]]"
---

# Test manifest parsing, uniqueness constraints, stale preconditions, and fail-closed validation

## Scope

- `dev/quality/tests/test_object_name_manifest.py`

## Changes

- `A` `dev/quality/tests/test_object_name_manifest.py`
- `verify:` `uv run --no-sync pytest -q -n0 dev/quality/tests/test_object_name_manifest.py` -> `pass`
- `verify:` `uv run --no-sync ruff check dev/quality/tests/test_object_name_manifest.py dev/quality/object_name_manifest.py` -> `pass`
- `verify:` `uv run --no-sync ty check dev/quality/tests/test_object_name_manifest.py dev/quality/object_name_manifest.py` -> `pass`
- `verify:` `uv run basedpyright dev/quality/tests/test_object_name_manifest.py` -> `pass`
- `verify:` `independent current-byte S03+S04 review` -> `pass`
