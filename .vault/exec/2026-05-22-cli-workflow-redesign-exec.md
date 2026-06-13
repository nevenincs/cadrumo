---
tags:
  - '#exec'
  - '#cli-workflow-redesign'
date: '2026-05-22'
modified: '2026-05-22'
step_id: 'S13'
related:
  - "[[2026-05-21-taxpayer-type-applicability-plan]]"
  - "[[2026-05-21-corporate-entity-calculation-adr]]"
---


# `cli-workflow-redesign` `W03.P11.S13`

Register the entity-type bracket / rate schedules for the Impuesto sobre
Sociedades and wire the cuota-íntegra rate dispatch. Corrects the
`tipo-gravamen-pyme` registry defect the corporate-entity ADR surfaced,
verifies the sibling LIS Art. 29 rates, confirms the IRPF tarifa already
exists, and connects the `lookup_parameter_by_entity_type` dispatch to
the Modelo 200 cuota chain.

- Modified: `src/aeat/_data/registry/aeat/modelos/200/revisions/2024-y-siguientes/records/parameters.toml`
- Modified: `src/aeat/_data/registry/aeat/modelos/200/revisions/2024-y-siguientes/records/formulas.toml`
- Modified: `src/aeat/_data/registry/aeat/modelos/200/revisions/2024-y-siguientes/records/bindings.toml`
- Modified: `src/aeat/_data/registry/aeat/modelos/200/revisions/2024-y-siguientes/records/constructs.part-002.toml`
- Modified: `src/aeat/_data/registry/aeat/modelos/200/revisions/2024-y-siguientes/casillas/liquidacion-00558-tipo-de-gravamen.toml`
- Modified: `src/aeat/application/overview/_applicability.py`
- Modified: `src/aeat/domain/calculations/registry/test_modelo_200_registry.py`
- Modified: `src/aeat/domain/calculations/registry/test_cross_dependency_calculations.py`
- Created: `src/aeat/domain/calculations/registry/test_modelo_200_tipo_gravamen_dispatch.py`

## Description

### The micro-empresa rate defect

The Modelo 200 `is.modelo-200.tipo-gravamen-pyme` parameter encoded the
micro-empresa rate as a single flat scalar `23` percent. LIS Art. 29.1
fixes the micro-empresa rate as a two-bracket scale, not a flat value:
17 % on the 0-50.000 EUR base tranche and 20 % on the rest for periods
initiated in 2025, and 19 % / 21 % for periods initiated in 2026 (AEAT
Manual práctico de Sociedades "Tipos de gravamen vigentes"; AEAT folleto
actividades económicas 4.3, the authority the corporate-entity ADR §5
records). The flat `23` matched no LIS Art. 29 micro-empresa tranche.

The parameter is now a `bracket_table` with four bracket rows — a
2025 window (17 % / 20 %) and a 2026 window (19 % / 21 %), keyed on the
`filing_period` axis. Each bracket carries the cuota-accumulation
`fixed_addition` (0 for the first tranche, 8.500 = 50.000 x 17 % for the
2025 rest tranche, 9.500 = 50.000 x 19 % for the 2026 rest tranche) so a
base amount resolves to its cuota directly. Every bracket is grounded in
`ley-27-2014:art-29`, which resolves in `legal/is.toml`.

### Sibling rate verification

The four scalar `is.modelo-200.tipo-gravamen-*` parameters were checked
against the LIS Art. 29 corpus text (BOE-A-2014-12328): general 25 %,
cooperativas fiscalmente protegidas 20 % (the 3-pp reduction capped so
the resulting rate does not exceed 20 %), entidades sin fines lucrativos
10 %, entidades de nueva creación 15 % for the first two profit-making
periods. All four were already correct; no change was needed beyond
keeping their grounding intact. The newly-created-entity 15 % rate is
correctly modelled as a period-dependent state, not a `legal_entity_form`
sub-form value.

### IRPF tarifa

The IRPF tarifa (Modelo 100 escala estatal and autonómica, base general
and base ahorro) already exists in the registry as `bracket_table`
parameters per ejercicio (`renta-{year}-escala-estatal-base-general`
etc.), grounded in `ley-35-2006:art-62` / `art-63`, and is the schedule a
natural-person profile resolves to through the existing
`lookup_bracket_by_ccaa` formulas. It is sound and was not duplicated.

### The entity-type rate dispatch

The Modelo 200 cuota-íntegra formula `[00562] = [01330] x [00558]/100`
previously took casilla 00558 (the tipo de gravamen) as a hand-typed
manual input. Casilla 00558 is now a `computed` casilla whose value is
selected by the new `modelo-200-tipo-gravamen-por-forma-juridica`
formula. That formula uses the `lookup_parameter_by_entity_type` op —
already implemented in the formula runtime and wired into the runtime
graph's enum-dispatch channel — keyed on a new profile binding
`modelo-200-2024-profile-legal-entity-form` (a `profile`-source enum
binding carrying the taxpayer's `legal_entity_form`). The dispatch table
routes the scalar baseline rate per legal form: sociedades de capital
(`sl`, `sa`), sociedades civiles mercantiles and `other` take the
general 25 % rate; cooperativas fiscalmente protegidas the 20 % rate;
entidades sin fines lucrativos the 10 % rate. The new formula, binding,
and the cooperative / non-profit parameters were added to the
`modelo-200-2024-foundation` construct.

### Deferred — the micro-empresa bracketed dispatch

`lookup_parameter_by_entity_type` requires a scalar parameter and
explicitly rejects `bracket_table` parameters, and the flat
`base x rate` cuota formula structurally cannot apply a tranche table.
Fully routing a micro-empresa (`pyme`) profile through the cuota chain
therefore needs a new `lookup_bracket_by_entity_type` runtime op plus a
restructured cuota formula — a formula-runtime design pass beyond a
registry + data change. Per `.claude/rules/aeat-source-hygiene.md` (no
design-only shells) this was not stubbed; the corrected micro-empresa
bracket data still lands so no consumer can read the previous wrong flat
value, and a `pyme` profile fed through the current dispatch fails loudly
rather than computing a wrong cuota.

The W02.S08 `_IS_RATE_SCHEDULE_DEFERRAL` constant in
`_applicability.py`, which asserted the dispatch was unwired and the
pyme value wrong, carried stale process labels and a now-false claim; it
was renamed to `_IS_RATE_SCHEDULE_BOUNDARY` and rewritten as a stable
domain-boundary note.

## Tests

`uv run --no-sync pytest` on the registry suite: 1825 passed. The
`test_modelo_200_registry.py` and `test_cross_dependency_calculations.py`
cuota-chain tests were updated to supply the `legal_entity_form` enum
binding instead of a hand-typed 00558 input — they now exercise the
dispatch and still assert the AEAT Manual de Sociedades worked-example
oracle (cuota íntegra 250.000 at the general rate, manual page 401).

A new `test_modelo_200_tipo_gravamen_dispatch.py` adds seven tests: the
scalar rates encode the LIS Art. 29 grounded values; the micro-empresa
parameter is a two-bracket scale carrying the ADR-grounded 17/20 and
19/21 rates and no flat 23; the rest-tranche `fixed_addition` is
structurally consistent with the tranche widths; the dispatch routes
00558 by `legal_entity_form` and produces distinct cuotas; an unsupplied
or unrecognised form raises `RegistryValidationError`; the dispatch
binding is a profile-sourced enum binding. Per
`.claude/rules/no-tautological-calculation-tests.md` the cuota oracle
comes from the AEAT manual, and the schedule tests assert the
registry-encoded rates against the ADR / LIS Art. 29 specification — a
spec-conformance check, not a re-application of a registry formula; the
dispatch tests assert graph wiring and validation errors.

Two unrelated registry-suite / application-suite failures
(`303.toml: 5003 lines > 2000` and the `_apply_iva_compensation_decision_binding`
signature mismatch) are foreign-campaign WIP in the shared worktree,
outside the Modelo 200 / W03.S13 scope, and were not introduced or
touched by this Step.

`ruff` and `ty` clean on every modified Python file. Committed as
`d3735bba8`.
