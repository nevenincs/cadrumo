---
tags:
  - '#exec'
  - '#cli-authority-verb-conformance'
date: '2026-07-25'
modified: '2026-07-25'
step_id: 'S199'
related:
  - "[[2026-07-15-cli-authority-verb-conformance-plan]]"
---

# Run full collect-only and classify every collection failure by owner

## Scope

- `src/cadrumo/`

## Description

Run full collect-only over the product tree and classify every collection failure by owner.

## Outcome

SATISFIED.

Command: `uv run --no-sync pytest --collect-only -q -n0 -m "" -p no:cacheprovider src/cadrumo`.
Result line `17692 tests collected in 41.63s`, exit code 0, at HEAD `482c41c59`.

Zero collection errors. The marker expression was explicitly unpinned, so the count is the whole
tree rather than the default unit lane, and 17692 is quoted as proof the corpus was non-empty.

## Fresh measurement at HEAD bc80aa28 (2026-07-28)

Re-run at the campaign-close HEAD confirms the same outcome.

Command: `uv run --no-sync pytest --collect-only -q -n0 -m "" -p no:cacheprovider src/cadrumo`
Exit: 0. Result line: `18449 tests collected in 43.67s`. HEAD: `bc80aa2808`.

Count rose from 17692 to 18449 (757 new tests across peer campaigns landing since the first
measurement). Zero collection errors. The marker was again unpinned to cover the full tree.

## Notes

A bare invocation of this path would have selected only the default unit lane and could have
reported a smaller number while looking equally green. The marker was unpinned deliberately.
