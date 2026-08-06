---
tags:
  - '#audit'
  - '#declaracion-real-render-verification'
date: '2026-07-27'
modified: '2026-07-27'
body_hash: 'sha256:cfafcc62ef50726adb820d030c2e2b680e557b1cdace9423208bfb234652e5ae'
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

### accepted-adr-was-being-violated | high | the role axis already decided this, and one assertion erased it

The `verification-fixture-roles` ADR (status accepted) puts two orthogonal axes
on every fixture sidecar: `provenance` (`real_corpus` / `synthetic_generated`)
and `role` (`parser_anchor` / `formula_verification`). It describes a real
sanitised specimen as a "parser-fidelity anchor" and a synthetic one as a
"formula-verification specimen", and states that synthetic specimens are the
ones carrying "formula-derived ground truth".

So the project had already decided the question. These were not merely sloppy
docstrings; they were an accepted decision being violated, because
`test_cross_dependency_calculations.py` and `test_verification_chain_m111.py`
consumed `parser_anchor` fixtures as calculation oracles.

The enforcement gap sat inside the offending file. Its sidecar assertion read
the exact field that would have refused it, accepted BOTH values, and called
the result "an oracle role". The ADR is explicit that `role` is "descriptive and
enables future role-specific assertions" — nothing enforced it, which is how
this drifted. The codebase already held the correct single-expected-role shape
twice, in the manual-annex provenance gate and in the bilingual presentador
parser test, so this was an outlier rather than an unsolved problem.

### definitional-sum-modelos-need-probes-not-numeric-oracles | high | 111, 180 and 190 carry no rate, so a numeric AEAT example is not their grounding artefact

Measured over the registry formula tree: modelo 111 declares only `add` and
`subtract`, modelo 180 only `copy`, modelo 190 only `add` and `copy`. There is
no rate, bracket, coefficient or percentage in any of the three. Closed by
construction on the `op = "..."` literal, which a formula cannot declare
without.

That changes what "grounded" means for them. AEAT states casilla 28 in prose —
"la suma de las retenciones e ingresos a cuenta que, por todos los conceptos, se
hayan hecho constar en los epígrafes anteriores" — and the M111 registry
revision already declares that formula with a `source_citations` entry requiring
exactly that wording. For a definitional sum the órden's stated aggregation IS
the grounding artefact; a numeric worked example would add nothing, because
there is no rate that could be wrong while the structure is right.

The real defect in the M111 test was therefore not that its amounts were
inauthentic but that they were IDENTICAL. `1000 + 1000 + 1000` cannot
distinguish a sum from a max, a first-element pick, or a hardcoded constant.
Distinct probe values can, and asserting no tax fact, they are not fabrication.

This also refines the earlier finding on generator circularity: engine-derived
ground truth is genuinely circular for a rate-bearing modelo, but for a
definitional sum it is circular only if derived by RUNNING the engine.
Independently implementing the órden's stated rule — which is what the probe
tests now do — is legitimate.

The correspondence between which modelos have bundled manual oracles
(100, 200, 202, 303, 322, 353, 390 — all rate-bearing) and which do not
(111, 180, 190 — all pure aggregation) therefore looks like the existing design
rather than an oversight.

### 111-to-190-is-entailed-not-stated | medium | the four-quarters-equal-the-annual claim is a consistency invariant, not a reconciliation rule

RIRPF art. 108 §1 obliges a quarterly declaration of "las cantidades retenidas y
de los ingresos a cuenta que correspondan por el trimestre natural inmediato
anterior"; §2 obliges an annual declaration of "las retenciones e ingresos a
cuenta efectuados". Both cover the same quantity, and the four natural quarters
partition the year, so a truthful pair must reconcile.

It is entailed, not stated. It is not a computation modelo 190 performs — the
190 diseño defines its totals as sums over its own type-2 perceptor records —
and no stated reconciliation REQUIREMENT was located in the bundled corpus. That
negative is bounded: it is over the material held, not a claim about what AEAT
requires anywhere.

Two bundled-corpus gaps support that bound and are operator corpus-refresh items
rather than fixable here. The modelo 111 órden excerpt is 1,519 bytes carrying
only the Article 1 approval clause, with no casilla instructions and no anexo.
The RIRPF art. 108 excerpt is partial, carrying §§1–2 while the full article
continues into the certificado and the relación nominativa de perceptores.
`legal-grounding-verifies-bundled-authoritative-corpus` names exactly this case
and prescribes flagging it rather than trusting the snippet.

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

Enforce the role axis wherever a fixture supplies a value, rather than only in
the two files corrected here. The assertion shape is settled — a single expected
role per fixture, as the manual-annex and bilingual-presentador tests already
do — and the corrected sidecar check in the cross-modelo module is a third
instance. A gate that refused any `parser_anchor` fixture supplying a
calculation expectation would close the class rather than these instances, and
would have caught both defects. It is NOT built here: whether such a gate
already exists somewhere is an open-by-nature question, and the truncated code
index cannot close it. Scoped and held deliberately.

Do NOT record 111, 180 and 190 as missing-oracle gaps. That recommendation was
considered and is argued against above: on the definitional-sum finding these
modelos do not need numeric AEAT oracles, so a loudly-failing gate demanding one
would assert a requirement the law does not impose and could only be turned
green by manufacturing figures. What they needed was discriminating probes,
which is what landed.

## Context

Evidence for every measurement in this audit was produced by pytest plugins that
monkeypatched the value source or the parse output, run with `-n0` against the
working tree. Post-fix, the amount mutation still leaves all thirteen
cross-modelo tests passing. That is the honest result and it is now what the
module docstring says: the coverage is structural, catching a broken fold, a
dropped relation, a mis-declared binding selector, or a resolution that silently
returns zero, and nothing about AEAT correctness.

A second pass, after the fixture-role ADR and the AEAT casilla instructions came
to light, replaced the placeholder-derived monetary assertions in the two
tainted modules with distinct probe amounts and proved the replacements
discriminate. Four mutations, all run with `-n0`:

- Engine returns a MAX for casilla 28 instead of the nine-operand sum: the M111
  aggregation test fails, `999.99` against an expected `4999.95`. Under the old
  placeholder inputs — one non-zero leaf of `1000.00` — max and sum are equal
  and this would have passed.
- Every epígrafe probe made identical: the aggregation test still passes, but
  the probe-distinctness guard fails, so the discriminating power cannot be
  quietly removed by a well-meaning edit.
- The M190 quarterly fold made degenerate, every period reading period 0: the
  cross-modelo test fails with `4938.24` against `12345.60` and `740.72`
  against `1740.73`.
- The original amount mutation, every fixture amount replaced by an arbitrary
  number: still 13 passed. That is now the CORRECT result for the M190 path,
  which no longer reads fixture amounts at all; the M180 path is a
  `formula_verification` specimen, the class the ADR designates for exactly
  this use.

What remains genuinely ungrounded is narrower than it first appeared. For 111,
180 and 190 nothing does — they are definitional aggregations whose rule is the
grounding artefact, and the engine is now proven to implement it. The bundled
corpus gaps recorded above (the 111 órden excerpt and the partial art. 108) are
operator corpus-refresh items, not calculation gaps. A rate-bearing modelo
without a bundled oracle would be a real gap; none of these three is one.
