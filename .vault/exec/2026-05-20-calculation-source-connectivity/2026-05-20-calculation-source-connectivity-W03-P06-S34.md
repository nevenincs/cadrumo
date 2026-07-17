---
tags:
  - '#exec'
  - '#calculation-source-connectivity'
date: '2026-07-04'
modified: '2026-07-17'
step_id: 'S34'
related:
  - "[[2026-05-20-calculation-source-connectivity-plan]]"
---

# [RETIRED] Extend category profile lookup to accept filing year and CCAA key

## Reconciliation outcome

Retired on 2026-07-17. The selector layered an always-empty regional override
onto a state-law category table and was reachable only through synthetic test
profiles. The resolver, selector, exports, and synthetic coverage were removed.
The material below is historical execution evidence, not current architecture.

## Scope

- `src/aeat/core/resources/_repos/category_profiles.py`

## Description

Add `resolve_region_category_profiles(year)` (the per-comunidad override resolver) and `select_deductibility_profile()` (state profile / region override / fail-closed) to the renta domain. Realise the "filing year plus CCAA" lookup intent as an additive resolver-plus-selector layered over the existing year-keyed category profiles, so the state pure-year lookup stays byte-identical.

## Outcome

Region-aware category-profile selection is available and consumed by the aggregation path. Pure-year state lookups are unchanged. Landed in commit `1ca532e93a`. A domain test pins all four selection branches. Gates green.

## Notes

Implements ADR `2026-07-04-renta-region-deductibility` decision D2-A. The plan's `int -> (int, CCAA)` `CategoryProfileRepository` key-widening intent is satisfied by the additive resolver + selector rather than mutating the generic `ResourceCacheRepository[..., int]` key type — the same backward-compatible outcome (pure-year lookups untouched) with far smaller blast radius.
