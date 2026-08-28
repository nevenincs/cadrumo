---
tags:
  - '#audit'
  - '#tui-architecture'
date: '2026-08-28'
modified: '2026-08-28'
body_schema: 'body-v2'
body_hash: 'sha256:746df21131afaee711c913e2982c440e9c68f5f6b6d1007e155a561b201b33d1'
related: []
---

# `tui-architecture` audit: `An unresolved relation drops its casilla with no diagnostic; the binding path has three`

## Finding

When a registry **binding** cannot be satisfied, three separate mechanisms make
that visible. When a **relation** cannot be satisfied, none of them fire: the
dependent casilla is dropped from the engine result with no unresolved outcome,
no source diagnostic, and no unresolved-casilla id.

The value is never wrong — this is not a silent-zero defect, which was checked and
excluded first (see "What is not wrong" below). The gap is in the signal.

## Proof

Driven on Modelo 180 for filing year 2025 — the minimal fixture, 33 casillas and
two formulas, both of which read a relation leaf:

| case | result |
|---|---|
| `relation_values={base: 50000, retenciones: 9500}` | `decl.base-total=50000.00`, `decl.retenciones-total=9500.00` |
| `unresolved_relation_ids=(both)` | `values={}`, **31 of 33 observations**, `unresolved_outcomes=()` |
| neither supplied | raises `RegistryValidationError: relation '...' has no supplied value` |

The middle row is the finding. Both computed totals vanish from `observations`,
and `unresolved_outcomes` is empty.

## The asymmetry

**Bindings** are covered at three layers:

- `expected_but_missing_binding_ids` (`application/modelo/_calculation_source_staging.py:421`)
  finds present-source, no-value gaps.
- `add_expected_missing_binding_diagnostics` wraps it, and its docstring states the
  intent outright: *"Mark present-source, no-value binding gaps unresolved instead
  of silent."* It emits `CalculationSourceDiagnostic` entries and extends
  `unresolved_binding_ids`.
- `application/modelo/_required_binding_gate.py` consumes that same function.

**Relations** have no counterpart. There is no `expected_but_missing_relation_ids`,
no relation-side diagnostic builder, and no relation branch in
`_calculation_source_staging.py`. `unresolved_relation_ids` is accumulated by the
mesh (`application/aggregation/_source_mesh.py:1328`, again at `:1490`) and handed
to the engine, and there the trail ends.

The one place the engine's own unresolved state is harvested is
`_calculation_source_staging.py:352`:

```python
unresolved_casilla_ids=tuple(sorted(outcome.casilla_id for outcome in engine_result.unresolved_outcomes)),
```

That derives from `unresolved_outcomes`, which the M180 run shows is empty in the
unresolved-relation case. So this channel is empty too.

`collect_unhandled_source_diagnostics` — the `no-silent-blank` safety net named in
`aeat-calculation-aggregation` — does not close the gap either, because it
iterates `revision.bindings` and asks whether each declared `source` **kind** has
an enrolled resolver. That is a static modelling question about the registry. It
cannot see that *this taxpayer's* M115 quarters produced no value.

## What is not wrong, checked first

An unresolved relation does **not** resolve to zero. `formula_runtime.py:1328`
raises `_UnresolvedFormulaDependencyError` when the relation is marked unresolved
and `RegistryValidationError` when it is simply unsupplied. The casilla leaf at
`:1290` has the same shape, so a dropped casilla **cascades as unresolved** rather
than as zero.

This matters for the relief case that prompted the check. M100 casilla 0604
(`irpf_pago_fraccionado_actividades_economicas`) is
`sum(relation rel-130-pagos-fraccionados, relation rel-131-pagos-fraccionados)`,
feeding 0609 `irpf_total_pagos_cuenta`. If the M130/M131 folds go unresolved, 0604
drops and 0609 drops with it. The taxpayer's pagos fraccionados are **not**
silently credited as zero, which would have been the over-payment defect. That
direction is safe.

## Direction

The residual exposure is a missing *signal*, not a wrong figure, and it is
therefore bounded by what the downstream gates do with an absent casilla. A
computed casilla absent from the persisted revision should be refused by the
export completeness gate, which requires every formula-declaring casilla to carry
a real value. So the likely operator experience is a late, indirect refusal at
export naming a blank box, rather than an early advisory naming the actual cause —
that the source quarters did not resolve.

`aeat-calculation-grounding` is relevant and, on its face, in tension with the
observed behaviour: *"Emit every casilla in `engine_result.values`, not only
computed entries... Never drop a casilla on the way to the persisted revision."*
Whether the unresolved case is an intended exception to that rule is exactly what
this audit does not decide.

## What this audit does not establish

`unresolved_relation_ids` is live on `CalculationSourceResolution`, so a consumer
this audit has not traced — verification findings, the CLI envelope's notice
channel, the readiness projection — may already surface it to the operator. The
claim here is narrow and checkable: **no diagnostic is produced on the calculate
staging path, where the binding equivalent produces three.** Confirming or refuting
downstream coverage is the first step of any remediation, and would move this from
a gap to a division of labour.

## Remediation — owner's decision, not taken here

If downstream coverage is absent, the shape is already written: a relation-side
`expected_but_missing_relation_ids` mirroring the binding helper, feeding
`CalculationSourceDiagnostic` entries through the same advisory channel. The
docstring of the binding version states the principle it would be extending.

Per the standing rule that a gate is unproven until it bites, any implementation
needs the M180 fixture above driven with `unresolved_relation_ids` and asserted to
produce a diagnostic — the same three-case table, with the middle row no longer
silent.

No production code, registry data or test was changed by this audit.
