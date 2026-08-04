---
tags:
  - '#adr'
  - '#minimo-descendientes-eligibility'
date: '2026-08-04'
modified: '2026-08-04'
body_schema: 'body-v1'
body_hash: 'sha256:4bd18eab895ee164ebc53cf9766a74a19f7589ddd77e62b99ee572d89908a159'
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
