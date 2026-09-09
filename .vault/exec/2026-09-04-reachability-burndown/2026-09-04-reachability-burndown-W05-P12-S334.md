---
tags:
  - '#exec'
  - '#reachability-burndown'
date: '2026-09-09'
modified: '2026-09-09'
body_schema: 'body-v2'
body_hash: 'sha256:e712b7b5ca0db39e47950070763d8870a99c0b1c49bd9d9579a096994deb400a'
step_id: 'S334'
related:
  - "[[2026-09-04-reachability-burndown-plan]]"
---

# Replace the mixed-format container literal census with direct canonical Dockerfile checks

## Scope

- `container base-image tests`
- `canonical resolver behavior`
- `exact reachability`
- `cadence reference`
- `and Step Record`

## Changes

- `D` `dev/packaging/tests/test_container_base_image_singularity.py`
- `A` `dev/packaging/tests/test_container_base_image.py`
- `M` `.vault/reference/2026-09-04-reachability-burndown-reference.md`
- `verify:` `uv run --no-sync pytest -q dev/packaging/tests/test_container_base_image.py` -> `pass`
- `verify:` `uv run --no-sync python -m dev.audit.unreachable_code --confidence exact` -> `fail`

## Notes

Exact remeasurement reports the campaign's remaining live signal: 36 unreachable modules and 278 unused symbols.
