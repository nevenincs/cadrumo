---
tags:
  - '#audit'
  - '#schema-hardening'
date: '2026-06-02'
modified: '2026-10-03'
body_hash: 'sha256:36d674275eaad2d28004398a8ed5231cad83059749d781e79a63ef09b3c21a82'
related:
  - '[[2026-06-02-registry-hardening-next-work-health-audit]]'
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
| 1706 | 44 | the retired data file |
| 1618 | 132 | the retired data file |
| 1612 | 138 | the retired data file |
| 1598 | 152 | the retired data file |
| 1555 | 195 | the retired data file |
| 1555 | 195 | the retired data file |
| 1550 | 200 | the retired data file |
| 1536 | 214 | the retired data file |
| 1506 | 244 | the retired data file |
| 1472 | 278 | the retired data file |
| 1472 | 278 | the retired data file |
| 1462 | 288 | the retired data file |
| 1430 | 320 | the retired data file |
| 1394 | 356 | the retired data file |
| 1388 | 362 | the retired data file |
| 1359 | 391 | the retired data file |
| 1304 | 446 | the retired data file |
| 1296 | 454 | the retired data file |
| 1296 | 454 | the retired data file |
| 1287 | 463 | the retired data file |
| 1239 | 511 | the retired data file |
| 1239 | 511 | the retired data file |
| 1234 | 516 | the retired data file |
| 1218 | 532 | the retired data file |

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

- the historical check
  - Result: 1 passed in 2.84s.
- the historical check
  - Result: 24 passed in 70.78s.
- `uv run --no-sync vaultspec-core vault plan status.vault/plan/2026-06-02-registry-hardening-next-work-plan.md`
  - Result before closing `P01.S01`: L2, 4 phases, 26 steps, 0/26 complete.
