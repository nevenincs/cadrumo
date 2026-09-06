---
tags:
  - '#exec'
  - '#tui-architecture'
date: '2026-09-06'
modified: '2026-09-06'
body_schema: 'body-v2'
body_hash: 'sha256:f10ca2533459b25a1c019b01b3d8e847f7285166ff961262e3b2fdbcb2271c52'
step_id: 'S473'
related:
  - "[[2026-08-11-tui-architecture-plan]]"
---

# Close the reference walk target and correct how this campaign has been measuring, since the suite itself warns that a parallel run failure list is a subset of unknown size and every sweep behind the reported counts was run under xdist

## Scope

- `dev/audit`, `dev/packaging`, `dev/registry` (measurement only; nothing changed)

## Changes

`test_the_live_reference_walk_read_every_file` PASSES serially. That target is
closed, and I did not close it -- it was already green when I came to work it.

THE FINDING IS ABOUT MY MEASUREMENT, AND THE REPO STATED IT PLAINLY. Running
`dev/audit dev/packaging` under `-n auto` printed:

    Do NOT read this run's failure list as the set of things wrong: it is a
    subset of unknown size. Re-run the affected path serially before drawing
    any conclusion from it.

Every sweep behind the counts I have reported in this campaign was run with
`-n auto`. So "29 failures", "34 failures" and the six non-export names were
never the failing SET -- they were unreliable subsets, and the project says so
in its own runner output.

VERIFIED SERIALLY, ALL GREEN:

* `dev/packaging/tests/test_preflight_recipe_selection.py` and
  `dev/registry/tests/test_export_tree.py::test_generated_tree_validation_requires_real_loader_and_authority_selection`
  -- 40 passed.
* `dev/audit/tests/test_size_budget_baseline.py` -- 9 passed, including the
  `grandfathers_nothing` case that had just failed under xdist.
* the reference walk itself -- 1 passed.

The parallel run also produced three failures I had never seen before
(`test_size_budget_baseline`, `test_smoke_split_install_sequence`,
`test_command_spec_source_lanes`), and the one I checked passes alone. These
are heavy install and corpus tests contending for shared state, which is what
the warning is about.

## Notes

WHAT THIS COSTS THE EARLIER RECORDS. S470's "29 failures and one collection
error" and S472's "28 of 29" were both read off `-n auto` runs. The collection
error in S470 was real and reproducible serially, and S472's export-tree
findings were each confirmed serially per tree -- the provenance-only drift was
read from individual serial runs of `m151-2015-2022`, `m303-2022` and
`m303-2025`, and the single unpublished tree from the filesystem. Those
conclusions stand. What does not stand is any claim that a sweep's count was
the number of things wrong.

HOW TO MEASURE FROM HERE: a sweep may be run in parallel to FIND candidates,
but no candidate is a finding until it has failed serially, and no count is
reportable from a parallel run at all. That is the runner's own instruction and
I should have read it the first time it printed.

NOTHING WAS CHANGED IN THIS STEP. The remaining known reds are the
export-tree group stopped in S472 and the three operator decisions -- the 125
`cli.*` extras, the 5 `application.*` extras, and the
`tui.ledger.reconciliation.direction` spelling.
