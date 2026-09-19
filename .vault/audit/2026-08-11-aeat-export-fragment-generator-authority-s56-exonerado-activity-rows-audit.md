---
tags:
  - '#audit'
  - '#aeat-export-fragment-generator-authority'
date: '2026-08-11'
modified: '2026-08-11'
body_schema: 'body-v1'
body_hash: 'sha256:dcb0f9f5b593397c04552a6b41b3c8ace3dfcb19a1473977187800cdd5b441ba'
related:
  - "[[2026-08-10-aeat-export-fragment-generator-authority-adr]]"
  - "[[2026-08-10-aeat-export-fragment-generator-authority-plan]]"
---
# `aeat-export-fragment-generator-authority` audit: `S56 exonerado-390 activity-row authority`

## Scope

This formal review covered only `W04.P07.S56` against the accepted generator-authority ADR and plan. It inspected the canonical immutable Modelo 303 filing-evidence owner, ordered exonerado-390 activity rows, all six activity-code and IAE projection pairs, the Modelo 347 decision marker, reuse of `FilingEvidenceReference`, calculation-revision identity, DP30304 source resolution and projection for the 2023, 2024-early, 2024-late, 2025, and 2026 design epochs, deletion of raw marker and producer-reference envelopes, Spanish `iva` naming, duplicate-home risk, test integrity, and preservation of shared-tree peer work.

The review was read-only outside this CLI-owned audit body. Initial focused validation ran 46 tests covering the projector, calculation-revision identity, filing-evidence validation, and export refusal path; all passed. Ruff passed for the S56 projector, application value-arrival module, and focused projector tests. Basedpyright reported zero errors, warnings, or notes for those same focused files. Resolution validation ran the current real application value-arrival suite: all 11 cases passed in 40.43 seconds, covering both Modelo 347 marker states across all five design epochs plus the source-identity mismatch refusal. Ruff passed and basedpyright reported zero errors, warnings, or notes for the same application proof. Repository-wide tests, the complete registry check, emitted-byte generation, and full campaign verification were not run because this review was scoped to S56 in a heavily contended shared tree.

## Findings

### value-arrival-epoch-proof | medium | The five-epoch matrix bypasses the application value-arrival boundary

- [ ] The parameterized 2023, 2024-early, 2024-late, 2025, and 2026 proof calls `project_m303_exonerado_390_activity_rows` directly. It proves the real DP30304 source anchors, all six ordered code/IAE pairs, and the true `X` Modelo 347 projection at the registry layer, but it does not call `project_m303_exonerado_390_value_arrival`. The only application/export test reaches that boundary indirectly for 2025, stops at the intentionally unsupported layout, and never asserts the returned field projection or the false decision's blank marker. Consequently the S56 requirement for exact value arrival and projection across all five design epochs is not fully proven, including the registry-citation, source-identity, filing-year/design-epoch selection, and application error-translation boundary.

### value-arrival-epoch-proof-resolution | medium | The real five-epoch application matrix resolves the finding

- [x] Resolved on re-review. `test_m303_exonerado_390_evidence_projection` now invokes `project_m303_exonerado_390_value_arrival` through live registry snapshots and runtime schema providers for 2023, 2024-early, 2024-late, 2025, and 2026. Each epoch derives the cited immutable record-design reference, loads the real DP30304 source, and asserts the exact thirteen offsets plus all six activity-code/IAE values for both the false Modelo 347 decision projected as `None` and the true decision projected as `X`. A separate real-provider case proves a mismatched record-design identity refuses with `FilingExportError`. All eleven cases pass, so the application value-arrival and registry projection layers are now jointly proven across every required design epoch. The original open task above is closed by this resolution entry.

No unresolved critical, high, medium, or low findings remain. The live implementation has one frozen ordered row owner, uses Spanish `codigo_actividad`, `epigrafe_iae`, and `iva` vocabulary, reuses the nominal `FilingEvidenceReference`, includes the evidence in the content-addressed calculation-revision identity, derives the marker only from the typed Modelo 347 decision, and deletes the prior raw `marker_reference`, `producer_reference`, and caller-authored applicability envelope. Targeted symbol and semantic sweeps found no competing exonerado-390 row or scalar-slot owner. Focused tests contain no fakes, mocks, stubs, patches, monkeypatches, skips, or xfails.

## Recommendations

No further S56-specific remediation is required. Retain the real five-epoch application matrix alongside the lower-level exact-anchor proof so future source-selection, provider-citation, row-order, or marker regressions fail at the boundary that exports consume.

Final verdict: approved. The original medium finding is resolved, all S56 acceptance surfaces reviewed here are satisfied, and the focused behavior and static checks are green within the stated validation boundary.
