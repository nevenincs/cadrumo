---
tags:
  - '#audit'
  - '#aeat-export-fragment-generator-authority'
date: '2026-08-12'
modified: '2026-08-12'
body_schema: 'body-v1'
body_hash: 'sha256:c8ed93eb8564f23fd418a9d53438d1d71baa736d88673a03e46d91039ca04bb6'
related:
  - "[[2026-08-10-aeat-export-fragment-generator-authority-plan]]"
  - "[[2026-06-13-m303-form-vs-semantic-casilla-dual-keying-adr]]"
---
# `aeat-export-fragment-generator-authority` audit: `S57 Typed Filing Projection Authority Audit`

## Scope

Audited the S57 implementation against the accepted dual-keying ADR and the plan's strict typed-projection boundary. The review covered the seven-variant `FilingProjectionRef` union, primitive compilation, semantic-map and registry loading, provenance and generator propagation, repeat-family partitioning, retained `RegistrySnapshot` authority, exact record-occurrence addressing, the four Modelo 303 projectors, renderer preflight, and deletion of the snapshot-free legacy rendering surface.

The immutable implementation candidate was `27b699524ec998e6bed4e3c90c42544adcc53b19`, with parent `f644d84b320e2ecd0bd864f6d9635cc6143cac71` and tree `735dd2d5c9235fba9dd4fc02ae71aeaa23c6db53`.

## Findings

### exact-fact-identity | medium | persisted identity normalization concealed semantic-map drift

The first immutable review found that whitespace stripping in the identity type normalized distinct persisted `fact_identity` primitives instead of refusing them. The implementation removed normalization, added an exact compiler precheck for every admitted string wire token, and added direct-model and compiler regressions for whitespace-bearing identities. The amended candidate refuses those inputs.

### typed-projection-authority | low | implementation satisfies the accepted strict boundary

The amended formal review approved the candidate with zero unresolved critical, high, or medium findings. The reviewer confirmed the flat discriminated union has no legacy defaults or aliases, projection and binding repeat families remain disjoint, the exact snapshot survives through rendering, projection values are addressed by record id, positive occurrence, and typed reference, and the retired snapshot-free renderer and inference-based projection identity do not remain.

## Recommendations

Keep the exact primitive and snapshot-owned projection boundaries under the S57 hard-cut and refusal tests. Treat any future normalization, raw mapping acceptance, snapshot re-resolution, inferred identity, or compatibility surface as a regression requiring refusal rather than migration support.
