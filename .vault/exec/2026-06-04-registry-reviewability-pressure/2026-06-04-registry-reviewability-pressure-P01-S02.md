---
tags:
  - '#exec'
  - '#registry-reviewability-pressure'
date: '2026-06-04'
modified: '2026-06-04'
step_id: 'S02'
related:
  - '[[2026-06-04-registry-reviewability-pressure-plan]]'
---

# `registry-reviewability-pressure` `P01.S02` decision

Scope: decide whether M123 and M369 inline-only revision directories need
mechanical fragment splits now or tracked deferral.

## Description

- Compared M123 and M369 line-count pressure and split feasibility.
- Authorised a mechanical M123 split for P02.S03.
- Deferred M369 split work because it is consistency-only and not near any
  reviewability threshold.
- Deferred row-width gate tightening until M100 row formatting is addressed.

## Outcome

S02 completed. P02 should split M123 only, then verify loader equivalence and
reviewability gates. M369 remains tracked as a deferred consistency candidate.

## Notes

No registry data files were edited in this step.
