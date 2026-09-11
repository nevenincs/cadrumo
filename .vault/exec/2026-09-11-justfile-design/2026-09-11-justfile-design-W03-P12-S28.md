---
tags:
  - '#exec'
  - '#justfile-design'
date: '2026-09-11'
modified: '2026-09-11'
body_schema: 'body-v2'
body_hash: 'sha256:668a230bf14ff899a22cafd8a4fba736248c585226d036ad956bd8e696619fb6'
step_id: 'S28'
related:
  - "[[2026-09-11-justfile-design-plan]]"
---

# Place the calculation cohort under registry-domain test ownership

## Scope

- `justfile`

## Changes

- `M` `justfile`
- `M` `dev/tests/test_lane_reachability.py`
- `verify:` `uv run --no-sync pytest -q -n0 --confcutdir=dev/tests dev/tests/test_lane_reachability.py -k canonical_population` -> `pass`
