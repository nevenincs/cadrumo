---
tags:
  - '#audit'
  - '#calculation-source-connectivity'
date: '2026-07-04'
modified: '2026-07-17'
body_hash: 'sha256:0eca90f721b8bb4ee34cfb3347e3945620615cec1466df63716f2b0c54740c6a'
related:
  - "[[2026-05-20-calculation-source-connectivity-plan]]"
---

# `calculation-source-connectivity` audit: `campaign closeout`

## Scope

The calculation-source-connectivity campaign closeout honesty-review (Wave W05 P11 axes plus the P10 governance inventory), run single-owner. Three axes are covered here in one consolidated closeout document: the source-enrollment inventory (S55), the persistence-boundary review of the W05.P10 approval-fingerprint and source-provenance work (S58), and the source-mesh directionality audit (S59). The grounding audit (S60) and the final registry-gate re-confirmation (S55/S61 green on a settled tree) are deferred to a settle-window because the shared registry is transiently churning under a concurrent modelo-145 fixed-width-export write; that mandatory re-confirm is recorded below, not yet performed.

## Findings

### source-enrollment-inventory | low | every declared binding source is enrolled, deferred, or manual — no dormant surface (verified in a stable window)

A stable-window run of the enrollment gate (`test_source_enrollment.py` plus `test_source_mesh_missing_sources.py`) passed 9/9: every binding `source` kind declared across the committed registry resolves to an enrolled resolver, an explicitly deferred kind, or manual input, upholding the no-dormant-source-resolvers connectivity contract. Modelo 145 (landing under a peer) declares no calculation binding sources — its only `source` token is a `workbook_source` parity reference and it has no `bindings/` fragment directory — so it introduces zero new source kinds to the mesh and the inventory is unaffected by it. A concurrent re-run flipped to 8 failed / 1 passed, but full-traceback isolation showed every failure is `RegistryLoadError: registry directory changed during cache fingerprinting; retry after concurrent registry writes settle` — the transient loader-cache race from the modelo-145 export peer's active writes, distinct from a genuine unenrolled-source assertion (which would name the kind). No calc-source gap; the inventory is clean.

### persistence-boundary-review | low | approval-fingerprint and source-provenance changes uphold roundtrip, no-legacy, provenance, and identity discipline

The W05.P10 persistence-boundary work reviewed against the roundtrip and no-legacy disciplines. Identity discipline holds: neither the revision `source_provenance` field nor the approval `prior_filing_observations_fingerprint` participates in `derive_calculation_revision_id` (both confirmed absent from the derivation), so content-addressing is unchanged. No-legacy holds: the approval-basis version is a single canonical `review-basis-v3` with no migration or read-tolerance shim across the v1 to v3 progression. Provenance is non-duplicated: `CalculationSourceRef` carries only the resolver-to-source-object-to-fingerprint trace (source_kind, binding_source, source_ref, fingerprint) and deliberately omits the per-casilla legal_refs and source_refs that the revision observations already own. The stable projection excludes the volatile `captured_at` so a re-save of identical data does not over-invalidate, and the review layer projects the stored observation structurally through a Protocol without importing the observation repository's private envelope type. The persisted-model changes are exercised by strict save-load-equality roundtrips plus corrupt-payload anti-tautology proofs and registry-free fingerprint unit tests.

### calculation-grounding | low | provenance, legal_refs, and source_refs are preserved through every calc-source boundary (settle-window, settled registry)

Settle-window grounding audit on the settled registry (the modelo-145 export write paused; the tree loads stably): 25/25 green across the provenance-preservation boundaries. The typed `CasillaObservation` envelope carries operand_refs, operand_values, legal_refs, and source_refs across the domain persistence boundary; the calculation-revision `source_provenance` (the resolver→object→fingerprint trace) survives the encrypted secure-object roundtrip with a corrupt-payload anti-tautology proof; the ledger filing evidence preserves per-row legal_refs/source_refs; and the source-mesh calculation path preserves provenance end to end. No grounding gap on the calc-source surface — every regulatory reference carried by the registry reaches the persisted revision.

### registry-gate-reconfirm | low | enrollment + missing-source gate re-confirmed a REAL green on the settled registry (no loader race)

Settle-window re-confirm of the S55/S61 dimension: the enrollment + missing-source gate (`test_source_enrollment.py` + `test_source_mesh_missing_sources.py`) passed 9/9 on the settled registry with NO `RegistryLoadError` — a genuine green, not the churn-contaminated red seen mid-write. This confirms the earlier stable-window result on a settled tree: every declared binding source is enrolled/deferred/manual and no source-backed binding can silently calculate zero. The mandatory campaign honesty-gate re-confirm is satisfied.

### source-mesh-directionality | low | production domain never imports application; mesh resolvers stay application-layer

The `domain-not-application` import-linter contract is KEPT over the full tree (3252 files, 15248 dependencies): no production domain module imports the application layer, so the source mesh's hexagonal direction holds — registry binding resolvers and observation protocols live in the domain while the storage-reading source resolvers and the mesh orchestration live in the application layer. A grimp runtime-graph pass confirms the only domain-to-application edges are test modules and conftests (legitimate cross-layer test wiring), including the three `domain.calculations.registry.tests -> application.aggregation` edges; there is no production directionality violation on the calc-source surface.

## Recommendations

- SETTLE-WINDOW RE-CONFIRM: DONE-green. The mandatory re-confirm ran on the settled registry — the enrollment + missing-source gate passed a real 9/9 (no `RegistryLoadError`) and the grounding audit passed 25/25. The campaign honesty-gate is satisfied on a settled tree, not on churn-contaminated reds or Phase-1 evidence alone.
- No code action required from any of the five axes; all findings are low and confirm the campaign's invariants hold.
- The two open W05.P10 follow-up rows (the profile-activity relation-scoping fingerprint) remain tracked and are out of scope for this closeout.
