---
tags:
  - '#research'
  - '#modelo-130-calc-verify'
date: '2026-04-27'
modified: '2026-04-27'
related:
  - "[[2026-04-25-mutation-harness-extension-research]]"
  - "[[2026-04-25-mandatory-citations-research]]"
---

# `modelo-130-calc-verify` research: closing the per-modelo Tier-L bar for 2024 / 2025 / 2026

Issue `#321` is the first per-modelo Tier-L issue delegated from EPIC
`#316`. The three foundational chores it depends on (`#338` mutation
harness extension, `#339` mandatory `LegalCitation` enforcement, `#340`
Tier-L CLI integration coverage) are already on `main`; this issue
extends the surface they enable by closing the Modelo 130 Tier-L bar
across 2024, 2025, and 2026.

This research document maps the BOE primary sources that ground every
Modelo 130 numeric value, enumerates the 19-casilla inventory with the
9-computed / 10-user split, surveys the rate / threshold / deduction
delta between 2024, 2025, and 2026, audits the existing extractor /
synthetic generator / integration test surface for gaps the
implementation must close, and records the L1 public-anchor decision.

## Modelo 130 — what the form is

Modelo 130 is the *pago fraccionado a cuenta del IRPF* for autónomos
en *estimación directa* (régimen general or *simplificada*). It is
filed quarterly: 1T (April), 2T (July), 3T (October), 4T (January
following). It is the mechanical companion to Modelo 100 (Renta) — the
quarterly Modelo 130 instalments are subtracted from the yearly Renta
liability when Kent files Modelo 100 in May–June following the fiscal
year.

Statutory grounding:

- **Ley 35/2006 IRPF (LIRPF) art. 99** — general obligation to make
  pagos a cuenta of IRPF (retenciones + ingresos a cuenta + pagos
  fraccionados); pagos fraccionados specifically apply to actividades
  económicas. (`BOE-A-2006-20764`.)
- **Real Decreto 439/2007 (RIRPF) art. 110** — the entire numerical
  surface of Modelo 130: rates, brackets, deductions, minoraciones.
  (`BOE-A-2007-6820`.)
- **Orden EHA/672/2007** — the formal model specification for Modelos
  130 + 131; defines the casilla layout the BOE template prints.
  (`BOE-A-2007-6032`.)

## Casilla inventory — 19 casillas, 9 computed, 10 user-supplied

Each casilla is keyed by the BOE form id (printed on the AEAT template).
"Computed" means the engine derives the value from a `FormulaDefinition`
in the ruleset; "user-supplied" means the caller (Kent or the upstream
T6 aggregator) supplies it.

| ID  | Role                                                                | Mode | Formula (where computed)                       | Statutory grounding |
| :-: | :------------------------------------------------------------------ | :--: | :--------------------------------------------- | :----------------- |
| 01  | Ingresos íntegros del periodo (Apartado I, acumulado)               | user | —                                              | RIRPF 110.1.a      |
| 02  | Gastos deducibles del periodo (Apartado I, acumulado)               | user | —                                              | RIRPF 110.1.a      |
| 03  | Rendimiento neto                                                    | calc | `01 - 02`                                      | RIRPF 110.1.a      |
| 04  | Importe del pago fraccionado bruto (20 %)                           | calc | `clamp_pos(20 % · 03)`                         | RIRPF 110.1.a      |
| 05  | Pagos fraccionados anteriores (Apartado I, cross-quarter pool)       | user | —                                              | RIRPF 110.3        |
| 06  | Retenciones e ingresos a cuenta del periodo (Apartado I)             | user | —                                              | RIRPF 110.3        |
| 07  | Resultado parcial del Apartado I                                    | calc | `04 - 05 - 06`                                 | RIRPF 110.1.a + 110.3 |
| 08  | Volumen de ingresos del trimestre (Apartado II, agraria, no acumulado) | user | —                                            | RIRPF 110.1.c      |
| 09  | Importe del pago fraccionado bruto agraria (2 %)                    | calc | `2 % · 08`                                     | RIRPF 110.1.c      |
| 10  | Retenciones del trimestre (Apartado II)                             | user | —                                              | RIRPF 110.3        |
| 11  | Resultado parcial del Apartado II                                   | calc | `09 - 10`                                      | RIRPF 110.1.c + 110.3 |
| 12  | Suma de resultados parciales (clamp ≥ 0)                            | calc | `max(0, 07 + 11)`                              | RIRPF 110          |
| 13  | Minoración por rendimientos netos ≤ 12 000 € (paso 100/75/50/25)    | user | (helper `compute_casilla_13_minoracion` exists) | RIRPF 110.3.c      |
| 14  | Neto tras minoración                                                | calc | `12 - 13`                                      | RIRPF 110.3.c      |
| 15  | Arrastre de negativos (cross-quarter pool)                          | user | —                                              | RIRPF 110.3        |
| 16  | Deducción por inversión en vivienda habitual (2 %, cap 660,14 €)    | user | (caller-gated under elegibilidad)              | RIRPF 110.3.d      |
| 17  | Diferencia                                                          | calc | `14 - 15 - 16`                                 | RIRPF 110.3.c + 110.3.d |
| 18  | Resultado a ingresar de autoliquidaciones anteriores (complementaria) | user | —                                            | RIRPF 110.4        |
| 19  | Resultado final                                                     | calc | `17 - 18`                                      | RIRPF 110.4        |

The "computed" set { 03, 04, 07, 09, 11, 12, 14, 17, 19 } is exactly 9
elements; the "user-supplied" set { 01, 02, 05, 06, 08, 10, 13, 15, 16,
18 } is exactly 10. Total 19 — matches the issue body's invariant.

### Casillas the engine deliberately leaves user-supplied

Three casillas the engine *could* derive in principle but does not in
this wave:

- **05** — pagos fraccionados anteriores: cross-quarter accumulator.
  The engine evaluates a single liquidación; the orchestration layer
  (Kent's quarterly cycle) maintains the rolling sum.
- **13** — minoración brackets art. 110.3.c: depends on the *prior-year*
  rendimiento neto, which is metadata the engine does not own. A
  helper `compute_casilla_13_minoracion(previous_year_rendimiento_neto)`
  ships in the 2024 ruleset for callers that want the brackets applied;
  the helper's lookup is itself a `BracketsFormula` shape and its
  worked-example coverage is part of the calc-verify bar.
- **15, 16** — arrastre + vivienda deduction: gated by elegibilidad
  flags the engine does not own (Ceuta/Melilla territoriality, prior
  carry-forward state, mutually-exclusive deduction selection).

These are intentional Tier-L scoping decisions documented in the 2024
ruleset's casilla notes; they are *not* extractor gaps.

## 2024 → 2025 → 2026 rule delta

I researched primary BOE sources for any rate / threshold / deduction
amendments between 2024 and 2026.

### Sources consulted

| Source                                                              | Reference                                                  |
| :------------------------------------------------------------------ | :--------------------------------------------------------- |
| RD 439/2007 RIRPF — consolidated text (last update 2026-02-28)      | <https://www.boe.es/buscar/act.php?id=BOE-A-2007-6820>     |
| RD 1003/2014 (modifies 110.3.c minoración brackets)                 | <https://www.boe.es/buscar/act.php?id=BOE-A-2014-12369>    |
| RD 960/2013 (modifies 110.3.d vivienda-habitual deduction)          | last consolidated form referenced from RD 439/2007 footer   |
| RD 1461/2018 (last cited 110-related modification)                  | last consolidated form referenced from RD 439/2007 footer   |
| RD 253/2025 — modifies RIRPF (article 69, *not* 110)                | <https://www.boe.es/buscar/doc.php?id=BOE-A-2025-...>      |
| AEAT Instrucciones Modelo 130 (template + filing instructions)      | <https://sede.agenciatributaria.gob.es/Sede/.../instrucciones.html> |
| Orden EHA/672/2007 (Modelo 130 / 131 layout)                        | <https://www.boe.es/buscar/act.php?id=BOE-A-2007-6032>     |

### Findings

**No 2025 amendment to RIRPF art. 110.** The RD 253/2025 amendment
touched RIRPF art. 69 (information obligations), *not* art. 110. The
20 % / 2 % rates, the 100/75/50/25 € minoración brackets at
9 000/10 000/11 000/12 000 €, and the 660,14 € vivienda-habitual cap
are all unchanged from the post-RD 1003/2014 + RD 960/2013 baseline.

**No 2026 amendment to RIRPF art. 110.** The consolidated text last
updated 2026-02-28 carries no modification notice in 2025 or 2026
that touches the 110-series numerical surface.

**Conclusion.** The 2024 → 2025 → 2026 rule delta on Modelo 130 is
**zero**: every numerical and structural element of the 2024 ruleset
remains in force for 2026. The 2026 ruleset is therefore a structural
clone of the 2024 / 2025 ruleset with new `effective_from` /
`effective_to` boundary dates (2026-01-01 to 2026-12-31).

This is consistent with the existing project pattern: the 2025 ruleset
is itself a structural clone of 2024 (its docstring documents the
"mid-year rule changes are absent for 2024→2025" finding from the
prior research wave). The 2026 file follows the same convention.

### Watch-list — out-of-scope for this issue but on the radar

The 2025 ruleset's docstring flags two prospective territorial
overlays that *would* shift the 2026 picture if they ship in this
issue's window:

- **La Palma 60 % reduction (art. 110.2)** — extends the existing 60 %
  reduction for actividades en zonas afectadas a residentes en La Palma
  for 4T 2025 onwards. The reduction sits behind a per-period
  elegibilidad flag the engine does not own (caller-gated), so it does
  not change the formula DAG of the base ruleset. The dedicated
  territorial overlay lands in a wave-2 issue on EPIC `#316`.
- **Generic art. 110.2 60 % reduction** — for activities in Ceuta /
  Melilla / Canarias. Same caller-gated treatment.

Neither overlay is part of this issue's Tier-L bar. The base ruleset
remains rate-stable across 2024 / 2025 / 2026; the overlays are layered
on top of the base and tracked separately.

## External-anchor strategy

The 2025 test file's `test_external_worked_example_rirpf_art_110`
worked example demonstrates the canonical pattern: the 20 % rate
quoted in the docstring is taken from `RIRPF art. 110.1.a`
(`BOE-A-2007-6820`), *not* the ruleset's `ParameterTable`. The fixture
expected value `7 100,00` is `35 500 · 0,20` — derived from the
**statute**, not from the ruleset's stored parameter. This means a
ruleset author that mis-stored the rate would fail this test.

The 2024 test file's `test_external_worked_example_rirpf_110`
demonstrates the same pattern with both rates (general 20 % and
agraria 2 %).

For the 2026 ruleset's worked-example test I follow the same shape but
shift the numerical scenario to a different parametric profile to
avoid mirror-fixture coupling: a Q3 2026 scenario with both an IRPF
general slice (Apartado I) and a small agraria slice (Apartado II)
plus a non-zero minoración from art. 110.3.c.

For the casilla-13 minoración helper, the BOE-anchored worked
examples come from `RIRPF art. 110.3.c` directly: at
`previous_year_rendimiento_neto = 8 999,99 €` the bracket is 100 €;
at 10 000,01 € it is 50 €; at 12 000,01 € it is 0 €. These boundary
values are statute-exact and serve as the threshold-edge test cases.

## Mutation harness — pre-existing M130 coverage

The `#338` harness already exercises Modelo 130:

- **`test_operand_swap_mutation`** — every `sub_op` in the M130 DAG.
  The shared `_modelo_130_rich_fixture` covers the six casillas with
  `sub_op` chains (03, 07, 11, 14, 17, 19) plus the two casillas
  whose formulas reach a `sub_op` via composition (12 via `add_op`
  inside `max_op`; 04 via `clamp_pos(percent(...))`).
- **`test_percent_rate_mutation`** — both percent rates (`04` IRPF
  general, `09` agraria) flagged for both 2024 and 2025 via
  `_f130_irpf_fixture` + `_f130_agraria_fixture`.
- **`test_mutator_kill_rate`** — expected counts table records
  M130 2024 + 2025 at `sub_op=8, percent_rate_param=2`.

When the 2026 ruleset is registered, the kill-rate harness's
`EXPECTED_COUNTS` table must add a `modelo_130.2026` row with the same
`sub_op=8, percent_rate_param=2` fingerprint — and the per-class
parametrisation tables in `test_operand_swap_mutation` and
`test_percent_rate_mutation` must add the 2026 cases. Because the 2026
ruleset is a structural clone, the existing M130 fixtures
(`_modelo_130_rich_fixture`, `_f130_irpf_fixture`,
`_f130_agraria_fixture`) apply unchanged.

The brackets-threshold mutator (`test_brackets_threshold_mutation`)
synthesises its own ruleset and does *not* exercise the casilla-13
helper directly — that is intentional per `#338`. The helper's
brackets coverage is a job for the calc-verify worked-example tests;
this issue adds explicit threshold-edge cases at 8 999,99 / 9 000,01 /
10 000,01 / 11 000,01 / 12 000,01 €.

## Synthetic generator + extractor — current state

`tests/fixtures/pdf_corpus/l3_synthetic/_generators/modelo_130_generator.py`
renders only **7** casillas (01 – 07). The corresponding
`src/aeat/adapters/inbound/declaracion/_extractors/modelo_130_v2025.py` parses the same
**7** casillas; `_REQUIRED_FOR_COMPLETE = frozenset({01..07})` so a PDF
with all seven hits returns `ExtractionStatus.COMPLETE`.

The DoD calls for "casilla-complete for the liquidación block (not just
MVP — enumerate full inventory)". The form's full liquidación block is
all 19 casillas. Two distinct expansion strategies:

- **Option A.** Extend both generator and extractor to all 19
  casillas. The synthetic generator picks up 12 new `CasillaBox`
  positions on the same A4 page; the extractor's
  `_LABEL_REGEX_MAP` picks up 12 new label regexes; the
  `_REQUIRED_FOR_COMPLETE` set keeps the 01-07 trim (so existing
  partial-extraction tests still treat the 12 new casillas as
  optional) **OR** is widened to the full 19 (in which case a clean
  PDF is required to surface every casilla, lining up with the
  Tier-L bar).
- **Option B.** Keep the extractor at 01-07 and document a scoping
  decision: the per-modelo Tier-L bar for *this* wave covers the 7
  printed-on-AEAT-PDF casillas (the others are user-supplied or
  cross-quarter and never appear on a single quarter's printed
  declaración). Issue says casilla-complete; a strict reading
  prefers Option A.

The audit trail favours **Option A with `_REQUIRED_FOR_COMPLETE` kept
at the existing 7 casillas** (the *extractor-MUST-find* set), while
adding label regexes for the remaining 12 so a PDF with non-zero
values on those casillas surfaces them. The reason `_REQUIRED_FOR_COMPLETE`
stays at 7: a real Modelo 130 declaración prints **all** 19 casillas
even when most carry zeros, but the cross-quarter and minoración
casillas (05, 13, 15, 16, 18) often print `0,00` and the extractor's
"casilla-not-found" warning would otherwise surface false-negatives.
The Tier-L bar is "every printed casilla is parseable", not "every
casilla is required for COMPLETE" — those are distinct invariants.

## Integration test — current state

`tests/integration/test_kent_workflows.py::TestKentImportsModelo130Declaracion`
has three cases:

- `test_happy_path_english` — clean PDF → `Verification status:
  VERIFIED`.
- `test_happy_path_spanish_default` — same PDF, `AEAT_OUTPUT_LANGUAGE=es`
  default, asserts the Spanish narrative `verificado` appears.
- `test_partial_extraction_needs_review` — 4-of-7 casillas → `PARTIAL`
  + `NEEDS_REVIEW`; asserts missing-casilla warnings for cas. 05 + 06.

The optional fourth case (`test_discrepancy_classified_correctly`) is
the issue's stretch goal. It requires (i) the generator to emit a PDF
where one printed casilla deliberately disagrees with the engine's
re-derivation; (ii) the verification pass to surface a
`ClassifiedDiscrepancy` of the right type (extraction / formula /
un-modelled / rounding). Modelo 130 is the **reference implementation**
of `verify_declaracion`, so the discrepancy classifier is mature on
this surface. The fourth case is in scope.

## L1 public-anchor decision

The DoD calls for either a real public BOE / AEAT-anchor PDF
hash-pinned at `tests/fixtures/pdf_corpus/l1_public_anchors/modelo_130/`
*or* an explicit waiver explaining why none is available.

Modelo 130 is the autónomo's quarterly pago fraccionado. AEAT does
**not** publish any specimen Modelo 130 declaración as a normative
exemplar — every real Modelo 130 filing is a private autoliquidación
of a specific NIF for a specific quarter. The Manual práctico de IRPF
prints worked examples *of art. 110* (numerical scenarios) but those
are not the printed PDF declaración itself.

I therefore document an explicit L1 waiver in the rule-delta manifest
under `.vault/reference/2026-04-27-modelo-130-rule-delta-reference.md` (the issue suggests
either that file or a separate waiver file; for review economy I
co-locate the waiver at the foot of the rule-delta manifest where the
2024 → 2025 → 2026 trail of references lives).

The L2 anchor (contributor-private Kent filings) is out of scope for
this issue — the L2 fixture tier carries its own consent + scrubbing
discipline tracked elsewhere.

## Open questions resolved

1. **Is there a 2026 amendment to RIRPF art. 110?** No. Confirmed
   via `boe.es` consolidated text (last update 2026-02-28) and the
   modification chain footer.
2. **Does the 2026 RD that changed RIRPF (RD 253/2025) touch
   art. 110?** No — it modifies art. 69 (information obligations),
   not art. 110.
3. **Is the casilla-13 helper still active in 2026?** Yes — RD
   1003/2014 (the last 110.3.c modification) introduced the current
   bracket structure and remains in force.
4. **Does the kill-rate harness require a 2026 row?** Yes — every
   ruleset registered in `ALL_RULESETS` must appear in the
   `EXPECTED_COUNTS` table (`test_per_ruleset_node_counts_match_expected`).
   The 2026 row carries the same fingerprint as 2024 / 2025
   (`sub_op=8, percent_rate_param=2`).
5. **Does the operand-swap harness require 2026 cases?** Yes — six
   casillas (03, 07, 11, 14, 17, 19) need explicit pytest.param
   entries pointed at `MODELO_130_2026`.
6. **Does the percent-rate harness require 2026 cases?** Yes — two
   casillas (04, 09) need explicit pairs pointed at `MODELO_130_2026`.
7. **What is the integration test's marker?** `pytest.mark.unit,
   pytest.mark.domain_financial_input, pytest.mark.fixture_tier_l3` —
   set at module level. Preserve as-is.
8. **What is the existing per-ruleset test marker convention?**
   `pytest.mark.unit, pytest.mark.domain_local_state` (per
   `test_modelo_130_2024.py` line 18 + `test_modelo_130_2025.py`
   line 19). The issue body calls for `domain_submission` but the
   established repo convention for ruleset tests is
   `domain_local_state`. The new `test_modelo_130_2026.py` aligns
   with the existing convention; the divergence is documented in the
   ADR.

## Implementation surface — files this issue touches

```
src/aeat/domain/formulas/_rulesets/
  modelo_130_2024.py           — back-fill audit (no functional changes expected)
  modelo_130_2025.py           — back-fill audit (no functional changes expected)
  modelo_130_2026.py           — NEW (clone of 2025 with new effective dates)
  test_modelo_130_2024.py      — extend with parametrised threshold-edge cases
  test_modelo_130_2025.py      — extend with parametrised threshold-edge cases
  test_modelo_130_2026.py      — NEW (mirrors 2025 test shape)
  __init__.py                  — register MODELO_130_2026 + ALL_RULESETS
  test_operand_swap_mutation.py — add 6 × 2026 cases
  test_percent_rate_mutation.py — add 2 × 2026 cases
  test_mutator_kill_rate.py    — add modelo_130.2026 row to EXPECTED_COUNTS

src/aeat/adapters/inbound/declaracion/_extractors/
  modelo_130_v2025.py          — extend label regex map to all 19 casillas;
                                 keep _REQUIRED_FOR_COMPLETE at 7

tests/fixtures/pdf_corpus/l3_synthetic/_generators/
  modelo_130_generator.py      — extend _MODELO_130_BOXES to 19 casillas

tests/integration/
  test_kent_workflows.py       — add test_discrepancy_classified_correctly

.vault/reference/
  2026-04-27-modelo-130-rule-delta-reference.md       — NEW (rule delta + L1 waiver)

.vault/{adr,plan,exec}/
  2026-04-27-modelo-130-calc-verify-{adr,plan}.md       — NEW
  2026-04-27-modelo-130-calc-verify/...                  — NEW

docs/coverage/
  modelos.md                   — flip M130 row
```

This file list is exhaustive — any additional surface (e.g.
`src/aeat/entrypoints/cli/audit/__init__.py`, `src/aeat/entrypoints/cli/__init__.py`) is out
of scope and explicitly forbidden by the handover STEP 5.
