---
tags:
  - '#research'
  - '#modelo-303-calc-verify'
date: '2026-04-27'
modified: '2026-04-27'
related:
  - "[[2026-04-27-modelo-303-calc-verify-adr]]"
  - "[[2026-04-27-modelo-130-calc-verify-adr]]"
  - "[[2026-04-25-mutation-harness-extension-research]]"
---

# `modelo-303-calc-verify` research: 2024 / 2025 / 2026 Tier-L closure

Issue `#326` closes the Modelo 303 calc-verify-roundtrip gap for Kent's quarterly IVA autoliquidación. The implementation mirrors the M130 reference pattern from `#321`: separate per-year ruleset files, year-scoped formula identifiers, a rule-delta manifest, mutation-harness enumeration, and L3 synthetic PDF round-trip evidence.

## Findings

### Current Modelo 303 surface

The existing Modelo 303 ruleset surface is a scoped régimen-general liquidación graph, not a full IVA special-regime engine. It covers 33 casillas in the liquidación block and computes 12 casillas:

| Casilla | Classification | Formula role |
| :--- | :--- | :--- |
| `02` | computed | printed 4 percent rate |
| `03` | computed | `01 x 4 percent` |
| `05` | computed | printed 10 percent rate |
| `06` | computed | `04 x 10 percent` |
| `08` | computed | printed 21 percent rate |
| `09` | computed | `07 x 21 percent` |
| `44` | computed | sum of deductible VAT buckets `29,31,33,35,37,39,40,41,42,43` |
| `45` | computed | output VAT `03+06+09` less `44` |
| `64` | computed | pass-through result for the scoped graph |
| `66` | computed | `64 x 65 / 100` state attribution |
| `69` | computed | `66 - 67` |
| `71` | computed | pass-through final self-assessment result |

The user-supplied casillas are `01, 04, 07, 28, 29, 30, 31, 32, 33, 34, 35, 36, 37, 38, 39, 40, 41, 42, 43, 65, 67`. The ruleset does not derive prorrata percentages, special-regime quotas, simplified-regime modules, recargo de equivalencia, foral allocation, or the small-enterprise franquicia regime.

### BOE grounding

The numerical rates represented in this ruleset are stable across 2024, 2025, and 2026:

| Rule family | Source | Impact |
| :--- | :--- | :--- |
| General rate | LIVA art. 90, `BOE-A-1992-28740#a90` | 21 percent for casillas `08` / `09` |
| Reduced and super-reduced rates | LIVA art. 91, `BOE-A-1992-28740#a91` | 10 percent and 4 percent for casillas `05` / `06` and `02` / `03` |
| Periodic self-assessment | RIVA art. 71, `BOE-A-1992-28925#a71` | quarterly/monthly liquidation framework |
| Modelo 303 form | Orden EHA/3786/2008, `BOE-A-2008-20953` | official autoliquidación model |

The small-enterprise franquicia material is not a Modelo 303 régimen-general formula change in this scope. Directiva (UE) 2020/285 is the EU small-enterprise source; the AEAT 2026 control plan describes foreseeable incorporation requiring future model surfaces, including `modelo 041` and `modelo 350`. That supports an explicit deferral rather than fabricating M303 casilla formulas.

### 2024 to 2025 to 2026 delta

The scoped ruleset has no numeric rate delta:

| Transition | Result |
| :--- | :--- |
| 2024 to 2025 | no change to scoped 21 / 10 / 4 percent régimen-general rates |
| 2025 to 2026 | no change to scoped 21 / 10 / 4 percent régimen-general rates |

The 2026 ruleset should therefore be a structural clone of 2024 / 2025 with its own `modelo_303.2026.*` formula IDs and `2026-01-01` to `2026-12-31` effective window.

### Extractor and generator

`Modelo303V2025Extractor` already parses all 33 liquidación casillas emitted by the L3 synthetic generator. Adding a thin `Modelo303V2026Extractor` subclass is enough because the synthetic and scoped printed layout is unchanged; only the `TemplateRevision` triple differs.

### Mutation node distribution

Modelo 303 is PercentFormula-heavy compared to M130. Each year has:

| Ruleset | `sub_op` | `percent_rate_param` | `percent_rate_casilla_ref_skipped` | `mul_div_scalar` |
| :--- | ---: | ---: | ---: | ---: |
| `modelo_303.2024` | 2 | 3 | 1 | 1 |
| `modelo_303.2025` | 2 | 3 | 1 | 1 |
| `modelo_303.2026` | 2 | 3 | 1 | 1 |

The percent mutator covers `03`, `06`, and `09`; operand-swap covers `45` and `69`; scalar mutation covers the `/100` denominator in `66`. The casilla-reference percent in `66` remains catalogued as out-of-AST input, matching the existing #338 harness policy.

### L1 anchor

A real Modelo 303 declaration PDF is taxpayer-specific and contains private filing data. The executable Tier-L evidence is therefore the L3 synthetic generator plus parser and verification round-trip. The L1 decision should be documented as an explicit waiver rather than pinning a public training or instruction PDF that is not a real declaration.
