---
tags:
  - '#adr'
  - '#declaracion-real-render-verification'
date: '2026-07-26'
modified: '2026-07-27'
related:
  - "[[2026-07-25-declaracion-profile-printed-box-scope-adr]]"
  - "[[2026-07-26-declaracion-real-render-verification-plan]]"
  - '[[2026-07-26-declaracion-real-render-verification-specimen-less-static-route-audit-audit]]'
  - '[[2026-07-26-declaracion-real-render-verification-r8-arbitration-enrollment-readiness-audit]]'
  - '[[2026-07-26-declaracion-real-render-verification-adversarial-verification-of-campaign-claims-audit]]'
  - '[[2026-07-26-declaracion-real-render-verification-campaign-close-honesty-review-audit]]'
  - '[[2026-07-27-declaracion-real-render-verification-modelo-100-manifest-reconciliation-gap-audit]]'
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
be decided.** Chosen. D1 through D5 below.

## Implementation

`_printed_box_numbers` reads `form_number` and treats the printed number as unknown
when it is absent, rather than falling through to `number`. The six casillas whose
printed number is not recorded have `form_number` populated from the bundled renders.
`number` is not touched on any casilla.

**That closes six of twenty-three known instances. Seventeen remain open and are a
live defect.** An earlier revision of this paragraph stopped at the sentence above,
which read as though the hazard were closed; a reader who trusted this record and
never opened an exec record would not have learned the rest existed. The remaining
seventeen are Modelo 180 ×3, Modelo 193 ×3 and Modelo 349 ×4 carrying fichero-BOE
positional ranges exactly as Modelo 190 did, plus seven `decl.ejercicio` targets
carrying `ejercicio` strings. Each can still return a box number as a monetary value
when its box is blank.

They were not swept with the six because the obvious remedy is worse than the defect:
failing closed on a bare integer would refuse real perceptor counts of 3, 2 and 5, an
explicit printed `0` in a rectificaciones box, and an ejercicio year of 2024 — trading
a fabricated value for a fabricated refusal. The remedy is to populate `form_number`
on nine further modelos' casillas, which is a separate pass and is tracked as one.

**Updated 2026-07-27: thirteen of the twenty-three are now armed, and the ten
remaining are two unlike problems rather than one backlog.** Seven more were grounded
without any specimen, because AEAT's own published instructions state printed box
numbers directly — Modelo 349's four and Modelo 180's three. Modelo 180's binding had
in fact been citing that very file as `required_text` since it was authored, so the
evidence sat in the registry the whole time without ever reaching the field the parser
reads. The first place to look for a printed box number is what the registry already
cites.

Of the ten left, Modelo 193's three are genuinely blocked: its bundled instructions
state no box numbers, it has no specimen, and its casilla structure being identical to
Modelo 180's makes inferring 01/02/03 tempting and inadmissible. The other seven are
`decl.ejercicio` targets and a milder, different defect — measured across the estate,
281 targets carry a `value_kind` and those seven disagree with their own casilla's
`data_type` **under a rule that distinguishes `year` from `integer`**. Those casillas
are `required`, so a blank one means a malformed document rather than a legitimate
blank, which makes the fabrication hazard there largely theoretical and the fix a
coherence correction.

**Corrected 2026-07-27, and the qualification above is the correction.** This
paragraph originally read "exactly those seven disagree", and elsewhere I called the
fix "the last incoherence in the estate". Both overstated. The seven surface only
because my probe treated `year` as non-money — a discrimination I made silently and
never stated, and `amount` over `integer` is a defensible reading. Swept by the naive
rule of `value_kind` against `data_type` and nothing else, the answer is **four**, and
they are *different* rows: `decl.event-kind`, `decl.tipo-ejercicio` twice, and
`decl.tipo-declaracion`, all `enum` over `text` or `integer`. Those four are
unadjudicated rather than fixed, since the schema enforces no distinction between
`enum` and `text`, which is exactly what makes their status arguable.

Two consequences worth carrying. "The last incoherence" was a completeness claim
smuggled in on the back of a count, and a completeness claim is strictly stronger and
strictly less checkable than the measurement it rode on — it tells the next reader to
stop looking. And the payoff I claimed, that a gate could now assert this invariant
without an exemption list, does not follow: a gate written against the naive rule
would be wrong in both directions at once, missing the seven and flagging four nobody
has ruled on. A derived assertion is only as good as the rule it derives from.

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

**D5 — Registry readiness is necessary but not sufficient to enrol a modelo in
casilla-level declaration reconcile. A real render is also required.**

The enrolment criterion recorded in the code is that a modelo's extraction profile
"line up with its registry casilla ids one-to-one". Measured, that criterion is
already satisfied by all nine unenrolled profiles: every target resolves to a real
casilla with no duplicates, and every engine-computed target is already declared in
its revision's computed set. On that criterion alone, all nine could be enrolled
today.

They may not be, because the criterion is insufficient and Modelo 390 is the proof.
It satisfied registry readiness completely, and its first real render scored 1 of 10
— nine printed boxes unread, because the filer had chosen English and the patterns
were Spanish. Registry readiness establishes that the *vocabulary* matches. It says
nothing about whether the profile can read the *document*, which is the only thing
reconcile actually depends on.

Enrolment therefore requires at least one real or facsimile render of that modelo,
verified through the real-render gate. All nine unenrolled profiles are specimen-less,
so none is enrollable today, and that is an evidence gap under D3 rather than a
backlog item.

The historical enrolment order is recorded as *not* being a discriminator: git
history shows the six enrolled modelos were added in three batches spanning 2 days
18 hours in development sequence, and Modelo 130 — enrolled first, with zero
specimens — is the counter-example that rules out any retrospective evidential
rationale. Five of the six happen to have specimens; that is a coincidence of order,
not a policy that was followed.

(An earlier revision of this paragraph said "five days". The measured span between
the first and last enrolment commits is 2 days 18 hours 51 minutes. The error did not
touch the ordering argument, which rests on M130 rather than on the span, but a wrong
number sitting beside a sound conclusion lends it unearned precision — and this one
was caught only by an adversarial pass that re-derived it from git rather than
re-reading the claim.)

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

**Resolved, and it is not a live defect.** This paragraph previously asserted that
the path "refuses loudly rather than silently" on a worker report adopted without
checking, and was marked provisional for that reason. It has since been verified by
reading the production path directly: the enrolment guard refuses before
`parse_declaracion` is called and before any file is opened, for all nine profiles,
and the bytes-based reconcile refuses the declaration source kind unconditionally for
every modelo. The refusal is real and it precedes parsing entirely.

The claim is therefore now confirmed rather than assumed. It is recorded this way,
rather than silently corrected, because the first version was right by luck: it was
adopted from a report and cited back as corroboration by that same report, and a
verification that had gone the other way would have made this a live defect across
nine profiles.

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

**The sidecar manifests under-describe what the sanitiser actually wrote, and this is
recorded here because it existed only as a phrase in conversation until now.** The
three Modelo 100 specimens each declare a single replacement constant, `1.000,00`. The
sanitiser is length-preserving, so it in fact wrote two forms: `1.000,00` into
eight-character fields and `1.001.000,00` into twelve-character ones, in a ratio of
roughly 55 to 17 per specimen. Both are legitimate sanitiser output; neither is
taxpayer data. But the manifest names only the first.

The consequence is specific and easy to get wrong. A test that grounds a value claim
on "the extracted amount equals the manifest's declared constant" is checking against
an incomplete description of the document, and will report a correct extraction as a
failure. This campaign's own real-render gate has exactly that check, which is one
reason Modelo 100 cannot be policed by it even after the parser defect is fixed. It
also means an earlier gating condition I imposed — that a fix was incomplete unless it
yielded the declared constant — was unsatisfiable by construction.

This is a fixture-metadata defect, not a parser defect and not a redaction leak: 54
unrelated boxes carrying an identical value cannot be real taxpayer data. It is
recorded rather than fixed, because correcting the manifests is a corpus change
outside this campaign's scope.

**Resolved 2026-07-27, and the manifests turn out not to be wrong.** The related
puzzle — manifests declaring 124, 133 and 137 amount replacements while only 70, 74
and 78 amounts render — is fully explained with no remainder, and the explanation is
neither of the two mechanisms first suspected.

`"1.001.000,00"[4:12]` is exactly `"1.000,00"`. The long form literally contains the
short form as a substring at a fixed offset. Verified at the raw content-stream byte
level with `pikepdf`, bypassing the text layer entirely: every long-form occurrence has
the short form nested at that offset, 54 of 54, 59 of 59 and 59 of 59 across the three
specimens with zero exceptions. The arithmetic closes exactly — 124−70, 133−74 and
137−78 are 54, 59 and 59, matching the independently measured long-form counts.

So whatever produces `replacements_applied` counts two events for every long-form box:
the twelve-character run, and again the eight-character substring inside it. The
manifests **over-count distinct events; they do not fabricate or misdescribe**. Every
declared row is a genuine byte-level match that existed and was redacted.

Both alternatives were ruled out by direct inspection rather than by elimination: there
is no AcroForm carrying separate invisible field values, no `OCProperties`,
`StructTreeRoot` or `MarkInfo` indicating tagged-PDF duplication, and none of the
double-strike character rendering found on another modelo earlier in this campaign.

The practical consequence is that declaring both constants is sufficient. The
row-count over-counting needs no fix of its own, because nothing found in this campaign
reads that count for anything beyond inspection.

## Codification candidates

None promoted. Project rule codification is retired by operator directive; D1 through
D4 are recorded here as the governing decisions for `declaracion_pdf` profiles and
should be cited from this record rather than duplicated into a rule.
