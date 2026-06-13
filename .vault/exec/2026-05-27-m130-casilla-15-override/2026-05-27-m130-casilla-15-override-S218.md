---
step_id: "S218"
feature: "m130-casilla-15-override"
date: 2026-05-27
modified: '2026-05-27'
tags:
  - "#exec"
  - "#m130-casilla-15-override"
related: []
---

# M130 casilla 15 override — S218

## Root-cause analysis

M130 casilla 15 (Resultados negativos de trimestres anteriores) is
`input_kind = "bound"` with binding `modelo-130-resultados-negativos-anteriores`
whose `source = "previous_filing"`.

The engine's `_initial_values` function (P07.S36 hardening) enforces two invariants
for `previous_filing`-bound casillas:

1. **Smuggle-rejection guard** — a bound casilla in `inputs` MUST have the matching
   `binding_values[binding_id]` entry; otherwise a `RegistryValidationError` is raised.
2. **Consistency check** — when both maps declare the same casilla, they must agree.

When an operator supplies `--casilla "15=2694"` without feeding prior-quarter filings
into the local observation store, `PreviousFilingSourceResolver` is not invoked in the
`calculate_modelo_revision_from_bucket_aggregation` path, so
`resolved_bindings["modelo-130-resultados-negativos-anteriores"]` is absent. The
casilla override ends up in `resolved_inputs["15"]` but has no matching binding entry,
triggering the smuggle-rejection guard with a cryptic error (or, before P07.S36, a
silent zero).

## Fix — Path A

Added `_lift_previous_filing_casilla_overrides_to_bindings` helper in
`src/aeat/application/modelo/_actions.py`.

The helper inspects every key in `casilla_inputs`, finds those whose casilla
definition carries `input_kind = "bound"` with a `previous_filing` binding, and
promotes the override value into `resolved_bindings` under the binding's id — but
only when the binding is NOT already present in `resolved_bindings`. This satisfies
both engine invariants by construction:

- The smuggle-rejection guard passes because `binding_id` is now in `binding_values`.
- The consistency check passes because `inputs[casilla_id] == binding_values[binding_id]`.

When `--binding modelo-130-resultados-negativos-anteriores=X` was explicitly supplied,
the binding is already in `resolved_bindings` and the helper does not overwrite it;
any divergence from a simultaneous `--casilla 15=Y` surfaces as the engine's
consistency error.

## Scope

- `src/aeat/application/modelo/_actions.py` — new helper + integration into
  `calculate_modelo_revision` after `resolved_bindings` is fully assembled.
- `src/aeat/application/modelo/test_previous_filing_casilla_override.py` — three
  oracle/anti-tautology tests for the Diego #218 scenario.

## M131 assessment

M131 casillas 11 (both 2019-2023 and 2024 revisions) share the same pattern:
`input_kind = "bound"`, `source = "previous_filing"` binding. The fix is generic
across all `previous_filing`-bound casillas and covers M131 without additional
changes. **Y — same fix applies to M131.**

## Tests

- `test_casilla_15_override_accepted_at_3t` — oracle: `--casilla "15=2694"` at 3T
  produces `casilla_values["15"] == 2694`.
- `test_casilla_15_override_flows_into_casilla_17` — anti-tautology: changing casilla
  15 by the override amount changes casilla 17 by the same amount.
- `test_casilla_15_binding_already_supplied_is_not_overwritten` — when an explicit
  `--binding` diverges from `--casilla 15`, the engine's consistency check still
  surfaces the contradiction.

All 33 targeted tests pass (8 M130 registry + 3 verificado_completo regression +
14 verification substance + 3 new oracle + 5 pre-existing).

## Quality gates

- ruff: no errors
- pyright: 0 errors on `_actions.py` (pre-existing fixture annotation pattern on test file)
- No mocks, no stubs, no tautological assertions
