---
tags:
  - '#audit'
  - '#registry-hardening-next-work'
date: '2026-06-04'
modified: '2026-06-04'
related:
  - '[[2026-06-02-registry-hardening-next-work-plan]]'
---

# `registry-hardening-next-work` audit: `M200 calculation completeness drift`

## Scope

Audited the Modelo 200 `2024-y-siguientes` calculation-completeness failure
reported by `test_record_design.py`. The audit was limited to registry
declaration data, calculation closure derivation, checked-in export refs, and
the official Diseño coverage extraction.

## Evidence

Reproduced two focused failures:

- `test_calculation_completeness_manifests_match_their_calculation_surface`
- `test_calculation_closure_bounds_the_full_diseno_coverage`

The manifest drift has no manifest-only rows. The closure-only rows are:

- `(None, "00501")`
- `(None, "00670")`
- `(None, "00671")`
- `(None, "01032")`
- `(None, "01494")`
- `(None, "01495")`
- `(None, "01498")`
- `(None, "01499")`
- `("DP200013", "00417")`
- `("DP200013", "00418")`
- `("DP200014", "00547")`
- `("DP200014", "00550")`
- `("DP200014", "DP200014:bin-aplicada-maxima")`

The full-Diseño subset failure is only the eight bare identities:

- `(None, "00501")`
- `(None, "00670")`
- `(None, "00671")`
- `(None, "01032")`
- `(None, "01494")`
- `(None, "01495")`
- `(None, "01498")`
- `(None, "01499")`

## Findings

- **High:** Eight declared M200 casillas participate in the calculation closure
  but still carry no `segmento`, so the identity-preserving closure emits
  `(None, number)` pairs that can never match the multi-segment Diseño coverage.
  The Diseño extraction and export refs map them to:
  `00501 -> DP200012`, `00670 -> DP200015`, `00671 -> DP200015`,
  `01032 -> DP200014`, and `01494/01495/01498/01499 -> DP200020D`.
- **High:** Five segment-scoped closure identities are valid registry
  declarations but absent from the completeness manifest:
  `DP200013:00417`, `DP200013:00418`, `DP200014:00547`,
  `DP200014:00550`, and `DP200014:bin-aplicada-maxima`.
- **Medium:** The bare-number declarations for `00417`, `00418`, `00547`, and
  `00550` remain legitimate accounting-statement occurrences. The calculation
  formulas already reference the segment-scoped Liquidación aliases, so the
  repair should add only the missing manifest rows, not remove or rewrite the
  unrelated bare declarations.
- **Medium:** `DP200014:bin-aplicada-maxima` is `internal_only = true` and is
  intentionally absent from the Diseño coverage, but the completeness manifest
  still needs to enumerate it because it is a formula target in the calculation
  closure.

## Recommended repair

1. Add `segmento` to the eight bare calculation-surface casilla declarations
   listed above, preserving their existing ids, numbers, labels, legal refs, and
   export refs.
2. Add the five valid closure-only segment-scoped identities to the M200
   completeness manifest.
3. Re-run `test_record_design.py` and the committed registry gate to detect any
   newly exposed manifest rows after the segment repair.
