---
tags:
  - '#exec'
  - '#tui-architecture'
date: '2026-09-04'
modified: '2026-09-04'
body_schema: 'body-v2'
body_hash: 'sha256:3b10b5054c92e1da9b36feb7178f2152c8f0466081d25c04f18ed358b9c09aed'
step_id: 'S412'
related:
  - "[[2026-08-11-tui-architecture-plan]]"
---

<!-- Machine-owned: the filename, the frontmatter, the title heading and the
     Scope list are all filled by `vaultspec-core vault add exec` from the
     originating Step row; never hand-edit them. Add no frontmatter fields.
     Wiki-links belong in `related:` only, never in the body. -->

# Stop a review run from serving frames it did not produce. MEASURED 2026-09-04: runs/current holds 210 PNGs while the run's own manifest names 174, so 36 frames from earlier renders at other viewports sit beside the current ones with nothing marking them. A reviewer opening the directory cannot tell which frames this run produced, which is how a surface gets signed off as it looked two code changes ago. This is the inverse of the silent-absence gate S407 added: that one hid frames a run should have produced, this one shows frames it did not. The manifest is right in both cases and the directory is what misleads. Either purge the run directory before writing it, or have the index name every file the manifest does not claim.

## Scope

- `dev/tui/_artifacts.py and dev/tui/cli.py`

## Changes

- `M` `dev/tui/_artifacts.py`
- `M` `dev/tui/cli.py`
- `M` `dev/tui/tests/test_tui_visual_inventory.py`
- `verify:` `uv run --no-sync pytest -q dev/tui/tests` -> `pass`

## Notes

A run now removes the frames its own manifest does not claim, and says how many went. The
purge is deliberately narrow: regular files under this run's png, svg and text directories
only, and only those the manifest does not name -- the manifest, index and log are never
touched and nothing outside the run directory is considered.

This is the inverse of the gate S407 added. That one catches frames a run should have
produced and did not; this catches frames it serves but did not produce. The manifest was
correct in both cases and the directory was what misled.

Worth recording because the first version of the test failed and the code was right: the
fixture used bare filenames while a real manifest stores png/<name>.png. The fix belonged in
the fixture, checked against a real manifest before anything was changed.
