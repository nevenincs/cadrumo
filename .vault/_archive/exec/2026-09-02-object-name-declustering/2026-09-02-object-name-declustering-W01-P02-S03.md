---
tags:
  - '#exec'
  - '#object-name-declustering'
date: '2026-09-02'
modified: '2026-09-02'
body_schema: 'body-v2'
body_hash: 'sha256:cfce04605b5dbaf452316712375d822eb1b65997f1124e91be20e7771292ecca'
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
- `verify:` `independent current-byte HIGH/CRITICAL re-review` -> `pass`
