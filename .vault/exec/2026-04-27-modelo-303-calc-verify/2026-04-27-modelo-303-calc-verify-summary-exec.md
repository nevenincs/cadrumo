---
tags:
  - '#exec'
  - '#modelo-303-calc-verify'
date: '2026-04-27'
modified: '2026-04-27'
related:
  - "[[2026-04-27-modelo-303-calc-verify-research]]"
  - "[[2026-04-27-modelo-303-calc-verify-adr]]"
  - "[[2026-04-27-modelo-303-calc-verify-plan]]"
  - "[[2026-04-27-modelo-303-rule-delta-reference]]"
---

# Modelo 303 calc-verify-roundtrip execution summary

## Outcome

Issue `#326` implements Modelo 303 calc-verify-roundtrip coverage for 2024, 2025, and 2026 on the scoped régimen-general IVA ruleset.

## Code Changes

- Added `modelo_303.2026` with 2026 effective dates, year-scoped formula IDs, stable 21 / 10 / 4 percent rates, and reused 2024 legal citations.
- Registered `MODELO_303_2026` in the formulas ruleset registry and public ruleset exports.
- Added `Modelo303V2026Extractor` as a thin 2026 template-revision subclass of the existing 33-casilla extractor.
- Added 2026 parser and Kent workflow round-trip coverage.
- Extended percent-rate, operand-swap, scalar-leaf, and kill-rate mutation harnesses for `modelo_303.2026`.

## Per-Year Inventory

| Ruleset | Computed casillas | User-supplied casillas | Mutation fingerprint |
| :--- | ---: | ---: | :--- |
| `modelo_303.2024` | 12 | 21 | `sub_op=2`, `percent_rate_param=3`, `casilla_ref_percent=1`, `mul_div_scalar=1` |
| `modelo_303.2025` | 12 | 21 | `sub_op=2`, `percent_rate_param=3`, `casilla_ref_percent=1`, `mul_div_scalar=1` |
| `modelo_303.2026` | 12 | 21 | `sub_op=2`, `percent_rate_param=3`, `casilla_ref_percent=1`, `mul_div_scalar=1` |

The aggregate mutation floor remains satisfied. Focused mutation tests covering percent-rate, scalar-leaf, operand-swap, and kill-rate aggregation passed with 131 tests.

## BOE Sources Used

| Source | URL |
| :--- | :--- |
| LIVA art. 90, 21 percent general rate | `https://www.boe.es/buscar/act.php?id=BOE-A-1992-28740#a90` |
| LIVA art. 91, 10 percent and 4 percent rates | `https://www.boe.es/buscar/act.php?id=BOE-A-1992-28740#a91` |
| RIVA art. 71, liquidation period and autoliquidación framework | `https://www.boe.es/buscar/act.php?id=BOE-A-1992-28925#a71` |
| Orden EHA/3786/2008, Modelo 303 form | `https://www.boe.es/buscar/act.php?id=BOE-A-2008-20953` |
| Directiva (UE) 2020/285, small-enterprise franquicia watch-list | `https://www.boe.es/buscar/doc.php?id=DOUE-L-2020-80356` |
| AEAT 2026 control-plan note, future small-enterprise model surfaces | `https://www.boe.es/diario_boe/txt.php?id=BOE-A-2026-5843` |

## Citation Audit

Before implementation, M303 reported:

- `modelo_303.2024`: computed `12`, with citation `12`, coverage `100.00%`.
- `modelo_303.2025`: computed `12`, with citation `12`, coverage `100.00%`.
- no `modelo_303.2026` ruleset row existed.

After implementation, `uv run aeat audit rulesets citations` reports:

- `modelo_303.2024`: computed `12`, with citation `12`, coverage `100.00%`.
- `modelo_303.2025`: computed `12`, with citation `12`, coverage `100.00%`.
- `modelo_303.2026`: computed `12`, with citation `12`, coverage `100.00%`.
- aggregate: computed `110`, with citation `110`, coverage `100.00%`.

No `citation-pending` casillas were introduced.

## L1 Anchor Decision

The L1 public-anchor decision is waiver. Real Modelo 303 declarations are taxpayer-specific; public legal or instruction PDFs are not completed declaration fixtures. The executable extraction evidence is the L3 synthetic 33-casilla generator plus parser and CLI round-trip tests.

## Verification Record

Bootstrap note:

`uv sync --all-groups --upgrade` and `uv lock --upgrade` were executed because the issue handoff required them. The dependency refresh was not retained in this PR because Modelo 303 calc-verify coverage does not require dependency changes.

Focused test command:

`uv run pytest src/aeat/domain/formulas/_rulesets/test_modelo_303_2026.py src/aeat/domain/formulas/_rulesets/test_percent_rate_mutation.py src/aeat/domain/formulas/_rulesets/test_operand_swap_mutation.py src/aeat/domain/formulas/_rulesets/test_scalar_mutation.py src/aeat/domain/formulas/_rulesets/test_mutator_kill_rate.py src/aeat/adapters/inbound/declaracion/test_modelo_303_v2025.py tests/integration/test_kent_workflows.py::TestKentImportsModelo303Declaracion src/aeat/domain/formulas/test_registry.py src/aeat/domain/formulas/test_cli.py src/aeat/domain/formulas/test_smoke.py`

Result: `175 passed` in the code-review focused rerun.

Post-documentation focused test command:

`uv run pytest src/aeat/domain/formulas/_rulesets/test_modelo_303_2024.py src/aeat/domain/formulas/_rulesets/test_modelo_303_2025.py src/aeat/domain/formulas/_rulesets/test_modelo_303_2026.py src/aeat/adapters/inbound/declaracion/test_modelo_303_v2025.py tests/integration/test_kent_workflows.py::TestKentImportsModelo303Declaracion src/aeat/domain/formulas/_rulesets/test_percent_rate_mutation.py src/aeat/domain/formulas/_rulesets/test_scalar_mutation.py src/aeat/domain/formulas/_rulesets/test_operand_swap_mutation.py src/aeat/domain/formulas/_rulesets/test_mutator_kill_rate.py`

Result: `167 passed`.

M303 integration command:

`uv run pytest tests/integration/test_kent_workflows.py::TestKentImportsModelo303Declaracion`

Result: `5 passed`.

Citation audit:

`uv run aeat audit rulesets citations`

Result: M303 2024 / 2025 / 2026 all 100 percent; aggregate 100 percent.
