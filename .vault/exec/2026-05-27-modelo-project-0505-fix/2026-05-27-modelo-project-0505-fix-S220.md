---
step_id: "S220"
feature: "modelo-project-0505-fix"
date: 2026-05-27
modified: '2026-05-27'
tags:
  - "#exec"
  - "#modelo-project-0505-fix"
related: []
---

# `aeat app modelo project` 0505 computed-input crash fix — S220

## Root-cause analysis

`modelo_project` in `_modelo.py` injected the M130 accumulated rendimiento neto
directly as casilla `"0505"` in the `m100_inputs` dict.  Casilla `0505`
(Base liquidable general sometida a gravamen) carries `input_kind = "computed"` with
formula `renta-2024-base-liquidable-general-sometida-a-gravamen` (max(0, 0500 − 0527)).

The `calculate_registry_snapshot` runtime rejects computed casillas supplied via
`inputs`:

```
_formula_runtime.py:311-316
computed = sorted(
    casilla_id
    for casilla_id in inputs
    if casillas[casilla_id].input_kind == "computed" or casilla_id in formula_targets
)
if computed:
    raise RegistryValidationError(
        f"computed registry casillas cannot be supplied as inputs: {computed!r}"
    )
```

Post-S353 (which made 0505 computed to wire it correctly into the cuota chain),
every call to `aeat app modelo project` raised:

```
M100 projection calculation failed: computed registry casillas cannot be supplied
as inputs: ['0505']
```

## Fix

Inject `projected_rendimiento_neto` at casilla `"0171"` (Ingresos de explotación,
`input_kind = "manual"`) instead.  With all EDS gastos casillas at zero, the
formula chain propagates the value cleanly:

```
0171 → 0180 → 0224 → 0226 → 0231 → 0235 → 0432 → 0435 → 0500 → 0505
```

This is semantically correct for a projection: the M130 net income (after M130's
own gastos deduction) is the best available proxy for M100 EDS ingresos de
explotación in a projection context.

## Files changed

- `src/aeat/entrypoints/cli/_modelo.py` — line ~4698: `"0505"` → `"0171"` with
  updated comment documenting the formula chain and injection rationale.
- `src/aeat/entrypoints/cli/test_modelo_projection.py` — update module docstring,
  test docstring, and oracle inputs to use `"0171"` instead of `"0505"`.  The
  pre-existing `_create_work_unit` test infrastructure failure (same pattern in
  `test_modelo_calculation_through_real_cli.py`) is tracked separately under #199.

## Verification

- `test_formula_runtime.py` — 22/22 pass (verifies computed-input rejection still
  works for other cases).
- The specific pre-existing test failure (`test_s361_0587_cuota_liquida_total_is_computed`
  — missing guardería binding) is unrelated to this fix.
