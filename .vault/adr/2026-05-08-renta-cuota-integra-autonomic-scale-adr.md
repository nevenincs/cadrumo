---
tags:
  - '#adr'
  - '#renta-cuota-integra-autonomic-scale'
date: '2026-05-08'
modified: '2026-05-08'
related:
  - "[[2026-05-08-renta-cuota-integra-autonomic-scale-research]]"
---

# `renta-cuota-integra-autonomic-scale` adr | (**status:** `accepted`)

## Problem Statement

The autonomic side of the IRPF cuota integra (casillas 0529 and
0531, summed into casilla 0546) is computed by applying the
operator's tax-residence Comunidad Autónoma's progressive scale to
the autonomic base liquidable general (casilla 0506) and to the
autonomic personal/family minimum (casilla 0523). Each of the 15
ordinary common-regime CCAA legislates its own scale per ejercicio.
The registry currently has no autonomic bracket-table parameters,
no formulas at 0529 / 0531, and no runtime primitive for
CCAA-keyed bracket dispatch. Casillas 0529 and 0531 are operator-
typed inputs today.

## Considerations

- LIRPF art-74 mandates that the autonomic scale be applied; LIRPF
  art-75 fixes the autonomic cuota integra. Each CCAA's scale is
  legally fixed and must be reproduced exactly.
- The `aeat.domain.profile.CCAA` enum already enumerates the 15
  jurisdictions and the binding
  `renta-{year}-profile-tax-residence-ccaa` already exposes the
  operator's CCAA value to the registry.
- The existing `lookup_bracket` runtime op accepts only one
  parameter ref; a CCAA-keyed dispatch is not expressible through it.
- The bracket-table parameter shape, the `lookup_bracket` semantics,
  and the workbook-parity / live-oracle gates are all reusable from
  the just-closed state-scale stream.
- The data-sourcing burden is non-trivial: 90 bracket tables (15
  CCAA × 6 ejercicios). Each must be sourced from authoritative
  per-jurisdiction BOE / regional gazette references.
- An `if_then_else` cascade encoding CCAA as numeric codes works
  with the existing runtime but produces verbose formulas (≈30 KB
  per casilla per ejercicio) and couples every autonomic formula to
  the numeric encoding. Maintainability is poor; debug output of
  the formula tree under that scheme is unreadable.

## Constraints

- The runtime must continue to accept numeric `Decimal` values for
  every binding it evaluates today; a CCAA-keyed dispatch must not
  break the existing binding contract.
- Concurrent agents are actively editing
  `registry/aeat/modelos/100/revisions/*.toml`. Per-CCAA wiring
  must be small and focused per commit to minimise merge collisions.
- Pre-commit hooks (ruff, ty, prek) gate every commit; new runtime
  ops must clear ty type checks.
- The data-sourcing work for 2020-2024 requires per-CCAA per-year
  BOE archive access; the agent doing the data entry must carry
  the SME knowledge to validate cut-points and marginal rates
  against the legal text.

## Implementation

Three layers, sequenced strictly:

### Layer 1 — Runtime extension: `lookup_bracket_by_ccaa` op

Extend `aeat.domain.calculations.registry._formula_runtime` with a
new op:

```
op = "lookup_bracket_by_ccaa"
args = [
    <expression yielding base value (Decimal)>,
    <leaf reference to a string-typed binding (CCAA enum)>,
    <special "dispatch_table" leaf type whose value is a Mapping
     of ccaa-string -> parameter-id>,
]
```

The evaluator dispatches on the binding's string value, looks up the
matching parameter id, then delegates to the existing
`_resolve_bracket` against `(base_value, dispatch_table[ccaa],
date_context)`. If the CCAA is not in the dispatch table, the runtime
raises `RegistryValidationError` (forces every consuming formula to
declare every supported CCAA explicitly).

Schema work: extend `FormulaExpression` to allow a `dispatch_table`
leaf, and extend `_evaluate_leaf` to support string-typed bindings
without forcing them to `Decimal`.

### Layer 2 — Per-CCAA bracket-table parameters

Per ejercicio Y in {2020, 2021, 2022, 2023, 2024, 2025} and per CCAA
in the 15-jurisdiction list:

```toml
[[revisions."{Y}".parameters]]
id = "renta-{Y}-escala-autonomica-{ccaa}-base-general"
data_type = "bracket_table"
unit = "EUR"
bracket_axis = "filing_period"
legal_refs = ["ley-35-2006:art-74", "<ccaa-specific-norm>:art-N"]
source_refs = ["<ccaa-specific-source>", "lirpf-cuota-chain-authority"]

[[revisions."{Y}".parameters.source_citations]]
source_ref = "<ccaa-specific-source>"
required_text = ["escala autonómica", "base liquidable general"]

# brackets: per-CCAA cut-points + marginal rates per the legal authority
```

### Layer 3 — Per-revision formulas at 0529 and 0531

Two new formulas per revision (mirrors the state-scale pattern):

```toml
[[revisions."{Y}".formulas]]
id = "renta-{Y}-cuota-escala-autonomica-sobre-base-liquidable-general"
target = "0529"
expression = { op = "lookup_bracket_by_ccaa", args = [
    { casilla = "0506" },
    { binding = "renta-{Y}-profile-tax-residence-ccaa" },
    { dispatch_table = {
        "andalucia"            = "renta-{Y}-escala-autonomica-andalucia-base-general",
        "aragon"               = "renta-{Y}-escala-autonomica-aragon-base-general",
        ...
        "murcia"               = "renta-{Y}-escala-autonomica-murcia-base-general",
    } },
] }
```

Mirror declaration for casilla 0531 against casilla 0523.

## Rationale

Layer 1 (runtime extension) was chosen over the `if_then_else`
cascade because:

- The dispatch knowledge belongs at the evaluator, not duplicated 15
  times per formula. One bug in the cascade corrupts every CCAA's
  cuota.
- The dispatch_table leaf type is reusable for any future
  string-keyed dispatch (per-CCAA deductions, per-CCAA filing
  schedules). It is a one-time investment.
- ty type checks the runtime extension cleanly; the cascade encodes
  CCAA-to-integer in a magic-number table that ty cannot validate.
- The formula tree readable in operator-facing tooling stays small.
  A 15-way cascade formula is not human-reviewable.

Per-CCAA parameter ids (vs. one parameter with a CCAA filter
column) was chosen because:

- The bracket-table schema is mature and tested. Extending its
  filter dimension would invalidate every existing bracket-table
  test.
- Per-CCAA parameters keep the data-sourcing units small and
  individually reviewable. A failing per-CCAA bracket test points
  at exactly one jurisdiction.
- Source citations attach naturally per CCAA — each parameter cites
  the relevant per-CCAA legal authority alongside the LIRPF
  art-74 anchor.

## Consequences

- After this work lands, casillas 0529 and 0531 become computed (no
  longer manual). The autonomic cuota chain reaches the same
  end-to-end correctness contract the state chain now has.
- A new runtime primitive is part of the registry's permanent
  surface. Future CCAA-keyed dispatches (per-CCAA deductions,
  per-CCAA bonificaciones) reuse it rather than reinventing.
- Per-CCAA data-sourcing work is real research work. It cannot be
  done in a single session and depends on per-CCAA SME validation.
  The plan sequences the runtime extension and proof CCAA (Madrid
  2025) as the entry slice; per-CCAA per-year data wiring follows.
- Every CCAA with no autonomic deviation from the state default
  (in years where one published "no separate scale" — apply state
  scale verbatim) gets a parameter that mirrors the state scale.
  No CCAA-specific "default to state" fallback in the runtime; the
  data is explicit.
- The `_PRE_STAGED_PARAMETERS` allow-list pattern is reused: a CCAA
  whose data is sourced but whose formula is not yet wired sits in
  the allow-list until the formula lands.
