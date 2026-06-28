---
tags:
  - '#exec'
  - '#registry-casilla-identity'
date: '2026-05-20'
modified: '2026-05-20'
step_id: 'S28'
related:
  - '[[2026-05-20-registry-casilla-identity-plan]]'
  - '[[2026-05-20-registry-casilla-identity-adr]]'
  - '[[2026-05-20-registry-casilla-identity-research]]'
---

# `registry-casilla-identity` `P06.S28`

Refocused the off-load-path derivation tool to derive the calculation
closure intersected with the Diseño, and retained the full-Diseño
extraction as a separate advisory coverage-report producer.

- Modified: `src/aeat/domain/calculations/registry/_record_design.py`
- Modified: `src/aeat/domain/calculations/registry/__init__.py`
- Modified: `src/aeat/domain/calculations/registry/test_record_design.py`

## Description

The P03 derivation tool extracted the full AEAT Diseño casilla set as the
manifest source. The ADR amendment refocuses the load-blocking gate to
calculation-completeness, so the derivation is split into two
off-load-path tools:

`calculation_closure_numbers(revision)` is a new helper that computes a
modelo revision's calculation closure — the casilla numbers the
cross-connecting calculation engine traverses: every `formula.target`,
every casilla referenced inside a `formula.expression` (via the
runtime-graph `expression_casilla_refs` walker), every casilla declaring
a `formula` or `binding` endpoint, every binding selector source casilla,
every relation `source_output`, and every verification-expectation
operand (`computed_casillas` and `reconciliation_totals`). Reference
tokens are reduced to bare casilla numbers; a token that matches no
declared casilla is kept verbatim so a calculation that names an
undeclared casilla — the Modelo 200 defect class — still surfaces.

`derive_calculation_completeness_casillas(path, revision, *,
multi_segment)` is the new manifest-derivation tool: it intersects the
calculation closure with the AEAT Diseño, the Diseño authoritative on
each casilla's record segment, the closure bounding the result to the
calculation surface. This produces the calculation-completeness manifest
casilla set the refocused load-blocking gate enforces.

`derive_diseno_completeness_casillas` is retained, repurposed, and
renamed to `derive_diseno_coverage_casillas`: the full-Diseño extraction
is no longer a manifest producer but the input to the off-load-path
advisory coverage report (P05.S31) that inventories form-level data
coverage without redding the load. `DerivedManifestCasilla` is renamed
`DerivedDisenoCasilla` since it is now a generic Diseño-derived
`(segmento, number)` row shared by both derivations.

All references updated: the registry `__init__.py` re-exports, and the
`test_record_design.py` import and call sites (mechanical rename to
`derive_diseno_coverage_casillas`; the advisory-coverage test reframing
lands in `P06.S30`).

## Tests

`pytest src/aeat/domain/calculations/registry/test_record_design.py
src/aeat/domain/calculations/registry/test_modelo_parity_coverage.py`
passes — 39 tests, all 26 modelos load valid, the gate stays dormant.
`ruff check` on the three touched files passes clean. The
`_record_design` module imports cleanly with no `_runtime_graph` import
cycle.
