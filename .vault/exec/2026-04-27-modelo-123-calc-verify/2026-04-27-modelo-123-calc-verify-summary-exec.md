---
tags:
  - '#exec'
  - '#modelo-123-calc-verify'
date: '2026-04-27'
modified: '2026-04-27'
related:
  - '[[2026-04-27-modelo-123-calc-verify-plan]]'
  - '[[2026-04-27-modelo-123-rule-delta-reference]]'
---

# `modelo-123-calc-verify` summary

Implemented issue #320 for Modelo 123 2024/2025/2026 calc-verify-roundtrip.

- Created: `src/aeat/domain/formulas/_rulesets/modelo_123_2026.py`
- Created: `src/aeat/domain/formulas/_rulesets/test_modelo_123_2024.py`
- Created: `src/aeat/domain/formulas/_rulesets/test_modelo_123_2026.py`
- Created: `.vault/reference/2026-04-27-modelo-123-rule-delta-reference.md`
- Modified: `src/aeat/domain/formulas/_rulesets/modelo_123_2025.py`
- Modified: `src/aeat/domain/formulas/_rulesets/__init__.py`
- Modified: `src/aeat/adapters/inbound/declaracion/_extractors/modelo_123_v2025.py`
- Modified: `src/aeat/adapters/inbound/declaracion/_extractors/__init__.py`
- Modified: M123 registry, CLI, smoke, mutation, extractor, integration, and
  coverage tests.
- Modified: `docs/coverage/modelos.md`

## Casilla Inventory

All three years share the same supported liquidación block.

| Casilla | Classification | Rule |
| :--- | :--- | :--- |
| `01` | user-supplied | Dividend recipients |
| `02` | user-supplied | Other recipients |
| `03` | computed | `01 + 02` |
| `04` | user-supplied | Dividend withholding base |
| `05` | user-supplied | Other withholding base |
| `06` | computed | `04 + 05` |
| `07` | user-supplied | Dividend withholdings |
| `08` | user-supplied | Other withholdings |
| `09` | computed | `07 + 08` |
| `10` | user-supplied | Complementaria prior result |
| `11` | computed | `09 - 10` |

## BOE Sources

Used BOE consolidated 2026 sources:

- LIRPF Ley 35/2006 art. 25 and art. 101.4:
  `https://www.boe.es/buscar/act.php?id=BOE-A-2006-20764&p=20260228&tn=1`
- RIRPF RD 439/2007 art. 90:
  `https://www.boe.es/buscar/act.php?id=BOE-A-2007-6820&p=20260228&tn=1`

## Evidence

Citation audit before/after M123 status:

| Ruleset | Computed | With Citation | Coverage |
| :--- | ---: | ---: | ---: |
| `modelo_123.2024` | 4 | 4 | 100% |
| `modelo_123.2025` | 4 | 4 | 100% |
| `modelo_123.2026` | 4 | 4 | 100% |

Mutation fingerprint:

| Ruleset | `sub_op` | Percent-rate nodes | Bracket thresholds | Mul/div scalar |
| :--- | ---: | ---: | ---: | ---: |
| `modelo_123.2024` | 1 | 0 | 0 | 0 |
| `modelo_123.2025` | 1 | 0 | 0 | 0 |
| `modelo_123.2026` | 1 | 0 | 0 | 0 |

Focused verification passed:

- `uv run pytest src/aeat/domain/formulas/_rulesets/test_modelo_123_2025.py src/aeat/domain/formulas/_rulesets/test_modelo_123_2024.py src/aeat/domain/formulas/_rulesets/test_modelo_123_2026.py src/aeat/domain/formulas/test_registry.py src/aeat/domain/formulas/test_cli.py src/aeat/domain/formulas/test_smoke.py src/aeat/adapters/inbound/declaracion/test_quarterly_extractors.py src/aeat/domain/formulas/_rulesets/test_mutator_kill_rate.py src/aeat/domain/formulas/_rulesets/test_operand_swap_mutation.py tests/integration/test_kent_workflows.py::TestKentImportsModelo123Declaracion`
  passed with 156 tests.
- `uv run aeat audit rulesets citations` passed with aggregate 100% coverage.

L1 public-anchor coverage is waived. Modelo 123 filings contain internal
withholding data, so L3 synthetic round-trip coverage is used.
