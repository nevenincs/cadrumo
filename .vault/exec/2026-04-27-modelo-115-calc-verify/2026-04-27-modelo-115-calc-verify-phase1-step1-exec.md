---
tags:
  - '#exec'
  - '#modelo-115-calc-verify'
date: '2026-04-27'
modified: '2026-04-27'
related:
  - "[[2026-04-27-modelo-115-calc-verify-plan]]"
  - "[[2026-04-27-modelo-115-calc-verify-adr]]"
  - "[[2026-04-27-modelo-115-rule-delta-reference]]"
---

# Step record — 2026 ruleset + harness rows

Plan reference:
`2026-04-27-modelo-115-calc-verify-plan` §1.1..§1.5.

## Files changed

- `src/aeat/domain/formulas/_rulesets/modelo_115_2026.py` — NEW.
  Re-import-clone of `modelo_115_2025` with the 2026 effective
  range. Module docstring quotes the verbatim BOE art. 100
  statute and references the rule-delta manifest. Numerical
  content of `ParameterTable` identical to 2024 / 2025.
- `src/aeat/domain/formulas/_rulesets/__init__.py` — register
  `MODELO_115_2026` in the import block, `ALL_RULESETS`, and
  `__all__`. Updated module docstring to add an issue-#319
  section noting M115's 2024 → 2025 → 2026 trail mirrors M130's.
- `src/aeat/domain/formulas/_rulesets/test_modelo_115_2026.py` — NEW.
  Mirrors `test_modelo_130_2026.py` on the smaller M115 surface.
  Seven class methods + six parametrised cases (13 tests total):
  - `test_consistent_quarter_is_clean` — base happy-path audit.
  - `test_2026_no_drift_from_2025` — no-drift invariant per ADR
    §D6.
  - `test_ruleset_id_and_effective_range` — registration smoke.
  - `test_external_worked_example_rirpf_art_100_2026` —
    externally-anchored worked example per ADR §D5 (4T 2026,
    9 500 € base, no overlay).
  - `test_zero_boundary_is_clean` — zero-boundary case.
  - `test_retention_rate_mismatch_raises` — negative-path.
  - `test_ceuta_melilla_fixture_validates_against_base_rate` —
    confirms the 19 % base rate is preserved when no overlay
    is applied (RIRPF art. 100 ¶ 2 territoriality flag is
    caller-gated per ADR §D12).
  - parametrised `test_casilla_derivations_at_various_bases_2026`
    — six (base, in-kind, complementaria) tuples covering zero-
    boundary, typical, and large-base scenarios.
- `src/aeat/domain/formulas/_rulesets/test_mutator_kill_rate.py` —
  added `modelo_115.2026` row to `EXPECTED_COUNTS` mirroring
  the 2024 / 2025 fingerprint (`sub_op=1, percent_rate_param=1`).
- `src/aeat/domain/formulas/_rulesets/test_percent_rate_mutation.py` —
  added `MODELO_115_2026` import + `(MODELO_115_2026, "03",
  _f115_fixture())` row in `_ruleset_cases`.
- `src/aeat/domain/formulas/_rulesets/test_operand_swap_mutation.py` —
  added `MODELO_115_2026` import + a 2026 `pytest.param` reusing
  `_modelo_115_fixture` for the casilla-06 sub_op chain.

## Verification

- `uv run pytest src/aeat/domain/formulas/_rulesets/test_modelo_115_2026.py`
  → 13 passed.
- `uv run pytest src/aeat/domain/formulas/_rulesets/test_mutator_kill_rate.py
  src/aeat/domain/formulas/_rulesets/test_percent_rate_mutation.py
  src/aeat/domain/formulas/_rulesets/test_operand_swap_mutation.py`
  → 113 passed.
- `uv run aeat audit rulesets citations | grep 115`
  → `OK modelo_115.2026 ... coverage=100.00%`.
- The aggregate-row remains at 100,00 % over 100 computed
  casillas across 20 rulesets.

## Notes

- The 2026 ruleset re-imports `_FORMULAS_2025` rather than
  re-declaring them under a `modelo_115.2026.<reason>` namespace
  (see ADR §D1 for the reasoning — the M115 module convention
  diverges from M130's, and preserving the existing 2024
  re-import pattern matters more than mirroring M130).
