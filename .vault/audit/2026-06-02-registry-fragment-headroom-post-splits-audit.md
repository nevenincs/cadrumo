---
tags:
  - '#audit'
  - '#registry-fragment-headroom-post-splits'
date: '2026-06-02'
modified: '2026-06-02'
related:
  - "[[2026-06-02-registry-hardening-next-work-plan]]"
---

# `registry-fragment-headroom-post-splits` audit: `Post-split registry fragment headroom audit`

## Scope

Audit committed AEAT modelo TOML line-count and row-size headroom after the
P05 residual M200 and M303 pressure splits. The audit measures current largest
fragments, row widths, threshold counts, and the next pressure substrate.

## Findings

- **PASS:** No committed TOML fragment exceeds the 1,750-line hard gate.
- **PASS:** No committed TOML row exceeds the 600-character focused row gate.
- **PASS:** The residual pressure split campaign removed every TOML file above
  1,500 lines. The prior P01 audit had nine files at or above 1,500 lines.
- **PASS:** Only one TOML file remains at or above 1,200 lines:
  `src/aeat/_data/registry/aeat/modelos/200/revisions/2024-y-siguientes/records/constructs.part-002.toml`
  at 1,465 lines.
- **WATCH:** The next largest file is M123
  `src/aeat/_data/registry/aeat/modelos/123/revisions/2024-y-siguientes/revision.toml`
  at 1,118 lines. P04.S27 already audited this and found no immediate split
  need.
- **WATCH:** M303 is now below 900 lines. Its largest files are the two
  `0003-export-layout.part-001.toml` fragments at 898 lines.
- **WATCH:** M200 remains the next real substrate, but not in export: the
  largest remaining pressure is `records/constructs.part-002.toml`.

## Recommendations

- Treat M200 `records/constructs.part-002.toml` as the next fragmentation
  substrate if another registry-size step is opened.
- Do not re-split M303 or M200 export in the next slice; both are below the
  residual pressure band.
- Keep M123 in watch status only. The P04.S27 audit already records that it is
  directory-mode and below pressure thresholds.
- Continue running both the hard gate and the lower baseline reviewability test
  after registry fragmentation commits.

## Largest TOML fragments

| Lines | Path |
| ---: | --- |
| 1465 | `src/aeat/_data/registry/aeat/modelos/200/revisions/2024-y-siguientes/records/constructs.part-002.toml` |
| 1118 | `src/aeat/_data/registry/aeat/modelos/123/revisions/2024-y-siguientes/revision.toml` |
| 900 | `src/aeat/_data/registry/aeat/modelos/200/revisions/2024-y-siguientes/records/constructs.part-001.toml` |
| 899 | `src/aeat/_data/registry/aeat/modelos/200/revisions/2024-y-siguientes/records/constructs.part-001b.toml` |
| 898 | `src/aeat/_data/registry/aeat/modelos/303/revisions/2009-y-siguientes/export/0003-export-layout.part-001.toml` |
| 898 | `src/aeat/_data/registry/aeat/modelos/303/revisions/2023-y-siguientes/export/0003-export-layout.part-001.toml` |
| 885 | `src/aeat/_data/registry/aeat/modelos/200/revisions/2024-y-siguientes/export/0010-modelo-200-page-007.toml` |
| 872 | `src/aeat/_data/registry/aeat/modelos/200/revisions/2024-y-siguientes/export/0075-modelo-200-page-053.toml` |

## Threshold counts

| Threshold | TOML files at or above threshold |
| ---: | ---: |
| 1700 | 0 |
| 1600 | 0 |
| 1500 | 0 |
| 1400 | 1 |
| 1300 | 1 |
| 1200 | 1 |
| 1000 | 2 |
| 900 | 3 |
| 800 | 60 |

The corpus currently contains 15,341 TOML files.

## Modelo pressure map

| Modelo | TOML files | Largest fragment |
| --- | ---: | ---: |
| M200 | 1188 | 1465 |
| M123 | 5 | 1118 |
| M303 | 19 | 898 |
| M202 | 257 | 732 |
| M130 | 20 | 667 |
| M232 | 500 | 637 |
| M131 | 69 | 624 |
| M115 | 14 | 485 |
| M369 | 7 | 430 |
| M180 | 129 | 423 |
| M100 | 12866 | 400 |

## Codification candidates

- No new codification candidate. The existing reviewability gate already
  encodes the durable rule; this audit updates the tracked pressure map.
