---
tags:
  - '#exec'
  - '#justfile-design'
date: '2026-09-11'
modified: '2026-09-11'
body_schema: 'body-v2'
body_hash: 'sha256:1bc5335581aeb6cd767f2ac794881811b632ee80370166ae194981aa96ee5839'
step_id: 'S57'
related:
  - "[[2026-09-11-justfile-design-plan]]"
---

# Reassign every tooling test population from the temporary backstop to a canonical subject or capability owner before closure

## Scope

- `dev`

## Changes

- `M` `justfile`
- `M` `dev/tests/test_lane_reachability.py`
- `verify:` `uv run --no-sync pytest -q -n0 --confcutdir=dev/tests dev/tests/test_lane_reachability.py -k capability_holds_out` -> `pass`
