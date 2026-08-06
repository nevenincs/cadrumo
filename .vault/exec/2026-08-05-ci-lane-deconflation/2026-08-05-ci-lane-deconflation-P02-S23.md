---
tags:
  - '#exec'
  - '#ci-lane-deconflation'
date: '2026-08-05'
modified: '2026-08-06'
body_schema: 'body-v1'
body_hash: 'sha256:accaeb70e45485c77a89aea47e3dd84989388eb7f6f99db77d9a7a45aa239e17'
step_id: 'S23'
related:
  - "[[2026-08-05-ci-lane-deconflation-plan]]"
---

# Fix thin_output_schema growing the schemas it thins, its oneOf inline-or-linked shape duplicates the property body so thinning a shared-defs verb enlarges it

## Scope

- `src/cadrumo/entrypoints/mcp`

## Description

- Stop the thinning helper building its alternative branch from two full copies of the property body.

## Outcome

Landed as `79cae3caaa` ("fix(mcp): stop result thinning from enlarging the schemas it thins"),
two files, 114 insertions and 41 deletions.

The mechanism the row names is specific and was confirmed: the helper built its
inline-or-linked alternation from two complete copies of the property body, so the only saving
came from pruning definitions the thinned array's items referenced. Where those definitions
stayed reachable from another property, the duplication was paid and nothing was saved, which
is why thinning a shared-definition verb enlarged it.

## Verification

    git log --format=%H --grep="stop result thinning from enlarging" -1
    git show 79cae3caaa --numstat
    (2 files, +114/-41)

## Notes

**One measurement is unreconciled and is recorded rather than resolved.** The implementing peer
reported `modelo.work.calculate` moving from 11629 to 8332. Measured at HEAD it is 11367, which
matches neither figure. The likeliest explanation is that later commits touched that verb's
schema between the two measurements, but I have not established it. The row's claim does not
rest on the absolute number: it rests on thinning no longer inflating, which the mechanism
change delivers by construction.

A second finding from the same fix belongs here because it is invisible from the row's text:
branch disjointness had relied on models forbidding extra properties. `overview.calendar`
allows them and carries a non-required profiles array, so it would have hit that hole had it
been thinned.
