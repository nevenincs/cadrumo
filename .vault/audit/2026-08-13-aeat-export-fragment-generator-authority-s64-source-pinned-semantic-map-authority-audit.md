---
tags:
  - '#audit'
  - '#aeat-export-fragment-generator-authority'
date: '2026-08-13'
modified: '2026-08-13'
body_schema: 'body-v1'
body_hash: 'sha256:f5b2d1b43e57d76e557292f50f4eaf0f1447e664345851a625c905fef67bf2b5'
related:
  - "[[2026-08-10-aeat-export-fragment-generator-authority-plan]]"
  - "[[2026-08-10-aeat-export-fragment-generator-authority-adr]]"
---
# `aeat-export-fragment-generator-authority` audit: `S64 Source-Pinned Semantic Map Authority Audit`

## Scope

Audited the S64 source-epoch identity amendment across semantic-map schema, persisted fragments, compilation, parser/revision validation, join, provenance digest, generation attestation, and refusal tests.

## Findings

### s64-source-pinned-semantic-map-authority | low | formal review approved the source-pinned authority

The formal Luna review found no Critical, High, or Medium defects. Every map and fragment requires an exact source reference and SHA-256, mixed fragments refuse, the map identity must match the parser intermediate and selected revision authority, and generation/provenance re-attest the same identity. No design-epoch fallback, implicit source choice, coordinate-bearing projection declaration, alternate anchor catalogue, legacy-layout input, or heuristic compatibility path was found.

### s64-source-pinned-semantic-map-authority | low | focused behavior and static gates passed

The reviewed lane passed 167 focused semantic-map, loader, validation, join, provenance, render-profile, and export-tree tests; an independent real-authority retry passed three source-identity cases. Ruff passed all touched code and tests, BasedPyright reported zero errors, Ty passed, and the diff check passed.

### s64-source-pinned-semantic-map-authority | low | five envelope fixtures remain outside S64

Five existing M303 variable-envelope parametrizations still refuse because their deliberately partial one-field maps omit the complete revision projection declaration set introduced by S62. The failure occurs at projection-declaration bijection, not source identity. S64 did not weaken that invariant or manufacture synthetic declaration coverage; the map-authoring/declaration steps retain this test-debt boundary.

## Recommendations

Close S64. Resume the separately owned DP30302 declaration deficit and five reviewed epoch maps before repairing the partial envelope fixture through complete persisted authority.
