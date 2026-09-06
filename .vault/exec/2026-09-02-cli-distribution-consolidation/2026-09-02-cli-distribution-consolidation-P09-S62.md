---
tags:
  - '#exec'
  - '#cli-distribution-consolidation'
date: '2026-09-06'
modified: '2026-09-06'
body_schema: 'body-v2'
body_hash: 'sha256:4e00608e5dd4052f8687dae943f0b4192119b7b51fccd673287fb5a1b9b4dc89'
step_id: 'S62'
related:
  - "[[2026-09-02-cli-distribution-consolidation-plan]]"
---

# Give the campaign preflight an explicit selection the recipe guard can see

## Scope

- `dev/packaging/campaign.py`

## Changes

- `M` `dev/packaging/campaign.py`
- `M` `dev/packaging/tests/test_preflight_recipe_selection.py`
- `M` `justfile`

## Notes

The silent deselection was worse than a count suggested. Every one of the
hundred and nine dropped tests was an integration test -- the default
expression's other exclusions matched nothing at all in that directory -- so
the preflight was excluding exactly the platform-sensitive surface it exists
to prove, on the only lanes that run this directory off one operating system.
The selection now covers everything but the performance cohort, which stays
out on its own registered policy rather than on cost.

A premise in the brief was wrong and the correction is worth keeping: the
thirty-eight serial tests reported as held are counted before the marker
expression is applied, so they were never dropped from a selection. The number
that mattered was two, and those two were executed by nothing anywhere --
selected by a parallel pass that holds them, and outside every serial lane.

The guard now reads the argument list the driver actually builds rather than a
second declaration of it, which is what let the driver sit outside its own
check for so long.

One change was made and reverted within the work: excluding the performance
cohort from the serial recipe immediately broke lane reachability, because a
comment claiming those tests were owned by a performance lane elsewhere was
false -- no such lane exists, and that recipe was their only owner. The comment
was corrected rather than the ownership moved.

## Scope

- `dev/packaging/campaign.py`

## Changes
