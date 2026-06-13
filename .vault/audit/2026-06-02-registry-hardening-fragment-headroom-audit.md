---
tags:
  - '#audit'
  - '#schema-hardening'
date: '2026-06-02'
modified: '2026-06-02'
related:
  - '[[2026-06-02-registry-hardening-next-work-plan]]'
  - '[[2026-06-02-registry-hardening-next-work-health-audit]]'
  - '[[2026-05-19-modelo-registry-fragment-architecture-adr]]'
---

# Registry Hardening Fragment Headroom Audit

## Scope

This audit executes `P01.S01` from `2026-06-02-registry-hardening-next-work-plan`.
It measures committed TOML fragment line pressure and row-size pressure after the
registry directory-mode rollout, so the next hardening slices are grounded in the
current corpus instead of assumed from pre-fragmentation file sizes.

## Summary

The committed corpus currently stays inside the reviewability gates:

- No committed TOML fragment exceeds 1750 lines.
- No committed TOML row exceeds 600 characters.
- The largest TOML fragment is the M100 2024 completeness manifest at 1706
  lines, leaving only 44 lines of headroom.
- The next pressure band is dominated by M200 export fragments, M100
  completeness manifests, and M303 casilla/export fragments.
- M123 has one 1218-line revision file; it is not urgent, but it is now tracked
  explicitly because it is above the 1200-line observation threshold.

## Largest TOML Fragments

| Lines | Headroom | Path |
| ---: | ---: | --- |
| 1706 | 44 | `src/aeat/_data/registry/aeat/modelos/100/revisions/2024/completeness-manifest.toml` |
| 1618 | 132 | `src/aeat/_data/registry/aeat/modelos/200/revisions/2024-y-siguientes/export/0028-modelo-200-page-019.part-002.toml` |
| 1612 | 138 | `src/aeat/_data/registry/aeat/modelos/200/revisions/2024-y-siguientes/export/0065-modelo-200-page-043.toml` |
| 1598 | 152 | `src/aeat/_data/registry/aeat/modelos/100/revisions/2023/completeness-manifest.toml` |
| 1555 | 195 | `src/aeat/_data/registry/aeat/modelos/200/revisions/2024-y-siguientes/export/0002-modelo-200-page-001.toml` |
| 1555 | 195 | `src/aeat/_data/registry/aeat/modelos/200/revisions/2024-y-siguientes/export/0033-modelo-200-page-020d.toml` |
| 1550 | 200 | `src/aeat/_data/registry/aeat/modelos/100/revisions/2022/completeness-manifest.toml` |
| 1536 | 214 | `src/aeat/_data/registry/aeat/modelos/303/revisions/2023-y-siguientes/casillas/0001-casillas.toml` |
| 1506 | 244 | `src/aeat/_data/registry/aeat/modelos/303/revisions/2009-y-siguientes/casillas/0001-casillas.toml` |
| 1472 | 278 | `src/aeat/_data/registry/aeat/modelos/200/revisions/2024-y-siguientes/export/0016-modelo-200-page-013.toml` |
| 1472 | 278 | `src/aeat/_data/registry/aeat/modelos/200/revisions/2024-y-siguientes/export/0054-modelo-200-page-032.toml` |
| 1462 | 288 | `src/aeat/_data/registry/aeat/modelos/200/revisions/2024-y-siguientes/records/constructs.part-002.toml` |
| 1430 | 320 | `src/aeat/_data/registry/aeat/modelos/200/revisions/2024-y-siguientes/export/0015-modelo-200-page-012.toml` |
| 1394 | 356 | `src/aeat/_data/registry/aeat/modelos/100/revisions/2021/completeness-manifest.toml` |
| 1388 | 362 | `src/aeat/_data/registry/aeat/modelos/100/revisions/2020/completeness-manifest.toml` |
| 1359 | 391 | `src/aeat/_data/registry/aeat/modelos/200/revisions/2024-y-siguientes/export/0031-modelo-200-page-020b.toml` |
| 1304 | 446 | `src/aeat/_data/registry/aeat/modelos/200/revisions/2024-y-siguientes/export/0055-modelo-200-page-033.toml` |
| 1296 | 454 | `src/aeat/_data/registry/aeat/modelos/303/revisions/2009-y-siguientes/export/0003-export-layout.toml` |
| 1296 | 454 | `src/aeat/_data/registry/aeat/modelos/303/revisions/2023-y-siguientes/export/0003-export-layout.toml` |
| 1287 | 463 | `src/aeat/_data/registry/aeat/modelos/200/revisions/2024-y-siguientes/export/0018-modelo-200-page-014b.toml` |
| 1239 | 511 | `src/aeat/_data/registry/aeat/modelos/303/revisions/2023-y-siguientes/export/0002-export-layout.toml` |
| 1239 | 511 | `src/aeat/_data/registry/aeat/modelos/303/revisions/2009-y-siguientes/export/0002-export-layout.toml` |
| 1234 | 516 | `src/aeat/_data/registry/aeat/modelos/200/revisions/2024-y-siguientes/export/0047-modelo-200-page-026g.toml` |
| 1218 | 532 | `src/aeat/_data/registry/aeat/modelos/123/revisions/2024-y-siguientes/revision.toml` |

## Threshold Counts

| Threshold | TOML files at or above threshold |
| ---: | ---: |
| 1700 | 1 |
| 1600 | 3 |
| 1500 | 9 |
| 1400 | 13 |
| 1300 | 17 |
| 1200 | 24 |
| 1000 | 25 |

The corpus contains 15261 TOML files.

## Modelo Pressure Map

| Modelo | TOML files | Largest fragment |
| --- | ---: | ---: |
| M100 | 12837 | 1706 |
| M200 | 1172 | 1618 |
| M303 | 13 | 1536 |
| M123 | 5 | 1218 |
| M202 | 253 | 790 |
| M130 | 20 | 721 |
| M232 | 500 | 688 |
| M131 | 69 | 624 |

## Work Tracked

This audit confirms the current P01 order remains defensible:

- `P01.S02`: split the M100 2024 completeness manifest first because it has
  only 44 lines of headroom.
- `P01.S03` through `P01.S06`: continue M100 completeness manifest splitting
  for 2023, 2022, 2021, and 2020.
- `P01.S07` and `P01.S08`: audit then split M200 export pressure where safe
  page or part boundaries exist.
- `P01.S09`: audit M303 casilla and export pressure before deciding whether to
  split.
- `P04.S27`: audit M123 revision-file pressure discovered in this pass.

## Verification

- `uv run --no-sync pytest src/aeat/domain/calculations/registry/test_loader_directory_mode.py::test_committed_registry_toml_files_stay_reviewable -q`
  - Result: 1 passed in 2.84s.
- `uv run --no-sync pytest src/aeat/domain/calculations/registry/test_loader_directory_mode.py -q`
  - Result: 24 passed in 70.78s.
- `uv run --no-sync vaultspec-core vault plan status .vault/plan/2026-06-02-registry-hardening-next-work-plan.md`
  - Result before closing `P01.S01`: L2, 4 phases, 26 steps, 0/26 complete.
