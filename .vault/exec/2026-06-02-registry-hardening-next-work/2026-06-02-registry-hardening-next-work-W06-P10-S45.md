---
tags:
  - '#exec'
  - '#registry-hardening-next-work'
date: '2026-06-04'
modified: '2026-06-29'
step_id: 'S45'
related:
  - '[[2026-06-02-registry-hardening-next-work-plan]]'
---

# `registry-hardening-next-work` `W06.P10.S45` repair

Scope: remove stale M303 total rows from completeness manifests after closure derivation proves they are no longer calculated.

## Description

- Removed manifest rows `27` and `45` from the Modelo 303
  `2009-y-siguientes` completeness manifest.
- Removed manifest rows `27` and `45` from the Modelo 303
  `2023-y-siguientes` completeness manifest.
- Preserved the M303 casilla declarations, export layouts, extraction profiles,
  formulas, verification expectations, legal refs, and source refs.

## Outcome

S45 completed. Both M303 revisions now derive with no manifest-only rows and no
closure-only rows. The full `test_record_design.py` gate passed with 41 tests.

## Notes

Verification also passed for `test_committed_registry.py` and
`test_registry_reviewability.py`.

## Current State - 2026-06-29

This repair record is historical. Subsequent current registry work made
`2023-y-siguientes` casillas `27` and `45` formula-backed official Diseño
projection targets, so they are again valid completeness-manifest members for
that revision. The current split is: `2009-y-siguientes` excludes `27` and `45`
from closure and manifest; `2023-y-siguientes` includes them in both.
