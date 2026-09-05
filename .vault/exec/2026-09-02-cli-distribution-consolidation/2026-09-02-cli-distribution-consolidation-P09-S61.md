---
tags:
  - '#exec'
  - '#cli-distribution-consolidation'
date: '2026-09-05'
modified: '2026-09-05'
body_schema: 'body-v2'
body_hash: 'sha256:1911cccbad96411506186a54df3f9e2541c9f8cb7cc4162391fa4fa61e987610'
step_id: 'S61'
related:
  - "[[2026-09-02-cli-distribution-consolidation-plan]]"
---

# Stop every packaging lane from re-running the whole packaging suite before it starts

## Scope

- `dev/packaging/campaign.py`

## Changes

- `M` `dev/packaging/tests/test_container_base_image_singularity.py`
- `M` `dev/packaging/tests/test_preflight_recipe_selection.py`

## Notes

The premise that the per-lane preflight is redundant did not survive
measurement. Eighty-one of five hundred tests carry a real behavioural fork on
the operating system -- junctions against symlinks, permission bits, descriptor
inheritance, launcher stubs -- and this campaign is the ONLY place the
directory runs anywhere but Linux. Skipping the preflight would have deleted
that coverage to buy speed.

But the cost is not in that subset: one platform-sensitive test appears in the
twenty-five slowest, and the top ten are platform-invariant static analysis.
So the answer was neither skipping nor partitioning, but making the invariant
work cheap. A declaring-surface scan visited seven hundred thousand paths to
reach thirty-nine thousand because it pruned after walking rather than during,
and a recipe collection booted the same pytest twice per case. Both fixed with
the surface set proven identical, not merely similar.

Partitioning was refused for a second reason worth keeping: the preflight
passes no marker expression at all, so it inherits the project default and
silently drops a hundred and nine tests, holding thirty-eight more as a warning
rather than a failure. The guard that exists to catch exactly that reads the
recipe surface and never the driver, so the driver sits outside it. Optimising
a selection that is already wrong would have built on sand.

## Scope

- `dev/packaging/campaign.py`

## Changes
