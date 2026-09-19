---
tags:
  - '#audit'
  - '#source-casilla-integration'
date: '2026-08-25'
modified: '2026-08-26'
body_schema: 'body-v1'
body_hash: 'sha256:ecf88c985c4b934cba1f42b3965ab2d0c37dd0521f981cc626829fb5c1cdfef4'
related:
  - "[[2026-08-22-source-casilla-integration-plan]]"
---
# `source-casilla-integration` audit: `S91 M720 worksheet roundtrip review`

## Scope

Independent review of the mixed M720 handoff commit `2b8164c1ae` and its scoped S91 follow-on `7a909f9d91`, including the S87-S90 boundaries and the worksheet export, pull, calculation, source-resolution, and encrypted revision route.

## Findings

### s91-m720-roundtrip | low | the scoped follow-on retains the canonical route and source identity

The real roundtrip test serializes an XLSX, edits it through `openpyxl`, decodes it with the existing pull decoder, crosses the S90 ingress boundary, invokes the existing M720 calculation action, and reloads through the encrypted calculation repository. It checks grouping, binding-and-row coordinate, worksheet source identity, and the content fingerprint after strict encrypted read-back. No resolver, pipeline, store, or provenance carrier is introduced beside the established M720 source mesh.

### s91-m720-roundtrip | low | canonical content digests and empty workbook bodies remain fail-safe

The M720 resolver uses the shared bare `content_hash_hex` canonical digest for both identity and provenance, avoiding a capped or alternative worksheet hash. The scoped styling changes prevent invalid body ranges when calculation or provenance data is empty while retaining header ranges. The new direct guard exercises the calculation-body branch; the symmetric provenance branch is simple and structurally identical, with no production defect found.

## Recommendations

Keep the real XLSX-to-encrypted-repository test as the boundary proof. If future styling work changes the provenance branch independently, add a focused empty-provenance assertion alongside that change so its present structural symmetry remains explicit.
