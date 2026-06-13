---
tags:
  - '#audit'
  - '#modelo-130-relation-regression'
date: '2026-05-26'
modified: '2026-05-26'
related:
  - "[[2026-05-19-modelo-130-relation-regression-plan]]"
  - "[[2026-05-19-modelo-130-relation-regression-adr]]"
  - "[[2026-05-19-modelo-130-relation-regression-research]]"
---

# `modelo-130-relation-regression` audit: `modelo-130-carry-forward-binding-silently-dead`

## Scope

Re-measurement of the Modelo 130 same-year carry-forward regression that
the 2026-05-19 plan identified. Executed as step `W01.P01.S02` of that
plan: run the cross-dependency contract and calculation suites and
inspect the binding declaration end-to-end against the formula runtime.

## Findings

### S1 cross-dependency suite is green and uninformative

`test_cross_dependency_contract.py` and
`test_cross_dependency_calculations.py` pass 31/31, including the three
M130-tagged tests. The cross-dependency suite asserts contract shape
(every `previous_filing` binding with a period anchor declares a
discoverable source), not end-to-end carry-forward arithmetic. A
binding that lacks a period anchor is classified as relation-driven
and SKIPPED by both `previous_filing_observation_requirements` and
`resolve_previous_filing_binding_values` (`_bindings.py` lines 214-218
and 252-257). The contract suite therefore cannot fail on a binding
that silently never fires.

### S1 the carry-forward binding is dead at runtime

The Modelo 130 carry-forward binding declares:

```
[[revisions."2019-y-siguientes".bindings]]
id = "modelo-130-resultados-negativos-anteriores"
source = "previous_filing"
selector = { source_modelo = "130", source_output = "saldo-negativo-fin-periodo" }
aggregation = { op = "copy" }
```

The selector has no `period`, no `source_periods`, no
`source_period_offset_from_target`, and no `relation`. By the rule in
`_is_direct_previous_filing_binding`: `source_output` present but no
period anchor → returns False → binding is classified as
relation-driven. Modelo 130 declares zero `RelationDefinition`
records, so no relation resolves it either. The binding sits in the
revision but never produces a value.

Casilla 15 carries `input_kind = "bound"`. The formula runtime's
`_initial_values` helper falls back to `inputs.get(casilla.id, _ZERO)`
for every non-computed casilla. With no binding value supplied and no
input supplied, casilla 15 silently becomes Decimal("0"). The
prior-quarter negative-result carry-forward (RD 439/2007 art. 110.5)
never reaches the diferencia (casilla 17) or the resultado final
(casilla 19).

### S2 existing tests mask the dead binding

`test_registry_formula_runtime_calculates_committed_modelo_in_dependency_order`
passes `"15": Decimal("0")` as an explicit input. That call shape
silently agrees with the dead-binding state of the registry: it
supplies the same zero the runtime would have defaulted to. A binding
fix that started routing the prior-quarter saldo-negativo into
casilla 15 would not be detected by this test because the test
declares C15=0 in its input mapping.

### S2 the comment in the registry promises behaviour the binding does not implement

`130.toml` lines 318-325 document the intent:

> Prior-quarter negative-result carry-forward (RD 439/2007 art. 110.5).
> When a quarter's "Diferencia" (casilla 17) is negative, the absolute
> value is carried forward as a deductible casilla 15 in the following
> quarter within the same ejercicio. The saldo-negativo-fin-periodo
> casilla exposes that carry-forward seed; casilla 15 picks it up via
> a previous_filing binding stamped by the resolver from the prior
> quarter.

The selector below the comment does not implement what the comment
declares. The seed casilla (`saldo-negativo-fin-periodo`) IS computed
correctly by `modelo-130-saldo-negativo-fin-periodo`: `max(0, -C17)`.
The gap is the binding that should pull last quarter's seed into this
quarter's C15.

## Recommendations

### Closure of `W01.P02.S02` requires three coupled changes, not one

The plan's `W01.P02.S02` step ("revise Modelo 130 binding, relation,
dependency classification, and construct references for same-year
unused negative results") is correctly scoped but the work is not a
one-line selector edit:

1. **Binding selector**: declare a period anchor that AEAT-correctly
   models "prior quarter within the same ejercicio". The naive choice
   `source_period_offset_from_target = -1` is wrong for the 1T case
   because it would pull 4T from the previous year (different
   ejercicio). The correct semantics: 2T pulls from 1T same year, 3T
   from 2T same year, 4T from 3T same year, 1T pulls nothing.

2. **Selector capability gap**: the `_PreviousModeloSelector` model
   does not currently express "same-year prior period only, with
   suppression for the first period". The two existing capabilities
   (`period`/`source_periods` and `source_period_offset_from_target`)
   neither cap year-delta nor support empty-anchor at boundaries. A
   third selector mode or a `same_ejercicio_only = true` filter is
   required.

3. **End-to-end test coverage**: write a real-behaviour test that
   builds a 2T snapshot, supplies a 1T `RegistryModeloObservation`
   with casilla 17 negative (so saldo-negativo-fin-periodo is
   positive), routes the value through
   `resolve_previous_filing_binding_values` into the 2T
   `calculate_registry_snapshot` call's `binding_values`, and asserts
   the 2T casilla 15 picks up that seed. Also assert C15 is capped at
   C14 when C14 is positive (per AEAT instructions), and assert C15
   is zero for the 1T case (no prior quarter in same year). This test
   is the regression gate the suite is missing.

### Recommended sequencing

Treat the selector capability gap (item 2) as an ADR-worthy decision.
Two valid architectural answers exist: extend the selector model with
a same-ejercicio filter (small, local), or declare per-target-period
relations (consistent with the relation-driven path the binding
already nominally uses). Decide via a fresh ADR rather than picking
one in a tactical commit.

### Plan disposition

Do NOT close `W01.P02.S02` or the parent plan in this session. The
S02 measurement step authored by this audit can be checked
(`vault plan step check ... W01.P01.S02`) because the measurement is
complete. The remediation work (`W01.P02.S02` onward) needs the ADR
above to land first.

## Verification (S02 evidence)

- `pytest src/aeat/domain/calculations/registry/test_cross_dependency_contract.py src/aeat/domain/calculations/registry/test_cross_dependency_calculations.py` — 31 passed, 65.86s.
- `pytest ... -k "130 or modelo_130 or m130"` — 3 passed, 28 deselected, 44.32s.
- `python -c "from aeat.domain.calculations.registry._schema import _brackets_overlap_in_same_window"` — resolves cleanly. `W01.P01.S01` is already closed by intervening commits.
- Confirmed `[[revisions."2019-y-siguientes".relations]]` does not exist in `src/aeat/_data/registry/aeat/modelos/130.toml`.
- Confirmed only `casilla.id == "15"` carries `input_kind = "bound"` in M130.
