---
tags:
  - '#adr'
  - '#minimo-descendientes-eligibility'
date: '2026-08-04'
modified: '2026-08-05'
body_schema: 'body-v1'
body_hash: 'sha256:8213b308f7af73bfe037161274edd117868a647d7cb0176f76ab4f92fc3e4548'
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

### The spend window's upper bound: grounded, and it is regional

The design review flagged the window's upper bound as REASONED and unverified — it read the
boundary as September of the calendar year the child turns three, and said so plainly rather
than asserting it. That grounding has now run against the live authority and the answer is
different, in a way that strengthens the recommendation rather than merely confirming it.

The authority states the rule and then declines to fix a month: the eligible window runs from
the child's third birthday **until the month before the one in which the second cycle of
infant education may begin**, and that is *"determined by when the second cycle of infant
education may begin in each region, not by a fixed calendar month."* No worked example with
concrete months is given.

So the boundary is a **per-comunidad schooling-calendar determination**, not a national
constant. That converts the argument for monthly primaries from prudent to forced:

- Every pre-split shape — a post-birthday split, a three-way split, an operator-supplied
  eligible figure — requires the boundary to be known **at the moment the data is written**.
  It is not knowable there, because it depends on the filer's comunidad and on a calendar the
  application does not hold.
- A monthly map defers the determination to computation, where the comunidad is already
  available on the profile. The persisted shape stays independent of a rule that varies by
  region and can change.

**A new precondition follows, and it is not the one the review named.** The engine cannot
hard-code a month either. Applying the window requires a per-comunidad rule for when the
second cycle may begin — a regional data table that must be grounded per comunidad before
any engine work lands. The review recorded "ground the September reading"; the actual
requirement is "ground a regional table", which is a materially larger piece and belongs in
the sequencing.

Until that table exists, the honest interim is the one the review already specified for a
different reason: require the monthly map for the turning-three year, and where the window
cannot be determined, grant nothing for that child-year with a visible advisory rather than
guessing a boundary. That errs toward under-grant, keeps the error visible, and does not bake
a regional guess into a filed figure.

### The regional-table blocker is DISSOLVED: the determination is not ours to make

Recorded after the blocker was attacked at source rather than accepted. The conclusion
reverses the precondition twice over — first the reading, then the requirement itself.

**What was checked, and what each source said.** The national ordenación fixes the second
cycle at ages three to six and is silent on the enrolment mechanism, leaving it to regional
administrations. The tax authority is deliberately formula-based and names no month, only
*"hasta el mes anterior a aquel en que pueda comenzar el segundo ciclo de educación
infantil"*, with no worked example carrying concrete months. So the earlier reading — that a
per-comunidad table must be grounded before any engine work — followed correctly from those
two sources.

**It was the wrong question.** The informative return that reports childcare custody is filed
**exclusively by the centre, never by the parents**, and the authority's own guidance states
what the centre must include for a child turning three: *"los meses posteriores al
cumplimiento de dicha edad hasta el mes anterior a aquel en que el menor pueda comenzar el
segundo ciclo de educación infantil."*

**The window determination is a legal obligation of the childcare centre.** The centre knows
its own region's calendar, is required to apply it, and reports the resulting months to the
authority directly. The figure a taxpayer holds — their invoices and the centre's certificate
— already encodes that determination.

**So this application must not re-derive it.** Building a per-comunidad table would mean
computing, from a calendar we do not hold, a determination the law assigns to a third party
who does — and then risking disagreement with the return the authority has already received
from that party. A mismatch would put the filer's figure at odds with the authority's own
data, in whichever direction our table erred.

**Consequence for the engine.** It applies what is computable from data it holds and refuses
to invent what is not:

- The lower bound is computable and stays enforced: only spend after the third birthday counts
  in that period.
- The upper bound is **not derived**. Monthly spend is accepted as supplied, because the
  months a taxpayer can evidence are the months the centre determined and reported.
- The operator-facing advisory points at the authoritative artefact rather than at a rule we
  cannot state: the eligible months are those the centre reports, checkable against the
  certificate the taxpayer already holds.

That is better than the table it replaces — it directs the filer to the document that settles
the question, instead of to a figure we computed and they cannot verify.

**Sequencing effect.** The monthly spend model is no longer blocked. The regional table is
retired as a precondition and should not be built. What remains is the shape, the entry
surface, the birthday bound and the caps — all unblocked.

### Grounding for the maternidad decision: it is not the binary the row poses

Recorded as decision input, not as the decision. Three Steps wait on whether the Art. 81.1
maternidad months are operator-asserted or engine-derived. Grounding the deduction against
the live authority shows the question decomposes into three parts with three different
answers, and that the binary framing is what makes it look hard.

**The eligible child is defined by our own predicate.** The authority states the deduction is
for women with children under three **"con derecho a la aplicación del mínimo por
descendientes"**. So the child-side condition is not a separate rule to be asserted or
re-derived — it *is* the mínimo eligibility this campaign has spent its length correcting.
The engine already computes it, for that exact child, from facts already on the profile.
Leaving it unenforced means the application ignores an answer it holds, on the same
descendant, in the same calculation.

**The month arithmetic is computable and has two rules worth stating**: the month of birth
counts in full, and the month in which the child turns three does **not** count. Both follow
from a birth date the profile carries. Neither is an operator judgement.

**Only the employment condition is genuinely the operator's**, and it is genuinely outside
our data: the mother must have been receiving contributory or assistance unemployment
benefit at the birth, or be registered with Social Security or a mutualidad with at least
thirty days contributed. That is her employment history, which the application does not hold
and should not guess. It is also independently reported to the authority by a separate
informative return, so the operator's figure is checkable against a record the authority
already has — the same structure as the childcare months.

**So the shape that follows the law is a hybrid**, and it mirrors the guardería resolution
reached earlier: the operator supplies what only they know, the engine applies what it can
compute, and neither re-derives the other's part. Operator-supplied employment months;
engine-derived child eligibility, from the mínimo predicate; engine-computed month
arithmetic from the birth date.

**A rule surfaced that appears unmodelled anywhere.** Where the Social Security registration
follows the birth, the month in which the thirty-day contribution period completes carries an
additional amount, making that single month materially larger than the ordinary monthly
figure. Nothing in the current path expresses it. Direction is under-grant, and it belongs in
whichever Step takes the maternidad work rather than being discovered afterwards.

### DECISION: the maternidad months are a hybrid, and the split follows the authority

Taken rather than deferred, because the grounding above makes it a reading of the law rather
than a preference between two designs. Three Steps were blocked on this and are now unblocked.

**Decided:**

1. **Child eligibility is engine-derived, from the mínimo predicate.** Not a new rule and not
   an operator assertion. The authority defines the qualifying child as one *con derecho a la
   aplicación del mínimo por descendientes* — so the condition already exists, already runs,
   and already governs the same descendant in the same calculation. Re-asserting it would
   create a second authority for a question this campaign spent its length giving one.

2. **Month arithmetic is engine-computed from the birth date.** The month of birth counts in
   full; the month in which the child turns three does not. Both are determinable from a fact
   the profile holds, so neither is an operator judgement and neither should be typed.

3. **Employment months are operator-supplied and stay so.** Whether the taxpayer held
   unemployment benefit at the birth, or Social Security registration with the required
   contributed period, is her employment history. The application does not hold it and must
   not infer it. It is separately reported to the authority by its own informative return, so
   the operator's figure is checkable against a record the authority already has — the same
   property that settled the childcare window.

**Why this is the same answer as the guardería resolution, arrived at independently.** In both
cases the tempting framing was a binary — derive it or assert it — and in both the law splits
the question along a line the binary cannot express: the operator supplies what only they
know, the engine applies what it can compute, and neither re-derives the other's part. A
design that picks one side wholesale is wrong on the other side's half.

**What this makes implementable.** The Art. 81.1 window Step now has a real consumer, because
the calculate path must read the descendant record to apply eligibility and month arithmetic
— which is what made that Step dead on arrival while the disconnect stood. The eligibility
Step resolves to *derive*, with the predicate already written. The disconnect Step resolves to
*connect*: the declared months must reach a casilla rather than being offered and discarded.

**Carried into the implementing work**, and not to be rediscovered: where Social Security
registration follows the birth, the month completing the required contribution period carries
an additional amount above the ordinary monthly figure. Unmodelled anywhere today, and the
direction is under-grant.

**Reversible on evidence rather than on preference.** The decision rests on the authority's own
definition of the qualifying child. If that definition is read differently — with a source —
the first clause falls and the other two stand independently.


### DECISION: the two Art. 81.1 exclusions get DIFFERENT shapes, and the stock problem gets neither

Research grounded both exclusions across the 2020-2025 manuals, byte-stable, and the
decision follows from three findings rather than from preference.

**Both exclusions are deliberate, not oversights, and the evidence is stronger than
the one that admitted tutela.** Each population carries a POSITIVE statement for Art.
58.1 - grandchildren are literally named as descendientes in the direct-lineal sense,
and judicial guarda y custodia is positively assimilated as a third category distinct
from tutela and acogimiento - while Art. 81.1 excludes both by name. Tutela's positive
statement was for the SAME article it had to be admitted to; here the positive statement
is for a DIFFERENT article, so the exclusion cannot be read as a drafting gap.

**Judicial guarda y custodia is added to the relacion axis. Grandchild is NOT.** They
are not the same shape and treating them alike is what makes the naive fix wrong.
Judicial guarda is a distinct legal-basis relationship, positively named by the
authority, exactly like tutela and acogimiento - it belongs on an axis that enumerates
legal bases, and the existing whole-enum default keeps it out of the Art. 81.1 set for
free. Hijo, nieto and bisnieto are NOT different legal bases: the authority's own text
treats them as one relationship type differing only in GENERATIONAL DEGREE. Encoding
degree-of-descent as a member of a relationship-type enum bolts a differently-shaped
fact onto the axis, which is the fragmentation this campaign exists to remove rather
than an instance of fixing it. The grandchild population needs a degree fact or a
predicate scoped to Art. 81.1, decided separately.

**Neither addition fixes the existing stock, and that is the load-bearing consequence.**
The default relacion today means any qualifying lineal descendant, generation-agnostic
by its own documentation. Adding a grandchild member would NARROW that default's
meaning retroactively, and every already-stored record was written under the wider one
with no way to determine which are correctly-defaulted hijos and which are grandchildren
recorded under the only value that existed. This is a semantic narrowing of an existing
default, not a pure addition - which is precisely why it was held as ADR-shaped rather
than patched.

**So the stock is addressed where the error actually occurs, not on the axis.** The
ordinary-eligibility predicate never reads relacion at all, so Art. 58.1 and 58.2 are
computed correctly today for both populations whatever value is recorded. The ONLY
broken consumer is Art. 81.1, and the over-grant additionally requires the operator to
have declared working months for that child. That narrow conjunction is the right place
to ask: an advisory or confirmation at the point months are declared reaches every
existing record, which no enum member can do.

**One tension is recorded unresolved rather than silently decided.** The same Art. 81.1
section's multi-filer proration sentence names guarda y custodia por resolucion judicial
among the populations sharing a prorated deduccion, three sentences from the exclusion
that bars it, byte-identical across all six years. The reading adopted here is that the
proration sentence is boilerplate reused from the parallel Art. 58.1 allocation rule and
is conditional rather than a grant, while the exclusion is the direct unhedged statement
of legal effect. That reading is adopted because the decision cannot wait on it and the
exclusion is the stronger instrument - but it is a reading, not a measurement, and if it
is wrong the correction is an under-grant for that population and this decision's first
limb falls while the shape argument stands independently.


### DECISION: casilla 0611 stays operator-supplied, and the 0613 asymmetry is not a defect

The row that asked for 0611 to become registry-computed "like its 0613 sibling" rested on a
parity premise. Research retired that premise, and the decision follows from the retirement
rather than from cost.

**0613 is not the precedent it appears to be.** Its formula is min(gastos, n x 1000,
cotizaciones): a single flat rate times a scalar count, minned against two other scalars.
Every eligible child contributes the identical amount, so the cap never varies per child.
0611 after the alta-posterior increment has a cap that varies with WHICH child carries the
increment. **0613 never had to solve 0611's problem**, so it demonstrates a
flat-rate-times-count pattern, not a per-item-varying-cap pattern.

**Two different rule shapes carried by two different mechanisms is not fragmentation.** It
is what correct modelling looks like. Fragmentation is two mechanisms for the SAME shape,
which is what this campaign removed elsewhere. The asymmetry was flagged in good faith and
the flag has now been measured out of existence.

**The arithmetic is not expressible with today's primitives, and that was measured rather
than assumed.** The closed aggregation-op set passes raw per-row fields through without
arithmetic; the formula-expression ops are fixed-arity over statically declared argument
lists. Nothing iterates a variable-length row set applying a per-row conditional cap. That
part necessarily stays in Python wherever it is placed.

**The obvious fix reproduces the barred defect in distributed form, and this is the finding
that settles it.** A profile-sourced resolver projecting per-hijo rows would avoid any entry
surface change - the descendant facts already have exactly the indexed sub-record shape the
live atribucion-member resolver reads. But if each synthesised row carries a Python-capped
euro amount, then folding those rows in the registry is cosmetically registry-computed while
the actual cap-selection rule sits in Python one layer FURTHER from view. That is the same
objection that barred the single-copy route, recurring per row instead of collapsed to one
scalar. A fix that makes a gap harder to see is worse than the honest gap.

**So the only route to genuine registry computation is a new aggregation primitive** - one
reading two selector fields per row and applying a conditional per-row cap before summing.
That is a schema and engine extension, not a refactor, and its entire value is auditability:
the figure 0611 produces today is correct, and no taxpayer receives a different number
either way. That does not justify the extension on its own, and it is not this campaign's
to take.

**Recorded honestly as a closure rather than a deferral, and flagged as the shape that can
look like scope reduction.** A campaign must not narrow its own completion criterion, so the
distinction matters: this is not the work being judged too expensive, it is the criterion
being measured false. "Parity with 0613" was never achievable because the two casillas do
not share a rule shape. If a future reform makes 0611's cap uniform again, the parity
question genuinely reopens and this decision should be revisited rather than cited.


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
