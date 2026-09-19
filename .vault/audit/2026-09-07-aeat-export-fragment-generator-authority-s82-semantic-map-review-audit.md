---
tags:
  - '#audit'
  - '#aeat-export-fragment-generator-authority'
date: '2026-09-07'
modified: '2026-09-07'
body_schema: 'body-v2'
body_hash: 'sha256:a45e0d3a885a9da00767d53a83f1e00cb37eccb390b5fc8726da991dfff9ed02'
related:
  - "[[2026-08-10-aeat-export-fragment-generator-authority-plan]]"
---

# `aeat-export-fragment-generator-authority` audit: `S82 Modelo 390 2025 semantic map review`

## Scope

Reviewed the S82 semantic map, render profile, and focused proof against the
hash-pinned 2025 workbook, the accepted year-scoped authority boundary, and the
2025 revision's existing layout and binding declarations. The review covered
all 612 numbered anchors, the separate 13-anchor auxiliary header, the complete
2024-to-2025 delta, every semantic payload and provenance axis, record
composition, and strict typing.

## Findings

No findings remain. The final review confirmed 523 parser-stable payloads, 89
changed common anchors, nine removed Page 5 rows, 477 exact layout owners, 119
exact binding owners, and 16 explicit fillers. Page 5 A27, A51, and A101 are
proved as the three retired semantic slots rather than silently omitted owners.

The 2025 map and profile render nine numbered records containing all 612 fields;
the official Page 7 close literal remains correct and requires no source-defect
declaration. No cast, `Any`, type-ignore, relaxed matcher, compatibility path,
or neighbouring-epoch fallback was introduced. The final review found no high-
or medium-severity issues.

## Recommendations

Proceed to the generated Modelo 390 publication step only with all four epoch
maps present and the explicit candidate-staging boundary retained.
