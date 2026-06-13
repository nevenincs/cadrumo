---
tags:
  - '#audit'
  - '#schema-hardening'
date: '2026-06-04'
modified: '2026-06-04'
related:
  - '[[2026-06-02-registry-hardening-next-work-plan]]'
---

# `schema-hardening` audit: `Registry reviewability gate headroom`

## Scope

Execute `W03.P07.S35` from the registry hardening next-work plan. The audit
measures the committed registry TOML corpus before tightening the regression
gates. It does not move registry data and does not change loader or schema
semantics.

## Findings

- PASS: The committed registry corpus contains 15,345 TOML files under
  `src/aeat/_data/registry/aeat/modelos`.
- PASS: No registry TOML file exceeds 1,500 lines.
- PASS: No registry TOML row exceeds 600 characters.
- OBSERVED: One registry TOML file remains above the 1,200-line review band:
  `src/aeat/_data/registry/aeat/modelos/123/revisions/2024-y-siguientes/revision.toml`
  at 1,218 lines.
- OBSERVED: Two registry TOML files are above 1,000 lines.
- OBSERVED: Six registry TOML files have at least one row wider than 550
  characters.

## Largest files

| Lines | Max row | Path |
| ---: | ---: | --- |
| 1,218 | 290 | `src/aeat/_data/registry/aeat/modelos/123/revisions/2024-y-siguientes/revision.toml` |
| 1,039 | 542 | `src/aeat/_data/registry/aeat/modelos/303/revisions/2023-y-siguientes/revision.toml` |
| 969 | 153 | `src/aeat/_data/registry/aeat/modelos/303/revisions/2023-y-siguientes/export/0003-export-layout.part-001.toml` |
| 969 | 153 | `src/aeat/_data/registry/aeat/modelos/303/revisions/2009-y-siguientes/export/0003-export-layout.part-001.toml` |
| 954 | 431 | `src/aeat/_data/registry/aeat/modelos/200/revisions/2024-y-siguientes/export/0010-modelo-200-page-007.toml` |
| 940 | 431 | `src/aeat/_data/registry/aeat/modelos/200/revisions/2024-y-siguientes/export/0075-modelo-200-page-053.toml` |
| 932 | 305 | `src/aeat/_data/registry/aeat/modelos/123/revisions/2019-2023/revision.toml` |
| 912 | 431 | `src/aeat/_data/registry/aeat/modelos/200/revisions/2024-y-siguientes/export/0008-modelo-200-page-005.toml` |
| 900 | 44 | `src/aeat/_data/registry/aeat/modelos/200/revisions/2024-y-siguientes/records/constructs.part-001b.toml` |
| 900 | 499 | `src/aeat/_data/registry/aeat/modelos/200/revisions/2024-y-siguientes/records/constructs.part-001.toml` |

## Widest rows

| Max row | Lines | Path |
| ---: | ---: | --- |
| 572 | 10 | `src/aeat/_data/registry/aeat/modelos/100/revisions/2025/casillas/0618-0552.toml` |
| 552 | 21 | `src/aeat/_data/registry/aeat/modelos/100/revisions/2023/completeness/0001-manifest.toml` |
| 552 | 14 | `src/aeat/_data/registry/aeat/modelos/202/revisions/2025-y-siguientes/constructs/0001-modelo-202-foundation.toml` |
| 552 | 21 | `src/aeat/_data/registry/aeat/modelos/100/revisions/2021/completeness/0001-manifest.toml` |
| 552 | 21 | `src/aeat/_data/registry/aeat/modelos/100/revisions/2024/completeness/0001-manifest.toml` |
| 552 | 21 | `src/aeat/_data/registry/aeat/modelos/100/revisions/2022/completeness/0001-manifest.toml` |
| 550 | 10 | `src/aeat/_data/registry/aeat/modelos/100/revisions/2025/casillas/0616-0550.toml` |
| 545 | 9 | `src/aeat/_data/registry/aeat/modelos/100/revisions/2020/casillas/0146-0153.toml` |
| 542 | 1,039 | `src/aeat/_data/registry/aeat/modelos/303/revisions/2023-y-siguientes/revision.toml` |
| 528 | 8 | `src/aeat/_data/registry/aeat/modelos/100/revisions/2025/casillas/0615-0549.toml` |

## Gate recommendation

- Tighten the corpus hard cap from 5,000 lines to 1,500 lines.
- Tighten the corpus row-width hard cap from 1,200 characters to 600
  characters.
- Tighten the baseline assertion from 3,500 lines to 1,250 lines, keeping a
  small allowance above the current 1,218-line M123 file.
- Tighten the baseline row assertion from 1,000 characters to 575 characters,
  keeping a small allowance above the current 572-character row.
- Keep M123 visible as the only current soft-band follow-up candidate.

## Verification

This audit was produced from a direct scan of committed TOML files under the
registry modelos directory. The next step owns changing the test constants and
running the focused registry reviewability tests.
