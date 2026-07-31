---
tags:
  - '#exec'
  - '#modelo-verify-nonzero-guards'
date: '2026-07-01'
modified: '2026-07-31'
related:
  - '[[2026-06-30-modelo-verify-nonzero-guards-plan]]'
  - '[[2026-06-30-modelo-verify-nonzero-guards-audit]]'
---

# M210 inmobiliaria silent-zero advisory end-to-end resolution

This record resolves the documented deferral `DFR-M210-INMOBILIARIA-E2E`: the
`modelo-210-2025-inmobiliaria-implica-base-imponible` ADVISORY predicate was
proven only against hand-constructed `casilla_values` / `text_values` dicts fed
directly to `evaluate_verification_predicates` in
`test_verification_m210_advisory.py`. This closes the gap with a real
end-to-end integration test that drives the advisory through the production
calculate-then-verify pipeline.

## Description

- Read the M210 2025 registry revision (`casillas/0001-casillas.toml`,
  `formulas/0001-m210-base-imponible-2025.toml`,
  `parameters/0003-m210-imputacion-inmobiliaria-2025.toml`,
  `verification_expectations/0001-verification_predicates.toml`) and the
  `_evaluate_m210_resolve_base_imponible` formula runtime to ground a real,
  non-fabricated silent-zero scenario.
- Confirmed `dias_imputacion = 0` (the scenario suggested at task inception)
  is not reachable: the runtime validator
  (`_m210_imputation_days`) refuses a non-positive `dias_imputacion` outright
  rather than silently producing a zero base. Re-grounded the scenario on a
  genuinely valid, positive input instead: `valor_catastral=100`,
  `coeficiente_imputacion_inmobiliaria=0.011` (the registry-authored "recent
  revision" LIRPF art. 85 rate), `dias_imputacion=1` — a real one-day imputed
  income (`EUR 0.00301...`) that rounds to `EUR 0.00` at the formula's declared
  `money-2` rounding.
- Probed the full calculate-then-verify pipeline with standalone scripts before
  writing the durable test, discovering and routing around two unrelated,
  pre-existing gaps rather than fabricating a shortcut:
  - the M210 country-of-fiscal-residence profile binding
    (`m210-2025-profile-country-of-fiscal-residence`) cannot be resolved
    through the bucket-profile auto-resolution path for the current 6-arg
    `m210_resolve_rate` / `m210_resolve_base_imponible` formulas —
    `enum_consumed_binding_ids`'s `_ENUM_DISPATCH_BINDING_ARG_INDEX` entry for
    `m210_resolve_rate` is stale (arg index 3, a parameter leaf, not the
    binding leaf now at index 5 after the pension-tariff argument was added),
    so `resolve_profile_sourced_bindings` would route the string country value
    onto the Decimal channel and raise. Routed around it by NOT declaring
    `country_of_fiscal_residence` as a bucket profile fact for the calculate
    step (the formula runtime tolerates an absent country binding via `.get()`
    defaults) and supplying the country directly on the `workflow_profile`
    object passed explicitly to `verify_modelo_revision`, which the
    representante-fiscal and inmobiliaria predicates actually consume;
  - `verify_modelo_revision`'s post-grant workflow gate
    (`_run_revision_workflow_gate`, gated by `if granted:`) runs the filing
    draft builder, which does not yet support `data_type="text"` casilla
    inputs (`_decimal_input` in `aeat/application/filing/__init__.py` raises
    `ModeloBuilderError` on the persisted `tipo_renta="inmobiliaria"` string).
    Routed around it by leaving the MANUAL, `required=true` (but
    inmobiliaria-branch-irrelevant) `rendimientos_integros` casilla unsupplied,
    which yields a real, coexisting `missing_required_casilla` BLOCKING
    finding and keeps `granted_verificado_completo=False`, so the draft
    builder never runs. Neither workaround touches production code; both are
    genuine, pre-existing gaps outside this deferral's scope.
- Wrote `test_modelo_210_inmobiliaria_e2e.py` under
  `src/aeat/application/modelo/tests/` (per `tests-live-under-domain-tests-folders`)
  driving `calculate_modelo_revision` directly (mirroring
  `test_declaration_period_binding.py`) with
  `text_casilla_inputs={"tipo_renta": "inmobiliaria"}`, then
  `verify_modelo_revision` over the persisted revision, both sharing one
  `isolated_runtime_profile` bucket session per test (mirroring
  `test_modelo_200_first_year_cuota_e2e.py`'s `secure_objects` fixture
  pattern).
- Two tests: the silent-zero scenario asserts (1) PERSISTENCE —
  `revision.input_values_by_casilla_id["tipo_renta"] == "inmobiliaria"`; (2)
  FIRES — the real verify gate's Layer-2 predicate evaluation (reading
  `input_values_by_casilla_id` back as `text_values`) yields exactly one
  `modelo-210-2025-inmobiliaria-implica-base-imponible` ADVISORY finding. The
  companion scenario (`valor_catastral=100000`, `dias_imputacion=365`) asserts
  (3) HOLDS — `base_imponible == Decimal("1100.00") > 0` and no such advisory
  fires, proving the inmobiliaria base-imponible formula branch computes
  through the real production pipeline.

## Outcome

Resolved. The advisory is now proven end to end through the real
`calculate_modelo_revision` → `verify_modelo_revision` pipeline rather than
only against hand-constructed dicts. No production code was modified; the two
unrelated gaps discovered during probing (the stale M210 enum-dispatch arg
index for `m210_resolve_rate`, and the filing-draft builder's missing
`data_type="text"` casilla support) are documented above for a future,
separately-scoped fix and are not claimed as closed here.

## Notes

No production code changes. No mocks, stubs, skips, or xfail; both tests
exercise the real registry authority, real formula runtime, real encrypted
SQLite persistence (`isolated_runtime_profile`), and real verification
predicate evaluation. Probe scripts used during discovery were scratch-only
and were not committed.

## Files

- `src/aeat/application/modelo/tests/test_modelo_210_inmobiliaria_e2e.py` (new)

## Verification

- `uv run --no-sync pytest src/aeat/application/modelo/tests/test_modelo_210_inmobiliaria_e2e.py -q`
  — 2 passed.
- `uv run --no-sync ruff check src/aeat/application/modelo/tests/test_modelo_210_inmobiliaria_e2e.py`
  — all checks passed.
- `uv run --no-sync ruff format --check src/aeat/application/modelo/tests/test_modelo_210_inmobiliaria_e2e.py`
  — already formatted.
- `uv run --no-sync ty check src/aeat/application/modelo/tests/test_modelo_210_inmobiliaria_e2e.py`
  — all checks passed.
