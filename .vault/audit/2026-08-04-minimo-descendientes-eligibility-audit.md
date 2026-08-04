---
tags:
  - '#audit'
  - '#minimo-descendientes-eligibility'
date: '2026-08-04'
modified: '2026-08-04'
body_schema: 'body-v1'
body_hash: 'sha256:43a82fa4549974588c508059eec7cffb9251dbb052f420b310afa5158f17e20e'
related:
  - "[[2026-08-04-minimo-descendientes-eligibility-adr]]"
  - "[[2026-08-04-minimo-descendientes-eligibility-plan]]"
  - "[[2026-08-04-minimo-descendientes-eligibility-research]]"
  - "[[2026-08-04-profile-derived-selectors-audit]]"
  - "[[2026-07-30-open-work-consolidation-plan]]"
---

# `minimo-descendientes-eligibility` audit: closing honesty review

## Context

A fresh-context honesty review of the campaign, run before closure was declared, as the
campaign-close honesty-review discipline requires. Performed read-only by an independent
reviewer pinned at commit `85c4d21f17`, inheriting the plan, the ADR and the twelve
execution records as a handover rather than re-reading its own work. The coordinator then
verified each finding against HEAD before acting, and ran one grounding check the reviewer
could not.

The campaign's substance survives the review. No finding changes a calculation or reopens a
defect. Three of the four items are artefacts describing the code less accurately than the
code behaves; the fourth is a handover note against a future duplication.

## Findings

### 1. MEDIUM — the plan and the records disagreed with each other and with HEAD

Two contradictions pointing in opposite directions. `P03.S12` was unticked while its work
was complete: the rentas-undeclared collector ships, carries its own test module and a
coordinator wiring test, and landed as `a011fedd68`. Separately, `P03.S11`'s record claimed
"half the work sits uncommitted in the working tree" for work that had finished — verified
at HEAD: zero inline threshold literals remain in either production module, and the shared
registry-threshold helper is consumed by both test modules.

Individually bookkeeping. Together they are what this gate exists to catch: an inheritor
reads a plan saying one Step is open and a record saying a different Step is open, and
neither statement is true of HEAD.

The unticked Step was a coordinator error of a specific kind worth recording. `S12` was held
open because a *different* collector — the prorrata-inferred advisory — had no tests. That
defect was real and was worth blocking on, but it was outside `S12`'s scope, and blocking a
Step on a defect it does not own makes the plan unreadable rather than cautious. The correct
instrument was to open the defect separately, which is what eventually happened.

Resolved: `S12` ticked, the plan reads 12/12. `S11`'s record takes an appended correction
rather than an edit, so the stale claim and its correction sit together.

### 2. LOW-MEDIUM — a six-year coverage claim that is six-year for two surfaces and one-year for the third

`P03-S10`'s record states all three surfaces were measured "across every revision
2020-2025". The two aggregate tests do iterate the full year set; the anualidades
capped-descendant test pins one year. The flag's *default* has six-year coverage, but the
corrected behaviour — the flag flipping for a capped descendant — is pinned at 2024 alone.

Substantively low risk, because the predicate is year-parameterised and the thresholds are
separately proven to resolve across the whole window. The claim is what overstates. Being
fixed by parameterising the test rather than narrowing the sentence: the claim is worth
making true rather than making smaller.

This is the third instance in two campaigns of a sentence whose qualifier reads as covering
the clause after it. The recurring root cause, named by two executors independently, is
enumerating a population from what the author touched rather than reading it off the owning
site.

### 3. LOW-MEDIUM — the ADR understates the operator cost in the sentence that accepts it

The ADR's Consequences says operators gain "two new descendiente questions". Three pages
landed. The third is sanctioned by the ADR's own Implementation, which provides for an
explicit per-descendant override that always beats the derivation, so the decision is intact
and this is not scope creep. Only the accepted-cost figure is wrong — in the one sentence
weighing setup friction against a wrong filed figure, which is where accuracy matters most.

### 4. LOW — the anchored clause governs three mínimos and the scoping statement names one

The legal entry this campaign authored anchors, verbatim, a clause covering the mínimo por
descendientes, **ascendientes o discapacidad**. The ADR bounds scope on the ascendientes side
only, and the entry's own notes describe the clause as descendientes-only — narrower than the
text it anchors. The parameter is likewise named for descendientes.

Nothing is wrong today, and the scoping decision is correct: ascendientes and discapacidad
are bare manual inputs with no formula and no binding, so neither carries an incomplete
predicate that could silently under-declare. The related ascendant bindings are identity and
export only, populating the fichero-BOE record rather than any mínimo.

The hazard is downstream. Whoever builds an ascendientes predicate will read a
descendientes-scoped note and a descendientes-scoped parameter name, and is likely to mint a
second parameter and a second legal entry for the same clause and the same figure — the
duplicate-authority outcome the canonical-home discipline exists to prevent. The remedy is a
handover line on the legal entry's own notes, where the next author will actually be looking,
rather than in an audit they may never open.

## Verified clean

The three claims flagged as most at risk before the review all hold.

**The registry thresholds resolve across the whole served window, and durably.** The ADR
recorded this as "expected but unverified, and a first implementation check". It did happen,
and shipped as two gates with an explicit division of labour: one iterates every revision
2020-2025 asserting both ceilings resolve, the other grounds their *values* against the LIRPF
text across the same years. Resolvability and values are checked separately, so neither can
silently stand in for the other.

**The Art. 64 base comparison is enforced and untouched.** The registry formula carries the
comparison nested inside a positivity guard, with the eligibility binding short-circuited
behind both conditions. All five anualidades formulas are unmodified by this campaign.

**No declarative Steps.** All twelve Step actions are imperative and file-scoped. The one
verification-only Step produced named tests, so it is a gate rather than a musing. This
campaign does not have the shape the discipline warns about.

**Every remaining behavioural promise in the ADR has a named test** — explicit-override-wins,
the spouse-record signal, shared-custody-remains-one-trigger, and anualidades sharing the same
predicate.

## The live legal cross-check

The campaign's grounding record admitted no live source was consulted for the two threshold
figures, relying on the bundled manual. The legal-grounding discipline is explicit that the
bundled corpus is preferred but **not infallible for a numeric amount or rate**, and requires
a live cross-check for exactly these. The reviewer had no network access, so the coordinator
ran it.

Both figures confirm against the live AEAT authoritative surface: the annual rentas ceiling
excluding exempt income, and the own-declaration threshold above which no entitled
contribuyente may apply the mínimo.

The boundary semantics were checked as well as the figures, because an off-by-one at a
threshold is the failure a figure-only check cannot see. Both are correct. The rentas cap
excludes strictly above the ceiling, so a descendant exactly at it stays eligible. The
own-declaration rule is modelled as a two-part test — the descendant files a return AND their
rentas exceed the figure — matching the authority's own "iguales o inferiores" language,
which the implementing docstring quotes. A descendant who files a return at or below the
figure therefore keeps the mínimo intact, which a naive boolean "files their own return"
modelling would have silently destroyed. It was not modelled that way.

An undeclared rentas figure excludes nothing, which is the fail-open direction; the advisory
that fires in exactly that state is what keeps it visible rather than silent.

## The defect this review's finding-class predicted

Recorded because it is the campaign's most consequential find and it arrived through the
review rather than through the implementation.

The prorrata-inferred advisory had no test of any kind — not the collector, not its wiring,
not its diagnostic kind. It is the advisory the ADR's chosen default direction rests on: the
engine deliberately errs toward under-claiming *because* the advisory makes that visible and
correctable. Writing the missing tests found a live defect in it. The collector named every
descendant in a length-capped message, so a large household raised a validation error
**instead of** the advisory — silencing the disclosure precisely for the filer with the most
children at stake, and removing the ADR's warrant for the direction it chose.

The same defect had already been found and fixed in a sibling collector during
implementation. It survived in this one because nothing exercised it. That is the argument
for the coverage class, made by the class itself.

A process note from the same episode, kept because it is instructive rather than incidental.
The coordinator read the collector while judging severity, reported it "sound", and was
reading the assigned agent's own uncommitted fix in flight — a false all-clear delivered to
the one party positioned to find the bug. It was found anyway, by writing the test instead of
trusting the read.

## Residuals carried forward

Unchanged from the ADR's own deferrals, and tracked in the consolidated open-work plan rather
than here: the three unmodelled Art. 58/61 conditions, all of which under-grant and therefore
harm the taxpayer rather than the revenue; and the entry-surface follow-up.

One residual is measured and newly recorded. The engine cannot reproduce the authority's
printed figure for an unmarried joint return, computing less. The shortfall is real and its
mechanism is understood: a descendant sitting inside a joint return whose rentas exceed the
own-declaration figure bars the other progenitor and leaves sole entitlement, so that
descendant takes a whole tranche rather than a prorated one. That is per-descendant
unidad-familiar membership, which the profile cannot express — a schema change, not a
predicate fix. It errs toward under-claiming, which is the safe direction, and it is pinned
by a test asserting the printed figure is *not* claimed as an expectation, so the gap stays
recorded rather than silent.

Six collector wirings outside the mínimo family remain unaudited. Given this class has now
produced an unguarded wiring and a live defect, they are being treated as suspect rather than
presumed covered.

## Assessment

The review ran before closure was declared, which is the gate. Four items, none blocking, and
the one that could not be left was the artefact contradiction — with a Step unticked and a
record contradicting itself, the campaign could not be assessed from its own artefacts, which
is the condition the discipline names. That is resolved.
