---
tags:
  - '#research'
  - '#modelo-390-calc-verify'
date: '2026-04-27'
modified: '2026-04-27'
related:
  - "[[2026-04-27-modelo-303-calc-verify-research]]"
  - "[[2026-04-27-modelo-130-calc-verify-research]]"
---

# `modelo-390-calc-verify` research: tier-l calc-verify completeness for the annual iva resumen

This research note grounds issue `#327` (Tier-L calc-verify-roundtrip for Modelo 390 across 2024 / 2025 / 2026) under the EPIC `#316` per-modelo completeness umbrella. It surveys the Modelo 390 BOE template, classifies every casilla currently parsed by the extractor, identifies the year-over-year delta surface, and selects an annual-cumulation approach compatible with the existing formula DSL.

## Modelo 390 in one paragraph

Modelo 390 is the *declaración-resumen anual del IVA*. A taxpayer who files the four quarterly Modelo 303 autoliquidaciones during the year files exactly one Modelo 390 with período code `0A` after year-end, summarising the full-year IVA position, the régimen-by-régimen result split, the regularización por bienes de inversión adjustment, and the cuota anual a ingresar / a devolver. The full BOE template runs to roughly 680 fields. The project's MVP — and the supported scope of this issue — targets the result chain Kent's autónomo profile actually produces: Apartado 1 datos estadísticos (Q1 base / cuota), Apartado 3 régimen general totals, Apartado 6 resultado anual, Apartado 7 regularización bienes de inversión.

## Statutory grounding

| Reference | Role | BOE id |
| :--- | :--- | :--- |
| Ley 37/1992 IVA art. 90 | General 21 percent IVA rate | `BOE-A-1992-28740#a90` |
| Ley 37/1992 IVA art. 91 | Reduced 10 percent and super-reduced 4 percent rates | `BOE-A-1992-28740#a91` |
| Ley 37/1992 IVA arts. 92-100 | IVA soportado deducible framework (interior + importaciones + intracomunitarias) | `BOE-A-1992-28740` |
| Ley 37/1992 IVA arts. 102-106 | Regla de prorrata, prorrata definitiva | `BOE-A-1992-28740` |
| Ley 37/1992 IVA arts. 107-110 | Regularización por bienes de inversión | `BOE-A-1992-28740` |
| Ley 37/1992 IVA art. 164 | General self-assessment + resumen-anual obligation | `BOE-A-1992-28740` |
| Real Decreto 1624/1992 art. 71 | IVA liquidation period and self-assessment framework | `BOE-A-1992-28925` |
| Real Decreto 1624/1992 art. 71.7 | Specific obligation to file Modelo 390 with last quarter | `BOE-A-1992-28925` |
| Orden EHA/3111/2009 | Approval of Modelo 390 form | `BOE-A-2009-18472` |
| Directiva (UE) 2020/285 | 2026 small-enterprise franquicia regime — out of base ruleset scope | `DOUE-L-2020-80356` |

The order EHA/3111/2009 is amended annually by an Orden HAC that updates non-substantive form metadata (revision year, BOE id of the pdf template, electronic-presentation rules). Those amendments do not change the rate buckets or the algebraic invariants encoded by the formula DSL; they affect form layout and submission logistics.

## Casilla inventory (extractor surface)

The extractor `Modelo390V2025Extractor` parses 15 casillas. Classification:

| Casilla | Apartado | Role | computed in MVP |
| :--- | :--- | :--- | :--- |
| `01` | 1 (datos estadísticos Q1) | Régimen general 1T base | no |
| `04` | 1 (datos estadísticos Q1) | Régimen general 1T cuota | no |
| `95` | 3 (régimen general anual) | Total bases imponibles | no |
| `96` | 3 (régimen general anual) | Total cuotas repercutidas | no |
| `100` | 3 | Total IVA soportado deducible interior | no |
| `101` | 3 | Total IVA soportado deducible importaciones | no |
| `104` | 3 | Total IVA soportado deducible (= 100 + 101 in MVP) | yes |
| `105` | 3 | Resultado régimen general (= 96 - 104) | yes |
| `108` | 4-5 | Resultado simplificado | no |
| `109` | 4-5 | Resultado otros regímenes | no |
| `190` | 6 | Suma resultado (= 105 + 108 + 109) | yes |
| `191` | 6 | Cuota resultante anual (= 190 - 662) | yes |
| `192` | 6 | Total a ingresar (= positive part of 191) | yes |
| `193` | 6 | Total a devolver (= negative part of 191, sign-flipped) | yes |
| `662` | 7 | Regularización bienes de inversión | no |

Casillas `01` and `04` are statistical-only: AEAT prints them at the top of Apartado 1 to recall the Q1 régimen-general base / cuota, but they are not in the algebraic chain that produces the anual liquidación. They remain user-supplied inputs in the ruleset to satisfy the extractor surface (so a partial-extraction integration test still rounds-trips), but no formula derives them.

The MVP does not derive casilla `96` from an underlying rate-bucket split — Modelo 390's Apartado 3 actually has bases / cuotas at every IVA rate (4 / 10 / 21 percent, plus historic transitional rates for alimentación básica / electricidad / gas) which would balloon the casilla count well past 15. Kent files Modelo 390 by transcribing his already-rolled-up annual cuota repercutida as casilla 96; the full per-rate decomposition is left for the IVA complexity sub-EPIC `#345`.

## Per-year delta survey (2024 → 2025 → 2026)

Primary BOE evidence reviewed:

- **LIVA art. 90** keeps the general 21 percent rate. No amendment between 2024 and 2026.
- **LIVA art. 91** keeps the reduced 10 percent and super-reduced 4 percent rates used by the project ruleset. No amendment between 2024 and 2026.
- **LIVA arts. 92-100** keep the deducible-input framework as taxpayer-supplied buckets in the project ruleset. No amendment between 2024 and 2026.
- **LIVA arts. 102-110** (prorrata + bienes de inversión) — the regularización mechanism is unchanged. The MVP keeps casilla 662 as a user-supplied annual adjustment.
- **RIVA art. 71** anchors the autoliquidación cycle and the resumen-anual obligation. Unchanged between 2024 and 2026.
- **Orden EHA/3111/2009** approves Modelo 390. Annually amended for form metadata only; the algebraic chain encoded by the project ruleset is unchanged.
- **2026 franquicia IVA** (Directiva (UE) 2020/285 transposed by Spain in 2025-2026): introduces a small-enterprise exemption regime. This is a *new optional regime*, not a modification of the régimen-general result chain — taxpayers in franquicia drop out of the standard Modelo 390 surface entirely. Out of scope for the base ruleset; tracked under sub-EPIC `#345` IVA complexity.

Conclusion: 2024, 2025, and 2026 share the same algebraic invariants for the result chain Kent files. The three rulesets are structural clones with year-scoped formula identifiers and per-year ParameterTable effective-date windows. This mirrors the pattern landed for Modelo 303 (`#326`), Modelo 130 (`#321`), Modelo 115 (`#319`), Modelo 111 (`#318`), Modelo 123 (`#320`), and Modelo 131 (`#322`).

## Cumulation design

Modelo 390 is structurally an annual aggregator of the four quarterly Modelo 303 filings. There are three plausible architectural approaches:

| Approach | Shape | Cost | Fits today? |
| :--- | :--- | :--- | :--- |
| A — DSL aggregator primitive | Add a new formula primitive to `aeat.domain.formulas` that references four sibling rulesets and aggregates per-rate-bucket totals | High: invents a new DSL primitive, cross-ruleset references | No |
| B — Live-AEAT-driven cumulation | Read four real M303 filings from AEAT and verify M390 against them | Out of scope | No |
| C — User-supplied annual aggregates | Treat the cumulated casillas (95, 96, 100, 101, 108, 109, 662) as user-supplied; derive only the algebraic relationships among them inside the M390 ruleset | Low: matches the existing M180 annual-summary pattern | Yes |

**Decision: approach C.** Justification:

- Approach C matches the only annual-summary precedent already in the codebase: Modelo 180 (annual IRPF retention summary) treats its consolidated values as user-supplied and derives only the algebraic invariants (casilla 03 = 19 percent of casilla 02). Modelo 390 follows the same pattern.
- Approach A would require inventing a new aggregator primitive in the DSL. Issue `#437` (needs-design ADR for aggregator cumulation) is open precisely to design that primitive once enough cumulation cases have surfaced. Inventing it inside this issue would lock the API before `#437` had a chance to harmonise across M390 + M180.
- Approach C still allows cumulation testing: a dedicated test class generates four synthetic quarterly M303 fixtures, computes their expected annual sums, generates an annual M390 fixture with those sums, and verifies the round-trip. The cumulation correctness is asserted at the test level, not encoded in the DSL.
- Approach C keeps the code surface deliberately thin so that a future `#437`-prescribed primitive can replace the user-supplied aggregator transparently.

## Algebraic invariants encoded in the ruleset

| Casilla | Formula | Source |
| :--- | :--- | :--- |
| `104` | `100 + 101` | AEAT Modelo 390 Instrucciones — total IVA soportado deducible operaciones interiores |
| `105` | `96 - 104` | AEAT Modelo 390 Instrucciones — resultado régimen general |
| `190` | `105 + 108 + 109` | AEAT Modelo 390 Instrucciones — suma resultado |
| `191` | `190 - 662` | AEAT Modelo 390 Instrucciones — cuota resultante anual after bienes-inversión adjustment |
| `192` | `clamp_pos(191)` | AEAT Modelo 390 Instrucciones — total a ingresar (positive part) |
| `193` | `clamp_pos(0 - 191)` | AEAT Modelo 390 Instrucciones — total a devolver (sign-flipped negative part) |

The `clamp_pos` choice for 192 / 193 mirrors the M130 pattern for casilla `04` (`clamp_pos(percent(rate, base))`). The pair is mutually exclusive at any point in time: when 191 ≥ 0 then 192 = 191 and 193 = 0; when 191 < 0 then 192 = 0 and 193 = -191. The ruleset preserves this invariant by independent clamps rather than a sign predicate, so the engine never has to branch.

## Worked-example anchoring

Per-year tests use externally-anchored expected values:

- **Zero-boundary**: every input zero ⇒ every computed casilla 0.00. Already exercised by `test_zero_boundary_coverage.py`.
- **Typical autónomo**: bases and cuotas at the rates LIVA arts. 90 / 91 prescribe; expected values derived from those statutory rates, not from the ruleset's parameter table.
- **Threshold edges**: zero crossing of casilla 191 (one year a ingresar, next year a devolver), regularización bienes-inversión large enough to flip 191 from positive to negative.
- **Cumulation edge**: M390 fixture whose 95 / 96 / 100 / 101 / 108 / 109 / 662 values equal the sum of four synthetic quarterly M303 fixtures; verifies that an annually-aggregated kent input round-trips.

Each test cites the BOE article that grounds the rate or threshold. No expected value is computed by feeding the ruleset back into itself.

## Mutation-harness extension

Modelo 390's mutable-node fingerprint changes from the current MVP:

| Surface | 2024 / 2025 / 2026 |
| :--- | :--- |
| `sub_op` | `105` (= 96 - 104) + `191` (= 190 - 662) + `193` internal (= 0 - 191) → 3 |
| `clamp_pos` | `192` (= clamp_pos(191)) + `193` (= clamp_pos(0 - 191)) → 2 |
| `add_op` | `104` (= 100 + 101) + `190` (= 105 + 108 + 109) → 2 |
| `percent_rate_*` | none — Modelo 390 sums pre-computed cuotas | 0 |
| `mul_div_scalar` | none | 0 |

Operand-swap mutation must cover the three `sub_op` chains. The aggregate kill-rate floor of 90 percent on the populated mutator surface (issue `#338` DoD) remains satisfied by the existing exhaustiveness defense.

## L1 anchor decision

Modelo 390 declarations are taxpayer-specific autoliquidaciones containing private NIF / period / liquidation data. Public BOE / AEAT instruction PDFs are legal-text references, not declaración exemplars; they would not validate the extractor's real-declaration path. The same waiver pattern as Modelo 303 (`#326`) applies: this issue ships an explicit L1 waiver in `.vault/reference/`, and L3 synthetic generation is the executable evidence tier.

The waiver may be revisited if AEAT publishes a non-private completed Modelo 390 declaration exemplar or a contributor provides a consented, scrubbed, hash-pinned declaration PDF.

## Out-of-scope deferrals

- Per-rate-bucket bases / cuotas in Apartado 3 (the casillas at 4 percent / 10 percent / 21 percent / transitional rates). The full ~680-casilla template waits on sub-EPIC `#305-Modelo-390-full`.
- 2026 franquicia IVA full hardening (annual revenue threshold rule, opt-in mechanics, regime-change transitions). Tracked under `#345` IVA complexity sub-EPIC.
- Prorrata derivation. The MVP keeps prorrata-adjusted IVA deducible as user-supplied; the deeper derivation belongs to `#345`.
- Bienes-de-inversión deeper modelling (multi-year regularización windows, adquisición date tracking). The MVP keeps `662` as a single user-supplied annual adjustment; deeper modelling belongs to `#345`.
- Foral regimes (País Vasco / Navarra). Tracked under EPIC `#424`.
- Regional deviations (Canarias IGIC, Ceuta / Melilla IPSI). Out of base ruleset scope.

## Closing reasoning

The issue collapses to the now-canonical Tier-L pattern that landed for the previous six modelos:

1. Per-year scoped rulesets (2024 / 2025 / 2026) with year-stamped formula IDs, declaratively cloning the same algebraic invariants because the underlying BOE text did not change.
2. Citation-backed `CasillaDefinition` rows for every computed casilla (issue `#339` mandatory-citation invariant).
3. A rule-delta manifest in `.vault/reference/` that documents the per-year sameness with BOE evidence.
4. An L1 anchor waiver because real Modelo 390 declarations are private.
5. L3 synthetic round-trip plus Kent CLI integration as the executable evidence tier.
6. Cumulation tests asserted at the *test* level (Approach C) rather than encoded in the DSL.

The implementation completes the seventh of eleven Tier-L modelos. The remaining four (`#317` M100 RENTA in flight, plus `#323` M180, `#324` M190, `#325` M193) are out of scope for this issue.
