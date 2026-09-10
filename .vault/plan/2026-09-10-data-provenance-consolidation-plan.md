---
tags:
  - '#plan'
  - '#data-provenance-consolidation'
date: '2026-09-10'
tier: L3
related:
  - '[[2026-09-10-data-provenance-consolidation-adr]]'
  - '[[2026-09-10-data-provenance-consolidation-lane-inventory-research]]'
  - '[[2026-09-10-data-provenance-consolidation-live-lane-map-reference]]'
modified: '2026-09-10'
body_schema: body-v2
body_hash: 'sha256:1f9d41bd5652529b1e02eb666972fe1476c269f0224014a5b014e1afba4fdf91'
---

# `data-provenance-consolidation` plan

Compile one read-only artifact identity and role catalog for bundled `_data`, while preserving the filing authority and the distinct quality gates that protect derivation and correctness.

## Description

This plan executes the accepted consolidation ADR. W01 defines and proves the compiler boundary; W02 migrates consumers without deleting the existing gates; W03 removes duplicate declarations and generic checks after parity; W04 verifies that the shipped corpus and distinct quality contracts remain protected.

## Steps

## Wave `W01` - Establish artifact catalog

Deliver the typed compiler and isolated defect vocabulary required before any consumer migration.

### Phase `W01.P01` - Catalog schema and compilation

Define identity, role, adapters, and diagnostics at one shared compiler boundary.

- [x] `W01.P01.S01` - Define immutable artifact roles, identity, derivation, disposition, and diagnostic records keyed by bundled relative path; `src/cadrumo/domain/calculations/registry/artifact_catalogue.py`.
- [x] `W01.P01.S02` - Implement adapters for record-design, manual, e-invoice, registry, and declared disposition records; `src/cadrumo/domain/calculations/registry/artifact_catalogue.py`.
- [x] `W01.P01.S03` - Compile identity conflicts, absent targets, unknown files, stale derivatives, and broken bindings into diagnostics; `src/cadrumo/domain/calculations/registry/artifact_catalogue.py`.

### Phase `W01.P02` - Temporary-tree detector teeth

Demonstrate that every catalog defect class is independently detected before production consumers migrate.

- [x] `W01.P02.S04` - Prove normal catalog compilation and every declared role in a temporary bundled tree; `src/cadrumo/domain/calculations/registry/tests/test_artifact_catalogue.py`.
- [x] `W01.P02.S05` - Prove conflicting identity, malformed data, orphaned targets, and unclassified files produce distinct diagnostics; `src/cadrumo/domain/calculations/registry/tests/test_artifact_catalogue.py`.
- [x] `W01.P02.S06` - Prove changed derivative inputs and divergent registry source identity fail closed; `src/cadrumo/domain/calculations/registry/tests/test_artifact_catalogue.py`.

## Wave `W02` - Migrate consumers behind the catalog

Move registry, acquisition, and derivative consumers while retaining their existing checks until parity is demonstrated.

### Phase `W02.P03` - Registry and coverage consumers

Bind registry verification and broad coverage to catalog identity without expanding runtime authority.

- [x] `W02.P03.S07` - Bind catalogue verification to the artifact identity join while retaining registry semantic validation; `src/cadrumo/domain/calculations/registry/corpus_catalogue.py`.
- [x] `W02.P03.S08` - Replace three-way origin admission with catalog diagnostics for unknown and conflicting files; `src/cadrumo/domain/calculations/registry/tests/test_corpus_provenance_coverage.py`.
- [x] `W02.P03.S09` - Prove official identity alignment and non-payload role handling in an integration fixture; `src/cadrumo/domain/calculations/registry/tests/test_corpus_provenance_coverage.py`.

### Phase `W02.P04` - Record-design consumer

Route sync acquisition checks through the catalog while preserving byte and retrieval validation.

- [x] `W02.P04.S10` - Route manifest loading, payload classification, and acquisition diagnostics through the catalog; `dev/corpus/sync_aeat_record_design_corpus.py`.
- [x] `W02.P04.S11` - Replace basename-only off-host assertion with exact catalog identity alignment fixtures; `dev/corpus/tests/test_record_design_support.py`.
- [x] `W02.P04.S12` - Prove catalog-backed sync rejects unclassified files and conflicting acquisition identity; `dev/corpus/tests/test_record_design_support.py`.

### Phase `W02.P05` - Derived-sidecar consumer

Centralize generic derivative validation while retaining producer-specific semantics.

- [ ] `W02.P05.S13` - Extract shared generic sidecar hash, schema, locality, and digest validation into the sidecar owner; `dev/docs/preprocess/sidecar.py`.
- [ ] `W02.P05.S14` - Migrate documentation-preprocessor freshness tests to the shared generic validator; `dev/docs/preprocess/tests/test_corpus_sidecar_freshness.py`.
- [ ] `W02.P05.S15` - Migrate corpus-sidecar freshness checks to shared validation and catalog derivation; `dev/corpus/tests/test_extraction_sidecar_freshness.py`.

## Wave `W03` - Retire proven duplicate lanes

Remove only declarations and full-tree checks whose catalog-backed successors prove the same failure modes.

### Phase `W03.P06` - Remove redundant record-design lanes

Delete duplicate off-host and sidecar authority routes only after exact catalog parity exists.

- [ ] `W03.P06.S16` - Delete redundant off-host acquisition projection after exact manifest and registry catalog bindings exist; `src/cadrumo/_data/corpus/aeat_official/disenos_registro/off_host_sources.json`.
- [ ] `W03.P06.S17` - Remove off-host loading, schema, and special authority routing after catalog parity; `dev/corpus/sync_aeat_record_design_corpus.py`.
- [ ] `W03.P06.S18` - Remove retired off-host-specific tests while retaining catalog-backed detector teeth; `dev/corpus/tests/test_record_design_support.py`.
- [ ] `W03.P06.S19` - Replace sync-only extracted-sidecar census with explicit catalog derivation records; `dev/corpus/sync_aeat_record_design_corpus.py`.

### Phase `W03.P07` - Prose and coverage cleanup

Leave prose as documentation and eliminate duplicate role classification from coverage.

- [ ] `W03.P07.S20` - Restrict PROVENANCE documentation checks to readable audit attribution rather than identity admission; `src/cadrumo/_data/corpus/tests/test_corpus_provenance.py`.
- [ ] `W03.P07.S21` - Remove duplicated payload, metadata, and derivative classification from the retired coverage sweep; `src/cadrumo/domain/calculations/registry/tests/test_corpus_provenance_coverage.py`.
- [ ] `W03.P07.S22` - Remove duplicate generic full-tree sidecar validation after shared validator parity; `dev/corpus/tests/test_extraction_sidecar_freshness.py`.

## Wave `W04` - Verify final quality evidence

Prove the shipped tree and all distinct quality contracts remain enforced after consolidation.

### Phase `W04.P08` - Focused and handoff verification

Exercise the compiled catalog and all retained distinct quality contracts against real data.

- [ ] `W04.P08.S23` - Verify catalog compilation classifies every shipped bundled data file exactly once; `src/cadrumo/domain/calculations/registry/tests/test_artifact_catalogue.py`.
- [ ] `W04.P08.S24` - Verify real registry authority publication rejects divergent source bindings; `src/cadrumo/domain/calculations/registry/tests/test_catalogue_verification_record_design.py`.
- [ ] `W04.P08.S25` - Verify record-design sync reproducibility and catalog-backed coverage without network writes; `dev/corpus/tests/test_record_design_support.py`.
- [ ] `W04.P08.S26` - Verify sidecar, export, normative-text, and calculation-oracle contracts remain distinct; `dev/docs/preprocess/tests/test_corpus_sidecar_freshness.py`.

## Parallelization

Waves are sequential. In W02, P03, P04, and P05 may proceed in parallel after W01; P04 must expose catalog-backed acquisition behavior before W03.P06, and P05 must complete before W03.P07.S22. W03.P06 and W03.P07 may proceed in parallel once their W02 dependencies pass. W04 follows all removals.

## Verification

Every catalog diagnostic has temporary-tree detector teeth and the compiled shipped tree assigns exactly one role to each in-scope file. Registry authority publication, record-design sync, corpus coverage, and both sidecar suites pass through their real paths. Generated-export reproduction, normative-text authenticity, and calculation/oracle gates remain separate passing contracts. Ruff, formatting, type checks, plan validation, and focused vault checks pass; unrelated pre-existing failures are reported separately.
