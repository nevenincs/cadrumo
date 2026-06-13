---
tags:
  - '#audit'
  - '#registry-hardening-next-work'
date: '2026-06-04'
modified: '2026-06-04'
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

The focused drift derivation reports:

- `2009-y-siguientes`: manifest-only `27`, `45`; closure-only none.
- `2023-y-siguientes`: manifest-only `27`, `45`; closure-only none.

Both revisions still declare casillas `27` and `45` as form/export fields, but
their `computed_casillas` lists no longer include those total rows. The open
suite-redgreen P09 work also names the same intent: M303 extraction profiles
should parse primitives and drop totals `27` and `45` from verification-chain
inputs.

## Findings

- **High:** The completeness manifests are stale for both M303 revisions. They
  still enumerate totals `27` and `45` after the calculation closure stopped
  traversing those total rows.
- **Medium:** The stale manifest rows are not missing registry declarations:
  casillas `27` and `45` remain declared/exported. The defect is only that the
  completeness manifest claims those totals are part of the calculation closure.
- **Medium:** Removing the manifest rows is the smallest source-grounded repair.
  It preserves the casilla definitions and extraction/export surfaces, while
  aligning the load-blocking calculation-completeness contract to the derived
  closure.

## Recommended repair

Remove `27` and `45` from the `completeness_manifest.casillas` list in both
Modelo 303 revisions, then run the full record-design gate and committed-registry
gate.
