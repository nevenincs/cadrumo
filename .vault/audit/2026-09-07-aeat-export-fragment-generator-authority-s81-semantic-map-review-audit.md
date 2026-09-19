---
tags:
  - '#audit'
  - '#aeat-export-fragment-generator-authority'
date: '2026-09-07'
modified: '2026-09-07'
body_schema: 'body-v2'
body_hash: 'sha256:03fe04c2c5e06eb008406cfcbe02d736f9073015beac7961f9525d004e73fdb7'
related:
  - "[[2026-08-10-aeat-export-fragment-generator-authority-plan]]"
---

# `aeat-export-fragment-generator-authority` audit: `S81 Modelo 390 2024 semantic map review`

## Scope

Reviewed the S81 semantic map, render profile, and focused proof against the
hash-pinned 2024 workbook, the accepted year-scoped authority boundary, and the
2024 revision's existing layout and binding declarations. The review covered
all 621 numbered anchors, the separate 13-anchor auxiliary header, the
2023-to-2024 parser delta, every semantic payload axis, provenance tuples,
record composition, and strict typing.

## Findings

No findings remain. The first verification pass found that layout-owned map
entries retained only the record-design source and dropped additional canonical
procedure/form provenance. The implementation was corrected to preserve each
layout field's complete `source_refs` tuple, and the exhaustive owner comparison
now proves that boundary for all 477 layout-owned anchors.

The final review found no high- or medium-severity issues. It confirmed 341
parser-stable payloads, 200 changed common anchors, 80 additions, 130 exact
binding owners, 14 explicit reserved fillers, the two Lorca replacements, all
nine DANA additions, and the corrected 2024 Page 7 close literal without a
source-defect declaration. No cast, `Any`, type-ignore, or relaxed matcher was
introduced.

## Recommendations

Proceed to S82 using the same exact-owner comparison, with the 2025 removals and
retired slots treated as an independently reviewed epoch delta.
