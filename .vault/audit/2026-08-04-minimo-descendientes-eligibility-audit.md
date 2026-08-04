---
tags:
  - '#audit'
  - '#minimo-descendientes-eligibility'
date: '2026-08-04'
modified: '2026-08-04'
body_schema: 'body-v1'
body_hash: 'sha256:26170b60d46cb5a138df7b476276c3b3dc77d93ecbf69bb7c05abb4160428e17'
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


### 5. MEDIUM — the three new descendiente pages are traversed and never answered

Raised in a follow-up pass after the four above, and reproduced independently by the
coordinator. The two established descendiente pages appear in four and six wizard test
files respectively. The three pages this campaign added appear in **zero**, and the CLI
door-surface test has zero hits for any of their tokens.

The zero is not an artefact of a generic page-set iteration — that was checked before the
finding was trusted, and none exists. The one genuine end-to-end walk drives the real flow
definition, but its canonical answer set supplies only birth date, convivencia, guardería
spend, adoption date and NIF. The three new pages sit unconditionally in the middle of the
page sequence, so they are walked past and never answered.

What that leaves unexercised: the new rentas non-negative validator never fires; the
prorrata page's two choices are never recorded; and the tri-state distinction between an
absent answer and an explicit decline never runs through the wizard, only at the domain
layer.

The wiring itself was checked specifically for a registered-but-unattached defect and is
sound at every point examined, and the tri-state survives end to end by design — the
canonical parser explicitly refuses to collapse a blank onto a false, and the encoded token
is truthy so it survives the drop-blank filter. So this is not a live defect. Nothing checks
that it stays that way.

Tracked as a Step rather than a deferral, on the strength of the direction involved: an
explicit decline on the prorrata page is the answer that *claims the whole mínimo*, an
operator asserting sole entitlement. The ADR promises an explicit per-descendant value always
beats the derivation; that promise is pinned at the predicate and not at the surface which
produces the value. This campaign has now produced two defects in exactly that shape — a
collector that existed and was merely unexercised, and a refusal test that could not
discriminate its own guard — which is why an unexercised surface here is not treated as
merely a coverage number.


### 6. MEDIUM — the flag-help gate guards one of two strings describing the same surface

Two strings describe the `--descendiente` flag format. The campaign corrected one and left
its sibling stale in all four catalogues; the parity gate guards the same one it corrected.
Reproduced independently, key for key: the wizard flag help is missing five accepted keys in
Spanish, six in English and Hungarian, and seven in Catalan.

This is the harm the entry-surface Step's own text describes and claims to close — that an
operator refused at the write door cannot discover from help how to express the rentas
figure. An operator reading the wizard help still cannot discover it, and that figure is what
the campaign turns on. The key is a registered flag-help family, so it renders as CLI help
rather than being dead copy.

The sharp part is that the gate is *good*. It is bidirectional — every advertised key honoured
by the parser, every parser key advertised — locale-parameterised across all four catalogues,
and it already guards against naming a euro figure. It needs no new logic. Its key constant is
a single string where it should be a tuple. Nobody finds that by reading the gate; it requires
noticing there are two strings.

This is the third instance in these two campaigns of one half of a mechanism being built or
fixed while its sibling half is left — the same shape as the wizard clearing set and the
emitter repair. It is now the first pattern to look for.

Part of the drift predates the campaign: four keys were already missing before the three new
ones existed, which is why Catalan is worst — it has been accumulating. Extending the gate
retires that for free, and the fix is required to leave the suite RED before the catalogues
are corrected, since a gate that is green over known-stale copy is worse than the gap.

### 7. LOW — the prorrata factor is a hard half where the statute says equal shares among N

The prorrata factor returns a fixed one-half whenever a second entitled contribuyente is
indicated. Norma 1ª says the mínimo is prorated among two **or more** entitled contribuyentes
in equal parts — 1/N, not 1/2. The operator-facing copy matches the implementation exactly in
all four catalogues, so copy and predicate agree and both are narrower than the statute.

The direction is over-grant, which under-declares, and that is the class this campaign exists
to close. It is rated LOW on arity rather than on direction: three same-degree entitled
contribuyentes for a *descendant* is near-impossible, since a child has two parents and norma
1ª's own degree rule collapses mixed-degree cases to the closest relative. The axis where 1/N
is ordinary — several siblings supporting one parent — is ascendientes, which has no formula
and no binding, so no engine predicate applies the factor at all. The copy is also honest
about the assumption rather than hiding it, advertising a split between both.

Carried to the follow-up as a note rather than implemented, on the same principle as the other
residuals: a statute-widening change does not belong inside a closing campaign.


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


**The thresholds were re-measured per revision, not inferred from the gate.** Every one of
the twelve parameters exists and carries the expected figure in all six revisions, read
through the validated authority. That live probe was worth running rather than trusting the
shipped gate, and for a reason worth recording: the resolvability test asserts only that each
parameter is positive, so a parameter mis-valued at the *other* threshold's figure would pass
it. The values are separately grounded against the LIRPF text across the same six years by a
different gate. The division of labour is sound and the coverage is real — but neither gate
alone would catch a swapped figure, and only reading both establishes that.

**The four-failure attribution in the verification Step re-derives correctly.** Re-derived
rather than inherited, because attribution in a shared worktree is this project's most
error-prone class. The count survives a probe that gets it wrong: three of the four repaired
sites became negative pins and the fourth became a positive per-child assertion, so counting
pins undercounts. The failures were caused by an emitter removed in the *sibling* campaign's
commit twelve minutes earlier, which is the load-bearing half of the claim and justifies the
decision to decline the repair. Agent-level attribution within that is not recoverable — one
shared git identity means author metadata distinguishes nothing — and is immaterial to the
judgement, which rested on cross-campaign ownership.


**The operator-facing copy for the three new facts was audited against the predicate in all
four catalogues, and the hypothesis that prompted the audit was wrong in the useful
direction.** The worry was that the own-declaration page might ask the bare behavioural
question — does this descendant file a return — which an honest operator would answer yes to
for a small-return filer, silently losing the mínimo while the code stayed correct.

It does not. Every catalogue states the two-part rule explicitly: filing only removes the
allowance if the descendant's rentas *also* exceed the legal limit. And the implementation
makes the bare answer harmless rather than merely documented — exclusion requires the filing
flag AND a present rentas figure AND that figure above the norma 2ª limit, with the docstring
quoting the manual verbatim. The operator described does not lose the mínimo.

The rentas prompt carries the exempt-income qualifier in all four catalogues, so none asks for
a bare annual income figure that would wrongly breach the ceiling. The prorrata prompt asks
whether another taxpayer is *entitled* to the allowance rather than whether they claim it —
matching the statute's own wording, and the distinction between a correct answer and an
over-claim. Choice-to-value mapping was verified against the factor's explicit-answer branch
in both directions.

One limit stated rather than glossed: this verified the semantic content of the Catalan and
Hungarian strings — the legal qualifiers, the two-part rule, the entitlement framing, the
choice mapping — not whether the phrasing reads naturally to a native speaker. That needs a
speaker, not a probe, and is not claimed.


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


### Second pass: the two deferred amounts, cross-checked before anyone authors a parameter

Run because the grounding discipline requires a live check for any numeric amount and the
reviewer who sized these residuals has no network access. It declined to author a registry
parameter on a bundled-corpus-only figure, which was the correct refusal; this closes that
block in advance rather than at implementation time.

Both confirm against the live authority: the under-three increment at **2.800 euros**, and
the mínimo where a descendant dies during the period at **2.400 euros**. The adopción and
acogimiento rule confirms too — the increment applies regardless of the child's age, in the
period of Registro Civil inscription and the two following, or from the judicial or
administrative resolution where inscription is not required.

**Three rules surfaced that no pass had found, and each is an implementation trap.**

**The increment survives the death of the descendant.** The authority states the under-three
increment applies even where the descendant died during the tax period. So the death case
and the supplement are not alternatives to be chosen between — they compose. An
implementation that treats the flat death amount as replacing the whole computation would
drop the increment for the household least able to query it.

**The three-year window is a cap, not a restart.** Where circumstances change — the
authority's own example is an adoption following a fostering — the increment continues for
the remaining periods up to a maximum of three. So a child fostered and later adopted does
not begin a fresh window on the adoption. An implementation anchoring on whichever entry
event it happens to hold would grant up to six years where the law allows three, which
under-declares. This also settles a design question the earlier passes left open: the field
cannot be a single entry date whose meaning depends on relationship kind, because both
events can occur for the same descendant and the window spans them.

**The death amount overrides autonomic divergence.** Where a comunidad has set mínimos por
descendientes different from the state figures, the death case is nonetheless 2.400 euros.
That matters here specifically: this engine already wires a divergent autonomic tranche
table for one comunidad, so a death-case implementation must override that table rather than
feed through it. A fix that applied the flat amount only to the estatal aggregate would
leave the autonomic side wrong for exactly the filers whose comunidad diverges.

None of these three is expressible today, and together they raise the norma 4ª item's cost
above the flat-amount framing it carried when it was sized — it is not one figure but an
interaction with the supplement, the window and the autonomic table.


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

**Five collector wirings outside the mínimo family are untested**, measured rather than
estimated: ten collectors are wired into the advisory coordinator and only two test files
drive that coordinator at all. The four mínimo kinds are now covered, as is the prorrata
regularización kind by an existing M303 test. The remaining five span other modelos with
their own fixture requirements, which is why they are a follow-up rather than absorbed here.

That count corrects an earlier statement of six in this document, which was the coordinator's
own tally before the sweep ran. The class has now produced findings three times, once
severely, so the five are treated as suspect rather than presumed covered.

A note carried into the conjunta-membership deferral rather than resolved here. The canonical
Art. 82.1 authority — the enum carrying the unidad-familiar modality test and the
registration-agnostic rule — now has **no consumer in the mínimo path at all**. The prorrata
predicate deliberately reads the AEAT ECIVIL filing code instead, and that choice is correct
and measured: both fields are optional and asked side by side in the same setup walk, so
neither is better populated, and switching would silently drop the prorrata for any profile
carrying only the ECIVIL code — the over-granting direction.

The decision being right is what makes the note necessary. An enum that is the canonical
authority for a question nothing asks it is the shape that invites a second one to be built
alongside it. Should the membership modelling ever land, it must decide whether that enum
becomes the source, and note that it distinguishes registered from unregistered pareja de
hecho while the article does not — so both must count as partnered, or an unregistered couple
over-grants.


## The Art. 58.2 supplement: attempted, stopped at the boundary, and why that was right

Added after the review, when acting on one of its own residuals surfaced a defect the
residual list had not anticipated. Recorded in full because the reasons are non-obvious and
would otherwise be re-derived by whoever takes it.

**The defect is real and sizeable.** Art. 58.2 grants the menor-de-tres supplement to an
adopted or fostered child **regardless of age**, in the inscription period and the two
following. The engine's predicate tests only age at year end from the birth date and never
consults the entry date, so a child adopted at five receives nothing where the law gives the
supplement, three years running. Confirmed against the live authority, not only the bundled
corpus, and backed by a printed worked example whose figures are usable because that
comunidad modified only the discapacidad mínimo.

**It was stopped before landing, and the reason is a scope difference of one word.** Art.
58.1 assimilates persons linked by *tutela y acogimiento* — both take tranches. Art. 58.2
covers *adopción o acogimiento* and omits tutela entirely. The descendant model carries an
adoption-named date and no relationship-kind axis at all, so the rule "adopción and
acogimiento but not tutela" is not expressible. A supplement keyed on the presence of that
date would pay a tutela guardian who recorded one — an over-grant, which under-declares.
The fix as scoped would have manufactured a silent revenue error while correcting a visible
over-tax.

**Measurement then found a second, independent reason, from a direction nobody anticipated.**
The predicate is shared across **three statutes**, not one: the menor-three count and the
aggregate supplement answer to Art. 58.2, the guardería population to Art. 81 bis, and the
maternidad deduction to Art. 81. And Art. 81 carries its own adoption clause with a
different window **shape** — three years from the inscription *date*, against Art. 58.2's
inscription *period* plus two periods. The two can diverge.

So a single shared predicate cannot serve all three correctly, and changing it in place
would silently apply one statute's window to another's deduction. That is the same
half-a-mechanism shape this review found three times elsewhere, arriving here through an
over-shared predicate rather than through a missed sibling.

**The oracle grounds less than it appears to.** The worked example's child is adopted, so it
evidences the adopción route only. It says nothing about acogimiento and nothing about
tutela — which is precisely the distinction that blocks the fix. An implementer who takes
the oracle as licence for the whole clause will ground the one route that was never in
doubt.

**Leaving the defect in place is the safer state**, and that is a deliberate judgement
rather than an inability to proceed. Today it over-taxes an adoptive family: wrong, but in
the direction the taxpayer can see and challenge. The available fix would leak the
supplement to tutela cases silently, in this article and possibly in Art. 81 as well. A
partially-correct supplement is worse than none.

**What the work actually needs**, from the measurement rather than as a design: a
relationship-kind axis distinguishing adopción, acogimiento preadoptivo o permanente, and
tutela; an entry-date field whose name is not adoption-specific, since the clause anchors on
Registro Civil inscription *or* the resolución judicial o administrativa where inscription
is not required, and a foster carer has no correct field for either today; and per-statute
predicates rather than one shared test. Whether Art. 81 bis carries its own adoption clause
is unread — if it does, the count is four statutes rather than three.


## Assessment

The review ran before closure was declared, which is the gate. Four items, none blocking, and
the one that could not be left was the artefact contradiction — with a Step unticked and a
record contradicting itself, the campaign could not be assessed from its own artefacts, which
is the condition the discipline names. That is resolved.
