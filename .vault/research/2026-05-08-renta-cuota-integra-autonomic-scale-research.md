---
tags:
  - '#research'
  - '#renta-cuota-integra-autonomic-scale'
date: '2026-05-08'
modified: '2026-05-08'
related: []
---

# `renta-cuota-integra-autonomic-scale` research

Grounding for wiring the autonomic side of the IRPF cuota integra
chain (casillas 0529 and 0531) — the per-CCAA progressive scale that
LIRPF arts. 74-75 mandate every Comunidad Autónoma must publish.
Distinct from the state-scale stream (already closed) because the
autonomic scale is jurisdiction-specific: each CCAA legislates its
own marginal rates and bracket cut-points, with substantial
divergence from the state default in some jurisdictions and minor
deviations in others.

## Mandate and scope

LIRPF art-74 fixes the autonomic scale as the legal authority for
casillas 0529 and 0531. LIRPF art-75 fixes the autonomic cuota
integra at casilla 0546. Each CCAA's autonomic scale is published in
its own per-year BOE / DOG / DOGC / etc. norm. The legal anchor
`ley-35-2006:art-74` is already declared in the registry's legal
catalogue (`registry/aeat/legal/irpf.toml`) with a reviewed citation.

The state-scale formulas already in the registry compute:

- `0528 = lookup_bracket(0505, renta-{year}-escala-estatal-base-general)`
- `0530 = lookup_bracket(0521, renta-{year}-escala-estatal-base-general)`

The mirror autonomic targets are:

- `0529 = <ccaa-dispatched lookup_bracket against 0506 + per-CCAA scale>`
- `0531 = <ccaa-dispatched lookup_bracket against 0523 + per-CCAA scale>`

where the bracket schedule is the operator's tax-residence CCAA's
autonomic scale for the relevant ejercicio.

## Jurisdictions in scope

The `aeat.domain.profile.CCAA` enum lists 15 ordinary common-regime
autonomous communities. The autonomic-scale work covers exactly
those:

| ccaa identifier         | nombre                |
| ----------------------- | --------------------- |
| `andalucia`             | Andalucía             |
| `aragon`                | Aragón                |
| `asturias`              | Principado de Asturias|
| `baleares`              | Illes Balears         |
| `canarias`              | Canarias              |
| `cantabria`             | Cantabria             |
| `castilla_la_mancha`    | Castilla-La Mancha    |
| `castilla_y_leon`       | Castilla y León       |
| `cataluna`              | Cataluña              |
| `comunidad_valenciana`  | Comunitat Valenciana  |
| `extremadura`           | Extremadura           |
| `galicia`               | Galicia               |
| `la_rioja`              | La Rioja              |
| `madrid`                | Madrid                |
| `murcia`                | Región de Murcia      |

Out of scope:

- **País Vasco / Navarra** — foral regimes administered by their
  Diputaciones Forales, not by AEAT. They have their own IRPF
  entirely and never appear in Modelo 100. The profile module
  excludes them from the `CCAA` enum.
- **Ceuta and Melilla** — autonomous cities, not autonomous
  communities. They apply the state default scale plus a 60 %
  deduction on the cuota for residents (LIRPF art. 68bis). The
  autonomic scale parameter is not declared for them; they fall
  through to a separate deduction codepath that is not part of this
  stream.

Six ejercicios per CCAA: 2020, 2021, 2022, 2023, 2024, 2025. Total:
**15 × 6 = 90 bracket-table parameters** to source and validate.

## Existing registry support

- The CCAA value is exposed to the registry via the binding
  `renta-{year}-profile-tax-residence-ccaa`, defined under selector
  `{ profile_model = "TaxResidenceProfile", field = "ccaa" }`. The
  binding's value type is the CCAA string enum.
- The casilla `ZCCAD` carries the operator's CCAA at filing time
  and is bound to that profile binding.
- The bracket-table parameter shape is well-tested:
  `data_type = "bracket_table"`, with an array of bracket entries
  carrying `lower_bound`, `upper_bound`, `fixed_addition`,
  `marginal_rate`, `valid_from`, and `valid_to`.

## Runtime gap

The current `_formula_runtime._evaluate_leaf` reads a binding's
value as `Decimal` (`binding_values[expression.binding]`). The CCAA
binding is a string enum, not numeric. The existing `lookup_bracket`
op takes exactly two args: a numeric base value and a single
parameter reference. There is no built-in dispatch primitive that
routes the bracket lookup against a string-typed binding.

Two design routes are open:

1. **Runtime extension: a `lookup_bracket_by_ccaa` op.** New op that
   takes `(base_value, ccaa_binding_value, dispatch_table)` where
   `dispatch_table` maps CCAA enum strings to bracket-table
   parameter ids. Cleanest formula declarations; one new op in the
   evaluator + supporting schema work. Localises the CCAA-routing
   knowledge inside the runtime rather than spreading it across
   formulas.
2. **Pure `if_then_else` cascade.** Encode CCAA as numeric codes
   (1..15), expose the CCAA binding numerically, and use the
   existing `if_then_else` + comparison ops to chain a 15-way
   dispatch per formula per year. No runtime change but produces
   verbose formulas (≈30 KB per casilla per year) and couples every
   autonomic formula to the numeric encoding.

This research recommends route 1; the ADR pins the decision and the
plan sequences the runtime extension before per-CCAA data wiring.

## Data-sourcing burden

Each CCAA × year scale requires sourcing:

- the BOE / DOG / DOGC / etc. legislative reference for the year;
- the bracket cut-points and marginal rates as declared in that
  reference;
- a published worked example (autonomic cuota for a specific base
  liquidable) that can serve as a parity gate.

For the 2025 ejercicio, AEAT's manual práctico parte 1 (already
declared as `aeat-renta-2025-manual-parte1` in the source catalogue)
includes a chapter on autonomic scales and references each CCAA's
BOE-published scale. That chapter is the consolidated authority for
2025 and the entry point for parity gating.

For 2020-2024, each CCAA's autonomic scale must be fetched from the
respective per-year BOE archive. Those references already exist in
the legal catalogue under jurisdiction-specific anchors (e.g.
`ley-cataluna-19-2010:art-1`); each new bracket parameter cites the
relevant CCAA-specific authority alongside `ley-35-2006:art-74`.

## Validation pipeline coverage

Once the formulas land per-CCAA, the existing test gates carry the
contract automatically:

- `test_no_orphan_parameters_in_any_revision` — every per-CCAA
  bracket parameter must be referenced by a formula expression. The
  `lookup_bracket_by_ccaa` op's `dispatch_table` argument counts as
  a reference.
- `test_every_formula_parameter_reference_resolves_to_a_declared_parameter`
  — confirms each per-CCAA parameter id is declared in the same
  revision.
- workbook parity — exercise the dispatch op against AEAT's
  workbook for each CCAA-specific worked example.
- AEAT live-oracle replay — Renta WEB Open lets the test harness
  drive a synthetic profile per CCAA and confirm the autonomic
  cuota matches the live oracle.

## Out of scope

- **Per-CCAA deductions** (e.g. Madrid's deducción por gastos
  educativos, Cataluña's deducción por inversión en empresas
  emergentes). Those are separate formulas at different casillas
  and follow their own per-CCAA wiring streams.
- **Special regimes** within a CCAA (e.g. Canarias' IGIC instead of
  IVA, although IGIC does not affect IRPF). Out of scope.
- **Mid-year residence change** (LIRPF art. 72.3 — the operator's
  CCAA at year-end determines the scale). The existing
  `tax_residence_change_history` field on `TaxResidenceProfile` is
  the right place to gate that logic when the time comes; for now,
  the profile's `ccaa` field is sufficient for the steady-state
  case.
