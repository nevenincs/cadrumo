---
tags:
  - '#adr'
  - '#declaracion-profile-printed-box-scope'
date: '2026-07-25'
modified: '2026-07-25'
related:
  - "[[2026-07-25-declaracion-profile-printed-box-scope-research]]"
  - "[[2026-06-02-m303-parser-engine-totals-impedance-adr]]"
  - "[[2026-06-03-m303-synthetic-generator-primitive-spec-adr]]"
  - "[[2026-06-03-synthetic-fixture-primitive-encoding-discipline-adr]]"
  - "[[2026-05-21-declaracion-extraction-architecture-adr]]"
  - "[[2026-06-13-m303-form-vs-semantic-casilla-dual-keying-adr]]"
---

# `declaracion-profile-printed-box-scope` adr: `extraction profiles target only what AEAT prints` | (**status:** `accepted`)

## Operator ruling (2026-07-25): BOTH revisions

Asked whether to re-scope both M303 revisions or only `2023-y-siguientes`, the
operator ruled **all revisions**. So the six ids leave `2023-y-siguientes` and the
five present in `2009-y-siguientes` leave it too, in one coherent change. The
alternative — leaving 2009 asserting five printed boxes the form does not print —
is rejected.

Two consequences follow directly from the ruling and are binding on the plan:

- The fixture generator's primitive draw block is **deleted**, not gated. Gating
  behind a legacy-template branch was only required under the rejected option.
- `2009-y-siguientes` is a live, fully-built authority for filing years 2009-2022
  (118 casillas, 67 formulas, 94 bindings) whose revision id is asserted by real
  parser and verification-chain tests over seven fixture PDFs. Its half is real
  work, not a rename.

The ruling does NOT resolve the arbitration below, which is a correctness
question rather than a scope question and must be settled in the same change.

## Problem Statement

A `declaracion_pdf` extraction profile is a contract about a document. The
Modelo 303 profile currently states a contract the document cannot honour: six
of its eighteen targets name engine-primitive casillas that the printed AEAT
form does not separately carry. Because those six match only text the project's
own fixture generator emits, the profile is satisfiable by the generated corpus
and refused by every real AEAT render.

The governing principle is not in dispute anywhere in the codebase, but it has
never been written down: **the profile targets engine primitives, but a
declaration PDF can only yield what AEAT printed.** Nothing enforces that today,
so the profile drifted into asking for values that exist in the electronic
submission record and in the engine's formula graph, but not on the page.

This needs deciding now because the defect is invisible from inside the test
suite. The generated corpus was authored to match the profile, so a green run
measures the generator's own conventions rather than AEAT — structurally the
same error as a tautological calculation test. The census in the related
research is what surfaced it; no amount of green tests would have.

## Considerations

- The census establishes that four of the six targets cannot be re-pointed at
  all: two have no evidence anywhere in the specimen, one has no printed box,
  and one is addressed by a neighbouring cell's value.
- `match_strategy` is a closed three-member Literal and none of its members can
  express a sibling-value predicate.
- The Modelo 390 precedent does not transfer; its rows are rate-fixed by
  position and Modelo 303's are not.
- Real-render coverage degrades quarter by quarter (12/11/11/10 of 18) on
  genuinely blank boxes, so any coverage floor must tolerate absent optional
  boxes rather than assume a fully-populated form.
- The originating Route A decision named this risk in its own Forces section and
  resolved it by changing the fixtures rather than by testing a real render; its
  error was treating the diseño de registro and the printed form as the same
  surface.
- The anti-tautology purpose behind the primitive-encoding discipline is sound
  and must survive whatever is decided here.

## Considered options

**(A) Profile targets only printed boxes.** Drop the six engine-primitive
targets; lower `min_coverage` to what the form actually yields; let the engine
obtain primitives from bindings on the calculate path. Chosen.

**(B) Extend `match_strategy` with a value-conditional row strategy.** Add a
member able to locate a base/tipo/cuota row and attribute its cuota by reading
the tipo as data. Rejected for now — see Rationale. Retained as the pathway for
a future capability, not as the answer to this defect.

**(C) Carry both label sets on the profile.** Rejected outright. A profile
matching both the generated and the printed layout can never fail when the two
diverge, which is the entire signal being sought. A guard that cannot fail is
not a guard.

**(D) Leave the profile and relax `failure_semantics`.** Rejected. It converts a
loud refusal into a silent partial extraction of a document the parser
misunderstands, trading a visible defect for an invisible one.

## Constraints

The engine's compute-from-primitives design is **not** in scope and is
deliberately preserved. This record narrows the *extraction* clause of Route A
while leaving its *engine* clause intact: `iva.cuota-devengada-total` and
`iva.cuota-deducible-total` remain computed from primitives, and the dual-keying
invariant that formulas reference `casilla.id` only is untouched.

The substantive open constraint is that removing primitive extraction reopens
the impedance Route A was created to resolve. On the reconcile path the parser
will supply printed totals for casillas the engine owns as computed, and the
arbitration between them is undecided. Route A dodged this by making the PDF
carry primitives; that escape is no longer available for Modelo 303 because the
document does not carry them. The implementation lane must settle this
explicitly and may not resolve it by silently discarding either side. The
current profile already targets boxes 27 and 45 alongside the six, and the
existing internal-consistency assertion that engine resultado equals box 27
minus box 45 is the natural shape for that arbitration to take.

A second constraint is that the anti-tautology proof for primitive summation
currently sources its primitives from a parsed corpus PDF. Once extraction stops
supplying them, that proof needs a different input path. It must not be deleted;
the property it defends is real.

No specimen exercising the 10% or 4% rate rows exists in the repository, so
those two casillas would remain ungrounded under any option including (B).

## Implementation

The profile drops `iva.repercutido.general`, `iva.repercutido.reducido`,
`iva.repercutido.super-reducido`, `iva.autorepercutido.intracomunitaria`,
`iva.soportado.interiores` and `iva.autoconsumo.promotor.base` from its target
list, retaining the printed-box targets it already carries. `min_coverage` is
restated at the level the form genuinely yields across all four annex quarters,
which must accommodate legitimately blank optional boxes rather than assume the
1T shape.

The generator stops printing the six `Primitivo` line items. Its remaining
output should be judged against the printed form rather than against the
profile, reversing the causality that produced the defect.

The moved expectations are a finding, not breakage. Any synthetic M303
expectation that stays green through this layout change is itself evidence that
the corpus is not measuring layout, and should be reported as such rather than
quietly left alone.

The sizing is 15 synthetic corpus fixtures, 48 expected-value entries across 8
fixture blocks, 3 parser-boundary modules, and roughly 24 modules referencing
the six ids of which most are engine-side and unaffected. Details and locators
are in the related research record.

### Sizing independently re-measured before implementation (2026-07-25)

The "roughly 24 modules" figure is **confirmed**: a single pass over
`src/cadrumo` and `dev`, matching the six ids as literal strings and skipping
`__pycache__`, finds exactly 24 `.py` modules — 16 tests, 7 registry, 1
fixture/corpus, and **zero production application modules**. The
"engine-side and unaffected" characterisation holds, and is sharper than
stated: the engine reaches these ids through registry TOML, not through Python.

Two things the paragraph above does not capture, both of which change the work:

- **The id footprint is TOML-dominated, not module-dominated.** 40 TOML files
  carry the six ids (38 registry, 2 extraction profiles) against 24 Python
  modules. The registry TOMLs are where the edit actually lands; a plan sized on
  module count alone would understate it by more than half.

- **There are TWO M303 extraction profiles, not one.** Both
  `303/revisions/2023-y-siguientes/extraction_profiles/0001-modelo-303-declaracion-pdf.toml`
  and `303/revisions/2009-y-siguientes/extraction_profiles/0001-modelo-303-declaracion-pdf.toml`
  carry these targets. The Implementation says "The profile drops ..." in the
  singular; dropping the targets from only the current revision leaves the
  2009 revision asserting printed boxes the form does not print — the very
  defect this decision exists to remove, preserved in the older revision.
  Whether the 2009 revision is re-scoped in the same change or deliberately
  left (with a stated reason) is a decision this ADR should make explicitly
  before a plan is written against it.

  **CORRECTION (same day).** An earlier revision of this paragraph said both
  profiles "name the six ids". That is wrong, and the difference changes the
  work. Parsed from the `target_casillas` tables: the 2023 profile carries **18**
  targets including all six; the 2009 profile carries **9** targets including only
  **five** — `iva.autoconsumo.promotor.base` is absent from it, and the underlying
  casilla does not exist anywhere in the 2009 revision (zero files mention
  `autoconsumo`, against one in 2023). Post-drop the target lists become **12**
  and **4**. So option (A), re-scoping both, removes six ids from one profile and
  five from the other, and touches no autoconsumo concept in 2009 because there is
  none to touch.

### The `min_coverage` floor, which the Implementation mandates restating but leaves unnumbered

`min_coverage` is a FRACTION (`Field(ge=0, le=1)`), values over targets. It sits
at `"1"` today, so every declared target must yield a value — which is why the
four real annex renders score 0.667 / 0.611 / 0.611 / 0.556 and are all refused.

Measured against the post-drop list of 12 targets, the same four renders score
**1.0000 / 0.9167 / 0.9167 / 0.8333**. The highest floor all four quarters satisfy
is therefore **10/12 ≈ 0.8333**, floored by 4T. Anything above that re-arms 4T;
anything above 11/12 also re-arms 2T and 3T.

The trap this closes: the synthetic corpus scores 1.0 at ANY floor, so leaving
`min_coverage` at `"1"` keeps the whole suite green while preserving the exact
defect this decision exists to remove. **The floor cannot be validated by the
synthetic corpus** — only the annex renders can move it.

Method note: three earlier attempts at these measurements were wrong, none of them
a finding about the code. One used unescaped `.` in a regex (dots matched any
character, inflating per-id counts); one misplaced `--include` so every file type
was searched (reporting 93 modules); and one guessed the profile schema's key
names (`targets`/`binding_id`) and returned zero targets for both revisions, which
would have read as "neither profile carries these ids" had it not been obviously
absurd. The figures above come from parsing the real `target_casillas` tables with
`tomllib`, which is why each is stated with its method attached.

## Rationale

(B) fails on the same criterion the whole exercise is about. Binding
`iva.repercutido.general` to box `09` encodes that one filer entered 21% into
the third rate triple; a filer using the first triple extracts blank. That is
the identical convention-binding defect being removed, relocated one layer down
and made considerably harder to see — the profile would look grounded in
official box numbers while still encoding a data-entry habit. Building the
sibling-value strategy that would make (B) honest is real work on a closed
schema Literal, and even completed it would leave three of the six targets
ungrounded: the 10% and 4% rows for want of a specimen, and autoconsumo because
no box exists on the form at all. (B) therefore costs schema surface and
delivers a profile still unable to parse a real render.

(A) wins because it makes the profile's claim true. The box-29 collision is the
clearest illustration: under (B) it would have to be encoded as two casilla ids
reading one printed box, whereas under (A) it simply dissolves — there was only
ever one box, and only one target now names it.

The primitive-encoding discipline is honoured rather than overturned. Its
anti-tautology argument is correct: a fixture encoding only a total and
asserting the engine reproduces it consumes its own input. What the census
challenges is the *encoding* that discipline was satisfied by. The real form
does encode per-rate primitives — positionally, as base/tipo/cuota rows, with
the rate identity in an entered value. A future fixture faithful to that
positional encoding would satisfy the discipline honestly. Inventing named
labels never did.

## Consequences

Lowering `min_coverage` is a **reduction in what the parser claims, not a
weakening of a gate.** Today the profile claims to read six things the document
does not contain, and refuses honestly because it cannot. Afterwards it claims
less and succeeds. The gate's strictness is unchanged; the assertion it guards
becomes true. A future reader encountering the lowered figure should not read it
as ratchet-loosening, and this paragraph exists so that they do not.

The immediate gain is that Modelo 303 can parse a real AEAT render for the first
time, which the `fail_hard` refusal has been correctly preventing.

The cost is that the declaration-parse path no longer exercises the engine's
primitive-summation formulas, so that coverage must be re-established from the
calculate path. This is a genuine loss of a test pathway and should not be
described as free.

The reopened impedance is the main difficulty and is deliberately left to the
implementation lane rather than pre-judged here, because it is an arbitration
question about parser-versus-engine authority that deserves its own evidence.

The pathway this opens is a positional row-reading strategy: the printed form
does carry the base/tipo/cuota information such a strategy would need, so
primitive extraction is inexpressible today rather than impossible. Should a
specimen exercising the reduced rates surface, that becomes a well-grounded
follow-on rather than the speculative extension it would be now.

The pitfall to guard against is treating this as Modelo 303 trivia. The
printed-versus-primitive distinction applies to every `declaracion_pdf` profile,
and the mechanism that let it drift — a corpus authored to match the profile —
is not modelo-specific.

## Codification candidates

None promoted. Project rule codification is retired by operator directive; the
printed-versus-primitive principle is recorded here as the governing decision
for `declaracion_pdf` profiles and should be cited from this record rather than
duplicated into a rule.
