---
tags:
  - '#research'
  - '#data-provenance-consolidation'
date: '2026-09-10'
modified: '2026-10-03'
body_schema: 'body-v2'
body_hash: 'sha256:aec722a2c2f9023e63f5ba24ab9c86d2539ae70875f1c5d67d9ddbd032dca880'
related:
  - "[[2026-09-10-corpus-evidence-integrity-corpus-text-provenance-adr]]"
  - "[[2026-09-09-registry-generator-adr]]"
---

# `data-provenance-consolidation` research: `lane inventory`

The `_data` tree has no single provenance problem. It has several different claims—official-artifact identity, runtime source authority, derived-output lineage, semantic evidence, and human documentation—represented by partially overlapping files and gates. The evidence favours one typed artifact-identity inventory with role-specific validation, while retaining the existing registry authority and derivation proofs rather than flattening their meanings.

## Findings

### Runtime source authority is canonical for filing consumers, but not every bundled payload

`SourceReference` carries a typed corpus path, content digest, byte count, retrieval date, source URL, publisher, source kind, review status, and evidence-tier semantics. The catalogue verifier hashes resolved bytes before `ValidatedRegistryAuthority` publishes them. This must remain the only runtime route for filing and calculation consumers; it does not cover every `_data` payload, and must not become a raw-file parsing API just to complete inventory. `src/cadrumo/domain/calculations/registry/schema_references.py:472-578` and the former source file.

### Record-design acquisition duplicates one relationship

The record-design sync tool verifies per-model manifests against disk bytes and uses indexed AEAT URLs, BOE off-host rows, and an extracted-sidecar census as acquisition dispositions. The off-host document is not an independent coverage mechanism today: all seven current entries match their per-model manifest's path, URL, and digest after resolving the `modelo_N/` path prefix. It is still an incomplete duplicate classification because it repeats path/URL without the manifest's digest, byte count, and retrieval date. `dev/corpus/sync_aeat_record_design_corpus.py:1425-1457,1697-1773` and the former source file.

The product coverage sweep accepts registry enrolment, a manifest location, or a filename mention in `PROVENANCE.md`. It is useful as a worklist detector but not a filing-grade identity contract: prose has no immutable binding to a payload, URL, or digest, and the test locally normalizes incompatible `stored_path` and `path` manifest formats. the former source file.

### Derived-output lineage and source acquisition are complementary claims

Manual corpus-text sidecars are runtime caches keyed to source digest; generic extracted sidecars are development/documentation outputs; generated export trees carry manifests for their source, semantic map, render, and output identities. They are not official-acquisition records. Their freshness, locality, and reproduction checks protect distinct failure modes and should be retained. the former source file, `dev/docs/preprocess/tests/test_corpus_sidecar_freshness.py:318-515`, and `dev/registry/pipeline/export_fragment_provenance.py:401-664`.

Generic sidecar freshness is duplicated between preprocessing and `dev/corpus`. Semantic re-extraction is not duplicate work, but generic hash/schema/locality checks should have one owner or a shared validator before a redundant full-tree walk is removed. `dev/corpus/tests/test_extraction_sidecar_freshness.py:172-380`.

### Payload role is classified in several hand-maintained places

Sync, coverage, and sidecar discovery each have their own metadata/derivative classification. Typed correction sidecars are hidden as filename derivatives despite being runtime semantic annotations. A future catalog needs exactly one role for every file: official artifact, derivative, semantic annotation, disposition, or explicitly non-authoritative fixture. `dev/corpus/sync_aeat_record_design_corpus.py:57-105`, the former source file, and the former source file.

### Quality signals must not be flattened

Legal applicability, corpus tier, normative-text authenticity, derivation fidelity, and calculation/oracle correctness are independent properties. A single boolean would hide the absence and advisory states the registry is designed to preserve. The existing generator ADR and proposed corpus-text ADR already distinguish these axes. `src/cadrumo/domain/calculations/registry/schema_references.py:263-280`, `.vault/adr/2026-09-09-registry-generator-adr.md`, and `.vault/adr/2026-09-10-corpus-evidence-integrity-corpus-text-provenance-adr.md`.

### The evidence favours a compiler boundary, not a catch-all runtime service

A typed, read-only artifact catalog keyed by canonical bundled relative path could centralize immutable acquisition facts and file role. Manifests, off-host rows, manual manifests, and e-invoice records would be validated adapters or generated projections. `SourceReference` would bind an artifact identity while retaining legal applicability and review semantics; derivatives would instead name input identity/digest and producer identity. This leaves the registry as runtime authority and gives focused gates a shared resolver without turning distinct quality claims into one test.

Not investigated: migration and compatibility impact for every Facturae, terminology, fixture, and companion-data payload; whether every normative HTML file has an available immutable external identity; and which active plans own individual remediation steps. These require the decision and plan phases.

## Sources

- `src/cadrumo/domain/calculations/registry/schema_references.py:263-280,472-578`

- `dev/corpus/sync_aeat_record_design_corpus.py:57-105,1425-1457,1697-1773`

- `dev/docs/preprocess/tests/test_corpus_sidecar_freshness.py:318-515`
- `dev/corpus/tests/test_extraction_sidecar_freshness.py:172-380`
- `dev/registry/pipeline/export_fragment_provenance.py:401-664`

- `.vault/adr/2026-09-09-registry-generator-adr.md`
- `.vault/adr/2026-09-10-corpus-evidence-integrity-corpus-text-provenance-adr.md`
