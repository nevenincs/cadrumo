---
tags:
  - '#reference'
  - '#modelo-390-calc-verify'
date: '2026-04-28'
modified: '2026-04-28'
related:
  - "[[2026-04-27-modelo-390-calc-verify-research]]"
  - "[[2026-04-27-modelo-390-calc-verify-adr]]"
  - "[[2026-04-27-modelo-390-calc-verify-plan]]"
  - "[[2026-04-28-modelo-390-l1-anchor-waiver-reference]]"
---

# Modelo 390 rule-delta manifest — 2024 / 2025 / 2026

This manifest documents the scoped Modelo 390 régimen-general rulesets used by the calc-verify engine for 2024, 2025, and 2026.

## Statutory grounding

| Reference | Role | BOE id |
| :--- | :--- | :--- |
| Ley 37/1992 IVA art. 90 | General 21 percent IVA rate | `BOE-A-1992-28740#a90` |
| Ley 37/1992 IVA art. 91 | Reduced 10 percent and super-reduced 4 percent rates | `BOE-A-1992-28740#a91` |
| Ley 37/1992 IVA arts. 92-100 | IVA soportado deducible framework | `BOE-A-1992-28740` |
| Ley 37/1992 IVA arts. 102-106 | Regla de prorrata, prorrata definitiva | `BOE-A-1992-28740` |
| Ley 37/1992 IVA arts. 107-110 | Regularización por bienes de inversión | `BOE-A-1992-28740` |
| Ley 37/1992 IVA art. 164 | Self-assessment and resumen-anual obligation | `BOE-A-1992-28740` |
| Real Decreto 1624/1992 art. 71 | IVA liquidation period and self-assessment framework | `BOE-A-1992-28925#a71` |
| Real Decreto 1624/1992 art. 71.7 | Specific obligation to file Modelo 390 with last quarter | `BOE-A-1992-28925` |
| Orden EHA/3111/2009 | Approval of Modelo 390 form | `BOE-A-2009-18472` |
| Directiva (UE) 2020/285 and AEAT 2026 control-plan note | 2026 small-enterprise franquicia regime; out of base ruleset scope | `DOUE-L-2020-80356` |

The Orden EHA/3111/2009 is amended annually by an Orden HAC that updates non-substantive form metadata (revision year, BOE id of the pdf template, electronic-presentation rules). Those amendments do not change the rate buckets or the algebraic invariants encoded by the formula DSL.

## Per-year numerical state

| Element | 2024 | 2025 | 2026 | Source |
| :--- | :--- | :--- | :--- | :--- |
| General IVA rate | 21 percent | 21 percent | 21 percent | LIVA art. 90 |
| Reduced IVA rate | 10 percent | 10 percent | 10 percent | LIVA art. 91 |
| Super-reduced IVA rate | 4 percent | 4 percent | 4 percent | LIVA art. 91 |
| Computed casillas | 6 | 6 | 6 | Modelo 390 scoped ruleset |
| User-supplied casillas | 9 | 9 | 9 | Modelo 390 scoped ruleset |
| Casillas parsed by extractor | 15 | 15 | 15 | Modelo 390 extractor surface |
| Bienes-inversión regularización adjust | user-supplied | user-supplied | user-supplied | LIVA art. 107 |

## 2024 to 2025 diff narrative

No scoped numeric amendment. `modelo_390.2025` is a structural clone of `modelo_390.2024` with a year-scoped formula namespace and 2025 parameter effective dates. LIVA arts. 90 and 91 continue to provide 21 / 10 / 4 percent for the upstream Modelo 303 quarterly rate buckets that feed casilla 96. LIVA arts. 92, 102, 107, 164 and RIVA art. 71.7 are unchanged.

## 2025 to 2026 diff narrative

No scoped numeric amendment. `modelo_390.2026` is a structural clone of 2024 / 2025 with a year-scoped formula namespace and 2026 parameter effective dates.

The 2026 small-enterprise franquicia regime introduced by Directiva (UE) 2020/285 is an opt-in regime under which a participating taxpayer drops out of the standard Modelo 390 surface entirely. It is not a modification of the régimen-general result chain encoded by this ruleset and is tracked by sub-EPIC `#345` IVA complexity rather than this base ruleset.

## Casilla inventory

| Apartado | Casillas (computed = bold) | Role |
| :--- | :--- | :--- |
| 1 — datos estadísticos Q1 | `01`, `04` | Statistical reproduction (régimen general 1T base / cuota); user-supplied |
| 3 — régimen general anual | `95`, `96`, `100`, `101`, **`104`**, **`105`** | Total bases / cuotas + IVA soportado (interior + importaciones) + sums |
| 4-5 — otros regímenes | `108`, `109` | Resultado simplificado / otros regímenes; user-supplied |
| 6 — resultado anual | **`190`**, **`191`**, **`192`**, **`193`** | Suma resultado, cuota anual, a ingresar, a devolver |
| 7 — regularización | `662` | Regularización por bienes de inversión; user-supplied |

## Cumulation rules — quarterly Modelo 303 → annual Modelo 390

Modelo 390 is structurally an annual aggregator of the four quarterly Modelo 303 filings. The scoped ruleset chooses Approach C (user-supplied annual aggregates) per the ADR `[[2026-04-27-modelo-390-calc-verify-adr]]`. The cumulation rule encoded by the cumulation tests (`test_modelo_390_cumulation.py`):

| M390 casilla | Annual aggregate | Source M303 casillas (per quarter, summed across 4 quarters) |
| :--- | :--- | :--- |
| `95` | Total bases imponibles | `Σ_q (01 + 04 + 07)` |
| `96` | Total cuotas repercutidas | `Σ_q (03 + 06 + 09)` |
| `100` | Total IVA soportado interior | `Σ_q 29` |
| `101` | Total IVA soportado importaciones | `Σ_q 33` |
| `108` | Resultado régimen simplificado | 0 (out of régimen-general scope) |
| `109` | Resultado otros regímenes | 0 (out of régimen-general scope) |
| `662` | Regularización bienes inversión | annual user-supplied figure (LIVA art. 107) |

Once the user-supplied annual aggregates are in place, the M390 ruleset derives:

| M390 casilla | Formula | Source |
| :--- | :--- | :--- |
| `104` | `100 + 101` | AEAT Modelo 390 Instrucciones |
| `105` | `96 - 104` | AEAT Modelo 390 Instrucciones |
| `190` | `105 + 108 + 109` | AEAT Modelo 390 Instrucciones |
| `191` | `190 - 662` | AEAT Modelo 390 Instrucciones (LIVA art. 107) |
| `192` | `clamp_pos(191)` | AEAT Modelo 390 Instrucciones (positive part of 191) |
| `193` | `clamp_pos(0 - 191)` | AEAT Modelo 390 Instrucciones (sign-flipped negative part) |

## Citation completeness

| Ruleset | Computed casillas | with `LegalCitation` | Coverage |
| :--- | ---: | ---: | ---: |
| `modelo_390.2024` | 6 | 6 | 100.00 percent |
| `modelo_390.2025` | 6 | 6 | 100.00 percent |
| `modelo_390.2026` | 6 | 6 | 100.00 percent |

## Mutation-harness fingerprint

| Ruleset | `sub_op` | `add_op` | `clamp_pos` | `percent_rate_*` | `mul_div_scalar` |
| :--- | ---: | ---: | ---: | ---: | ---: |
| `modelo_390.2024` | 3 | 2 | 2 | 0 | 0 |
| `modelo_390.2025` | 3 | 2 | 2 | 0 | 0 |
| `modelo_390.2026` | 3 | 2 | 2 | 0 | 0 |

The 2024 / 2025 / 2026 sub_op surfaces are structurally identical: casilla `105` (= `sub_op(96, 104)`), casilla `191` (= `sub_op(190, 662)`), and the nested `sub_op(0, 191)` inside casilla `193`'s `clamp_pos`. Operand-swap mutation tests cover casillas `105` and `191` directly across all three years; the nested sub_op inside `193` is enumerated for the catalogue and killed transitively when an upstream casilla diverges.

## Out-of-scope deferrals

- Per-rate-bucket detail of Apartado 3 (the casillas at 4 percent / 10 percent / 21 percent / transitional rates). Tracked under sub-EPIC `#305-Modelo-390-full`.
- Deeper prorrata derivation (LIVA arts. 102-106). Tracked under `#345`.
- Multi-year bienes-de-inversión regularisation window modelling. Tracked under `#345`.
- 2026 small-enterprise franquicia regime full hardening. Tracked under `#345`.
- Foral regimes (País Vasco / Navarra). Tracked under EPIC `#424`.
- Canarias IGIC and Ceuta / Melilla IPSI regional deviations. Out of base ruleset scope.

## L1 anchor decision

No real public Modelo 390 declaración PDF is pinned for this issue. The rationale is documented in `[[2026-04-28-modelo-390-l1-anchor-waiver-reference]]`: real declarations are taxpayer-specific and contain private NIF / liquidation data, while public legal anchors stay in BOE citations. L3 synthetic generation and extraction round-trip are the executable evidence for this Tier-L closure.
