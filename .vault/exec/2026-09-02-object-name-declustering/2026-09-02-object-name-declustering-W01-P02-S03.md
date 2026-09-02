---
tags:
  - '#exec'
  - '#object-name-declustering'
date: '2026-09-02'
modified: '2026-09-02'
body_schema: 'body-v2'
body_hash: 'sha256:dfd2172b47e42398f352ffcf3be2e71f0581d94b69648f0d2bad4a7021646ffe'
step_id: 'S03'
related:
  - "[[2026-09-02-object-name-declustering-plan]]"
---

# Implement the typed reviewed rename-manifest loader and reject ambiguous, incomplete, or stale intent

## Scope

- `dev/quality/object_name_manifest.py`

## Changes

- `A` `dev/quality/object_name_manifest.py`
- `verify:` `uv run ruff check dev/quality/object_name_manifest.py` -> `pass`
- `verify:` `uv run ty check dev/quality/object_name_manifest.py` -> `pass`
- `verify:` `uv run basedpyright dev/quality/object_name_manifest.py` -> `pass`
- `verify:` `uv run python -m py_compile dev/quality/object_name_manifest.py` -> `pass`
- `verify:` `live inventory binding and stale-refusal probe` -> `pass`
