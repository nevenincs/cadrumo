---
tags:
  - '#plan'
  - '#minimo-descendientes-eligibility'
date: '2026-08-04'
modified: '2026-08-05'
body_hash: 'sha256:18c03bb4e97411a08cb6084d19b7728bf59f38c2f7a30a0c570c740c5b41076a'
tier: L2
related:
  - '[[2026-08-04-minimo-descendientes-eligibility-adr]]'
  - '[[2026-08-04-minimo-descendientes-eligibility-research]]'
  - '[[2026-08-04-minimo-descendientes-eligibility-deferred-descendant-axes-adr]]'
---

# `minimo-descendientes-eligibility` plan

## Description

Executes `2026-08-04-minimo-descendientes-eligibility-adr` in full. The Modelo 100
mínimo por descendientes derivation implements three of the seven conditions the law
states, and three of the omissions inflate the mínimo and under-declare tax. This plan
completes the eligibility predicate.

The ordering against `2026-08-04-profile-derived-selectors-plan` is a hard dependency,
not a courtesy: that plan closes the operator override which is today the only channel
by which a filer reaches a correct figure. Every Step here must land before that plan
reaches its refusal Phase.

## Steps

### Phase `P01` - Ground the thresholds in the registry

Author the Art. 58.1 rentas cap and the Art. 61 norma 2a own-return figure as registry money parameters across revisions 2020-2025, each with a legal-catalogue entry anchored to the bundled consolidated LIRPF text, so no regulatory literal enters Python.

- [x] `P01.S01` - Author the Art. 58.1 rentas-cap money parameter for revisions 2020-2025 with a legal-catalogue entry anchored to the bundled consolidated LIRPF clause; `src/cadrumo/_data/registry/aeat/modelos/100/revisions/*/parameters/, src/cadrumo/_data/registry/aeat/legal/`.
- [x] `P01.S02` - Author the Art. 61 norma 2a own-return money parameter for revisions 2020-2025 with its own legal-catalogue entry and corpus anchor; `src/cadrumo/_data/registry/aeat/modelos/100/revisions/*/parameters/, src/cadrumo/_data/registry/aeat/legal/`.
- [x] `P01.S03` - Verify every revision 2020-2025 loads with both new parameters resolvable and the legal-grounding gate green; `src/cadrumo/domain/calculations/registry/tests/`.

### Phase `P02` - Complete the eligibility predicate

Add the two per-descendant factual inputs, extend the ordinary-eligibility test with the two exclusions, and generalise the norma 1a prorrata from the shared-custody special case to the entitlement rule, deriving it from profile signals with an explicit per-descendant override and a visible advisory.

- [x] `P02.S04` - Add the annual-rentas-excluding-exempt and own-return-filed facts to the descendiente axis in the profile schema and the descendant model; `src/cadrumo/_data/registry/cadrumo/user_profile/schema.toml, src/cadrumo/domain/contribuyente/family.py`.
- [x] `P02.S05` - Extend the ordinary-eligibility test with the Art. 58.1 cap and the Art. 61 norma 2a exclusion, taking both thresholds as caller-supplied registry parameters, and clear the twelve staging entries the drift gate carries for those parameters, deleting them outright if the consumer is visible to the gate AST scan or re-documenting each against its real consumer if it lands in the application-layer injector instead; `src/cadrumo/domain/contribuyente/family.py, src/cadrumo/application/modelo/_profile_binding.py, src/cadrumo/domain/calculations/registry/tests/test_modelo_100_drift_detection.py`.
- [x] `P02.S06` - Generalise the norma 1a prorrata from the shared-custody special case to the entitlement rule, keeping shared custody as one trigger and adding an explicit per-descendant override; `src/cadrumo/domain/contribuyente/family.py`.
- [x] `P02.S07` - Derive the prorrata from marital status, spouse record, and declaration type when no explicit per-descendant answer exists, and raise a non-blocking advisory naming the descendant and the inference; `src/cadrumo/application/modelo/_profile_binding.py, src/cadrumo/domain/contribuyente/family.py`.

### Phase `P03` - Entry surface and grounded proof

Give the two new facts a production writer on the descendiente CLI flow, and prove each corrected scenario against an external oracle rather than against the formula under test.

- [x] `P03.S08` - Add the three new facts to the interactive descendiente flow, its prompts and its renderer, and correct the flag help string which still lists only the original keys so an operator refused at the write door cannot discover from help how to express the rentas figure, updating the four locale catalogues for that string through the locales CLI rather than by hand; `src/cadrumo/entrypoints/cli/_config/_descendiente.py, src/cadrumo/application/wizard/, src/cadrumo/locales/`.
- [x] `P03.S09` - Author two manual-oracle fixtures from the AEAT worked examples that carry printed figures, the Asturias two-entitled-filer example whose individual total is exactly half its conjunta total and which needs no CCAA correction because that comunidad exercised no normative competence, and the own-return-exclusion example grounded on its estatal column ONLY because its comunidad did diverge, then keep the cap and the anualidades flag as structural proofs since a zero, a preserved birth-order rank and a boolean flip are properties no printed figure would prove better; `src/cadrumo/_data/corpus/manual_oracles/, src/cadrumo/application/modelo/tests/`.
- [x] `P03.S11` - Replace the hardcoded ceiling literals in the two descendant test modules with reads of the registry parameters the campaign authored, matching how the new eligibility module already resolves them, because inlined regulatory figures decouple those tests from the authority and would keep them passing against a stale ceiling if a future revision moved it; `src/cadrumo/domain/contribuyente/tests/test_custodia_compartida.py, src/cadrumo/domain/contribuyente/tests/test_descendant_info.py`.
- [x] `P03.S10` - Confirm the autonomico aggregate and the anualidades eligibility flag are both corrected by the same predicate change; `src/cadrumo/application/modelo/tests/`.
- [x] `P03.S12` - Advise when a declared descendant contributes to the minimo with no rentas figure on record, because the existing undeclared diagnostic returns early whenever descendiente facts exist and that early return reasons about a declared ZERO, which does not hold for a declared descendant whose rentas are simply absent and who therefore over-claims silently; `src/cadrumo/application/modelo/_minimo_descendientes_advisory.py, src/cadrumo/application/modelo/tests/`.

### Phase `P04` - the deferred descendant axes, reopened after closure

Reopens this feature for the residue its own closing audit carried forward, so it is not a settled question being reopened but a deferral being executed. The deferred-descendant-axes ADR decided the two precondition axes and amended all four of its original decisions. The numbering continues from the closed range rather than restarting, so the feature index reads as one lifecycle with a gap where the campaign closed and reopened, which is what happened. A separate plan for that ADR was opened and then archived as superseded by this Phase: the exec lifecycle gate binds on the feature tag, an ADR carrying a topic infix cannot get its own plan with exec records, and two plans describing one body of work is the drift this campaign spent its day removing.

- [x] `P04.S13` - Add the DescendantRelacion closed set, the two named entry-event dates replacing adoption_date, and their flag, wizard and locale entry surface; `src/cadrumo/core/_descendant_relacion.py`.
- [x] `P04.S14` - Scope the Art. 58.2 missing-anchor advisory to descendants that actually carry a tranche; `src/cadrumo/domain/contribuyente/family.py`.
- [ ] `P04.S15` - Give the Art. 81.1 maternidad adoption clause its own date-scoped three-year window, separate from the Art. 58.2 period-scoped one, BLOCKED on S21 because nothing on the calculate path reads a descendant record for maternidad, so the predicate would land with no consumer and rebuild the dead shape S19 removed; `src/cadrumo/domain/contribuyente/family.py`.
- [x] `P04.S16` - Model month-level guarderia spend as an optional sparse per-month map alongside the annual figure, refusing both at once for one child, and route the calculate path through the canonical record so a declared map reaches the cap terms; `src/cadrumo/domain/contribuyente/family.py, src/cadrumo/domain/contribuyente/_guarderia_mensual.py, src/cadrumo/application/modelo/_profile_binding.py`.
- [x] `P04.S17` - Assimilate an economically dependent descendant where the filer declares no anualidades at all, sweeping the existing incompatibility injector in the same change, BLOCKED on per-child attribution of anualidades; `src/cadrumo/application/modelo/_profile_binding.py`.
- [ ] `P04.S18` - Rename the derived guarderia cap-population path and its binding away from the menor-de-tres name it outgrew, in ONE atomic commit carrying the schema pattern, the binding TOML, the formula reference, the injector and every M100 fixture supplying the binding id by name; `src/cadrumo/_data/registry/cadrumo/user_profile/schema.toml, src/cadrumo/application/modelo/_profile_binding.py`.
- [x] `P04.S19` - Retire the dead advisory cluster on RentaFamilyProfile, opened on a partial measurement naming one property and widened on a fuller one to five members, including the maternidad method superseded by the live free function and the guarderia cap constant whose last Python consumer it is, replacing the cotizaciones-binds-the-cap assertion against the live registry path in the SAME commit; `src/cadrumo/domain/contribuyente/family.py, src/cadrumo/domain/contribuyente/tests/test_incremento_guarderia_0613.py, src/cadrumo/core/external_constants.py, src/cadrumo/core/tests/test_external_constants_centralisation_part2.py, src/cadrumo/locales/`.
- [x] `P04.S20` - Route the canonical-record refusals reaching the descendiente add verb to the operator, because the verb catches only the answer-type error and the boundary projects the rest to a GENERIC translated refusal that discards the validator's own sentence, so the entry-date coherence rules this Phase shipped told the operator nothing about which field conflicted, and the discarded detail was written to the error log carrying the declared record; `src/cadrumo/entrypoints/cli/_config/_descendiente.py`.
- [ ] `P04.S21` - Decide whether the Art. 81.1 maternidad months are operator-asserted or engine-derived, because the engine never sees the descendants at all and takes an operator-supplied list of hijo and month pairs, so the under-three and cohabiting conditions cannot be enforced while the profile already holds the birth dates and cohabitation facts, and the answer may be a refusal, an advisory or a documented operator-asserted input but must be chosen rather than inherited, BLOCKING S15 whose window predicate has no consumer until this resolves; `src/cadrumo/application/modelo/_calculate_input.py, src/cadrumo/domain/contribuyente/family.py`.
- [x] `P04.S22` - Connect or retire the declared maternidad months, because an operator declaring MESES_TRABAJO through descendiente add or the guided flow gets nothing, the fact round-trips and rides the payload and is declared in the user-profile schema as a model selector while no formula targets casilla 0611 and no binding names the path, so a documented entry surface is today lying about what it does whichever way S21 resolves; `src/cadrumo/application/modelo/_calculate_input.py, src/cadrumo/_data/registry/cadrumo/user_profile/schema.toml, src/cadrumo/entrypoints/cli/_config/_descendiente.py`.
- [ ] `P04.S23` - Add the Art. 81.1 post-birth alta increment, 150 euros for the month completing the 30-day contribution period, raising that child cap to 1.350 euros for filing years from 2023 only, gated on a new operator-supplied fact naming that month; `src/cadrumo/core/external_constants.py, src/cadrumo/domain/contribuyente/_deduccion_maternidad.py`.

## Parallelization

`P01` and the schema half of `P02` are independent and may run concurrently. The
predicate work in `P02` depends on `P01` landing first, because the thresholds are
caller-supplied parameters rather than literals. `P03` depends on `P02`.

`P04.S13` had to be one Step and one commit rather than several. Retiring the
adoption-named date is a field removal, and the relocation discipline requires the
canonical site, every consumer, every fixture and every test to share one index and one
commit, so splitting the axis from its entry surface would have left the tree
uncollectable in between. `P04.S14` followed separately because it corrects a defect
found by self-review after the first landed, not because the two are independent.

`P04.S15` was recorded here as open and unblocked and is NOT. It is blocked on `S21`,
and the dependency runs the opposite way from how `S21` was opened, which is why this
paragraph states it rather than leaving a reader to infer it from two row texts. The
statutory content of `S15` is sound and unchanged: both entry-event dates now exist, the
Art. 81.1 adoption clause runs three years from the inscription DATE while Art. 58.2
counts the entry PERIOD and the two following, the two genuinely diverge, and one
predicate serving both would silently apply one statute's window to the other's
deduction.

What blocks it is that the predicate would have nowhere to live. Nothing on the
calculate path reads a descendant record for maternidad: casilla 0611 has no formula
targeting it and no binding naming a maternidad profile path, and it is set directly
from an operator-supplied list of hijo and month pairs. A window predicate on the
descendant record would therefore land with no consumer, which is exactly the shape
`S19` removed five members of. `S21` decides whether maternidad derives from profile
facts as the guardería increase now does, and only its answer gives `S15` a consumer.

`P04.S22` is independent of that answer and should not wait for it. An operator who
declares the maternidad months through the descendiente verb or the guided flow gets
nothing: the fact round-trips, rides the JSON payload, survives the resume walk and is
declared in the user-profile schema as a model selector, while no formula consumes it.
Declared and unconsumed is worse than absent, because absent reads as an omission and
declared reads to any inspector as wired. Whichever way `S21` resolves, a documented
entry surface is today telling the operator it records something it does not use.

`P04.S16` was BLOCKED on a per-comunidad regional table and no longer is. The row's own
text still carries that clause and is stale; this paragraph is the correction, and the
blocker must not be reinstated from reading the row. The Art. 81.2 increase extends into
the period the child turns three, for spend incurred after the birthday and up to the
month before the second cycle of infant education may begin, and that upper bound is a
per-comunidad determination rather than a fixed calendar month. The earlier reading
followed correctly from the statute and the tax authority alone, and it was still the
wrong question: the informative return reporting childcare custody is filed EXCLUSIVELY
by the centre, which is required to apply its own region's calendar and report the
resulting months. So the determination is a third party's legal obligation, the figure a
taxpayer holds already encodes it, and re-deriving it here would compute from a calendar
this application does not hold an answer that could contradict the return the authority
already has. The regional table is RETIRED as a precondition and must not be built.

`P04.S16` has since landed in two commits and is awaiting code review, which is why the
row is still open. The first shipped the persisted shape and the engine month rules and
declared itself incomplete by design, because nothing could write the field. The second
shipped the entry surface and, necessarily, the fix for a second aggregation path found
while building it: the derived-facts injector summed the annual spend fact under its own
inline age test and never read the canonical record, so the whole domain half had no
production consumer. Without that fix the entry surface would have been worse than the
gap it closes, because a taxpayer following the new advisory would have moved their
figure onto the monthly map and received nothing.

`P04.S17` was BLOCKED on per-child attribution of anualidades and has landed at the
staged boundary the ADR names, so the row is closed and its own BLOCKED clause is
likewise stale. It is REOPENED from retired. The ADR
retired the dependencia assimilation on the reasoning that the statutory carve-out for
judicial anualidades removes the one common household shape and that no reachable case
could be constructed, and both halves were refuted against the live authority: the
carve-out turns on anualidades actually being SATISFIED rather than on the regime being
available, and the authority states the no-custody non-paying supporter as entitled in
terms. The staged boundary the ADR names, and the one that shipped, is to assimilate
only where the filer declares no anualidades at all, which errs toward under-grant with
a visible advisory. Per-child attribution remains unbuilt, so the suppression is still
profile-wide rather than per-child. The existing incompatibility injector was swept in
the same change, because landing one half of an incompatibility pair is this campaign's
most frequently repeated defect.

`P04.S18`, `P04.S19` and `P04.S20` all came out of executing `S16` and are open and
unblocked. None may be folded back into `S16`: each is a separate load-bearing change,
and bundling any of them with a fix that was already inverting a live under-grant is the
risk the relocation discipline exists to refuse.

`S18` is the one with a hard shape requirement. The derived path and its binding are
named for the menor-de-tres population while carrying the guardería one, which is wider
by exactly the turning-three period, and the mismatch is now LOAD-BEARING because that
count is the cap term. It is a naming lie of the same class as a docstring asserting a
property the code lacks, which was this campaign's most repeated failure, and the only
reason it was not corrected in place is blast radius. The rename must land as ONE atomic
commit: the schema pattern, the binding TOML, the formula reference, the injector and
every M100 test fixture that supplies the binding id by name share one index and one
commit, with a clean collect-only observed immediately before it. Splitting it leaves
the tree uncollectable in between.

`S19` and `S20` are independent of `S18` and of each other. `S19` must decide rather
than defer: a derived property duplicating a registry formula in Python with no
production consumer is either dead code to delete or a second authority to enroll, and
leaving it as the third state is what this campaign has spent its time removing. `S20`
is operator-facing and self-inflicted, because the untranslated refusals reaching that
verb are the entry-date coherence rules this Phase itself shipped.

## Verification

The plan is complete when every Step is closed and all of the following hold: the two
new registry parameters resolve for every revision 2020-2025 and their legal-catalogue
entries pass the grounding gate; a descendant above the Art. 58.1 rentas cap contributes
zero to both aggregates; a household with two entitled filers receives a prorated
mínimo and an advisory naming the inference; the anualidades flag reads sin derecho for
a descendant excluded by the cap; and every expected figure in the new tests derives
from the bundled AEAT manual or the consolidated LIRPF text rather than from the
formula under test.

`P04` adds its own criteria. `S13` is verified: the closed relación set carries all five
members with the entitling subset declared once and derived everywhere, the retired
adoption-named date survives only in docstrings explaining the re-anchoring, and the cap
is measured rather than asserted, with a child fostered in 2019 and adopted in 2022
granted three periods and nothing after. The persisted-shape change carries a
save-load-strict-equality roundtrip over one record per relación with every defaultable
field set to a non-default value, plus an anti-tautology proof that deleting the stored
token changes the reloaded record and changes it toward under-grant rather than toward
entitlement. Coverage is structural rather than numeric, so nothing re-derives a
registry formula against itself; the monetary side stays grounded against the bundled
worked example, whose child is adopted and which therefore evidences the adopción route
only.

Three mutations were run against `S13` and each must turn the suite red: removing the
relación check from the entry-date resolver, making the coherence validator a no-op, and
switching the window anchor from the earliest entitling event to the latest. The first
initially left every test green, because the coherence validator makes that check
unreachable through the model, so a second-layer test constructing the forbidden record
directly was added. Any later change to these guards re-runs that probe rather than
reasoning about coverage.

`S14` is verified by a case table asserting the missing-anchor report stays silent
wherever nothing is lost: a descendant already under three, one the statute excludes
from the limb, one not cohabiting, and one over 25 with no discapacidad.

`S15` is complete when the Art. 81.1 window is date-scoped, a test shows it diverging
from the Art. 58.2 period-scoped window for the same child, AND the predicate has a
production consumer. The last clause is added because the first two are satisfiable by
dead code: two windows that agree on every case tried are indistinguishable from one
window, and a window nothing calls is indistinguishable from no window. The divergence
runs both ways for an inscription late in a year — the entry year is wholly inside the
Art. 58.2 window while its early months are outside the date window, and the fourth
calendar year is inside the date window and outside the Art. 58.2 one — so a test
exercising only one direction proves half the claim.

`S22` is complete when the declared maternidad months either reach a casilla or stop
being offered, and explicitly not when the entry surface merely documents that they do
nothing. Its verification is operator-facing: declaring the months through the
descendiente verb changes a computed value, or the verb no longer accepts them.
Whichever way `S21` resolves, the schema declaration and the entry surface must end
agreeing with the engine.

The rule that governed `S16` and `S17` stands and is restated because both have now been
closed against it: neither could be closed by narrowing its scope to the unblocked part,
because a campaign that narrows its own completion criterion reads as rigour while
leaving the gap open. Each was closed by the blocker ceasing to apply on measurement,
not by scope reduction. `S17`'s blocker still stands in part and its staged boundary is
recorded above rather than quietly redefined as the whole rule.

`S16` is verified by a proof that the declared map ARRIVES, not merely that it persists,
because the layer between the two is where it was broken. The end-to-end gate drives the
real CLI: declare a child turning three in April with monthly spend spanning the
birthday, calculate, and the guardería casilla resolves to the post-birthday months
alone. Nothing in that expectation re-derives the registry formula: the figure is the
arithmetic of the fixture's own declared months. The second aggregation path was
measured rather than argued, by replaying the superseded algorithm in process with no
tracked file mutated, which showed a monthly-only child yielding zero against a record
holding real spend, a turning-three child yielding a zero cap population, and the annual
path unchanged. Any later change to that injector re-runs that replay rather than
reasoning about coverage. The persisted-shape change carries a fact-boundary round-trip
plus an anti-tautology proof that four separately corrupted stored maps each REFUSE
rather than reading as undeclared, which is the dangerous fallback: an empty map in the
turning-three period withholds the whole increase.

`S16` also has a CLOSING condition, and it binds whoever closes the row rather than
whoever wrote it. The row may not be checked while its action text still states the
per-comunidad regional table as a blocker: correct that text in or before the closing
change. Both halves of the reason are needed, because a reader who gets only the first
will misread the second. The blocker is gone because it was RETIRED ON MEASUREMENT and
not because the Step was descoped: the determination belongs to the childcare centre,
which files the informative return reporting childcare custody, is required to apply its
own region's calendar, and reports the resulting months to the authority. The table was
therefore never this application's to build, and the Step landed at its full recorded
scope. Reading the correction as scope reduction is exactly what the no-narrowing rule
above forbids, and a row that still names a retired blocker is a trap for the reader who
trusts rows over prose, which is the ordinary reader, because the row is the structured
surface.

`S18` is complete only as one atomic commit, and its verification is the collect-only
gate observed clean immediately before that commit rather than after. A partial rename
is the failure mode, so a green suite on a split landing is not evidence. `S19` is
complete when the duplicate property is either deleted or given a production consumer,
and explicitly not when it is merely documented. `S20` is complete when a malformed
entry-date coherence flag reaches the operator as a translated refusal in all four
catalogues rather than a traceback, proven through the real CLI rather than by calling
the parser.
