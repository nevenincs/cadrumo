---
tags:
  - '#exec'
  - '#reachability-burndown'
date: '2026-09-07'
modified: '2026-09-07'
body_schema: 'body-v2'
body_hash: 'sha256:e8aa0e39c0a145b1842474fd47ec28700adf60146cea5cfef7d5ac89b1da3d04'
step_id: 'S84'
related:
  - "[[2026-09-04-reachability-burndown-plan]]"
---

<!-- Machine-owned: the filename, the frontmatter, the title heading and the
     Scope list are all filled by `vaultspec-core vault add exec` from the
     originating Step row; never hand-edit them. Add no frontmatter fields.
     Wiki-links belong in `related:` only, never in the body. -->

# Close the last open module decision by finding the caller the entry said was gone: the registered-values projection feeds a mapping the TUI flow screen threads through its presenter and reads to fill the review overview's registered cell, and every link exists except the composition that would pass it, which sits inside the frozen TUI prefix both ratchets defer to. Reclassify from orphaned to deferred-by-ownership rather than widening the ratchet's transitive deferral, which is read from the live import graph and deliberately excludes a supplier nothing imports yet.

## Scope

- `dev/audit/reachability_classification.toml`

## Changes

- `M` `dev/audit/reachability_classification.toml`
- `verify:` open module decisions 1 -> 0; every module-level finding in this
  campaign is now adjudicated
- `verify:` module ratchet, secure-store gate and docstring ratchet exit 0;
  duplication 10 / 0.05%; dead code 0; unused 1040, exact 411
- `verify:` symbol ratchet exits 1 on the same two peer-introduced lines
- `verify:` ledger validated -- no double classification, cited paths resolve

## Notes

The entry said the caller was gone. It is not: `project_registered_values`
produces the mapping `entrypoints/tui/flows/app.py` threads through `FlowScreen`
and reads at line 1257 for the review overview's registered cell. Every link in
that chain exists except the composition that would pass it --
`select_flow_frontend` takes `registered_values` and has no shipped caller, and
no module outside the TUI package references `FlowScreen` or `run_flow_tui` at
all.

So the projection belongs to the frozen TUI cluster, and wiring the composition
is not this campaign's to do.

The module ratchet could not have reached this on its own, and should not be
changed to. Its transitive deferral is read from the live import graph, and a
supplier whose consumer does not import it YET supplies nothing -- a bound its
own docstring states deliberately, because loosening it would exempt the entire
backlog. The judgement is exactly what this ledger exists to carry, and the
ratchet's `frozen_prefixes` comment already names the shape: the cluster's
application-layer projections live outside the prefix because the dependency
direction requires it.

Fifty-five symbol decisions remain open. Every one is now a symbol-level
question; the module tier is finished.
