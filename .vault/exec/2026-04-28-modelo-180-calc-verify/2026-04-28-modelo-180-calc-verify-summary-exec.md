---
tags:
  - '#exec'
  - '#modelo-180-calc-verify'
date: '2026-04-28'
modified: '2026-04-28'
related:
  - "[[2026-04-28-modelo-180-calc-verify-plan]]"
  - "[[2026-04-28-modelo-180-calc-verify-adr]]"
  - "[[2026-04-28-modelo-180-calc-verify-reference]]"
---

# `modelo-180-calc-verify` summary

- Modified: `src/aeat/domain/formulas/_rulesets/__init__.py`
- Modified: `src/aeat/domain/formulas/_rulesets/test_modelo_180_2025.py`
- Modified: `src/aeat/domain/formulas/_rulesets/test_percent_rate_mutation.py`
- Modified: `src/aeat/domain/formulas/_rulesets/test_mutator_kill_rate.py`
- Modified: `src/aeat/adapters/inbound/declaracion/_extractors/__init__.py`
- Modified: `src/aeat/adapters/inbound/declaracion/_extractors/modelo_180_v2025.py`
- Modified: `tests/integration/test_kent_workflows.py`
- Modified: `docs/coverage/modelos.md`
- Modified: `uv.lock`
- Created: `src/aeat/domain/formulas/_rulesets/modelo_180_2026.py`
- Created: `src/aeat/domain/formulas/_rulesets/_modelo_180_cumulation.py`
- Created: `src/aeat/domain/formulas/_rulesets/test_modelo_180_2024.py`
- Created: `src/aeat/domain/formulas/_rulesets/test_modelo_180_2026.py`
- Created: `.vault/reference/2026-04-28-modelo-180-calc-verify-reference.md`

## Description

Modelo 180 now has registered 2024, 2025, and 2026 rulesets with non-overlapping full-year effective windows. The new 2026 ruleset is a primary-source-backed structural clone of 2025: the four summary casillas remain unchanged, and casilla 03 is computed as 19 percent of casilla 02 under RIRPF art. 100.1.

Extractor registry coverage now includes 2024, 2025, and 2026 summary-block extractor classes. The Kent CLI integration class now verifies per-year synthetic annual PDFs for 2024, 2025, and 2026 while preserving English, Spanish, partial, and discrepancy-classifier cases.

Cumulation design choice: Approach A, scoped to four Modelo 115-style quarterly rental-withholding sources. The implementation deliberately does not aggregate M111 or M123 because primary sources define Modelo 180 as the annual rental-withholding summary; M111 and M123 feed other informative annual modelos. The helper requires exactly four quarter records and then verifies the annual summary through the real formula engine.

L1 anchor decision: waiver. No public taxpayer-free Modelo 180 declaration PDF was found; BOE/AEAT public sources anchor the form and L3 synthetic PDFs anchor the parser/CLI path.

## Casilla Inventory

| Year | Ruleset | Casillas | Computed | Mutation fingerprint |
| :--- | :--- | :--- | :--- | :--- |
| 2024 | `modelo_180.2024` | 01, 02, 03, 04 | 03 | percent-rate param: 1 |
| 2025 | `modelo_180.2025` | 01, 02, 03, 04 | 03 | percent-rate param: 1 |
| 2026 | `modelo_180.2026` | 01, 02, 03, 04 | 03 | percent-rate param: 1 |

## Sources

- BOE-A-2000-21430, Orden de 20 de noviembre de 2000.
- BOE-A-2021-20004, Orden HFP/1351/2021.
- BOE-A-2007-6820, RD 439/2007 RIRPF art. 100.
- BOE-A-2006-20764, Ley 35/2006 LIRPF arts. 99-101.
- AEAT Modelo 180 help and AEAT activities-folleto for the M115/M180 operational relationship.

## Tests

- `uv run pytest src/aeat/domain/formulas/_rulesets/test_modelo_180_2024.py src/aeat/domain/formulas/_rulesets/test_modelo_180_2025.py src/aeat/domain/formulas/_rulesets/test_modelo_180_2026.py -q` passed: 25 tests.
- `uv run pytest tests/integration/test_kent_workflows.py::TestKentImportsModelo180Declaracion -q` passed: 7 tests.
- `uv run pytest src/aeat/domain/formulas/_rulesets/test_percent_rate_mutation.py src/aeat/domain/formulas/_rulesets/test_mutator_kill_rate.py -q` passed: 99 tests.
- `uv run pytest src/aeat/domain/formulas/test_cli.py::test_list_subcommand src/aeat/domain/formulas/test_registry.py::test_registry_ships_modelo_130_and_303_rulesets src/aeat/domain/formulas/test_smoke.py::test_registry_has_shipped_rulesets -q` passed: 3 tests.
- `uv run aeat audit rulesets citations` passed: M180 2024/2025/2026 each 1 of 1 computed casillas cited; aggregate 127 of 127 cited.
- `just lint` passed.
- `just typecheck` passed.
- `just test` passed: 3875 passed, 13 skipped, 26 deselected.
- `just hooks` passed.
- `uv run vaultspec-core vault check all` reports clean frontmatter, links, dangling links, schema, references, and structure after vault filename normalization.

## Review Pool

- Gemini review (`gemini-2.5-pro`) found no actionable findings.
- Codex local review found P2 formula-id provenance and recurring-recipient count issues; both were fixed and regression-tested.
