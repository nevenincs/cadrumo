---
tags:
  - '#reference'
  - '#data-provenance-consolidation'
date: '2026-09-10'
modified: '2026-09-10'
body_schema: 'body-v2'
body_hash: 'sha256:bbf9a534073ef71b5afd48dfb16d77325989b437c6abb684024061254a8cf077'
related:
  - "[[2026-09-10-data-provenance-consolidation-lane-inventory-research]]"
  - "[[2026-09-09-registry-generator-adr]]"
---

# `data-provenance-consolidation` reference: `live lane map`

## Summary

The implementation has a strong canonical runtime source path—typed `SourceReference` records compiled into `ValidatedRegistryAuthority` and byte-verified by `corpus_catalogue`—but acquisition metadata and test discovery are split among manifests, prose, exception files, and local filename rules. Consolidation needs a reusable catalog compiler for artifact identity and role; it must not replace registry authority, sidecar freshness, or generated-export proof with a generic boolean.

## Existing authority boundaries

- `SourceReference` is the runtime identity and regulatory-semantics record. Its verifier checks existence, containment, byte count, and SHA-256 before authority publication. `src/cadrumo/domain/calculations/registry/schema_references.py:472-578`; `src/cadrumo/domain/calculations/registry/corpus_catalogue.py:49-69`.
- Record-design manifests are acquisition and packaging projections. The sync tool reads/writes them and verifies their bytes; preprocessors also parse them for human attribution. `dev/corpus/sync_aeat_record_design_corpus.py:1589-1602,1775-1868`; `dev/docs/preprocess/_workbook.py:148-187`.
- The off-host record is an acquisition classification adapter, not a separate payload identity. Its seven records are already present in per-model manifests and the registry source catalogue with matching URL/digest/size after path normalization. `src/cadrumo/_data/corpus/aeat_official/disenos_registro/off_host_sources.json:1-61`; `src/cadrumo/domain/calculations/registry/tests/test_catalogue_verification_record_design.py:20-47`.
- `PROVENANCE.md` is readable audit documentation. The local test should continue to check a document that exists, but it must not establish hash-pinned official identity. `src/cadrumo/_data/corpus/tests/test_corpus_provenance.py:151-247`.

## Duplicate seams to replace

1. The coverage test independently interprets two manifest location schemas and considers prose, manifest, and registry paths equivalent successful origins. `src/cadrumo/domain/calculations/registry/tests/test_corpus_provenance_coverage.py:142-198`.
2. The sync tool and coverage test each carry metadata/derivative classifications. The sync-only extracted-sidecar census is a third acquisition route that should become an ordinary `derived_from` relation. `dev/corpus/sync_aeat_record_design_corpus.py:57-105,1697-1773`.
3. Generic sidecar freshness is checked in both preprocessing and `dev/corpus`. Retain producer-specific semantic tests, but share or centralize hash, schema, and locality validation. `dev/docs/preprocess/tests/test_corpus_sidecar_freshness.py:318-515`; `dev/corpus/tests/test_extraction_sidecar_freshness.py:172-380`.
4. The off-host test only verifies that an asserted TOML declaration exists and contains a basename; it does not verify source identity. Replace it with the existing full catalogue-to-manifest alignment predicate. `dev/corpus/tests/test_record_design_support.py:394-406`; `src/cadrumo/domain/calculations/registry/tests/test_catalogue_verification_record_design.py:20-47`.

## Consolidation seam

Introduce a typed, read-only `ArtifactIdentity` catalog/compiler keyed by canonical bundled relative path. Its record needs immutable identity facts—path, digest, bytes, retrieval/canonical URL, publisher, retrieval date—and exactly one role:

- official artifact;
- derived artifact, with input artifact/digest and producer identity;
- semantic annotation, with an explicit target;
- disposition, with a reason and target; or
- explicitly non-authoritative fixture.

The compiler should emit diagnostic classes rather than one verdict: missing identity, malformed identity, conflicting acquisition declaration, orphaned target, unknown unclassified file, stale derivative, and broken registry binding. `SourceReference` then binds the artifact identity and continues to own source kind, evidence tier, applicability, review, and design authority. Manifest/prose output becomes a projection, not an alternate runtime source.

## Gates to retain versus retire after migration

Retain distinct checks: registry byte verification, record-design acquisition reproducibility, sidecar freshness/locality, semantic re-extraction, generated-export reproduction, legal-text authenticity, and calculation/oracle correctness. Each tests a different failure mode.

Replace the broad three-way coverage sweep, duplicated metadata/derivative lists, off-host duplication, and generic duplicate full-tree sidecar loops only after the catalog compiler has temporary-tree detector teeth for each replacement failure mode. Existing analysis screens that emit findings but return zero remain advisory until explicitly promoted.
