---
tags:
  - '#adr'
  - '#registry-edition-authoring'
date: '2026-09-09'
modified: '2026-09-09'
body_schema: 'body-v2'
body_hash: 'sha256:246353a65b7a65fc284eaaffa1858805ef7c3562cd461a649922c845134c22fd'
related:
  - "[[2026-09-09-registry-edition-authoring-edition-restatement-measurement-research]]"
  - "[[2026-09-09-registry-edition-authoring-registry-mechanics-audit-research]]"
  - "[[2026-09-09-registry-edition-authoring-code-shape-and-blast-radius-reference]]"
---

# `registry-edition-authoring` adr: `edition-relative casilla authoring` | (**status:** `proposed`)

## Problem Statement

Two thirds of the registry's casilla rows belong to a successor edition rather than a first
edition, and almost all of them are copies of the row before. They cannot be recognised as copies
because each row also restates the edition it sits in, so every one is authored and maintained by
hand. The measurement is in
`2026-09-09-registry-edition-authoring-edition-restatement-measurement-research`.

A decision is needed now because two campaigns already in flight rewrite this surface — per-modelo
export authoring and declaration hardening — and both will re-author successor rows under the
current shape unless the authoring model changes first. Every edition migrated under the present
model is work that must be redone.

## Considerations

- Identity by containment is sound and is not in question; the mechanism and its four failure
  points are recorded in `2026-09-09-registry-edition-authoring-registry-mechanics-audit-research`.
- Restatement removal alone accounts for the larger half of the benefit, independent of
  inheritance.
- Lineage is the precondition, not the consequence: it is declared on a fifth of rows and absent
  from most multi-edition modelos.
- A base, override and exact model already ships for locale text on this same lineage field, with
  an explicit barrier for a repurposed concept.
- Casilla identity is edition-local and does not address the wire; roughly half of resolved wire
  slots carry no casilla at all.
- Every consumer reads the registry through the validated authority, and the caches key on files
  rather than rows — see `2026-09-09-registry-edition-authoring-code-shape-and-blast-radius-reference`.
- The word *stamp* is spent twice over: on the runtime-persisted snapshot reference carried by
  calculation records, and nearer still on the governance stamp marking `engineered_by`,
  `review_status`, `reviewed_by` and `reviewed_at` on the edition itself.

## Considered options

**Leave the model alone.** Declarations are correct and the only cost is human effort. Rejected:
the effort recurs annually per modelo, and the wall of restatement hides the real changes inside
it.

**Move the registry to a database.** Rejected: it addresses storage, and storage is not the
problem. A copy would still restate its edition and still not be recognisable as a copy.

**Lift restatement only, without inheritance.** Delivers most of the measured benefit and is the
simpler change. Kept — but as the first migration step rather than the destination, because
without inheritance the identical rows must still be authored; they merely become visibly
identical.

**Field-level patches rather than whole changed rows.** Compresses the single-field differences
further. Rejected as a false economy: a declaration file would no longer be readable without its
ancestors.

**A temporal lineage field on the casilla for legal grounding.** Rejected on evidence: the legal
catalogue already carries dated rows per article and the references already carry their own
effective windows, so a casilla-side field would create two temporal truths that can disagree.

**Inheritance keyed on lineage, with restatement lifted to the edition.** Chosen.

## Constraints

- **Lineage must be stated first.** Inheritance cannot key on a field absent from most
  multi-edition modelos. Seeding it is a blocking prerequisite, and modelo 309 — which renumbers
  boxes while keeping identifiers stable — may require adjudication rather than mechanical
  seeding.
- **The harness must be converted first.** Roughly thirty assertions across twelve test files
  assert that the live corpus still contains findings. Converting them to detector-teeth form is
  a precondition of this decision's own gates, not a follow-up.
- **Two dependencies are proposed, not accepted.** The declaration-kinds ruling and the enum
  canonicalisation ruling are both unaccepted. If declaration-kinds is not accepted first, this
  decision declares `export_refs` a derived field on its own authority and that becomes its
  fallback position; any enumeration introduced here must not contradict enum canonicalisation.
- **Development tooling reads raw files directly** and is outside the consumer guarantee. It must
  be updated in the same change.
- **Cache fingerprints must key on the physical files read**, never on expanded output, or
  self-invalidation breaks.

## Implementation

### What a successor edition declares

**Scope: casilla declarations only.** An edition has twenty-one declaration families plus its
manifest. Lineage exists on casillas and nowhere else, and the measurement backing this decision
counted casilla rows and nothing else. Formulas, bindings, export layouts, parameters and the
remaining families continue to be declared in full by every edition. They may be worth the same
treatment later; this decision does not make that claim and no measurement here supports it.

**The completeness manifest is excluded explicitly, not by implication.** Its rows are
casilla-shaped and there are roughly 4,821 of them, so the family boundary alone does not settle
them — and silence would settle them wrongly. The manifest is a revision section merged by the
same directory-fragment machinery as the casillas, so a materialiser written against "merge the
raw revision mapping" inherits it by default. The exclusion must therefore be an explicit entry
with a stated reason, never an omission.

Three reasons, of which the third is decisive. A manifest row is a *derived assertion about its
own edition's formula closure*, not a declaration carrying identity — inheriting one would carry
the predecessor's claim about the predecessor's formulas into the successor, false in exactly the
case where a successor exists. Its header cites the official design it was derived from, and
those citations genuinely differ between editions in most successor pairs. And **the presence of
a manifest is itself a graded capability claim**: a missing manifest at calculation or filing
grade is reported as under-supported, and a present one below those grades as under-declared. So
silent inheritance would let a successor inherit an attestation of support it never earned — the
same failure this decision already refuses for a successor that withholds by design, arriving
through a different door, in a family where the minimality screen cannot see it.

What makes the exclusion safe rather than merely convenient is that nothing consults a
predecessor's manifest today: omission is judged entirely against the successor's own closure, and
there is no cross-edition manifest logic anywhere in the product tree.

There is also a mechanical trap behind the same door. Within the manifest section the casilla
collection is an append array, so a naive merge concatenates inherited and stated rows, and the
manifest's own duplicate-identifier validator then refuses the load. That failure is loud, which
is good, but it names a duplicate identifier and says nothing about inheritance — a misattributed
error that would cost real time to diagnose.

Within the casilla family, a successor edition declares rows **new** in this edition and rows that
**differ** from the inherited one, stated in full rather than patched. Anything unmentioned is
inherited unchanged.

**Precedence is by lineage.** A stated row supersedes the inherited row carrying the same
lineage, in the inherited row's position. A stated row whose identifier collides with an
inherited row of *different* lineage is refused, naming both lineages: that is an undeclared
repurpose, and it must be declared rather than inferred. This has to be stated because the loader
cannot currently tell the two apart — casilla sections merge by bare concatenation and the
duplicate-identifier guard reaches only nested arrays, never top-level rows.

A **declared** repurpose behaves differently, and the shipped code already decides it: a
repurposed casilla keeps its lineage and supersedes, with the evolution record waiving the field
comparison. Only the undeclared case is a collision.

**Removal reuses the shipped evolution vocabulary, unchanged.** A row withdrawn in a successor is
declared through the existing casilla evolution retirement, whose `(lineage, to_revision)` pair is
exactly the key and scope a materialiser needs, and which is already required to be authored under
the edition doing the omitting. The existing validators are already self-consistent with this in
both directions: one accepts a retired lineage absent from the successor, and another already
*demands* a retirement whenever a strict chain disappears between adjacent editions. Nothing new
is needed, and no list of removed identifiers exists anywhere in this design. A first edition
cannot express a removal and does not need to, because it inherits nothing.

### One format, declared explicitly

A full-copy edition is a valid edition: every row is stated and no predecessor is declared. An
edition becomes delta-authored by declaring a `predecessor` in its manifest. **The loader never
infers this.** Migration changes what is written, not what is accepted.

**The predecessor graph is a forest with exactly one root per modelo.** Every edition declares a
predecessor except one; the graph must be a single tree rooted at that one, with no cycle, no
unknown or self target, and every edition reachable. The unique root *is* the positive
identification of a first edition. A successor that omits its predecessor becomes a **second
root**, and two roots is a refusal naming both — which is what closes the silent case, because a
first edition and a delta with a forgotten key are otherwise shape-identical.

This rule uses no temporal reasoning, which is why it handles the modelo whose three editions are
parallel scheme variants sharing one validity date: all three declare the same predecessor, a
legal fan-out that any ordering-based rule would have wrongly chained. Where a pair does not
overlap, the declared predecessor must agree with the date ordering; overlapping editions are
exempt, and that exemption is exactly the variant case.

It also makes the minimality screen non-vacuous: with one root per modelo the denominator is every
non-root edition, so a single-edition modelo reports not-applicable rather than clean.

**A predecessor may not be declared where the successor withholds by design.** An edition
declaring a lower authority grade than its predecessor, or deliberately declaring only a header
while refusing to state figures it cannot ground, must remain full-copy. Inheriting into such an
edition would silently materialise rows the author explicitly withheld, converting an honest
deferral into a complete-looking edition. This is real and present: one modelo declares nearly two
thousand rows in one edition and two in the next, its own declaration recording that the sparse
edition refuses to fabricate what it cannot ground. The minimality screen is blind to it — two
stated rows match nothing inherited, so it reports clean — so this is a load-time refusal keyed on
the declared grades, not a screen finding.

**A printed box number is not unique within a modelo.** On the largest modelo in the corpus the
same printed number appears on three different páginas of the same edition, carrying three
different concepts. Box number is therefore an identity key only when it is qualified by the page
it is printed on, and a number-keyed match across editions sends a row onto a different page's
concept. The ambiguity is not marginal: 812 of that modelo's
3,417 printed numbers appear on more than one sheet, so nearly a quarter of them mean nothing
without their page. Nor is the consequence hypothetical. Of the 137 casilla-bound export fields in
its current edition, 41 address a casilla on their own anchor sheet and 96 address the right number
on the wrong sheet — a página-10 equity slot bound to a liquidación deduction box, whose number the
design does print on that equity slot. There is no third category: not one legitimate cross-sheet
binding exists in the revision, which is what makes the whole cross-sheet population the defect
rather than a mixed set needing triage. The same shape the span rule
guards against is already committed here on the wire, so the qualification is a correction to
existing data and not only a rule for new work.

**A row with no predecessor must say which kind of none it is.** Absent-in-the-predecessor and
absent-from-the-form are different facts and the lineage field must not spell them the same way.
One modelo makes the difference the whole story: of 383 rows that chain to nothing, only 110 are
boxes AEAT actually added, and 248 were printed on the official form all along while the corpus's
own earlier edition — a thin extraction epoch declaring ten rows at a lower authority grade — is
simply silent about them. Writing those 248 as "new" would be true of the corpus and false of the
law, and it would convert a known authoring gap into a fabricated statement about the form. So the
lineage field distinguishes *no predecessor existed* from *the predecessor edition does not state
one*, and the second carries the evidence for why. This constrains the field's design before it is
built, not after.

### Inheritance and its barrier

Inheritance matches on casilla lineage, reusing the **key and the barrier** of the shipped locale
cascade — not its mechanism, which is a field-level variant model this decision rejects.

**Declared lineage adds no reach.** Of 19,553 successor rows it chains 4,796, and every one of
those also chains by another route: rows chainable *only* by declared lineage number zero. It is a
labelling backlog, not a capability.

**The real constraint is 2,509 unchainable rows — 12.8%.** Chaining reaches 87.2% by three keys:
declared lineage, the wire record with its byte span and official label, and the bare identifier
under a refusal predicate. One modelo is excluded from chaining entirely, its three editions being
parallel schemes sharing one validity date rather than a sequence.

**One modelo is the phase.** It carries 993 of the 2,509 unchainable rows — 39.6% — plus 94% of
all refused chains, and it has no oracle of any kind: no export surface, no wire record, no byte
spans, no dedicated printed-number field, and a semantic role that labels a grid column rather
than a box. **Nothing about it may be seeded mechanically.** Its 250 refusals are also not
renamings: 201 of them are disjoint role changes, which is real box reassignment under stable
identifiers, at scale.

**The wire key corroborates; it does not rescue.** Its entire net contribution is 486 rows in a
single modelo whose identifiers are derived from AEAT label text. Elsewhere it fires only on rows
the bare identifier already reached, naming the same predecessor every time. A sweep of all
fifty-eight modelos found only that one carrying the label-derived-identifier problem, so the
earlier figures were inflated for one modelo rather than corpus-wide. It also has a stated limit:
where a declared width contradicts a matching label, the label must not decide — the two rows in
the corpus with that shape are precisely the ones a label-tier match gets wrong.

**A byte span alone must never chain.** On one modelo the successor edition keeps the record, the
campo ordinal, the offset and the width of its predecessor and puts a different concept in the
slot: box 17 stops being the *ajuste de cuota íntegra* and becomes the *cuota íntegra atribuible a
la Administración del Estado*, while the displaced concepts reappear intact six boxes lower
because six new boxes were inserted ahead of them. A span-keyed match certifies that reassignment
backwards and manufactures exactly the false chain this decision exists to prevent. The span is
admissible only as corroboration behind a label that already agrees. A second modelo confirms it from the
other direction: across one boundary 189 of 296 casillas that did not change at all moved their
span, and every one of the 58 chains a span key offered there is refuted by the declared semantic
role.

**The official record design is a fourth oracle, and the strongest one where it exists.** Editions
name sha-pinned AEAT record designs in their source refs; those designs are bundled and extract to
text that diffs cleanly. Two boundaries were settled that way and by nothing else: an edition's
entire delta proved to be reserved cells becoming a new territory's fields, so every one of its
unchained rows is genuinely new and needs no adjudication at all. Where a modelo declares no
formulas of its own, the design carries the operand renumbering that identifies a moved box.
Try it first on any modelo whose designs are bundled. It stops being self-certifying where the
design cannot speak: which of several repeating blocks a row belongs to is positional convention,
not a record fact, and needs the printed form.

**The dangerous population is 273 contradicted chains**, almost all a changed semantic role. These
fail silently where an unchainable row fails loudly, so seeding must refuse rather than fall
through to a weaker signal.

**Box number is taken from the dedicated printed-number field and from nothing else.** Falling
back to the reviewed record-design metadata field when it happens to hold a plain integer
reintroduces the original error, because a one-byte wire campo declares exactly that. The field is
heterogeneous by design — one modelo carries positional byte ranges there — and no production
consumer treats it as identity.

**A modelo-level tripwire refuses all bare chains where a redesign reassigned an identifier
space**: row count changed, every prior identifier reused, section vocabularies largely disjoint.
It must not fire merely because a small edition precedes a large one, which is ordinary growth.

Semantic role cannot serve as a universal fallback. On the largest modelos it labels a
repeating-grid column, with up to 38 rows sharing one, so it yields no signal exactly where the
gap is largest.

Seeded lineage carries an origin marker distinguishing it from grounded lineage, and the
continuity gate must read that marker rather than accepting a seeded chain as evidence.

### The three restatement families are treated differently

`source_refs`, nested constraint source references, and orden references are declared once on the
edition and inherited by rows that state none.

`export_refs` is **derived**, not inherited. It is per-row and per-edition — the slot identifier
carries the edition and the ordinal moves on insertion — so an inherited row inheriting its
predecessor's value would inherit the wrong slot. The layout owns the edge through its own casilla
back-pointer, and the loader computes the field and refuses an authored value.

`formula` and `binding` references on an inherited row resolve to the successor edition's
declaration of the same formula or binding lineage. A reference that does not resolve is a
validation failure, not an inherited pointer. Those identifiers must therefore stop embedding an
edition key; that rename is authorised here **for those two families only**.

### Where expansion happens

Inside typed construction, immediately after the raw editions resolve and **before per-edition
localization enrolment**. That position is not free and the consequence must be stated rather than
assumed.

Locale keys are scoped per edition, derived from the modelo, the edition and the casilla. So an
inherited row enrolled before localization takes the **successor's** key — which is the shape
restatement produces today, and therefore the right shape. But the label catalogue is authored per
edition too, and an inherited row has no successor-keyed entry in it, so the lookup raises rather
than falling back.

**Therefore the label catalogue must inherit alongside the declarations.** That is not new
machinery: the shipped locale cascade already runs base, override and exact resolution on this
same lineage field, which is why this decision reuses that key. What this decision adds is the
requirement that the two inherit together — a materialised edition whose rows inherit while its
labels do not is not a complete edition, it is one that raises on first read.

Materialising *after* enrolment is the alternative and it is worse: the inherited row would keep
its predecessor's key, resolving correctly but leaving a successor edition carrying locale keys
that name another edition.

Two live consumers detect a wrong choice immediately, and one of them loudly: a historical-epoch
test sweeps every edition asserting each casilla yields a non-empty label, and a development
manager reads labels in a path whose failure mode is a silent missing-title ambiguity rather than
an error. The loud one is the gate; the quiet one is the reason to get it right.

Ordering of rows is fully determined today by sorted fragment paths and an ordered row tuple, so
the materialiser must reproduce it: inherited rows first in the predecessor's materialised order, a
superseding row taking the inherited row's position, and genuinely new rows appended in stated
order. Superseders are position-pinned by lineage, so a successor renaming its fragment files
cannot move them.

This is not a compatibility layer because there is one format, declared explicitly per edition,
and one reader. The loader does not accept a retired shape; the shape before this decision is the
degenerate case of the shape after it.

**Every caller of the shared loader was audited before this position was fixed.** Thirty-six call
it directly. Twenty-seven are indifferent to the change, eight are correct with inherited rows,
and the set requiring a distinct declared-only accessor is **empty** — no caller reasons about what
an edition states in a way a materialised view corrupts. The one caller keyed to declared rows is a
test population floor, which is already scheduled for conversion to detector-teeth form on other
grounds and needs no accessor.

### What this changes for the validators

No validator's code changes, but two validators' **inputs** do, and both move toward fewer
findings. A contiguity check reads the edition's rows, so an inherited row fills a gap that was
previously visible as absence. A retirement check computes a difference between adjacent editions'
rows, so it stops demanding a retirement for a lineage the successor merely failed to restate.

That is the design's point rather than a side effect: **removal moves from derived to declared.**
An absence used to mean a removal; now a removal is an authored evolution record. Claiming no
validator is affected would be false.

Inheritance can only remove absences, never create one, so the present-absent-present shape those
checks refuse can now arise only from an authored retirement followed by re-introduction — an
explicit act rather than an authoring slip.

The compensating control that survives intact is the record-design and export-completeness
comparison, which measures the materialised edition against the official published form rather
than against an absence, and therefore still refuses a row the form does not carry.

The residual risk is bounded and must be stated: a **newly authored** successor has no
pre-migration baseline to round-trip against, so it can inherit a row its author meant to drop and
no validator will say so. The migration itself is covered, because round-trip equality fails if a
previously-absent row appears. The forest rule must land in the same change, or silent inheritance
compounds with a silently missing predecessor.

### Proof obligations

No modelo is migrated without: typed round-trip equality between its materialised edition and its
pre-migration materialisation, compared element-wise over the whole edition rather than by a
set or an identifier-keyed map, with a separate assertion on row order so an ordering failure
reports distinctly from a content failure; export bytes unchanged **where the modelo has an export
surface at all**; a cache-teeth test; and the minimality screen reporting clean for that modelo.

Eleven modelos have no export surface on any edition and several change lane mid-chain, so the
byte proof is not universal and a step must not report it as satisfied where there are no bytes to
compare.

**Every gate this decision touches must state where it stops.** The failures found while grounding
this decision were not wrong answers; they were correct answers whose scope nobody had written
down. Five instances share the shape: a chaining tool that answered "a difference exists" and was
read as "the box changed"; a similarity figure measured over shared identifiers and read as a
statement about a modelo; a cardinality gate run against a deliberately partial registry with no
way to know it was partial; a review stamp still literally true over a scope that had shrunk
underneath it; and a coverage gate keyed on the presence of a generation artefact, which reads an
edition it cannot see as passing rather than as unexamined. The last is the one this decision
creates more of: a migrated edition is manifest-less by construction, so a gate keyed on artefact
presence gets less capable the more of this work succeeds, and its greenness tracks migration
progress rather than correctness. A gate must therefore distinguish UNCHECKED from ABSENT, and take
its eligibility from what an edition declares about itself rather than from what artefact happens
to sit beside it.

## Naming

The migration renames data on disk, so the terms are settled here rather than during it.
`ModeloEdition` is one published shape of a form; `ModeloEditionKey` is the directory label naming
it; `CasillaLineageId` chains a casilla across editions, keeping `continuidad_id` as the field
name; `StatementOrigin` distinguishes a row stated here from one inherited; `EditionRestatement`
names a token in a row repeating its own edition. `Modelo` means the physical form AEAT publishes
and nothing else; derived names take the form `Modelo<Thing>` and `Casilla<Thing>`.

`Casilla` means a numbered box on the published form. It does **not** mean a printed cell, and the
two must not be treated as interchangeable: at least one official design declares a single
four-byte cell whose own content text divides it at stated sub-offsets into a two-digit province
code and a two-letter country code, emitted as two wire fields of which one is a casilla and one
is a binding. So a printed cell may carry more than one addressable field, and a casilla may
address part of a cell rather than all of it. This is recorded because the looser reading is a
near-truth that would harden into a wrong assumption.

Two renames are explicitly **not** authorised here: consolidating the modelo number type, and
renaming the export family to wire. Both are code-cheap and data-expensive, and must ride on a
change already rewriting those files.

One boundary property belongs here because it outlives this campaign and will otherwise be
rediscovered expensively. **The export schema is closed by construction and the registry schema
is not.** Adding a field to the export field model invalidates every shipped generation manifest,
through both a schema version and a canonical-byte comparison performed at load, so it is a
coordinated migration rather than an edit. Adding a field on the registry side costs a cache
rebuild and nothing more. This decision's two new keys sit on the registry side, which is why they
are cheap; a future decision carrying a field across that boundary should not assume the same.

## Rationale

The measurement is decisive on its own: the gap between rows identical as authored and rows
identical once restatement is removed is the whole argument, and it is two orders of magnitude.
No alternative closes that gap without either lifting restatement or accepting that the copies
stay hand-authored.

**This decision does not reverse the temporal-coverage design-authority refusal.** That refusal
declined a general successor-inheritance rule for *export-layout source authority*: a later AEAT
document may not be inherited backward as evidence for an earlier interval, and a derived layout
must pin both inputs by hash. It remains in force and this decision must not weaken it.
Casilla-row inheritance runs the other way — a successor inherits its predecessor's declaration —
and inherits no source evidence, because source references are declared per edition. The refusal
pin that asserts it in a live test is untouched. If any reader finds the two in conflict, this
decision yields.

Choosing whole changed rows over field patches, and the loader over any consumer-side shim, both
follow from one preference: the change must be invisible downstream and legible upstream. A
reader of one declaration file should still see a complete row.

## Consequences

What a person maintains falls by roughly seven tenths. A diff between editions begins to show only
what changed — and, once a legal-reference period-correctness gate lands, only what the law
changed. Until then the diff shows law plus the residual authoring drift, and the drift will look
like law.

Two screens that currently infer cross-edition continuity become near-automatic; six need
restating against inherited state.

Against that: reading a successor edition's files no longer shows the complete edition, so the
materialised view becomes the thing to inspect and tooling must make that easy or the tree gets
harder to work with rather than easier. Every modelo must be migrated and the work genuinely
differs per modelo — of modelo 100's citation changes, 76% are genuine temporal grounding rather
than restatement, so its lower similarity is real. Development tooling that reads raw files must
move in the same change.

This decision reduces what is authored, not what is proven. Completeness coverage is unchanged —
the modelo with the largest declared surface sits at under two percent manifest coverage before
and after — and this must not be described as a correctness improvement.
