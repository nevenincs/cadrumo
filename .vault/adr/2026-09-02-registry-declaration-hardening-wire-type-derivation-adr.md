---
tags:
  - '#adr'
  - '#registry-declaration-hardening'
date: '2026-09-02'
modified: '2026-09-02'
body_schema: 'body-v2'
body_hash: 'sha256:bc4f12b23617b63bd43149fd6c8de6bd7a52b692626869662033954e0054a088'
related:
  - "[[2026-09-01-registry-temporal-coverage-live-remeasurement-adr-regrounding-audit]]"
  - "[[2026-09-02-registry-declaration-hardening-declaration-kinds-adr]]"
  - "[[2026-09-02-registry-declaration-hardening-plan]]"
---

# `registry-declaration-hardening` adr: `An export field derives its wire type and scale from the casilla, or attests why not` | (**status:** `proposed`)

## Problem Statement

## Problem Statement

A casilla declares a data type carrying its domain meaning. The export field that renders it
declares its own type from a deliberately narrower wire vocabulary, because a fixed-width record
carries fewer distinctions than the domain does. The narrowing is a design choice. What is
missing is any declaration of which narrowings are legitimate, so every transition is accepted
because no rule exists to reject one.

Measured through the canonical resolved export surface, the corpus carries 8075 casilla-to-wire
transitions on field-carrying endpoints, of which 3349 diverge, across 33 distinct pairs. Row
mapped endpoints are excluded rather than dropped: after binding derivation a repeated row's slot
names the binding rather than the casilla, so it carries no rendered type to compare.

Most of that divergence is sound and three mechanisms account for it. Money rendered as decimal is
2140 fields, and 2139 declare two decimal places, which is the cents encoding. The money wire type
itself scales inside the codec, multiplying by the cents factor when writing and parsing at two
places, so a money-typed field needs no declared count. And several official designs split one
amount across an integer-part field and a decimal-part field pointing at the same casilla, where
the split is the encoding and neither half declares a scale; 132 fields are in that shape.

What remains is small and concentrated. Twenty-four monetary fields are rendered by a wire type
that applies no scale at all and declare none: twenty-three as text and one as an integer. For
those the emitted magnitude is decided nowhere in this registry, and a wrong reading is a filing
out by two orders of magnitude. The twenty-three are the sign-prefixed alphanumeric form the
official design itself types as alphanumeric, so their wire type is faithful and only the scale is
absent. The one integer field is neither design-faithful nor structurally scaled, and it emits an
unscaled magnitude beside five identical sibling amounts that emit cents.

Beside those, text rendered as date is 49 fields and text rendered as integer is 60, both changing
the kind of value with no stated reason, and one field renders money at four decimal places where
every other money field uses two, on a unit security value where four is plausible and unrecorded.

An earlier draft of this record put the unscaled count at 133 and located 120 of them in a single
informativa. That figure counted every money-to-integer transition without accounting for the part
split or the codec's own scaling, and it is superseded by the measurement above.

## Considerations

The wire vocabulary is narrower than the domain vocabulary by design, and that design is
documented at the export schema boundary. This record does not propose widening the wire
vocabulary; it proposes declaring the mapping between the two.

The sound majority and the undeclared minority need different treatment. A rule that refused every
divergence would refuse 2139 correct cents encodings, and a rule that permitted every divergence
would keep permitting the twenty-four unscaled money fields. The mapping has to distinguish them.

Scale is the sharpest case because it is silently lossy. A money value rendered as an integer with
no declared scale is not a formatting choice; it is an amount whose magnitude depends on a
convention held in the official record design and nowhere in the registry. Nothing in the project
can verify it, and a wrong reading is a filing that is out by a factor of a hundred.

The declaration-kinds decision supplies the mechanism. A derived wire type is exactly a derived
field: computed by one named function from the casilla type and the declared mapping, with an
authored value refused. An attested exception is exactly an attesting field: evidence pointing at
an owned fact rather than a second copy of it.

## Considered options

**Leave the transitions undeclared and keep the screen.** The screen already reports all 33 pairs
and would keep doing so. It costs nothing and changes nothing: the twenty-four unscaled money fields stay
unscaled, and the next one is added without friction.

**Declare a permitted transition table and refuse anything outside it.** One owned table states
which casilla type may render as which wire type. Anything else refuses at load. Simple, and too
blunt for the evidence: it turns every currently undeclared transition into a build failure at
once, including ones that are probably correct and merely unrecorded, and it offers no way to
record a justified exception.

**Derive the wire type and scale from the casilla through a declared mapping, and require an
attested override for anything else.** The common transitions are derived, so the field stops
carrying a type at all and cannot disagree with its casilla. A transition outside the mapping is
permitted only with an attestation naming the official record design that requires it. Scale is
part of what is derived, so a money field cannot be emitted without one.

## Constraints

A derived wire type is not authored. Under the declaration-kinds contract the loader refuses an
authored type on a field whose transition the mapping covers, which removes the possibility of a
field and its casilla disagreeing.

A monetary field declares a scale or refuses. Absent scale is not a default of zero and not a
default of two; it is a missing declaration, and the no-silent-under-declaration rule requires it
to stay visible rather than be coerced.

An attested override names the official record design position that requires it. An override
without that citation is not an exception, it is an unexplained divergence with extra ceremony.

The mapping is owned in one place and derived nowhere else. Six sites currently declare how an
amount renders, and this record must reduce that number rather than add a seventh.

## Implementation

Author the mapping from the measured distribution rather than from first principles, so it begins
by describing what the corpus does. Money to decimal at two places, ratio to decimal, and the
identity transitions are the initial derived set, covering the large majority of fields.

Require scale on monetary fields next, which converts the twenty-four unscaled money fields into a
declaration each. They sit in four modelos, twenty-three of them the sign-prefixed alphanumeric form
whose wire type is already faithful to the design, and one an integer field that disagrees with the
five sibling amounts beside it. Each is answered by reading the official record design for that
position, and a wrong answer is a filing out by two orders of magnitude, so this is the part that
warrants unhurried review rather than a sweep. The single disagreeing field is the corpus's one
known filing-correctness defect and is the place to start.

Record the remaining minority transitions as attested overrides or correct them, deciding each
against its record design: text to date, text to integer, money to text, and the single money
field rendering at four decimal places.

Derive the type last, once the mapping and the overrides account for every transition the corpus
contains, so that turning on refusal is a no-op rather than a build break.

## Rationale

A blunt permitted-table was rejected because the evidence does not support treating the divergences
as one population. Two thirds of them are a correct cents encoding declared 2139 times; the ones
that matter are a small, concentrated group whose meaning is genuinely missing. A rule that cannot
tell those apart would either block the build or protect nothing.

Deriving rather than permitting is chosen because a permitted table still lets a field carry a type
that happens to be allowed but is not the casilla's. Derivation removes the second declaration
instead of policing it, which is the general shape the declaration-kinds decision establishes.

Scale is separated from type and given its own refusal because it is the only part of this axis
where silence produces a wrong number rather than an ugly one.

Authoring the mapping from measurement follows the same reasoning as the identifier decision: it
lets enforcement land while describing the present state, so protection does not wait on the
review of every exception.

## Consequences

An export field stops declaring a type the mapping covers, so a field and its casilla can no longer
disagree. The screen that measures divergence keeps running and should trend toward reporting only
attested overrides.

One hundred and thirty three monetary fields acquire a declared scale, and until they do they
refuse rather than emit an ambiguous magnitude. That is a visible, bounded piece of work with a
real filing consequence behind it.

The count of sites declaring how an amount renders falls, which is the point. Nothing in this record
adds a site.

The risk is that authoring the mapping from measurement blesses a transition that is in fact wrong.
The mitigation is that the initial mapping covers only the transitions whose correctness the
evidence establishes, and every other transition stays visible as an override requiring a citation
rather than being absorbed into the derived set.
