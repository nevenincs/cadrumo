---
tags:
  - '#audit'
  - '#casilla-schema'
date: '2026-08-11'
modified: '2026-08-11'
body_schema: 'body-v1'
body_hash: 'sha256:a2bb6b9611773eba782cb59d466ec9aea4afb6eeb692f12d1a1ed17b6dc41463'
related:
  - "[[2026-08-10-casilla-schema-plan]]"
  - "[[2026-08-10-casilla-schema-research]]"
---
# `casilla-schema` audit: `S07 internal-only manifest reconciliation`

## Scope

Reviewed W01.P02.S07 against the approved plan, research, canonical registry authority, calculation-grounding and quality rules. The review covered the complete implementations of `derive_record_design_coverage` and `validate_calculation_completeness`, the M200 2024-and-later completeness manifest, and the changed real registry tests. The required contract is that calculation completeness is the calculation closure minus every casilla declared `internal_only`, identically for single- and multi-segment modelos, with no compatibility or tolerant alternate path.

## Findings

No actionable findings.

The derivation now excludes `internal_only` casillas before the single-versus-multi-segment branch. Therefore neither branch can enroll those implementation-only nodes. The validator independently applies the same semantic denominator to required closure membership. Exact checked-in-manifest drift coverage supplies the stronger equality gate, so the validator's intentional lower-bound check does not permit the removed M200 row to return unnoticed.

The M200 manifest change deletes exactly `DP200014:bin-aplicada-maxima`, an internal-only calculation-closure node. A real-corpus probe covered 55 single-segment manifest revisions and one multi-segment manifest revision and found zero overlap between derived coverage and internal-only metadata. The multi-segment case is M200; real single-segment internal-only cases include M100, M131, and M303 revisions. This confirms the exclusion is unconditional rather than accidentally branch-specific.

The changed tests import production behavior and use the bundled registry, M200 DiseÃƒÂ±o corpus, and `RegistryValidator`. They neither reproduce the derivation algorithm nor use fakes, mocks, stubs, patches, monkeypatches, skips, or expected failures. The closure-bound assertion and M200 regression each have an independent semantic oracle, and the supplied mutation bite demonstrated that removing the exclusion makes the real manifest-drift gate fail on an M100 internal-only closure node.

No shim, alias, legacy manifest admission, or tolerant fallback was introduced.

## Verification

- Exact S07 regression selection: 3 passed.
- Full owning two-module lane: 32 passed and 1 failed. The sole failure is pre-existing/concurrent M303 legal-reference drift in `test_calculation_completeness_manifest_legal_refs_match_calculation_closure`; it concerns legal-reference sets, not the S07 casilla denominator, derivation, M200 row, or validator behavior.
- Real registry verification: passed with 73 modelos, 94 revisions, 799 legal references, and 16,800 casillas.
- Corpus fixed-point probe: 55 single-segment revisions and 1 multi-segment revision inspected; no derived/internal-only overlap.
- Scoped Ruff: passed.
- Scoped BasedPyright: 0 errors, 0 warnings, 0 notes.
- Scoped `git diff --check`: passed.
- Prohibited test-construct scan: no hits.

## Recommendations

No corrective action is required for S07. Keep the unrelated M303 legal-reference drift owned and resolved in its existing workstream; it does not block this step.

Verdict: **PASS.** W01.P02.S07 satisfies the approved internal-only completeness-denominator contract and is ready for lifecycle closure.
## Review-time strengthening

After the initial PASS was recorded, the production validator was strengthened to reject any completeness-manifest row whose declared registry casilla is `internal_only`. The real M200 regression now appends the actual `DP200014:bin-aplicada-maxima` metadata to the real loaded manifest and proves `RegistryValidator` raises the targeted validation error. This closes recurrence both at the exact checked-in drift gate and at runtime validation; it does not add a compatibility or tolerant path.

The updated exact S07 selection passed 3 tests. Updated scoped Ruff passed, scoped BasedPyright reported 0 errors, 0 warnings, and 0 notes, and scoped `git diff --check` passed. The verdict remains **PASS** with no findings.
