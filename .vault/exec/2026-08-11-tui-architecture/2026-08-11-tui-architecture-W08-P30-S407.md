---
tags:
  - '#exec'
  - '#tui-architecture'
date: '2026-09-04'
modified: '2026-09-04'
body_schema: 'body-v2'
body_hash: 'sha256:31226e244f4ad4c94ef301992acbd90a7aa5ff70f4d0bef1034db55f35b25b6b'
step_id: 'S407'
related:
  - "[[2026-08-11-tui-architecture-plan]]"
---

# Render the whole registered matrix and prove no surface, state, viewport, theme or locale is silently absent. Every fixture must produce a deterministic raster and text artifact, and a fixture that CRASHES or REFUSES must be reported as such rather than skipped -- a review inventory whose own gaps are invisible proves nothing about the surfaces it claims to cover.

## Scope

- `dev/tui/cli.py and dev/tui/_raster.py`

## Changes

- `M` `dev/tui/_artifacts.py`
- `M` `dev/tui/cli.py`
- `M` `dev/tui/tests/test_tui_visual_inventory.py`
- `verify:` `uv run --no-sync pytest -q dev/tui/tests` -> `pass`
- `verify:` `uv run --no-sync python -m dev.tui render -v medium -t dark -t light` -> `pass`

## Notes

The full matrix rendered 174 frames over 87 surfaces with zero refusals and zero crashes,
carrying coverage from 37 uncovered interfaces to 29.

A render now refuses outright when the manifest leaves a requested frame unaccounted for.
A frame is accounted for by being rendered, by carrying its refusal or crash, or by being
recorded as skipped behind an earlier refusal; anything else is a silent absence that reads
to a reviewer exactly like a frame nobody asked for. The detector is proven non-vacuous by a
synthetic manifest missing one requested frame.
