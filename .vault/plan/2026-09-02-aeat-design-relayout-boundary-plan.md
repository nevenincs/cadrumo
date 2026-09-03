---
tags:
  - '#plan'
  - '#aeat-design-relayout-boundary'
date: '2026-09-02'
tier: L3
related:
  - '[[2026-08-08-aeat-design-relayout-boundary-modelo-200-partition-adr]]'
  - '[[2026-09-02-aeat-design-relayout-boundary-research]]'
  - '[[2026-08-10-aeat-export-fragment-generator-authority-adr]]'
modified: '2026-09-03'
body_schema: body-v2
body_hash: 'sha256:2e4964aa8e667a6bd686314a52daa07cb7a05f719e750ab8707f508e23587a82'
---

# `modelo-200-semantic-crosswalk` plan

Target-first, source-hash-bound reconciliation makes Modelo 200 2024 loadable, exportable, and filing-grade without hand-authoring its export geometry.

## Description

This plan executes the accepted Modelo 200 partition decision, export-fragment generator authority decision, and semantic-crosswalk research. Wave `W01` freezes target evidence and removes historic-tree semantic authority. Wave `W02` reconciles physical identity and exact source bindings. Wave `W03` closes target-year semantic and legal authority. Wave `W04` compiles only complete reviewed authority and regenerates privately. Wave `W05` validates the real authority path, publishes atomically, promotes filing grade only after proof, and obtains independent review.

## Steps

## Wave `W01` - establish the immutable 2024 reconciliation boundary

Freeze the exact pinned 2024 design as the sole target identity authority and record the full population before mutation.

### Phase `W01.P01` - freeze the declaration and source evidence census

Separate current declarations from semantic adjudications and bind every result to the exact 2024 source SHA.

- [x] `W01.P01.S01` - Extend the deterministic census across 3,173 current declarations, 156 reconstructed candidates, 3,171 exact map-owned rebinds, 2 unmapped declarations, 15 printed-identity diagnostics, 185 map-owner mismatches, and declaration and map legal gaps; `dev/registry/analysis/m200_2024_full_reconciliation.py`.
- [x] `W01.P01.S02` - Prove census completeness, determinism, source-SHA binding, contamination visibility, and partition-drift refusal; `dev/registry/tests/test_m200_2024_full_reconciliation.py`.

### Phase `W01.P02` - remove non-authoritative historic semantic reuse

Prevent historical fragments, adjacent designs, and description similarity from becoming 2024 semantic or legal authority.

- [x] `W01.P02.S03` - Retire historic-payload restoration as authority-producing behavior while retaining proposal-only diagnostics; `dev/registry/analysis/m200_2024_restoration_candidates.py`.
- [x] `W01.P02.S04` - Detect target-description, semantic-role, legal-reference, and source-SHA mutations at the historic-restoration boundary; `dev/registry/tests/test_m200_2024_restoration_candidates.py`.

## Wave `W02` - derive physical reconciliation from the pinned design

Build deterministic tooling that changes only facts proven by the 2024 design and never infers semantic ownership from siblings.

### Phase `W02.P03` - program the exact source-reference rebind

Derive exact 2024-anchor rebinds while preserving every non-source authority fact byte-for-byte.

- [x] `W02.P03.S05` - Implement the source-SHA-bound planner and canonical TOML mutation surface for 3,171 exact map-owned declaration rebinds while refusing two true orphans; `dev/registry/analysis/m200_2024_full_reconciliation.py`.
- [x] `W02.P03.S06` - Reject missing anchors, source drift, duplicate output, altered non-source payloads, and partial rebind application; `dev/registry/tests/test_m200_2024_full_reconciliation.py`.

### Phase `W02.P04` - classify mismatched and orphan target identities

Assign identity mismatches and source-map orphans to closed target-first dispositions without sibling fallback.

- [x] `W02.P04.S07` - Implement target-anchor identity classification and explicit dispositions for every unmapped declaration; `dev/registry/analysis/m200_semantic_casilla_candidates.py`.
- [x] `W02.P04.S08` - Prove identity ambiguity, segment qualification, non-casilla ownership, and orphan omission fail closed; `dev/registry/tests/test_m200_semantic_casilla_candidates.py`.

## Wave `W03` - adjudicate 2024 meaning and legal authority

Turn target-year evidence into reviewed semantic-map and legal authority after the identity worklist is closed.

### Phase `W03.P05` - close the legal catalogue worklist

Resolve legal-catalogue gaps against applicable 2024 authority before semantic rows become authoritative.

- [x] `W03.P05.S09` - Derive the source-bound legal worklist with applicability-window and unresolved-reference evidence; `dev/registry/analysis/m200_2024_full_reconciliation.py`.
- [x] `W03.P05.S10` - Author reviewed 2024-applicable legal catalogue entries and anchors for the closed worklist; `src/cadrumo/_data/registry/aeat/legal/`.
- [ ] `W03.P05.S11` - Enforce legal resolution, target-window coverage, anchor reachability, and rejection of later-year substitution; `dev/registry/tests/test_m200_2024_full_reconciliation.py`.

### Phase `W03.P06` - record closed semantic adjudication families

Resolve every candidate semantic through explicit reviewed target-year families and reviewer provenance.

- [ ] `W03.P06.S12` - Compile reviewed target-year authority for exact same-2024 template repairs; `dev/registry/mappings/modelo_200/2024/`.
- [ ] `W03.P06.S13` - Adjudicate uniquely proposed cross-revision candidates against official 2024 evidence; `dev/registry/mappings/modelo_200/2024/`.
- [ ] `W03.P06.S14` - Adjudicate conflicting cross-revision candidate sets against official 2024 evidence; `dev/registry/mappings/modelo_200/2024/`.
- [ ] `W03.P06.S15` - Author target-year authority for target fields with no applicable cross-revision candidate; `dev/registry/mappings/modelo_200/2024/`.

## Wave `W04` - materialize complete target authority and generate privately

Integrate reviewed declaration, legal, map, and render authority and regenerate into a fresh temporary root.

### Phase `W04.P07` - enforce complete semantic-map admission

Reject unresolved proposals, stale sources, incomplete legal grounding, and reciprocal export-reference drift.

- [ ] `W04.P07.S16` - Require reviewed target-year adjudication provenance and reject proposal-only semantic entries; `dev/registry/pipeline/_semantic_map_validation.py`.
- [ ] `W04.P07.S17` - Preserve source identity, parser-map bijection, qualified casilla ownership, and declaration admission in the semantic join; `dev/registry/pipeline/_semantic_map_join.py`.
- [ ] `W04.P07.S18` - Add positive and mutation coverage for adjudication, legal applicability, identity mismatch, and unresolved-anchor refusal; `dev/registry/tests/test_semantic_map_validation.py`.

### Phase `W04.P08` - generate and validate the private 2024 export tree

Render from the pinned design and reviewed authority into a temporary root without hand-authored coordinates.

- [ ] `W04.P08.S19` - Bind Modelo 200 2024 bootstrap generation to the exact target design and digest; `dev/registry/pipeline/generated_export_bootstrap_targets.toml`.
- [ ] `W04.P08.S20` - Generate the complete export package, provenance manifest, and reciprocal references through the canonical pipeline; `src/cadrumo/_data/registry/aeat/modelos/200/revisions/2024/export/`.
- [ ] `W04.P08.S21` - Prove temporary-root regeneration, whole-tree equality, provenance equality, and source-drift refusal; `dev/registry/tests/test_generated_export_trees.py`.

## Wave `W05` - publish filing-grade authority and independently verify it

Publish and promote only after the complete generated package passes the real fail-closed authority path.

### Phase `W05.P09` - publish only the validated generated package

Exercise canonical check and publish under established locks, receipts, and destination-identity contracts.

- [ ] `W05.P09.S22` - Exercise Modelo 200 2024 check and publish through the canonical pipeline authority path; `dev/registry/pipeline/cli.py`.
- [ ] `W05.P09.S23` - Reject target mutation, stale receipts, partial trees, reference asymmetry, and post-validation drift; `dev/registry/tests/test_generated_tree_publication.py`.
- [ ] `W05.P09.S24` - Promote the 2024 revision to filing grade only after committed generated-package validation; `src/cadrumo/_data/registry/aeat/modelos/200/revisions/2024/revision.toml`.

### Phase `W05.P10` - prove end-to-end registry and filing readiness

Verify loaded authority, generated export bytes, revision selection, focused gates, and independent review.

- [ ] `W05.P10.S25` - Prove the 2024 filing context selects filing-grade Modelo 200 through ValidatedRegistryAuthority; `src/cadrumo/domain/calculations/registry/tests/test_modelo_200_ejercicio_2024_resolves.py`.
- [ ] `W05.P10.S26` - Run focused crosswalk, generator, publication, loader, export-tree, and authority suites with separately attributed full-suite results; `dev/registry/tests/`.
- [ ] `W05.P10.S27` - Produce an independent formal review of semantic authority, legal grounding, generated publication, promotion, and evidence; `.vault/audit/`.

## Parallelization

Waves are sequential. Within `W01`, census verification and the historic-restoration refusal boundary may proceed independently after their shared target-state read. The two `W02` phases may proceed concurrently, but each implementation precedes its mutation tests. `W03.P05` must close legal applicability before `W03.P06` output becomes authoritative. `W04` begins only after every `W03` row is closed. `W05` begins only after fresh temporary-root generation passes.

## Verification

The plan is complete only when the frozen census accounts for all 3,173 current declarations and 156 reconstructed candidates; all 3,171 exact map-owned source rebinds are reproducible; both true orphans have closed typed dispositions; all 15 printed-identity diagnostics remain visible; all 185 map-owner mismatches have source-bound outcomes; every semantic case has reviewed 2024 authority; and every legal reference resolves and covers the target window.

The canonical pipeline must independently regenerate and validate the full 2024 export package in a fresh temporary root, reject representative malformed and stale inputs, publish atomically through its receipt and lock path, and reproduce the committed tree in check mode. `ValidatedRegistryAuthority` must load the 2024 filing context as filing-grade with its generated layout. Focused suites, separately attributed long-suite results, and independent formal review must report no unresolved high or critical authority findings.
