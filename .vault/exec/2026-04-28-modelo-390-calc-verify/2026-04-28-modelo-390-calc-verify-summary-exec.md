---
tags:
  - '#exec'
  - '#modelo-390-calc-verify'
date: '2026-04-28'
modified: '2026-04-28'
related:
  - "[[2026-04-27-modelo-390-calc-verify-research]]"
  - "[[2026-04-27-modelo-390-calc-verify-adr]]"
  - "[[2026-04-27-modelo-390-calc-verify-plan]]"
  - "[[2026-04-28-modelo-390-rule-delta-reference]]"
  - "[[2026-04-28-modelo-390-l1-anchor-waiver-reference]]"
---

# Modelo 390 calc-verify-roundtrip execution summary

## Outcome

Issue `#327` implements Modelo 390 calc-verify-roundtrip coverage for 2024, 2025, and 2026 on the scoped régimen-general annual IVA résumen surface (15 casillas: Apartado 1 datos estadísticos, Apartado 3 régimen general anual, Apartados 4-5 otros regímenes, Apartado 6 resultado anual incl. the full 191/192/193 result chain, Apartado 7 regularización por bienes de inversión).

## Code Changes

- Added `modelo_390_2024.py` as the year-master module owning `_CASILLAS` and `_CITATIONS`. Documented 15 casillas (6 computed + 9 user-supplied) and 6 formulas (`104` = 100 + 101, `105` = 96 - 104, `190` = 105 + 108 + 109, `191` = 190 - 662, `192` = clamp_pos(191), `193` = clamp_pos(0 - 191)).
- Refactored `modelo_390_2025.py` to re-import `_CASILLAS` and `_CITATIONS` from the 2024 master; year-stamped formula identifiers (`modelo_390.2025.*`); empty `ParameterTable` (Modelo 390 sums pre-computed cuotas, no DSL parameters).
- Added `modelo_390_2026.py` mirroring the 2024 / 2025 pattern; year-stamped formula identifiers (`modelo_390.2026.*`).
- Registered `MODELO_390_2024` and `MODELO_390_2026` in `_rulesets/__init__.py` (imports, `ALL_RULESETS`, and `__all__`).
- Added `Modelo390V2024Extractor` and `Modelo390V2026Extractor` as thin template-revision subclasses of `Modelo390V2025Extractor`; registered in `declaracion/_extractors/__init__.py`.
- Authored `test_modelo_390_2024.py`, refactored `test_modelo_390_2025.py` for the expanded shape, authored `test_modelo_390_2026.py` — each with ≥ 3 parametrised cases per computed casilla, externally anchored to BOE articles.
- Authored `test_modelo_390_cumulation.py` exercising Approach C: parametrised across the three years, deriving four quarterly Modelo 303 fixtures, summing them per the cumulation rule, generating M390 user-supplied annual aggregates, and asserting the M390 ruleset audits cleanly. Includes an edge case where bienes-inversión regularización flips `191` from positive to negative.
- Extended `test_mutator_kill_rate.py::EXPECTED_COUNTS` for the three M390 years (`sub_op=3` per year reflecting `105`, `191`, and the nested `0 - 191` in `193`).
- Extended `test_operand_swap_mutation.py` with six new sub_op chains (casillas `105` and `191` for each of 2024 / 2025 / 2026); fixture updated to carry asymmetric values across the new chains.
- Extended `test_zero_boundary_coverage.py` to include `modelo_390.2024` and `modelo_390.2026`.
- Updated `docs/coverage/modelos.md` Modelo 390 row to ✅ across applicable columns; provenance line cites `#327`.
- Authored `.vault/reference/2026-04-28-modelo-390-rule-delta-reference.md` (per-year sameness with BOE citations + cumulation rules) and `.vault/reference/2026-04-28-modelo-390-l1-anchor-waiver-reference.md` (real M390 declaraciones are taxpayer-specific; L3 synthetic + Kent CLI integration are the executable evidence).

## Per-Year Inventory

| Ruleset | Computed casillas | User-supplied casillas | Mutation fingerprint |
| :--- | ---: | ---: | :--- |
| `modelo_390.2024` | 6 | 9 | `sub_op=3, add_op=2, clamp_pos=2, percent_rate_*=0, mul_div_scalar=0` |
| `modelo_390.2025` | 6 | 9 | `sub_op=3, add_op=2, clamp_pos=2, percent_rate_*=0, mul_div_scalar=0` |
| `modelo_390.2026` | 6 | 9 | `sub_op=3, add_op=2, clamp_pos=2, percent_rate_*=0, mul_div_scalar=0` |

The aggregate mutation kill-rate floor (≥ 90 percent on the populated mutator surface) remains satisfied. Operand-swap mutation tests cover `105` and `191` directly; the nested sub_op inside `193`'s `clamp_pos` is enumerated for the catalogue and would be killed transitively by an upstream casilla divergence.

## Citation Coverage

`aeat audit rulesets citations` aggregate over the three M390 rulesets: 18 / 18 computed casillas with ≥ 1 `LegalCitation`, coverage 100.00 percent, no missing casillas. Each computed casilla's `legal_basis` tuple is bound to the LIVA / RIVA / Orden Ministerial articles that ground the computation:

- `104` ← LIVA arts. 92 (deducción) + 102 (prorrata).
- `105` ← LIVA arts. 90 / 91 (rate buckets feeding 96) + 92 / 102 (deducción framework grounding the 104 subtraction) + 164 (autoliquidación).
- `190` ← LIVA art. 164.
- `191` ← LIVA arts. 107 (bienes-inversión regularización) + 164.
- `192`, `193` ← LIVA art. 164 (resultado a ingresar / a devolver) + RIVA art. 71.7 + Orden EHA/3111/2009 (annual résumen filing obligation).

## BOE Sources Used

| Source | URL |
| :--- | :--- |
| Ley 37/1992 IVA art. 90 (21 percent general rate) | `https://www.boe.es/buscar/act.php?id=BOE-A-1992-28740` |
| Ley 37/1992 IVA art. 91 (10 percent reduced and 4 percent super-reduced) | `https://www.boe.es/buscar/act.php?id=BOE-A-1992-28740` |
| Ley 37/1992 IVA art. 92 (deducción del IVA soportado) | `https://www.boe.es/buscar/act.php?id=BOE-A-1992-28740` |
| Ley 37/1992 IVA art. 102 (regla de prorrata) | `https://www.boe.es/buscar/act.php?id=BOE-A-1992-28740` |
| Ley 37/1992 IVA art. 107 (regularización bienes de inversión) | `https://www.boe.es/buscar/act.php?id=BOE-A-1992-28740` |
| Ley 37/1992 IVA art. 164 (autoliquidación + resumen-anual obligation) | `https://www.boe.es/buscar/act.php?id=BOE-A-1992-28740` |
| Real Decreto 1624/1992 art. 71.7 (RIVA Modelo 390 obligation) | `https://www.boe.es/buscar/act.php?id=BOE-A-1992-28925` |
| Orden EHA/3111/2009 (Modelo 390 form approval) | `https://www.boe.es/buscar/act.php?id=BOE-A-2009-18472` |
| Directiva (UE) 2020/285 (2026 small-enterprise franquicia, out of base ruleset scope) | `DOUE-L-2020-80356` |

## Cumulation Design

Approach C (user-supplied annual aggregates), per the ADR. The cumulated casillas (`95`, `96`, `100`, `101`, `108`, `109`, `662`) remain user-supplied; the M390 ruleset only encodes the algebraic relationships among them. Cumulation correctness is asserted at the test level by `test_modelo_390_cumulation.py`, which:

- Parametrises across the three M303 ↔ M390 year pairs.
- Derives four synthetic quarterly Modelo 303 fixtures with chosen rate-bucket inputs.
- Sums the per-quarter values into the corresponding annual Modelo 390 casillas.
- Audits the annual M390 fixture against the M390 ruleset.
- Asserts `is_clean()` on uniform / mixed-quarter / regularización-flip cases and surfaces a discrepancy on a tampered annual aggregate.

Issue `#437` (needs-design ADR for aggregator cumulation) may later prescribe a unified DSL primitive harmonising M390, M180, M190, M193, M347, M349. Approach C keeps the current API thin enough that a later refactor is mechanical.

## Test Evidence

- 54 M390-specific unit tests pass (`test_modelo_390_2024.py`, `test_modelo_390_2025.py`, `test_modelo_390_2026.py`, `test_modelo_390_cumulation.py`).
- 104 mutation-harness + zero-boundary + operand-swap tests pass across the registered ruleset surface.
- 4 Kent CLI integration cases pass (`TestKentImportsModelo390Declaracion`: English / Spanish / partial / discrepancy).
- 9 audit-citations CLI tests pass.

## L1 Anchor Decision

Waived. Real Modelo 390 declarations are taxpayer-specific autoliquidaciones containing private NIF / period / liquidation data. Public BOE / AEAT instruction PDFs are legal-text references, not declaración exemplars. The same waiver pattern as Modelo 303 (`#326`) applies: explicit waiver lives at `[[2026-04-28-modelo-390-l1-anchor-waiver-reference]]`; L3 synthetic generation and extraction round-trip remain the executable evidence tier. Revisit triggers documented in the waiver.

## Out-of-Scope Deferrals

- Per-rate-bucket detail of Apartado 3 (4 / 10 / 21 percent decomposition). Deferred to sub-EPIC `#305-Modelo-390-full`.
- Deeper prorrata derivation (LIVA arts. 102-106). Deferred to `#345`.
- Multi-year bienes-de-inversión regularisation window modelling. Deferred to `#345`.
- 2026 small-enterprise franquicia regime full hardening. Deferred to `#345`.
- Foral regimes (País Vasco / Navarra). Deferred to EPIC `#424`.
- Canarias IGIC and Ceuta / Melilla IPSI regional deviations. Out of base ruleset scope.
