---
tags:
  - '#audit'
  - '#data-provenance-consolidation'
date: '2026-09-10'
modified: '2026-09-11'
body_schema: 'body-v2'
body_hash: 'sha256:304927415e082f6eaf6597301817ac3dda2cc908d6b129a33c9a8e079864cbb8'
related:
  - "[[2026-09-10-data-provenance-consolidation-plan]]"
---

# `data-provenance-consolidation` audit: `w04 p08 s23 consumer boundary review`

## Scope

Reviewed the corrected S23 consumer-boundary acceptance evidence: the amended ADR and plan, the record-design synchronizer boundary, and its shipped-data test. The review checked that the change does not introduce a universal `_data` taxonomy and that the pre-existing M200 unattested workbook remains visible rather than silently admitted.

## Findings

### registry-boundary-missing | high | S23 is marked complete without evidence for every production boundary

The amended S23 requires exhaustive exactly-once classification for each production consumer-owned evidence boundary, but the implementation adds only the record-design synchronizer test. The registry consumer's `compile_record_design_manifest_catalogue` remains a distinct bounded compilation assembled from registry-cited paths, and no changed test compiles its real boundary or asserts its roles cover that boundary. Existing synthetic catalog tests and the pending S24 divergent-binding publication test do not establish that exhaustive S23 invariant. Leave S23 incomplete until the registry-owned boundary receives its real-path coverage assertion.

### sync-boundary-evidence | low | The record-design proof is correctly bounded and debt-visible

The new synchronizer test derives its candidate set from `_payload_paths`, asserts that catalog roles plus the sole declared exception equal that set, checks disjointness, and limits accepted roles to official and derived artifacts. It also requires the only unknown diagnostic to equal the explicit M200 allowlist. This fails if a second unclassified payload appears or if M200 is silently attested while still allowlisted. The boundary deliberately excludes declarations and extractor outputs owned by their own contracts, so it does not create a global configuration taxonomy.

### registry-boundary-recheck | high | The new publication fixture is S24 detector evidence, not S23 exhaustiveness evidence

The added authority-publication fixture constructs one record-design source and one matching manifest row, then mutates its digest to demonstrate a fail-closed binding. That is a valid S24-shaped detector, but it never obtains the production registry's complete set of record-design source paths, invokes `compile_record_design_manifest_catalogue` for that set, or compares that set with catalog roles. Consequently it cannot resolve the prior registry-boundary finding. The focused collection currently fails before the publication tests run because the concurrent compiler relocation leaves `dev.registry.compiler._m303_orden_constants` unavailable; the independently collected synchronizer suite still passes 14 tests. This import failure is external to the S23 test changes, but it does not turn the missing exhaustive assertion into passing evidence.

### registry-boundary-resolved | low | The live companion-boundary test closes the prior S23 finding

The current `test_registry_cited_record_design_boundary_is_exhaustively_catalogued` is the relevant S23 evidence, not the publication fixture reviewed above. It loads the committed registry, compiles `compile_record_design_manifest_catalogue` from its real source mapping, derives the exact registry-cited record-design path set, and requires empty diagnostics plus equality of that set with both catalog roles and catalog identities. It also requires the sole role to be official and verifies each immutable payload join before running the production binding verifier. Together with the synchronizer's full payload-boundary proof, this demonstrates exhaustive exactly-once classification within both caller-owned boundaries without inventing a global taxonomy. The prior high findings are resolved by this test.

## Recommendations

- Fulfilled: the live registry-owned boundary assertion now compiles the production record-design catalog and proves its registry-cited paths receive exactly one official role with no diagnostics.
- Retain the synchronizer test and its M200 equality assertion; it is the appropriate producer-owned proof and keeps the debt actionable.
- Keep the publication fixture as S24 evidence once its unrelated compiler import chain is repaired; do not substitute it for S23's production-boundary census.
