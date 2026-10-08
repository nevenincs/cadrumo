---
tags:
  - '#reference'
  - '#data-provenance-consolidation'
date: '2026-09-10'
modified: '2026-10-03'
body_schema: 'body-v2'
body_hash: 'sha256:0a9b45b0b98b56a4cda332f70642692c689324151a60e3ba758675adf6a4f0f9'
related:
  - "[[2026-09-10-data-provenance-consolidation-lane-inventory-research]]"
  - "[[2026-09-09-registry-generator-adr]]"
---

# `data-provenance-consolidation` reference: `live lane map`

## Summary

The implementation has a strong canonical runtime source path—typed `SourceReference` records compiled into `ValidatedRegistryAuthority` and byte-verified by `corpus_catalogue`—but acquisition metadata and test discovery are split among manifests, prose, exception files, and local filename rules. Consolidation needs a reusable catalog compiler for artifact identity and role; it must not replace registry authority, sidecar freshness, or generated-export proof with a generic boolean.

## Existing authority boundaries

- `PROVENANCE.md` is readable audit documentation. The local test should continue to check a document that exists, but it must not establish hash-pinned official identity. `src/cadrumo/_data/corpus/tests/test_corpus_provenance.py:151-247`.

## Duplicate seams to replace

1. The sync tool and coverage test each carry metadata/derivative classifications. The sync-only extracted-sidecar census is a third acquisition route that should become an ordinary `derived_from` relation. `dev/corpus/sync_aeat_record_design_corpus.py:57-105,1697-1773`. 3. Generic sidecar freshness is checked in both preprocessing and `dev/corpus`. Retain producer-specific semantic tests, but share or centralize hash, schema, and locality validation. `dev/docs/preprocess/tests/test_corpus_sidecar_freshness.py:318-515`; `dev/corpus/tests/test_extraction_sidecar_freshness.py:172-380`. 4. The off-host test only verifies that an asserted TOML declaration exists and contains a basename; it does not verify source identity.

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
