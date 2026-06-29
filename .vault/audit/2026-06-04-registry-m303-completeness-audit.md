---
tags:
  - '#audit'
  - '#registry-hardening-next-work'
date: '2026-06-04'
modified: '2026-06-29'
related:
  - '[[2026-06-02-registry-hardening-next-work-plan]]'
  - '[[2026-06-02-suite-redgreen-2026-06-02-plan]]'
---

# `registry-hardening-next-work` audit: `M303 completeness manifest stale totals`

## Scope

Audited the Modelo 303 manifest-only drift surfaced by the full
`test_record_design.py` gate after the M200 repair. The audit covers both
Modelo 303 revisions in the committed registry and compares their
calculation-completeness manifests to the derived calculation closure.

## Evidence

2026-06-04 focused drift derivation reported:

- `2009-y-siguientes`: manifest-only `27`, `45`; closure-only none.
- `2023-y-siguientes`: manifest-only `27`, `45`; closure-only none.

Both revisions still declare casillas `27` and `45` as form/export fields, but
their `computed_casillas` lists no longer include those total rows. The open
suite-redgreen P09 work also names the same intent: M303 extraction profiles
should parse primitives and drop totals `27` and `45` from verification-chain
inputs.

## Current State - 2026-06-29

This finding is superseded by the current registry state.

Executable derivation through `calculation_closure_casilla_ids`,
`derive_calculation_completeness_casillas`, and
`calculation_closure_legal_refs` now reports:

- `2009-y-siguientes`: manifest exists; closure count `31`; manifest count
  `31`; derived count `31`; `27` and `45` appear in neither closure nor
  manifest; manifest-only none; closure-only none; legal refs match the
  calculation closure.
- `2023-y-siguientes`: manifest exists; closure count `53`; manifest count
  `53`; derived count `53`; `27` and `45` appear in both closure and manifest;
  manifest-only none; closure-only none; legal refs match the calculation
  closure.

The 2023 revision now declares `27` and `45` as formula-backed official Diseño
projection targets in
`src/aeat/_data/registry/aeat/modelos/303/revisions/2023-y-siguientes/formulas/0001-dr303-projections.toml`
and the matching casilla declarations carry those formulas. Keeping them in the
2023 completeness manifest is therefore required by the current calculation
closure. The 2009 revision keeps the form/export casillas but no longer includes
them in the calculation-completeness manifest.

## Findings - Closed

- **Closed High:** The stale-manifest condition no longer exists. Both M303
  revisions derive with no manifest-only rows and no closure-only rows.
- **Closed Medium:** `27` and `45` are still form/export fields in both
  revisions, but only the 2023 revision currently makes them calculation
  closure members through explicit projection formulas.
- **Closed Medium:** The old blanket repair recommendation to remove `27` and
  `45` from both manifests is no longer valid. Removing them from the 2023
  manifest would under-declare the current calculation closure.

## Closure Record

Current verification:

- `uv run python -` read-only registry derivation over Modelo 303 revisions:
  no manifest-only rows, no closure-only rows, and matching manifest legal refs.
- `test_calculation_completeness_manifests_match_their_calculation_surface` and
  `test_calculation_completeness_manifest_legal_refs_match_calculation_closure`
  remain the standing regression gates for this surface.
