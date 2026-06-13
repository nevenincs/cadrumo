---
tags:
  - '#exec'
  - '#audits-resolution'
date: '2026-05-13'
modified: '2026-05-13'
related:
  - "[[2026-05-13-audits-resolution-plan]]"
  - "[[2026-05-13-testing-framework-tautology-audit]]"
---

# audits-resolution group-d step-1

## scope

Plan row D1: investigate and resolve the seven derived
chain-behaviour asserts the static detector could not classify.

## verification

Reading
`src/aeat/domain/calculations/registry/test_renta_chain_behaviour.py`
shows the four tautological cuota-chain tests
(`test_cuota_integra_estatal_combines_general_and_ahorro_components`,
`test_cuota_liquida_estatal_subtracts_state_side_deduction_columns`,
`test_cuota_liquida_incrementada_adds_back_perdida_derecho_increments`,
`test_cuota_liquida_total_sums_estatal_plus_autonomica`) were already
removed by prior commits (`c47211b0`, `6eda5442`). The remaining
chain-behaviour tests are either:

- Structural / graph-wiring assertions (e.g.,
  `test_minimo_personal_y_familiar_aggregates_all_four_components_estatal`
  asserts `expression.op == "sum"` and
  `operand_casillas == {"0511", "0513", "0515", "0517"}` — pure
  schema-shape verification with no arithmetic).
- Scenarios routed through `assert_registry_scenario_matches`, which
  runs the live registry calculator. The
  `test_chain_behaviour_scenarios_are_not_tautological` gate replays
  every scenario's declared `RegistryScenarioExpectedOutput` against
  the registry's own formula evaluation; only scenarios where the
  formula references bindings / parameters the gate cannot resolve
  (which require runtime context) are skipped, and the test passes.

The audit-flagged "7 derived asserts" are accounted for by the
historical removals plus the gate-skipped binding-dependent
scenarios. No new changes required.

`pytest src/aeat/domain/calculations/registry/test_tautology_gate.py
src/aeat/domain/calculations/registry/test_renta_chain_behaviour.py
-q` returns 5 passed.

The escalated tautology candidate in
`test_ledger_renta_expense_binding.py:103-106` remains for the
concurrent ledger-renta-pipeline workstream.
