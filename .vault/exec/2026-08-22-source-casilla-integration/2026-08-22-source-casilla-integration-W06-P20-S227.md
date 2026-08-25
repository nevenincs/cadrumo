---
tags:
  - '#exec'
  - '#source-casilla-integration'
date: '2026-08-25'
modified: '2026-08-25'
body_schema: 'body-v1'
body_hash: 'sha256:7c09efc040a5be1401d230c3f7995bd1d03cf6283813fb92ea7f80c223524bd4'
step_id: 'S227'
related:
  - "[[2026-08-22-source-casilla-integration-plan]]"
---

# defer Modelo 220 group values as an ingress-blocked evidence decision

## Scope

- `.vault/research/2026-08-25-source-casilla-integration-modelo-220-group-value-source-grounding-research.md`
- `.vault/exec/2026-08-22-source-casilla-integration/2026-08-22-source-casilla-integration-W06-P20-S227.md`
- `.vault/plan/2026-08-22-source-casilla-integration-plan.md`
- `.vault/index/source-casilla-integration.index.md`

## Description

- Attest the 2024 AEAT design hash
  `a8f398dd42db0b1142d5f2e98bf3a60d79069e31d63af32001373f459fee4f2e` and
  2025 design hash
  `69c3a234e96eb4485a31c65209348bbcede0a49a8c143223c952000784f3f2df` as
  distinct year-scoped target evidence.
- Preserve the composite group/member source grain, including an explicit
  absent-versus-inapplicable-versus-zero state, rather than collapsing it to a
  header or total.
- Defer the genuine M220 group-value candidate as ingress-blocked because no
  encrypted non-lossy owner exists. Reject export coordinates, direct/manual
  casillas, Modelo 200 relationships, and M222 group identity as source proof.
- Reuse the accepted source-connectivity ADR; add no competing ADR, census row,
  producer, binding, resolver, lifecycle, layout, or export route.

## Outcome

Modelo 220 group values are a genuine source-connectivity candidate at
composite group/member grain, but no non-lossy encrypted owner is evidenced.
The evidence result is therefore **defer / ingress-blocked**, not connection
or `not_applicable`. The 2024 and 2025 designs establish separate targets and
must not be collapsed into one era. Manual/direct M220 entry, M220 export
coordinates, Modelo 200 relationships, and M222 fiscal-group identity are not
source acquisition or lifecycle proof.

No M220 producer key, binding, casilla change, layout, source-mesh route, or
census disposition was created. Reopen only when one secure owner preserves
composite group/member and representative identity, individual-declaration
references, exact period/revision, native role/units, fingerprinted capture
provenance, and absent/inapplicable/zero semantics; it must then prove
resolver enrollment, diagnostics/provenance, encrypted persistence/replay,
review, and supported source-owned export separately for 2024 and 2025.

## Notes

- The accepted source-connectivity ADR governs this evidence decision. A later
  separately authorized census step must attach the bounded campaign follow-up
  before it can admit an ingress-blocked row.
- Semantic RAG initially selected binary workbook blobs, whose renderer cannot
  decode them as UTF-8. Discovery was narrowed to text registry and filing
  surfaces; the official workbook evidence was read through its hash-pinned
  extracted text and source catalogue.
