---
tags:
  - '#exec'
  - '#modelo-130-calc-verify'
date: '2026-04-27'
modified: '2026-04-27'
related:
  - "[[2026-04-27-modelo-130-calc-verify-plan]]"
  - "[[2026-04-27-modelo-130-calc-verify-adr]]"
  - "[[2026-04-27-modelo-130-calc-verify-research]]"
  - "[[2026-04-27-modelo-130-rule-delta-reference]]"
---

# `modelo-130-calc-verify` phase-1 step-2: 2026 ruleset + harness rows

Phase-1 step-2 of issue `#321` authored the 2026 ruleset and wired
it into the existing mutation-harness coverage tables. The ruleset
is a structural and numerical clone of the 2024 / 2025 rulesets per
the rule-delta manifest's no-amendment finding.

## Files created

- `src/aeat/domain/formulas/_rulesets/modelo_130_2026.py` — new ruleset.
  Re-imports `_CASILLAS_2024` + `_CITATIONS_2024` from
  `modelo_130_2024`. Declares own `_FORMULAS` with the
  `modelo_130.2026.<reason>` formula-id namespace and own
  `_PARAMETERS` with `effective_from=2026-01-01` /
  `effective_to=2026-12-31` and identical numerical values
  (`irpf.trimestral_rate=0.20`, `agraria.trimestral_rate=0.02`).
- `src/aeat/domain/formulas/_rulesets/test_modelo_130_2026.py` — 8
  class-level cases plus 11 parametrised threshold-edge minoración
  cases. Includes:
  - `test_consistent_quarter_is_clean` — Q2 2026 mixed-régimen
    worked example (distinct from 2024 / 2025 fixtures to avoid
    coupling).
  - `test_2026_no_drift_from_2025` — derived ledger entries equal
    the 2025 ruleset's on identical inputs (no-amendment invariant).
  - `test_external_worked_example_rirpf_art_110_2026` — externally-
    anchored 4T 2026 scenario with 20 % rate from RIRPF art. 110.1.a
    statute.
  - `test_agraria_income_computes_2_percent` — pure-agraria fixture
    exercising RIRPF art. 110.1.c.
  - `test_zero_boundary_is_clean` — all-zero edge.
  - `test_suma_parciales_clamps_negative_to_zero` — `max_op` clamp
    threshold-edge.
  - `test_pago_fraccionado_rate_mismatch_raises` — negative-path
    audit-discrepancy regression.
  - `test_ruleset_id_and_effective_range` — ruleset-id + dates.

## Files modified

- `src/aeat/domain/formulas/_rulesets/__init__.py` — registered
  `MODELO_130_2026`. Added to `ALL_RULESETS` and `__all__` in
  numerically-ascending order between 2025 and 131. Updated module
  docstring to mention issue `#321` + the rule-delta manifest.
- `src/aeat/domain/formulas/_rulesets/test_mutator_kill_rate.py` — added
  `modelo_130.2026` row to `EXPECTED_COUNTS`. Fingerprint matches
  2024 / 2025 (`sub_op=8, percent_rate_param=2`).
- `src/aeat/domain/formulas/_rulesets/test_operand_swap_mutation.py` —
  added `MODELO_130_2026` import and 6 `pytest.param` entries (one
  per `sub_op`-bearing casilla: 03, 07, 11, 14, 17, 19) reusing the
  existing `_modelo_130_rich_fixture`.
- `src/aeat/domain/formulas/_rulesets/test_percent_rate_mutation.py` —
  added `MODELO_130_2026` import and 2 case-table entries (casillas
  04 + 09) reusing the existing `_f130_irpf_fixture` /
  `_f130_agraria_fixture`.

## Tests added

31 new tests for 2026:

- 18 in `test_modelo_130_2026.py` (7 class methods + 11 brackets).
- 1 kill-rate fingerprint regression
  (`test_per_ruleset_node_counts_match_expected[modelo_130.2026]`).
- 6 operand-swap parametrisations.
- 4 percent-rate parametrisations (2 casillas × 2 directions).
- + 2 implicit checks via `test_zero_boundary_coverage` and the
  `test_all_rulesets_have_citations` regression guard which both
  parametrise over `ALL_RULESETS`.

All 31 green; aggregate kill-rate floor ≥ 90 % preserved.

## Citation audit (post-2026)

```
modelo_130.2024: total=9 with_citation=9 coverage=100.00% missing=()
modelo_130.2025: total=9 with_citation=9 coverage=100.00% missing=()
modelo_130.2026: total=9 with_citation=9 coverage=100.00% missing=()
aggregate (19 rulesets): total=98 with_citation=98 coverage=100.00%
```
