---
tags:
  - '#plan'
  - '#minimo-descendientes-eligibility'
date: '2026-08-04'
modified: '2026-08-04'
body_hash: 'sha256:762777896d822162d22ca944e0833530a33485d4432f79fa5b324c093b456394'
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
- [ ] `P04.S15` - Give the Art. 81.1 maternidad adoption clause its own date-scoped three-year window, separate from the Art. 58.2 period-scoped one; `src/cadrumo/domain/contribuyente/family.py`.
- [ ] `P04.S16` - Model month-level guarderia spend as an optional sparse per-month map alongside the annual figure, refusing both at once for one child, BLOCKED on a per-comunidad regional table for when the second infant-education cycle may begin; `src/cadrumo/domain/contribuyente/family.py`.
- [x] `P04.S17` - Assimilate an economically dependent descendant where the filer declares no anualidades at all, sweeping the existing incompatibility injector in the same change, BLOCKED on per-child attribution of anualidades; `src/cadrumo/application/modelo/_profile_binding.py`.

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

`P04.S15` is open and unblocked. Both entry-event dates now exist, so the Art. 81.1
adoption clause can carry the date-scoped window it actually has rather than borrowing
the Art. 58.2 period-scoped one. The two genuinely diverge, and one predicate serving
both would silently apply one statute's window to the other's deduction.

`P04.S16` is BLOCKED and must not be started. The Art. 81.2 increase extends into the
period the child turns three, for spend incurred after the birthday and up to the month
before the second cycle of infant education may begin. That upper bound is a
per-comunidad regional determination rather than a fixed calendar month, grounded
against the live authority on 2026-08-04, so neither the persisted shape nor the engine
can hard-code one. Every pre-split shape would bake an unverified answer into stored
data. The blocker is the regional table, not the modelling, and it is a larger
precondition than the governing ADR originally recorded.

`P04.S17` is BLOCKED and must not be started. It is REOPENED from retired. The ADR
retired the dependencia assimilation on the reasoning that the statutory carve-out for
judicial anualidades removes the one common household shape and that no reachable case
could be constructed, and both halves were refuted against the live authority: the
carve-out turns on anualidades actually being SATISFIED rather than on the regime being
available, and the authority states the no-custody non-paying supporter as entitled in
terms. The blocker is per-child attribution of anualidades. The staged boundary the ADR
names is to assimilate only where the filer declares none at all, which errs toward
under-grant with a visible advisory. Whoever takes it must sweep the existing
incompatibility injector in the same change, because landing one half of an
incompatibility pair is this campaign's most frequently repeated defect.

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

`S15` is complete when the Art. 81.1 window is date-scoped and a test shows it diverging
from the Art. 58.2 period-scoped window for the same child. `S16` and `S17` are complete
only when their named blockers are cleared first, and neither may be closed by narrowing
its scope to the unblocked part: the ADR records both at full scope deliberately, and a
campaign that narrows its own completion criterion reads as rigour while leaving the gap
open.
