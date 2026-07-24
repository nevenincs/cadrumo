---
tags:
  - '#exec'
  - '#profile-setup-flow'
date: '2026-07-23'
modified: '2026-07-23'
step_id: 'S01'
related:
  - "[[2026-07-23-profile-setup-flow-plan]]"
---

# Reconcile the dual TaxpayerProfile derivation paths with a side-by-side read of load_active_taxpayer_profile versus taxpayer_profile_from_mapping, consolidating or documenting the layering before any commit-path wiring

## Scope

- `src/cadrumo/domain/deadlines/_profiles.py`

## Description

- Read `load_active_taxpayer_profile`, `projection_for_taxpayer`, and
  `taxpayer_profile_from_mapping` side by side and traced every production
  constructor call site.
- Establish the layering verdict: the three symbols form one layered
  coercion chain (state resolution -> fact projection -> typed
  construction), not parallel derivations.
- Find the one genuine bypass: the workflow state projection built its
  `TaxpayerProfile` from a bare selector-keyed mapping with a local
  hardcoded default, skipping `projection_for_taxpayer`, while the shared
  coercer reads a mix of path-keyed and selector-aliased fields - each
  entry point silently blanked a different field family.
- Merge both key spaces in `projection_for_taxpayer`'s record branch
  (`_merged_taxpayer_values`) and delegate the state projection helper to
  it.
- Add a selector-alias regression (fiscal-address family populates from a
  record) and a chain-parity regression (record and merged flat mapping
  coerce identically) to the projection test module.

## Outcome

Committed as `bc794c9699` (explicit pathspec: `_projections.py`,
`state_projection.py`, `test_projections.py`). Projection suite 12/12 and
state-projection suite 20/20 green.

## Notes

The still-open composition question between `domain/contribuyente`
family math and the derived-fact injectors is out of this Step's scope
and remains a flagged prerequisite for the descendant/family Steps only.

