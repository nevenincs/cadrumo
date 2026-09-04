---
tags:
  - '#exec'
  - '#tui-architecture'
date: '2026-09-04'
modified: '2026-09-04'
body_schema: 'body-v2'
body_hash: 'sha256:eb58974ec87f66d22b6b8a24ec183250307614d1395ed8e908d0e804828a89a9'
step_id: 'S412'
related:
  - "[[2026-08-11-tui-architecture-plan]]"
---

# Stop a review run from serving frames it did not produce. MEASURED 2026-09-04: runs/current holds 210 PNGs while the run's own manifest names 174, so 36 frames from earlier renders at other viewports sit beside the current ones with nothing marking them. A reviewer opening the directory cannot tell which frames this run produced, which is how a surface gets signed off as it looked two code changes ago. This is the inverse of the silent-absence gate S407 added: that one hid frames a run should have produced, this one shows frames it did not. The manifest is right in both cases and the directory is what misleads. Either purge the run directory before writing it, or have the index name every file the manifest does not claim.

## Scope

- `dev/tui/_artifacts.py and dev/tui/cli.py`

## Changes

- `M` `dev/tui/_artifacts.py`
- `M` `dev/tui/cli.py`
- `M` `dev/tui/tests/test_tui_visual_inventory.py`
- `verify:` `uv run --no-sync pytest -q dev/tui/tests` -> `pass`
- `verify:` `uv run --no-sync python -m dev.tui render -v medium -t dark -t light` -> `pass`

## Notes

Proven end to end, not only by unit gates: a real run reported `removed 351 stale frames
left by an earlier run` and left the directory holding exactly the 174 its manifest names.
The run says what it discarded rather than tidying silently.

The purge is deliberately narrow -- regular files under this run's png, svg and text
directories, only those the manifest does not claim; the manifest, index and log are never
touched and nothing outside the run directory is considered.

Closing this surfaced a WORSE sibling hazard, filed separately: the purge only removes
frames from EARLIER runs, so a run whose own frames span a code change is internally
inconsistent while every frame is reported as current.
