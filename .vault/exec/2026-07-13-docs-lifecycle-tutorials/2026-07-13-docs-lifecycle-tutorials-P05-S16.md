---
tags:
  - '#exec'
  - '#docs-lifecycle-tutorials'
date: '2026-07-13'
modified: '2026-07-13'
body_hash: 'sha256:a3d416533b16dcaf6664c98d45a8e118f6afaa6e9211ff67a9f3d26fb2ee47a9'
step_id: 'S16'
related:
  - "[[2026-07-13-docs-lifecycle-tutorials-plan]]"
---

# Run the documented-command conformance gate and the Sphinx nitpicky build gate

## Scope

- `fix every failure the campaign's edits caused`
- `docs src/aeat/entrypoints/cli/tests/test_documented_command_conformance.py dev/docs/tests/test_docs_build.py`

## Description

- Run `uv run --no-sync pytest
  src/aeat/entrypoints/cli/tests/test_documented_command_conformance.py -m
  integration -q`: 62 passed - every command cited across the campaign's new
  and reworked pages resolves against the live CLI tree.
- Run `uv run --no-sync pytest dev/docs/tests/test_docs_build.py -q`
  (full-log background capture, read from disk): first pass FAILED with one
  unique warning - `The parent of a 'grid-item' should be a 'grid-row'
  [design.grid]` at the new `docs/tutorials/index.md` grid, whose colon
  fences were nested inverted (outer 3, inner 4).
- Fix the nesting (outer `::::{grid}`, inner `:::{grid-item-card}`) and
  re-run: 12 passed in 185s. Both gates green.

## Outcome

Both campaign gates are green at this commit. The reviewer-feared Sphinx
orphan trip on `docs/USERDOCS-KICKOFF-BRIEF.md` did not occur (the nitpicky
build passed with the file present); its retirement is tracked separately as
P05.S18.

## Notes

Full gate logs captured without truncation per the background-capture rule
(first-run failure list preserved on disk before slicing).
