---
tags:
  - '#exec'
  - '#registry-casilla-identity'
date: '2026-05-21'
modified: '2026-05-21'
step_id: 'S23'
related:
  - "[[2026-05-20-registry-casilla-identity-summary-exec]]"
  - "[[2026-05-20-registry-casilla-identity-adr]]"
---



# `registry-casilla-identity` follow-up: calculation-completeness gate generalisation

Resolves the open follow-up recorded in the registry-casilla-identity
execution summary (originating step P05.S23): the
calculation-completeness manifest derivation produced manifests only for
Modelo 200, the one modelo whose registry casilla numbers are genuine
five-digit AEAT Diseño tags. The derivation is now vocabulary-agnostic
and the load-blocking gate is live for every calculation-bearing modelo.

- Modified: `src/aeat/domain/calculations/registry/_record_design.py`
- Modified: `src/aeat/domain/calculations/registry/_schema.py`
- Modified: `src/aeat/domain/calculations/registry/__init__.py`
- Modified: `src/aeat/domain/calculations/registry/test_record_design.py`
- Created: per-modelo `completeness-manifest.toml` registry fragments and
  inline manifest blocks, bringing the corpus to 39 manifest-bearing
  modelo revisions across 24 modelos.

## Description

The old `derive_calculation_completeness_casillas` derived a manifest as
the calculation closure intersected with the set of five-digit `[NNNNN]`
casilla tags AEAT embeds in its Diseño de Registros field text. Only
Modelo 200's registry casilla numbers are such tags; the other
calculation-bearing modelos identify casillas by semantic slug
(`iva.cuota-devengada-total`) or short ordinal (`01`-`19`), so the
Diseño-tag intersection was empty and no manifest was derivable.

The derivation is now keyed on each closure casilla's own registry
`(segmento, number)` identity. A new identity-preserving closure walker,
`calculation_closure_identities`, resolves each calculation reference to
the declared casilla it names — by composite `id` first, which is how a
multi-segment modelo's formulas pin a reference to a record segment, then
by `number` — and keeps that casilla's full `(segmento, number)`
identity. `derive_calculation_completeness_casillas` consumes that
identity-aware closure: for a multi-segment modelo the derived segments
are verified against the AEAT Diseño de Registros (still authoritative on
which segment carries a number); for a single-segment modelo the registry
identity alone is authoritative and no Diseño parse is required.

A real defect surfaced while generalising. The bare-number closure walker
`calculation_closure_numbers` folded cross-modelo binding
`source_casillas` / `source_output` selector entries into the closure.
Those selectors name casillas on the foreign `source_modelo`, not on the
modelo being derived — the same error class the walker already excluded
for `RelationDefinition.source_output`. An inventory confirmed all 68
binding selectors that carry `source_casillas` / `source_output` are
cross-modelo (every one declares a `source_modelo`); none are
within-modelo. They are now excluded from the closure. This is why the
old Diseño-tag derivation surfaced those tokens as undeclared "missing"
casillas: they were foreign-modelo casillas the derivation was wrongly
demanding.

The `CalculationCompletenessCasilla.number` field had a `max_length=32`
cap that rejected the longest semantic-slug casilla numbers (up to 42
characters). The cap is removed to match the unconstrained
`CasillaDefinition.number`.

Calculation-completeness manifests are authored as registry data for
every calculation-bearing modelo revision — 39 manifest-bearing
revisions across 24 modelos. This newly covers 37 revisions and retains
the pre-existing Modelo 200 manifest plus the Modelo 100 2025 manifest,
which was re-derived and confirmed identical and additionally converted
off `manual_extraction` because the registry-keyed derivation is now
machine-checkable. Modelo 308 and Modelo 360 carry no calculation
surface (empty closure) and correctly remain manifest-less; the gate
stays dormant for them by design.

No modelo's calculation closure revealed a missing or ungrounded
casilla — zero findings. Every closure casilla across all 24
calculation-bearing modelos is declared, at the correct
`(segmento, number)` identity, and carries `legal_refs` / `source_refs`.

## Tests

The off-load-path drift re-verification test was rewritten to re-derive
every checked-in manifest from the registry calculation surface and
assert equality, with a Diseño segment verification for multi-segment
modelos. A new test asserts the gate is live for every
calculation-bearing modelo — every non-empty-closure revision declares a
manifest and every empty-closure revision declares none. The
full-Diseño coverage tests were updated for the keyword-only derivation
signature.

`test_modelo_parity_coverage` is green: all 26 modelos load valid. The
`test_record_design.py` and `test_referential_integrity.py` suites pass
(87 tests). `ruff` is clean on every touched production and test file.

One pre-existing unrelated failure remains in the broader registry
suite — `test_cross_boundary_roundtrip.py` fails because a concurrent
campaign's in-flight edit corrupted `src/aeat/locales/es.yml` into
invalid YAML; that file is outside this follow-up's scope and untouched
here.

## Correction: cross-modelo binding-selector exclusion narrowed

A subsequent code review found the closure-exclusion invariant stated
above to be too broad. The original generalisation claimed every binding
`source_casillas` / `source_output` selector is cross-modelo and dropped
all of them from the calculation closure. That invariant is false: the
three Modelo 202 `previous_filing` self-binding selectors carry
`source_modelo = "202"` — `source_modelo` equals the modelo being
derived, so their `source_output = "34"` names a within-modelo casilla,
a genuine closure member. A blanket drop would silently shrink a real
closure the first time a `previous_filing` self-binding landed on an
otherwise-non-closure casilla.

The closure walkers now actively walk binding `source_casillas` /
`source_output` selectors and `RelationDefinition.source_output`, and
exclude a selector from the closure **only when it is genuinely
cross-modelo** — when the selector explicitly names a `source_modelo`
that differs from the modelo being derived. A selector that omits
`source_modelo` or sets it equal to the modelo id is a within-modelo
self-binding / self-relation and stays in the closure.
`calculation_closure_numbers`, `calculation_closure_identities`, and
`derive_calculation_completeness_casillas` now take an explicit
`modelo_id` argument so the predicate can be applied; the false
"all selectors are cross-modelo" docstring wording was replaced with the
accurate `source_modelo`-comparison rule. Modelo 202's manifest is
unchanged — casilla 34 was already in-closure via its formula-target and
verification-operand paths. The drift re-verification test re-derives
every manifest with the corrected closure and all 39 stay identical; the
gate stays live for the 24 calculation-bearing modelos and all 26
modelos load valid.
