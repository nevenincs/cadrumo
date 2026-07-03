---
tags:
  - '#audit'
  - '#registry-hardening-next-work'
date: '2026-06-04'
modified: '2026-06-29'
related:
  - '[[2026-06-02-registry-hardening-next-work-plan]]'
---

# `registry-hardening-next-work` audit: `M200 calculation completeness drift`

## Scope

Audited the Modelo 200 `2024-y-siguientes` calculation-completeness failure
reported by `test_record_design.py`. The audit was limited to registry
declaration data, calculation closure derivation, checked-in export refs, and
the official Diseño coverage extraction.

## Current State — 2026-06-29

The M200 completeness drift reproduced by this audit is closed in the current
registry:

- The listed calculation-surface casillas are present in the M200
  `completeness-manifest.toml` with reviewed segment metadata.
- The five segment-scoped Liquidación closure identities are present in the
  manifest.
- `DP200014:bin-aplicada-maxima` remains intentionally app-internal and
  `internal_only = true`; the full-Diseño subset gate subtracts internal-only
  metadata before requiring exported closure casillas to appear in the official
  Diseño coverage.
- The full `test_record_design.py` suite passes in the current tree.

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

- **Closed High:** the eight M200 calculation-surface casillas that previously
  emitted `(None, number)` closure identities are now enumerated in
  `completeness-manifest.toml` with their reviewed Diseño segments:
  `00501 -> DP200012`, `00670 -> DP200015`, `00671 -> DP200015`,
  `01032 -> DP200014`, and `01494/01495/01498/01499 -> DP200020D`.
- **Closed High:** the five segment-scoped closure identities are present in the
  completeness manifest:
  `DP200013:00417`, `DP200013:00418`, `DP200014:00547`,
  `DP200014:00550`, and `DP200014:bin-aplicada-maxima`.
- **Closed Medium:** the bare-number declarations for `00417`, `00418`, `00547`,
  and `00550` remain legitimate accounting-statement occurrences; the
  calculation formulas reference the segment-scoped Liquidación aliases, so the
  repair preserved the unrelated bare declarations.
- **Closed Medium:** `DP200014:bin-aplicada-maxima` remains enumerated in the
  completeness manifest because it is a formula target, while the
  full-Diseño coverage assertion treats it as an internal-only exception.

## Closure Record

1. The eight formerly bare calculation-surface identities are represented in the
   manifest with reviewed segment metadata.
2. The five valid closure-only segment-scoped identities were added to the M200
   completeness manifest.
3. The full-Diseño subset gate now subtracts `internal_only` casillas before
   comparing exported closure identities against Diseño coverage.

Current verification on 2026-06-29: `test_record_design.py` passes.
