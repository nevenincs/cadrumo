---
tags:
  - '#reference'
  - '#modelo-303-calc-verify'
date: '2026-04-27'
modified: '2026-04-27'
related:
  - "[[2026-04-27-modelo-303-calc-verify-research]]"
  - "[[2026-04-27-modelo-303-calc-verify-adr]]"
  - "[[2026-04-27-modelo-303-calc-verify-plan]]"
---

# Modelo 303 rule-delta manifest — 2024 / 2025 / 2026

This manifest documents the scoped Modelo 303 régimen-general rulesets used by the calc-verify engine for 2024, 2025, and 2026.

## Statutory grounding

| Reference | Role | BOE id |
| :--- | :--- | :--- |
| Ley 37/1992 IVA art. 90 | General 21 percent IVA rate | `BOE-A-1992-28740#a90` |
| Ley 37/1992 IVA art. 91 | Reduced 10 percent and super-reduced 4 percent rates | `BOE-A-1992-28740#a91` |
| Ley 37/1992 IVA arts. 92-100 | Deduction right and taxpayer-supplied deductible VAT buckets | `BOE-A-1992-28740` |
| Real Decreto 1624/1992 art. 71 | IVA liquidation period and autoliquidación framework | `BOE-A-1992-28925#a71` |
| Orden EHA/3786/2008 | Official Modelo 303 form | `BOE-A-2008-20953` |
| Directiva (UE) 2020/285 and AEAT 2026 control-plan note | Small-enterprise franquicia watch-list; not a scoped M303 formula change here | `DOUE-L-2020-80356`, `BOE-A-2026-5843` |

## Per-year numerical state

| Element | 2024 | 2025 | 2026 | Source |
| :--- | :--- | :--- | :--- | :--- |
| General IVA rate | 21 percent | 21 percent | 21 percent | LIVA art. 90 |
| Reduced IVA rate | 10 percent | 10 percent | 10 percent | LIVA art. 91 |
| Super-reduced IVA rate | 4 percent | 4 percent | 4 percent | LIVA art. 91 |
| Computed casillas | 12 | 12 | 12 | Modelo 303 scoped ruleset |
| Liquidación casillas parsed by extractor | 33 | 33 | 33 | Modelo 303 extractor/generator surface |
| State attribution denominator | 100 | 100 | 100 | Modelo 303 form arithmetic |

## 2024 to 2025 diff narrative

No scoped numeric amendment. `modelo_303.2025` is a structural clone of `modelo_303.2024` with a year-scoped formula namespace and 2025 parameter effective dates. LIVA arts. 90 and 91 continue to provide 21 / 10 / 4 percent for the represented rate buckets.

## 2025 to 2026 diff narrative

No scoped numeric amendment. `modelo_303.2026` is a structural clone of 2024 / 2025 with a year-scoped formula namespace and 2026 parameter effective dates.

The 2026 small-enterprise franquicia context is not encoded in this base ruleset. It is a special-regime watch-list item with separate future model surfaces and belongs to the IVA complexity workstream, not the current 33-casilla régimen-general formula graph.

## Casilla inventory

| Category | Casillas |
| :--- | :--- |
| Computed | `02, 03, 05, 06, 08, 09, 44, 45, 64, 66, 69, 71` |
| User-supplied | `01, 04, 07, 28, 29, 30, 31, 32, 33, 34, 35, 36, 37, 38, 39, 40, 41, 42, 43, 65, 67` |
| Explicitly out of scoped formula derivation | special regimes, prorrata derivation, simplified regime, recargo de equivalencia, OSS/IOSS, foral/regional overlays, franquicia |

## Citation completeness

| Ruleset | Computed casillas | with `LegalCitation` | Coverage |
| :--- | ---: | ---: | ---: |
| `modelo_303.2024` | 12 | 12 | 100.00 percent |
| `modelo_303.2025` | 12 | 12 | 100.00 percent |
| `modelo_303.2026` | 12 | 12 | 100.00 percent |

## Mutation-harness fingerprint

| Ruleset | `sub_op` | `percent_rate_param` | `percent_rate_casilla_ref_skipped` | `mul_div_scalar` |
| :--- | ---: | ---: | ---: | ---: |
| `modelo_303.2024` | 2 | 3 | 1 | 1 |
| `modelo_303.2025` | 2 | 3 | 1 | 1 |
| `modelo_303.2026` | 2 | 3 | 1 | 1 |

The 2026 percent-rate mutator cases cover casillas `03`, `06`, and `09`. Operand-swap mutation covers `45` and `69`. Scalar mutation covers the `/100` denominator in `66`.

## L1 anchor decision

No real public Modelo 303 declaración PDF is pinned for this issue. The rationale is documented in `2026-04-27-modelo-303-l1-anchor-waiver-reference.md`: real declarations are taxpayer-specific, while public instruction/legal PDFs are not declaration fixtures. L3 synthetic generation and extraction round-trip are the executable evidence for this Tier-L closure.
