---
tags:
  - '#exec'
  - '#unstructured-document-ingestion'
date: '2026-08-07'
modified: '2026-08-13'
body_schema: 'body-v1'
body_hash: 'sha256:4b4c98649ddfb35779c4e2696da178a33c604b4bb9648d4dcce0461cf3fe8c43'
step_id: 'S122'
related:
  - "[[2026-08-07-unstructured-document-ingestion-plan]]"
---

# Ground the Spanish province-to-IVA-territory mapping in the registry authoring tree and resolve a Spanish party through it, since the mapping is regulatory-adjacent under LIVA art. 3.Dos and belongs in registry TOML rather than as Python literals, and no postal authority exists in production today. Extend the existing country-code scope resolver rather than adding a second one, because the country axis and the sub-national axis are one question with two evidence sources. A Spanish party with no printed postal code stays UNKNOWN and never the mainland: the peninsula is the majority population so defaulting to it would be invisible, and it would silently pull Canarian and Ceutan parties into a territory their operations are not subject to, which is the same restrictive-default trap the country-level resolver already refuses one level up

## Scope

- `src/cadrumo/_data/registry`
- `src/cadrumo/domain/iva`

## Description

## Outcome

Executed. Verified against HEAD: the Spanish territory mapping is grounded in the registry authoring tree.

**Retrospectively reconstructed on 2026-08-13 at operator direction. NOT a contemporaneous account** — nobody observed this work being done. What is recorded is that the deliverable exists at HEAD and how that was established. Per-row verification detail is in the record-gap close audit.

## Notes
