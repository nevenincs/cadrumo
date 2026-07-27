---
tags:
  - '#audit'
  - '#declaracion-real-render-verification'
date: '2026-07-27'
modified: '2026-07-27'
related:
  - "[[2026-07-26-declaracion-real-render-verification-adr]]"
  - "[[2026-07-26-declaracion-real-render-verification-plan]]"
---

# `declaracion-real-render-verification` audit: `fixture amount grounding claim retraction`

## Scope

A set of calculation and verification-chain tests asserted, in their names and
docstrings, an AEAT grounding that has never held. This audit records the
instrumented evidence for that, the blast radius, and the retraction applied.

The operator's framing separated two lanes: privacy (whose real data sits in the
committed fixtures) and correctness (whether the tests consuming those fixtures
verify anything). This audit is the correctness lane only. Three constraints
bound it: the tests are not deleted, no replacement numbers are invented, and
the defect treated as the defect is the CLAIM, not the coverage.

## Findings

### mutation-survives-arbitrary-amounts | high | every monetary assertion in the cross-modelo suite passes with fixture amounts replaced by an arbitrary number

`src/cadrumo/domain/calculations/registry/tests/test_cross_dependency_calculations.py`
was measured, not read. A pytest plugin replaced the fixture value source so
every extracted monetary amount became `777777.77`. Baseline was `13 passed in
27.95s`; under mutation, `13 passed in 27.29s`. This is an assertion-level
mutation, not a fixture-killing one: the tests compare an engine value against a
fixture value, and both sides move together, so the comparison closes for any
amount.

The root cause is that the fixture amounts are not an oracle. The M190 specimen
is `provenance = "real_corpus"`, `role = "parser_anchor"`, and the redaction
pipeline replaced its amounts with the uniform placeholder `1000.00`. The M180
specimen is `provenance = "synthetic_generated"` with hand-authored generator
literals. The extracted M190 values were `decl.total-percepciones = 1` (a count,
not an amount), `decl.percepciones-total = 1000.00`, and
`decl.retenciones-total = 1000.00`.

The helper `_grounded_quarterly_source_values` and its docstring sentence "The
fixture total remains the expected oracle" asserted the opposite of the measured
fact.

### vacuous-4t-case | high | the M111 4T case received zero inputs, executed zero assertions, and reported success

`src/cadrumo/adapters/inbound/declaracion/tests/test_verification_chain_m111.py`
was instrumented to record per-case inputs and count closure-assertion
firings. Result across the four parametrised cases: `2024-1T`, `2024-2T` and
`2024-3T` each received three inputs (`07 = 1`, `08 = 1000.00`, `09 = 1000.00`),
and `2024-4T` received none. The closure assertion fired six times, every one
comparing `1000.00` against `1000.00`. Four tests passed.

The 4T render prints casilla 30 alone. Both closure branches were guarded on
`has_leaf_inputs`, which was false, so the case ran to completion having
asserted nothing. A test that cannot fail must not report success; this is the
sharper of the two defects and is independent of the grounding question.

The same shape was present in the M131 chain, where the closure loop did
`continue` on an absent casilla, so a parse regression dropping all four closure
casillas would have left the test green.

### false-grounding-docstrings | medium | the AEAT-grounding claim was copy-pasted across eight sibling test modules

The M111 docstring claimed "GROUNDED authority: AEAT corpus PDFs from the
sanitised real-form fixture set". The fixtures' own sidecars declare
`role = "parser_anchor"` for all four quarters, which is precisely the role that
does NOT assert the amounts are usable as a formula oracle. Seven sibling
modules carried the same header in the self-contradictory form "GROUNDED
authority: synthetic fixture", where a generator-authored specimen was named as
an authority.

The borrador chain is a distinct and stronger case: its fixture values are
generated from the registry's own committed bracket tables, so the expected
cuota is derived from the same tables the engine applies. That test is circular
by construction and cannot detect a bracket table wrong against AEAT.

### honesty-gate-had-no-jurisdiction | medium | the registry grounding gate could not have caught this, and no registry declaration is affected

`test_external_oracle_grounding_enrolled.py` binds registry
`externally_grounded_casilla_ids` declarations against bundled oracle payloads
in both directions. It reads registry TOML and the bundled corpora; it has no
visibility into Python docstrings. The false claim lived entirely in prose, in a
surface the gate does not and structurally cannot scan. The gate was working as
designed.

The blast radius on registry data is nil. The modelos declaring
`externally_grounded_casilla_ids` are 100, 200, 202, 303, 322, 353 and 390.
Modelos 111, 180 and 190 declare none, so no registry grounding claim needed
withdrawing. The M100 casillas exercised by the affected tests (`0604`, `1577`)
are absent from every declared set.

### synthetic-amounts-are-invented-not-circular | medium | the synthetic formula_verification class is ungrounded but, outside the borrador case, not self-referential

Recorded as fact for the separately-scoped question, not acted on. Sampling the
generators, the M180 fixture's amounts (`3`, `12.000,00`, `2.280,00`) are
hard-coded dataclass literals in
`src/cadrumo/tests/fixtures/justificantes/_generate_misc_a.py`. They are not
computed by the registry engine, so the M180/M193/M115/M123/M131 chains are not
circular in the "engine computes its own expected value" sense that
`no-tautological-calculation-tests` forbids.

They are, however, invented: author-chosen numbers with no AEAT authority. The
generators are careful about a different axis — the M180 generator's own
docstring grounds its LABELS against the AEAT printed form and states its
non-tautology proof in terms of parse patterns, not amounts. The honest reading
of the `formula_verification` class is therefore that layout and labels are
AEAT-grounded and load-bearing, while amounts prove formula closure only. The
borrador fixture is the exception and is genuinely circular.

### guarded-skip-vacuity-is-an-unscreened-shape | medium | the vacuity screen cannot see the shape that produced the 4T false green

The `test-harness-honesty` campaign built `dev/audit/vacuity_screen.py` to hunt
exactly this class. It does not cover this instance. The screen detects a gate
that asserts a collection is empty or a count is zero without proving it
scanned, and its own docstring is explicit that it covers the four known shapes
only.

The 4T case is a different shape: not an empty-set assertion, but a conditional
guard wrapping every assertion in the function, where the guard is false for
some parametrised cases. Nothing is asserted and nothing is asserted to BE
empty, so there is no empty-assertion node for the screen to match. The shape
generalises to any `if <precondition>:` that wraps a test's entire assertion
body, and to a loop with `continue` on absent data, which is how the M131
instance arose.

This belongs to the `test-harness-honesty` feature rather than this one; it is
recorded here because this is where the instance was measured. A screen for it
would look for a test function whose every assertion is dominated by a
conditional, or would compare assertion-execution counts across parametrised
cases and flag a case that executes none.

## Recommendations

Retract the claim, keep the coverage. Applied in this pass: the cross-modelo
module now carries a module docstring stating what it verifies and what it does
not, `_grounded_quarterly_source_values` is renamed `_split_total_across_quarters`
and the "expected oracle" sentence is gone, `_m180_grounded_relation_source_values`
becomes `_m180_fixture_relation_source_values`, and the eight sibling modules
carry a truthful "FIXTURE, NOT ORACLE" header naming each specimen's declared
provenance and role.

Make the M111 parametrisation declare per case both the casilla set the render
prints and the casillas it can close, then assert that leaf presence and claimed
closure agree. This turns the 4T case into a parse-fidelity assertion with real
content and makes a parser regression red rather than silently reducing a case
to a no-op. Apply the equivalent guard to the M131 closure loop in place of the
`continue`.

Leave the oracle seam explicit rather than building machinery for it. Each
retracted docstring names where an AEAT figure plugs in: a payload under
`corpus/manual_oracles/` keyed by `expected_by_casilla_id`, with the casilla
declared in the revision's `externally_grounded_casilla_ids`, which the existing
honesty gate then binds in both directions.

Treat the borrador circularity as a separate decision. It is a different defect
class from the placeholder-amount sites and warrants its own disposition rather
than being folded into this retraction.

## Context

Evidence for every measurement in this audit was produced by pytest plugins that
monkeypatched the value source or the parse output, run with `-n0` against the
working tree. Post-fix, the amount mutation still leaves all thirteen
cross-modelo tests passing. That is the honest result and it is now what the
module docstring says: the coverage is structural, catching a broken fold, a
dropped relation, a mis-declared binding selector, or a resolution that silently
returns zero, and nothing about AEAT correctness.

What remains ungrounded, for the agent sourcing AEAT worked examples: modelos
111, 180 and 190 have no bundled per-casilla oracle of either kind. The specific
figures a real oracle would need to supply are the M111 quarterly retenciones
leaves and totals for casillas 28 and 30, the M180 annual `decl.base-total` and
`decl.retenciones-total`, and the M190 annual `decl.percepciones-total`,
`decl.retenciones-total` and `decl.total-percepciones`.
