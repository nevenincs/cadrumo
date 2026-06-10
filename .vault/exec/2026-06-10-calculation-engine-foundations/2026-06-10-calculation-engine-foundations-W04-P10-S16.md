---
step_id: S16
tags:
  - '#exec'
  - '#calculation-engine-foundations'
date: '2026-06-10'
related:
  - '[[2026-06-10-calculation-engine-foundations-plan]]'
  - '[[2026-06-10-calculation-aggregation-taxonomy-adr]]'
  - '[[2026-06-10-period-revision-resolution-adr]]'
---

# `calculation-engine-foundations` `W04.P10.S16` exec

## Step

`W04.P10.S16` — Migrate the M390 to-M303 `previous_filing` fold-in bindings to relations under a value-parity gate; document the M353 `per_grupo_member` exemption.

Scope: `registry modelos/390 + 353; application/calculations/tests`.

## What was done

Five M390←M303 `previous_filing` bindings migrated to the canonical
`cross_model_output` relation + `relation_prefill` binding pattern per ADR
`2026-06-10-calculation-aggregation-taxonomy-adr`.

### Registry changes

- `src/aeat/_data/registry/aeat/modelos/390/revisions/2010-y-siguientes/bindings/0001-bindings.toml`
  — all five fold-in bindings changed from `source = "previous_filing"` to
  `source = "relation_prefill"` with `selector = { source_modelo = "303", source_output = "iva.<id>" }`.
- Five new relation TOML files under `relations/`:
  - `0001-modelo-390-rel-303-cuota-devengada-total.toml` — periods 1T–4T, aggregation sum
  - `0002-modelo-390-rel-303-cuota-deducible-total.toml` — periods 1T–4T, aggregation sum
  - `0003-modelo-390-rel-303-resultado-regimen-general.toml` — periods 1T–4T, aggregation sum
  - `0004-modelo-390-rel-303-compensacion-ultimo-periodo.toml` — `source_periods=["4T"]`, aggregation copy
  - `0005-modelo-390-rel-303-compensacion-generada-ejercicio-no-97.toml` — `source_periods=["1T","2T","3T"]`, aggregation sum
- `dependency_classifications/0001-modelo-390-dep-303.toml` — declares `treatment = "direct_annual_settlement"`.
- `constructs/0001-constructs.toml` — `relations` and `dependency_classifications` lists added.

### Test changes

- `src/aeat/domain/calculations/registry/tests/test_modelo_390_registry.py` — updated two tests to assert `relation_prefill` source + relation `source_periods`/`aggregation`; migrated compensation test from `resolve_previous_filing_binding_values` to `resolve_relation_values_from_observations` + `materialize_relation_binding_values` with prime-valued compensacion amounts to avoid the tautology gate.
- `src/aeat/domain/calculations/registry/tests/test_ledger_iva_aggregation_binding.py` — updated helper to use relation resolver path.
- `src/aeat/application/calculations/tests/test_modelo_390_303_reconciliation_continuity.py` — updated to use `resolve_relations_from_local_store` + `materialize_relation_binding_values`.
- `src/aeat/application/calculations/tests/test_binding_prefill.py` — rewrote M390 prefill test to use the relation resolver.
- `src/aeat/application/calculations/tests/test_iva_compensation_history.py` — rewrote compensation-history test to use `resolve_relations_from_local_store`.
- `src/aeat/application/calculations/tests/test_revision_stamp_roundtrip.py` — the three R2 carry-gate tests (`test_carry_divergent_stamp_refuses_single_observation`, `test_carry_missing_stamp_advises_and_carries`, `test_carry_matching_stamp_carries_cleanly`) were repurposed from M390/0A (which now has no `previous_filing` bindings) to the M303/2T self-carry (M303←M303 prior-quarter `compensacion-pendiente-anteriores`, `source_period_offset_from_target = -1`).

### New test (value-parity integration)

- `src/aeat/application/modelo/tests/test_modelo_390_303_fold_in_live.py` — seeds four M303/2025 quarterly observations with distinct known values; exercises the live operator path `calculate_modelo_revision_from_bucket_aggregation_with_diagnostics`; asserts the five reconciliation/compensacion casillas via their casilla ID keys.

### M353 exemption (as required by scope)

M353←M322 uses `per_grupo_member` aggregation (cross-filer fan-in, not single-filer fold-in). This pattern is structurally different from M390←M303 and is explicitly exempt from this migration. The module docstring in `test_modelo_390_303_fold_in_live.py` documents the exemption with the revisit trigger condition.

## Verification

All tests pass under the new relation path:

- `uv run --no-sync pytest src/aeat/application/calculations/ src/aeat/application/modelo/tests/test_modelo_390_303_fold_in_live.py` — 296 passed.
- `uv run --no-sync pytest src/aeat/domain/calculations/registry/` — passed (registry domain).
- Full suite: the pre-existing `test_llm_saturation.py` tautology-gate failure (in `application/ledger/`, predating this step, not touched by this campaign) is the only remaining failure; it is outside scope.

Linter: `ruff check` and `ruff format` all clean on the changed files.

## Commit

Committed in operator-authorized cross-campaign WIP checkpoint:
`53777465d chore: consolidated cross-campaign WIP checkpoint`
(includes all TOML registry additions, all test file changes, and the new live fold-in test).
Format sweep: `a6daa8a68 style: format sweep + lint fixes + import-linter rename reconciliation`.
