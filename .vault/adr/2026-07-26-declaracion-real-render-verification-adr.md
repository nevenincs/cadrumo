---
tags:
  - '#adr'
  - '#declaracion-real-render-verification'
date: '2026-07-26'
modified: '2026-07-26'
related:
  - "[[2026-07-25-declaracion-profile-printed-box-scope-adr]]"
  - "[[2026-07-26-declaracion-real-render-verification-plan]]"
  - '[[2026-07-26-declaracion-real-render-verification-specimen-less-static-route-audit-audit]]'
---

# `declaracion-real-render-verification` adr: `what grounds a declaracion_pdf profile's claims` | (**status:** `accepted`)

## Problem Statement

The printed-box decision established that an extraction profile is a contract about
a document, and that a profile targeting text the AEAT form does not print is a
false contract. It closed that for Modelo 303 and named the pitfall of treating the
result as Modelo 303 trivia.

Sweeping the remaining profiles proved the pitfall real on the first attempt, and
surfaced three questions the earlier record did not have to answer because it dealt
with one modelo and one defect. All three have now been decided under measurement
rather than argument, and this record fixes them so the next sweep does not
re-litigate them.

The questions: which registry field carries the printed box number; on what evidence
a coverage floor may be set; and what it means for a profile to be "verified" when
no real render of it exists. Twenty-two of twenty-nine profiles have no specimen at
all, so the third question governs most of the estate.

## Considerations

- Nothing in the repository read a real AEAT render until this campaign. The
  generated corpus scores full coverage at any threshold, so every floor rested on
  measurements no test repeated.
- `declaracion_pdf` profiles number 29 across 20 modelos. Attributed per revision
  rather than per modelo, only 7 have a real or facsimile specimen.
- The nine `real_corpus` specimens had every monetary amount overwritten by the
  sanitiser with a single constant declared in their own sidecars. They are layout
  and label evidence, not value evidence.
- A coverage floor derived from one specimen encodes that filer's shape, which is
  the error the printed-box decision avoided when it refused to assume the 1T shape.
- `artefact_kind` is a free-form `str` carrying two spellings for one concept, 18
  `declaration_pdf` against 11 `declaracion`, while production selects on `surface`.

## Considered options

**(A) Decide each question as it arises, per profile.** Rejected. The three questions
below were each answered at least twice during one sweep, in one case in opposite
directions, and the cost is not the deciding but the re-litigating.

**(B) Verify only the profiles that have specimens, and say nothing about the rest.**
Rejected, and it is the tempting option because it produces a clean green report. It
would leave 22 profiles carrying an implied pass they have not earned, which is the
condition that let six unprintable casillas survive in a profile for months.

**(C) Derive a coverage floor for every profile from whatever evidence exists, even
one specimen.** Rejected. A floor from one specimen encodes that filer's shape and
refuses valid filings that differ, which is a worse failure than the vacuous floor it
replaces because it harms a real taxpayer rather than merely hiding a defect.

**(D) Fix the printed-box-number hazard by correcting `number` on the affected
casillas.** Rejected on measurement: `number` feeds revision-identity validation,
completeness validation, record-design coverage and operator-facing display, and for
the informativas its positional-range values are correct for what the field means.
The reading is wrong, not the data.

**(E) Record the decisions once, apply them across the estate, and name what cannot
be decided.** Chosen. D1 through D4 below.

## Implementation

`_printed_box_numbers` reads `form_number` and treats the printed number as unknown
when it is absent, rather than falling through to `number`. The six casillas whose
printed number is not recorded have `form_number` populated from the bundled renders.
`number` is not touched on any casilla.

Coverage floors are set only where more than one specimen agrees. Modelo 111 keeps
its zero floor because four specimens put the worst case at 1 of 29; Modelo 390 keeps
its zero floor because it has one specimen and no floor can be grounded; Modelo 130
keeps its zero floor with neither justification, and is recorded as an evidence gap
rather than as a settled decision. In every case the exact extracted-set assertion is
the operative gate.

Every profile with a specimen is enrolled in the real-render gate, which runs the
production extraction path and asserts the profile accepts the render at its own
declared floor. Profiles without a specimen are enrolled in the evidence register
instead, naming the routes blocked and the specimen class that would unblock them.

Selection of a declaration-PDF profile matches `surface` and `accepted_artefact_kinds`
everywhere, including in tests.

The grounding for all of the above is the companion static route audit and the
printed-box scope audits recorded under this feature and its predecessor, which carry
the per-profile measurements and the method that produced each number.

## Decisions

**D1 — The printed box number is `form_number`. `number` is record-design metadata.**

`CasillaDefinition` states that `number` and `segmento` are reviewed AEAT
record-design metadata, and carries a separate `form_number` for the printed form.
A consumer needing the number a taxpayer sees on the page reads `form_number`;
`number` answers a different question and coincides with the printed number only
when the casilla id is itself numeric.

This resolves a live hazard. The blank-box guard keyed on `number`, so on casillas
with semantic ids it compared against a record-design string and could not fire —
letting a blank box return its own box number as a monetary value. Modelo 190's
`number` values are positional ranges of the fichero-BOE record and are correct as
such; the defect was never in that data.

**D2 — A coverage floor is set from evidence across specimens, never from one.**

Where specimens disagree, the floor is the highest value all of them satisfy. Where
only one specimen exists, no floor is set: a vacuous floor plus an exact
extracted-set assertion is preferred to a plausible floor that refuses valid
filings. The set assertion is the real gate in either case, because a ratio hides
substitution while a set does not.

Modelo 111 keeps its zero floor on this basis — four specimens, worst case 1 of 29,
every absence confirmed blank — and Modelo 390 keeps its zero floor for the opposite
reason, having only one specimen. The two are recorded together deliberately: the
same floor for opposite evidential reasons, which is the point.

**D3 — An untestable profile is an evidence gap, never a pass.**

A profile whose render-dependent routes cannot be decided for want of a specimen is
recorded as such, naming the routes blocked and the specimen class that would unblock
them. It is not reported as verified, and its floor is not treated as evidenced.

**D4 — Profile selection is by `surface`, never `artefact_kind`.**

Any consumer selecting a declaration-PDF profile matches `surface ==
"declaracion_pdf"` and the `accepted_artefact_kinds` list, as production does. A gate
authored against `artefact_kind` silently missed 18 of 29 profiles, which is how this
was found.

## Constraints

The engine's compute-from-primitives design remains out of scope and untouched, as
the printed-box decision left it.

Correcting `number` on any casilla is out of scope and forbidden under D1: the field
feeds revision-identity validation, completeness validation, record-design coverage
and operator-facing display. The remedy is always to populate or read `form_number`.

A profile whose targets include engine-computed casillas reopens the parser-versus-
engine impedance. Twenty of twenty-nine profiles do so, and nine of those belong to
modelos outside the enrolled reconcile set, where the arbitration has never been
made. It is deliberately **not** decided here: it needs its own evidence and its own
record. It is named so it is not mistaken for settled.

**Provisional, pending verification.** An earlier revision of this paragraph stated
that this is "not a live defect, because the path refuses loudly rather than
silently". That claim was carried from a worker report and adopted here without being
verified against the production path, which is the failure this feature has already
recorded twice. The counts are measured; the loudly-versus-silently behaviour is not,
and a silent discard would make this a live defect rather than a deferred one. A
follow-on record settles it; until then no reader should rest on it.

## Rationale

D1 was not a judgement call once the schema was read. The field's own documentation
answers it, and the precedent already existed in the tree on the modelo this work
started from. Recording it as a decision rather than a bug fix matters only because
the misreading was load-bearing on a guard, and a future author reaching for
`number` should find this record rather than repeat it.

D2 codifies the asymmetry the printed-box work discovered: an over-strict floor and a
vacuous floor fail in opposite directions, and only one of them fails safely. A
vacuous floor lets a defect hide, which is bad; an over-strict floor refuses a real
taxpayer's valid filing, which is worse. Where evidence is thin the decision therefore
leans to the vacuous floor and puts the enforcement in the set assertion.

D3 exists because the alternative is the failure this whole line of work exists to
correct. A profile reported green on a corpus authored to match it is not verified,
and calling the absence of contrary evidence a pass is how six casillas that AEAT
never prints survived in a profile for months.

## Consequences

Most of the estate remains unverified and now says so. Twenty-two profiles carry a
recorded evidence gap rather than an implied pass, which will read as a regression in
apparent coverage and is not one.

The R8 arbitration is left open with its scope measured, so a future record can decide
it against evidence instead of rediscovering it.

The value-level claim available from `real_corpus` specimens is weaker than it looks:
their amounts are a sanitiser constant, so they can prove a substitution occurred but
cannot corroborate an arithmetic relationship. Only the AEAT-published facsimiles
support a printed-arithmetic cross-check.

## Codification candidates

None promoted. Project rule codification is retired by operator directive; D1 through
D4 are recorded here as the governing decisions for `declaracion_pdf` profiles and
should be cited from this record rather than duplicated into a rule.
