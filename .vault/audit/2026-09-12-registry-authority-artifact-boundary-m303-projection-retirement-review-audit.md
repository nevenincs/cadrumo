---
tags:
  - '#audit'
  - '#registry-authority-artifact-boundary'
date: '2026-09-12'
modified: '2026-09-12'
body_schema: 'body-v2'
body_hash: 'sha256:350dea14567915ac993b4afe1191a26b8d5d954ef46665812d11497d2d1e811e'
related:
  - "[[2026-09-10-registry-authority-artifact-boundary-plan]]"
  - "[[2026-09-10-registry-authority-artifact-boundary-adr]]"
---

# `registry-authority-artifact-boundary` audit: `M303 projection endpoint retirement review`

## Scope

Reviewed only the sixteen `projection_endpoints` retirements authored at the
Modelo 303 `2024-hasta-08-y-2t` and `2025` revision boundaries. The review
compared each exact identifier with the immediately preceding revision's
projection declaration and the official DP30302 mappings for 2023,
2024-early, 2024-late, and 2025. It also checked the live typed evolution
schema and compiler inheritance contract: omission preserves an endpoint,
whereas a `retired` evolution removes it from the named revision onward.

The four 2023 staff-snapshot endpoints occupy the 2023 DP30302 fields whose
corresponding 2024-early positions are filler. The twelve temporary DANA and
Lorca endpoints exist in the 2024-late design, while their complete occupied
spans are replaced by the AEAT-reserved `f094`, `f121`, and `f148` positions
in the 2025 design. Each declaration cites both sides of its revision boundary
and the governing simplified-regime provisions.

This audit does not review publication of a regenerated runtime artifact, does
not claim completion of any broader plan step, and does not adjudicate the two
unindexed `superficie_horno_dias_cuarto_trimestre` endpoints.

## Findings

No findings. All sixteen retirement declarations are truthful at their stated
revision boundaries: four unique 2023 endpoints retire in
`2024-hasta-08-y-2t`, and twelve unique 2024-late endpoints retire in `2025`.
No reviewed identifier is a rename, simple continuation, or supported
successor projection in the destination revision.

## Recommendations

Accept the bounded sixteen-endpoint retirement slice. Keep the two
`superficie_horno_dias_cuarto_trimestre` endpoints outside this acceptance:
their predecessor-to-successor relationship remains an unresolved one-to-four
split and requires separate official-evidence adjudication before any evolution
record is authored.
