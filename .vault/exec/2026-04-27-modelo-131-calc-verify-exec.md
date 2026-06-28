---
tags:
  - '#exec'
  - '#modelo-131-calc-verify'
date: '2026-04-27'
modified: '2026-04-27'
related:
  - "[[2026-04-27-modelo-131-calc-verify-plan]]"
---



# modelo-131-calc-verify execution summary

- Created: `src/aeat/domain/formulas/_rulesets/modelo_131_2026.py`
- Created: `src/aeat/domain/formulas/_rulesets/test_modelo_131_2024.py`
- Created: `src/aeat/domain/formulas/_rulesets/test_modelo_131_2026.py`
- Created: `.vault/reference/2026-131-rule-delta.md`
- Modified: ruleset registry, registry/list tests, mutation tests, zero-boundary coverage, Modelo 131 2025 test markers, deterministic auth test endpoint, lockfile/bootstrap metadata, and `docs/coverage/modelos.md`

## Description

Modelo 131 now has registered annual rulesets for 2024, 2025, and 2026. The 2026 ruleset uses a non-overlapping full-year effective window and year-specific formula IDs while preserving the casilla-level M131 liquidación chain.

Per-year computed casilla inventory:

| Year | Computed casillas | Mutable nodes |
| :--- | :--- | :--- |
| 2024 | 04, 06, 07, 10, 13, 15 | 5 sub_op, 2 percent-rate params |
| 2025 | 04, 06, 07, 10, 13, 15 | 5 sub_op, 2 percent-rate params |
| 2026 | 04, 06, 07, 10, 13, 15 | 5 sub_op, 2 percent-rate params |

BOE sources used: RD 439/2007 art. 110, Orden EHA/672/2007, Orden HFP/1359/2023, Orden HAC/1347/2024, and Orden HAC/1425/2025. No citation-pending casillas remain.

L1 anchor decision: waived in `.vault/reference/2026-131-rule-delta.md`; synthetic declaration import remains the test anchor.

## Tests

Focused verification passed:

- `uv run aeat audit rulesets citations`: M131 2024, 2025, and 2026 each report `computed=6`, `with_citation=6`, `coverage=100.00%`; aggregate reports 100%.
- `uv run pytest src/aeat/domain/formulas/_rulesets/test_modelo_131_2024.py src/aeat/domain/formulas/_rulesets/test_modelo_131_2025.py src/aeat/domain/formulas/_rulesets/test_modelo_131_2026.py src/aeat/domain/formulas/test_registry.py src/aeat/domain/formulas/test_cli.py src/aeat/domain/formulas/test_smoke.py src/aeat/domain/formulas/_rulesets/test_mutator_kill_rate.py src/aeat/domain/formulas/_rulesets/test_percent_rate_mutation.py src/aeat/domain/formulas/_rulesets/test_operand_swap_mutation.py src/aeat/domain/formulas/_rulesets/test_zero_boundary_coverage.py`: 176 passed.
- `uv run pytest src/aeat/domain/formulas/_rulesets/test_modelo_131_2024.py src/aeat/domain/formulas/_rulesets/test_modelo_131_2026.py src/aeat/domain/formulas/_rulesets/test_mutator_kill_rate.py src/aeat/domain/formulas/_rulesets/test_percent_rate_mutation.py src/aeat/domain/formulas/_rulesets/test_operand_swap_mutation.py tests/integration/test_kent_workflows.py::TestKentImportsModelo131Declaracion`: 129 passed after code-review fixes.
- `uv run pytest src/aeat/adapters/outbound/aeat/adapters/outbound/aeat/auth/test_authenticator.py::test_reauthenticate_does_not_deadlock`: passed after changing the test-only certificate verification URL to a local closed-port endpoint.
- `uv run pytest src/aeat/entrypoints/cli/test_json_schema_conformance.py::test_registered_schema_validates_real_cli_output src/aeat/entrypoints/cli/test_root_json_alias.py::test_root_json_alias_reaches_auth_status`: 16 passed after logging out the manual CLI auth session used for this work.
- `just lint`: passed.
- `just typecheck`: passed.
- `just test`: 3795 passed, 13 skipped, 26 deselected, 26 warnings.
- `just hooks`: passed.
