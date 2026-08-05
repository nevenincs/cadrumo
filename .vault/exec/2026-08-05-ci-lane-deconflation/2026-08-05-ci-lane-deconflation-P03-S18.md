---
tags:
  - '#exec'
  - '#ci-lane-deconflation'
date: '2026-08-05'
modified: '2026-08-05'
body_schema: 'body-v1'
body_hash: 'sha256:fee068e7fd9aeb08c39f9e0be3673447cf21b80f441fb82b7254994017929074'
step_id: 'S18'
related:
  - "[[2026-08-05-ci-lane-deconflation-plan]]"
---
# Pin which snapshot coordinates the filing-period cross-check covers, the consistency validator returns early on a null filing period so administrative-token snapshots quietly lost a check the validator's name still implies

## Scope

- `src/cadrumo/domain/calculations/registry/tests/test_snapshot_filing_period_coverage.py`

## Description

- Pin the five administrative coordinates as carrying no filing period.
- Pin two real filing coordinates as carrying one that agrees with its coordinates, as the positive control.
- State the validator's reduced coverage as an asserted fact rather than leaving it to be inferred.

## Outcome

Landed as commit `73423f0386` ("test(registry): declare which snapshots the filing-period
cross-check covers"), one file, 94 insertions and 0 deletions. Sha resolved with
`git log --format=%H --grep=` and read with `git show <sha> --numstat`, never with
`git show HEAD`.

The hazard the row names is real and unchanged by this work: a snapshot addressed by a
token that names no period a taxpayer files in carries a null filing period, so the
consistency validator returns early and cross-checks nothing. The early return is correct —
there is no filing period to check against — but it leaves the validator covering a smaller
set than its name implies, with nothing stating where the boundary lies.

The landed gate converts that boundary from an inference into an asserted fact. It pins the
five administrative coordinates as carrying no filing period, covering both owning modelos
rather than only the three of the first, and pins real filing coordinates as carrying one
that agrees with its coordinates.

## Notes

The positive-control half is load-bearing rather than decorative, and this is the property
that makes the gate a gate. A pin asserting only "these five coordinates carry no filing
period" would pass equally well if the filing period were null everywhere, including for
coordinates where its absence would be a defect. The filing-coordinate arms are what
exclude that reading, so removing them would leave a gate that cannot distinguish the
condition it documents from a total failure of the field it reads.

Executed with the parity gate of `S11` in one invocation: 15 passed. The file carries both
the integration and hex-domain markers, so a default-lane invocation deselects it entirely
and reports `NOTHING RAN`.

This row is a declaration of coverage, not a behaviour change. Nothing in the validator
moved, and the gate would have passed the day before the filing-period type split landed.
Its value is that the reduced coverage is now written where it reds if it changes: if a
future change gives an administrative snapshot a filing period, or takes one away from a
filing coordinate, the assertion fails and names which coordinate moved.

The pinned coordinates are the same set the type-boundary work established as the
administrative vocabulary, so this gate and the selector parity gate of `S11` now hold that
set from two directions — one asserting every declared selector token is accepted by the
production validator, the other asserting which of those tokens yield a snapshot with no
filing period.
