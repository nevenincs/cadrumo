---
tags:
  - '#exec'
  - '#source-casilla-integration'
date: '2026-08-25'
modified: '2026-08-25'
body_schema: 'body-v1'
body_hash: 'sha256:526f1e207c6ee1eb816c30415bfcef701942fddd19f9fc751c72da58cce5466c'
step_id: 'S227'
related:
  - "[[2026-08-22-source-casilla-integration-plan]]"
---

# Adjudicate the Modelo 220 2024 and 2025 group-value origins, grain, source identity, provenance, and absence semantics before any m220 producer key, binding, casilla, or filing layout is introduced.

## Scope

- `.vault/research/`
- `.vault/adr/`
- `src/cadrumo/_data/source_connectivity/census.toml`
- `src/cadrumo/_data/registry/aeat/modelos/220/`

## Description

- Verify the exact AEAT 2024 and 2025 record-design artefacts, version windows,
  source hashes, and relevant BOE records.
- Examine the M220 registry, Modelo 200 guidance, producer, binding, source
  mesh, secure-connectivity, census, and filing-capability surfaces.
- Record the existing source-connectivity ADR as sufficient governance; do not
  create a competing M220 ADR.

## Outcome

Modelo 220 group values are a genuine source-connectivity candidate at
composite group/member grain, but no non-lossy secure owner is evidenced. The
official designs prove targets and the Modelo 200 relationship; they do not
prove an acquisition, resolver, durable value identity/provenance, or absence
policy. The evidence result is therefore **defer**, not connection or
not-applicable.

No M220 producer key, binding, casilla change, layout, source-mesh route, or
census disposition was created. Future work may reopen only with a secure
owner for group and member identities, individual-declaration references,
group/member value roles, provenance/fingerprints, and absence semantics, plus
two-era lifecycle proof through encrypted persistence, replay, review, and
supported export.

## Notes

- The source-casilla plan and feature-index lane were concurrently dirty for
  S114 at this record's creation. This record intentionally does not alter
  their state; S227 closure tracking waits for that lane.
- Semantic RAG initially selected binary workbook blobs, whose renderer cannot
  decode them as UTF-8. Discovery was narrowed to text registry and filing
  surfaces; the official workbook evidence was read through its hash-pinned
  extracted text and source catalogue.
