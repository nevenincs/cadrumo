---
tags:
  - '#adr'
  - '#minimo-descendientes-eligibility'
date: '2026-08-04'
modified: '2026-08-04'
body_schema: 'body-v1'
body_hash: 'sha256:62e442d3d2030e5bfcc6546898d6a4d229695c2055c727392bbdb2ea7022f66d'
related:
  - "[[2026-08-04-minimo-descendientes-eligibility-audit]]"
  - "[[2026-08-04-decimal-notation-under-declaration-research]]"
---

# `minimo-descendientes-eligibility` adr: `Add the relationship-kind and entry-event axes the descendant model lacks, defer month-level guarderia spend` | (**status:** `accepted`)

## Problem Statement

Four Art. 58/61 conditions remain unmodelled after the eligibility campaign. Every one
under-grants, so each harms the taxpayer rather than the revenue, and they share a single
root: the descendant model lacks axes the law distinguishes. They were repeatedly recorded as
follow-up work and repeatedly failed to become Steps, because a Step cannot be written against
a design that has not been decided. This record makes the decisions so the work can be planned.

The measurements, magnitudes and blocking reasons are in
`2026-08-04-minimo-descendientes-eligibility-audit`; the write-boundary residual is in
`2026-08-04-decimal-notation-under-declaration-research`.

## Considerations

- The descendant record carries one date field whose meaning is adoption. Every unmodelled
  condition needs either a distinction that field cannot express or a granularity the spend
  figure does not have.
- Art. 58.1 assimilates tutela and acogimiento to descendants; Art. 58.2 covers adopcion and
  acogimiento and omits tutela. The two limbs draw different lines, so one relationship field
  cannot be inferred from the other.
- Live cross-check confirmed both deferred amounts against the authority: 2.800 euros for the
  under-three increment, 2.400 euros for the mid-year death case.
- The same check surfaced three rules no earlier pass had found, each an implementation trap:
  the increment survives the descendant's death, the three-year window is a cap rather than a
  restart, and the death amount overrides autonomic divergence.
- Every condition errs toward under-claiming today, which is the safe direction. That is why
  they are deferrable at all, and it is not a reason to leave them unrecorded.

## Considered options

**Decide the axes now and plan the work against them.** Chosen. The blocking factor was never
effort; it was that nobody had ruled on the model. Recording the rulings converts four
unplannable items into planned work.

**Open a plan and discover the design while executing.** Rejected. It was attempted twice and
failed twice, and the rows it produced could not carry verification gates because the behaviour
they would verify was undecided.

**File the items in the consolidated open-work plan.** Rejected on that plan's own governing
constraint: it admits no coding work by construction, and coupling gated coding rows to a
deliberately drivable non-coding flow is the failure it exists to prevent.

**Model relationship kind as a boolean adoption flag.** Rejected: it cannot express tutela,
which Art. 58.1 assimilates and Art. 58.2 excludes, so it reproduces the current gap under a
new name.

## Constraints

- The entry-event window is a CAP, not a restart. The authority's own example is an adoption
  following a fostering, where the increment continues for the remaining periods up to a
  maximum of three. An implementation anchoring on whichever event it happens to hold would
  grant up to six years where the law allows three, which under-declares.
- The under-three increment SURVIVES the descendant's death, so the flat death figure and the
  supplement compose rather than being alternatives.
- The death amount OVERRIDES autonomic divergence. This engine already wires a divergent
  autonomic tranche table for one comunidad, so a death-case implementation must override that
  table rather than feed through it.
- Both figures are live-confirmed and may be authored as registry parameters without a further
  corpus check.

## Implementation

**Decision 1 - the descendant axis gains a relationship kind.** A closed set distinguishing
adopcion, acogimiento preadoptivo o permanente, and tutela. Art. 58.1 assimilates tutela and
acogimiento while Art. 58.2 omits tutela, so the two limbs need the distinction drawn
explicitly rather than inferred. Without it the entitled acogimiento carer is under-granted,
and the tutela case is reachable only through the one date field that exists, which means
through a field whose name asserts something else. This is a precondition for two of the fixes
below and lands first.

**Decision 2 - the entry date is a general entry-event date, not an adoption date.** The
cap-not-restart rule forces this, and the reasoning is stated so the cheaper design is visibly
excluded rather than merely unchosen: both events can occur for the same descendant and the
three-year window spans them, so a single field whose meaning depends on relationship kind
cannot express the rule. A fostered-then-adopted child does not begin a fresh window. Read as
an adoption date, the second event restarts the count and grants six years where the law allows
three.

**Decision 3 - month-level guarderia spend is DEFERRED, and this is a decision rather than an
omission.** It gates the largest under-grant found in the campaign: the Art. 81.2 extension
into the year the child turns three, which reaches every family paying childcare through that
birthday and reduces cuota directly. The window is sub-annual while the stored figure is
annual, so granting the full year would swap an under-grant for an over-grant, and refusing to
grant is the safe direction while the data is absent. It is deferred because it is a larger
model change than the other two combined, and it is recorded here so the gap reads as weighed
rather than missed.

**Decision 4 - the dependencia assimilation is RETIRED, with its reasoning preserved.** The
statute carves out judicial anualidades, which removes the one common household shape, and no
reachable case could be constructed. A retired item carrying its argument is worth more than a
silently dropped one, because the next reader can check the argument rather than rediscover the
question.

Deliberately out of scope: the five untested collector wirings and the fragment-capture rate
defect. Both are real and both are recorded in the audit and the research, but they share no
root with these axes and no decision with each other. Folding them in would make this a bucket
rather than a decision record.

## Rationale

The four conditions look like four items and are one. Each is blocked by the same absence: a
descendant model carrying less distinction than the law it serves. Deciding the axes once
unblocks the set, whereas deciding them per condition would produce a field shaped by whichever
condition was implemented first - which is how the current adoption-only date field came to
exist.

The order follows the dependency rather than the magnitude. Relationship kind is the
precondition, so it lands first even though the guarderia extension is the largest under-grant.
Sequencing by size would land the biggest fix against a model that cannot express it.

Deferring decision 3 while recording it is the honest form of the judgement the campaign made
everywhere else: an acknowledged gap with its blocking reason named is trackable, while the
same gap unrecorded is indistinguishable from an oversight. The audit's own principle applies
to its residuals, not only to its findings.

## Consequences

Two of the four conditions become plannable immediately once the axes land. The third stays
blocked on a data-model decision that is now named rather than implicit, so a future reader
knows what unblocks it. The fourth is closed.

The descendant schema gains two axes, which is a persisted-shape change and therefore needs a
roundtrip test and an anti-tautology proof at the boundary, per the standing persistence
discipline.

A note on records that describe themselves: the consolidated open-work plan's Description
hard-codes its own phase and row counts, so any structural addition makes it inaccurate about
itself. That is the same class as a gate whose prose argued against its own scope, found and
fixed in the decimal campaign - documentation a reader will act on, describing a mechanism that
has moved. Worth correcting in whichever change next touches that plan.


## Amendment: a design review corrected all four decisions, and refuted one

An independent design advisory was commissioned after this record was written. It read the
sources, swept semantically for canonical homes, and checked the law against the live
authority. **All four decisions needed correction and one was wrong outright.** The original
decisions and their reasoning are preserved above; this section records what refuted them,
because a reader who sees only the corrected shapes will re-derive the originals from the
same reasoning that produced them.

### The retirement in decision four is WRONG. Reopened as deferred.

The dependencia assimilation was retired on the reasoning that the statutory carve-out for
judicial anualidades removes the one common household shape, and that no reachable case
could be constructed. **Both halves are refuted against the live authority**, and the
coordinator confirmed the quotations independently before amending.

The carve-out is narrower than the retirement assumed. The authority states the assimilation
applies *"salvo que se **satisfagan** anualidades por alimentos"* — the exception is the
**actual payment**, not the availability of the regime. Retiring on regime-availability
removes a set the law does not remove.

And the case declared unconstructible is stated by the authority as entitled, in terms:
*"El progenitor que sin tener asignada la guarda y custodia de los hijos, ni siquiera de
forma compartida, y sin satisfacer anualidades por alimentos en favor de estos por decisión
judicial contribuye, no obstante, al mantenimiento económico de aquellos, tendrá derecho a
la aplicación del mínimo por descendientes."* The same source cites a unified criterion from
the economic-administrative tribunal establishing the three-scenario structure this sits in.

Further reachable shapes the retirement's reasoning does not remove: never-married separated
parents with no court order; an agreement fixing no cash alimentos; an obligor who does not
in fact pay; and, with no separation context at all, an economically dependent disabled adult
descendant living in supported accommodation. Direction is under-grant, and the population is
not exotic. The implementing code already knew — it carries a comment recording that economic
dependency is not yet modelled as an equivalent.

**Reclassified from retired to deferred**, with the blocker named: the carve-out's
composition needs per-child attribution of anualidades. The safe staged boundary is to
assimilate only where the filer declares no anualidades at all, with any declared amount
suppressing the assimilation for every descendant until per-child attribution lands — which
errs toward under-grant with a visible advisory, and is expressible today. The existing
incompatibility injector for the same regime encodes the converse of this rule and must be
swept with it rather than separately; landing one half of an incompatibility pair is this
campaign's most frequently repeated defect.

Recorded prominently because a retired item is the one nobody revisits. It was retired on
reasoning that felt complete and was never measured against the authority that settles it.

### Decision one under-counts the enum, and the missing member is an over-grant

The three-value set (adopción / acogimiento / tutela) does not model a boundary the statutes
draw. Art. 58.2 grants the supplement to acogimiento *"tanto preadoptivo como permanente"*,
while Art. 58.1's assimilation covers acogimiento generally. **A temporal acogimiento carer
is assimilated for the tranches and excluded from the supplement.** With a single acogimiento
member that carer has no honest value and will select the entitling one — an over-grant
produced by the fix intended to correct an under-grant, which is the exact partially-correct
failure this campaign stopped at three times.

The recommended set separates preadoptivo-or-permanente from temporal, keeps tutela as one
member covering its post-2021 successor since no statute distinguishes them, and makes the
ordinary case the default so absence of the fact means an ordinary descendant. Being wrong by
carrying an unused member costs a retirement sweep; being wrong by collapsing two costs
silent wrong filings.

The typed-sum-over-placement-records alternative is rejected on a measured constraint: the
fact layer is flat and the wizard's repeating-group substrate has no nested-repetition
primitive, so a placement sub-list per descendant is the expensive shape. An enum with named
dates and coherence validators is the pragmatic flattening, with the validators carrying the
coherence the sum type would have enforced.

### Decision two is insufficient: one general date cannot serve, for a reason this record did not have

This record ruled out a kind-dependent single field and specified a general entry-event date.
Measurement shows a single date fails too, because of a consumer not weighed here: **the
autonomic nacimiento/adopción deducción already reads the adoption date specifically**, and
its governing decree keys on nacimiento and adopción only — acogimiento does not trigger it.
For a fostered-then-adopted child the supplement's window anchors on the first entitling
event while that deducción anchors on the adoption. A third consumer, the maternity
deduction's own clause, is date-granular rather than period-granular.

Three consumers, two distinct anchors for the same child. The recommendation is two optional
named dates with fixed kind-independent meanings, replacing the current field outright. Note
the semantic shift this carries: the present field is documented as adoption *finalisation*
while the law anchors on *inscription*, so the change is a re-anchoring and not only a
rename.

### Decision three gains a shape, and the two cheaper shapes are rejected on measurement

The recommendation is a sparse per-month spend map, optional, alongside the retained annual
figure, with a cross-field refusal when both are present for one child — one authority per
child rather than two figures to reconcile. The engine requires the monthly map for the
turning-three year and grants zero with a visible advisory when it is absent.

Both cheaper shapes are rejected for measured reasons. A post-birthday split leaks spend
after the window's upper bound, and a three-way split hard-codes that bound into the data
shape. An operator-supplied eligible figure reverses a decision this tree already made: the
write door refuses operator numbers on derived paths precisely so an operator's figure can
never be substituted for the law's. The decisive argument is that **the window's upper bound
is itself a legal determination that has not been grounded** — when the second infant-education
cycle may begin. Monthly primaries keep the persisted shape independent of that
determination; every pre-split shape bakes an unverified answer into stored data.

That grounding is now a precondition of the engine work and is recorded as unresolved.

