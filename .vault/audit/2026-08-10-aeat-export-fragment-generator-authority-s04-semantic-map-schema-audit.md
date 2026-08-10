---
tags:
  - '#audit'
  - '#aeat-export-fragment-generator-authority'
date: '2026-08-10'
modified: '2026-08-10'
body_schema: 'body-v1'
body_hash: 'sha256:d1885b849250c08ad6c9b756182dea6e6dae804ad3d8473212b77ac5c199391b'
related:
  - "[[2026-08-10-aeat-export-fragment-generator-authority-plan]]"
---
# `aeat-export-fragment-generator-authority` audit: `S04 semantic-map schema`

## Scope

Review the development-only `SemanticMap` contract and its direct validation tests against the approved official-binary and semantic-map authority boundary.

## Findings

### public-facade-import-boundary | medium | Initial shared-type imports bypassed the registry facade

The first S04 implementation imported shared field-kind and grounding aliases from private registry modules. That made the development tool depend on internal module placement rather than the public registry contract.

### public-facade-import-boundary-remediation | low | The public contract now owns every shared S04 type

The registry facade now exports the legal and source reference aliases alongside the existing canonical identifiers and field-kind taxonomy. The schema and its test import each shared type through that facade only. Focused tests, lint, and static analysis pass after the correction, and the independent reviewer confirmed that no coordinate, renderer, catalogue-resolution, or join behavior entered S04.

## Recommendations

No further S04 action is required. Keep catalogue resolution in S05 and exact parser-to-map joining in S07.
