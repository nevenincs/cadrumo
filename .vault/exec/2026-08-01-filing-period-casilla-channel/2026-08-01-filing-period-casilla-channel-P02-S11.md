---
tags:
  - '#exec'
  - '#filing-period-casilla-channel'
date: '2026-08-01'
modified: '2026-08-02'
body_schema: 'body-v1'
body_hash: 'sha256:6ceacc83f913d3c3eac0a8672d841a6de8ddaccc3ba95dace1ee8aa2084028cc'
step_id: 'S11'
related:
  - "[[2026-08-01-filing-period-casilla-channel-plan]]"
---

# Retire declaration_period_ordinal and its ordinal table with their tests (zero production consumers confirmed at HEAD, no sweep needed)

## Scope

- `src/cadrumo/core/_period.py`

## Description

- Re-measure the consumer set against the current tree rather than trusting the count carried in the dispatch brief.
- Delete the `declaration_period_ordinal` property and the ordinal table it read.
- Drop the ordinal column from the parametrised accessor test and rename it to describe what it still covers.
- Remove the surviving ordinal assertion from the extended-period expressibility test, keeping the retirement explained in its docstring.

## Outcome

The projection is gone, along with its table. The property was the ordinal fill's only reason to exist, and the period token replaced it in P01.

The consumer count was re-measured rather than inherited. A tree-wide sweep at the time of deletion returned exactly three sites: the property's own definition and two test references. Zero production consumers, confirming the brief's measurement still held after the tree had moved. This mattered because the brief itself flagged that the tree moves and an earlier number could have gone stale.

The extended-period test kept its coverage without keeping the call. Its assertion that the retired projection returned nothing for an extended token could not survive the deletion, so the fact moved into the docstring, where it still explains why the token representation is the one that makes the case expressible at all. The test continues to assert the behaviour that matters: the token reaches the string channel.

Confirmed after commit that the attribute no longer exists and the module still imports.

## Notes

Deleting the property left a blank-line gap the formatter flagged. It was closed by hand rather than by running the formatter across the file, so no unrelated reformatting rode along.

The scope named only the core period module, and that proved accurate: two test files needed updating, but no production sweep was required, exactly as the Step's action text anticipated.
