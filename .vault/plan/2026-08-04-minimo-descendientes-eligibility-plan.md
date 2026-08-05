---
tags:
  - '#plan'
  - '#minimo-descendientes-eligibility'
date: '2026-08-04'
modified: '2026-08-05'
body_hash: 'sha256:86e22b13827e65c11d02de9b2f6d0aa86129c734dd4a7482b45f51a07ffcc634'
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
- [x] `P04.S15` - Give the Art. 81.1 maternidad adoption clause its own date-scoped three-year window, separate from the Art. 58.2 period-scoped one, BLOCKED on S21 because nothing on the calculate path reads a descendant record for maternidad, so the predicate would land with no consumer and rebuild the dead shape S19 removed; `src/cadrumo/domain/contribuyente/family.py`.
- [x] `P04.S16` - Model month-level guarderia spend as an optional sparse per-month map alongside the annual figure, refusing both at once for one child, and route the calculate path through the canonical record so a declared map reaches the cap terms; `src/cadrumo/domain/contribuyente/family.py, src/cadrumo/domain/contribuyente/_guarderia_mensual.py, src/cadrumo/application/modelo/_profile_binding.py`.
- [x] `P04.S17` - Assimilate an economically dependent descendant where the filer declares no anualidades at all, sweeping the existing incompatibility injector in the same change, BLOCKED on per-child attribution of anualidades; `src/cadrumo/application/modelo/_profile_binding.py`.
- [x] `P04.S18` - Rename the derived guarderia cap-population path and its binding away from the menor-de-tres name it outgrew, in ONE atomic commit carrying the schema pattern, the binding TOML, the formula reference, the injector and every M100 fixture supplying the binding id by name; `src/cadrumo/_data/registry/cadrumo/user_profile/schema.toml, src/cadrumo/application/modelo/_profile_binding.py`.
- [x] `P04.S19` - Retire the dead advisory cluster on RentaFamilyProfile, opened on a partial measurement naming one property and widened on a fuller one to five members, including the maternidad method superseded by the live free function and the guarderia cap constant whose last Python consumer it is, replacing the cotizaciones-binds-the-cap assertion against the live registry path in the SAME commit; `src/cadrumo/domain/contribuyente/family.py, src/cadrumo/domain/contribuyente/tests/test_incremento_guarderia_0613.py, src/cadrumo/core/external_constants.py, src/cadrumo/core/tests/test_external_constants_centralisation_part2.py, src/cadrumo/locales/`.
- [x] `P04.S20` - Route the canonical-record refusals reaching the descendiente add verb to the operator, because the verb catches only the answer-type error and the boundary projects the rest to a GENERIC translated refusal that discards the validator's own sentence, so the entry-date coherence rules this Phase shipped told the operator nothing about which field conflicted, and the discarded detail was written to the error log carrying the declared record; `src/cadrumo/entrypoints/cli/_config/_descendiente.py`.
- [x] `P04.S21` - Decide whether the Art. 81.1 maternidad months are operator-asserted or engine-derived, because the engine never sees the descendants at all and takes an operator-supplied list of hijo and month pairs, so the under-three and cohabiting conditions cannot be enforced while the profile already holds the birth dates and cohabitation facts, and the answer may be a refusal, an advisory or a documented operator-asserted input but must be chosen rather than inherited, BLOCKING S15 whose window predicate has no consumer until this resolves; `src/cadrumo/application/modelo/_calculate_input.py, src/cadrumo/domain/contribuyente/family.py`.
- [x] `P04.S22` - Connect or retire the declared maternidad months, because an operator declaring MESES_TRABAJO through descendiente add or the guided flow gets nothing, the fact round-trips and rides the payload and is declared in the user-profile schema as a model selector while no formula targets casilla 0611 and no binding names the path, so a documented entry surface is today lying about what it does whichever way S21 resolves; `src/cadrumo/application/modelo/_calculate_input.py, src/cadrumo/_data/registry/cadrumo/user_profile/schema.toml, src/cadrumo/entrypoints/cli/_config/_descendiente.py`.
- [x] `P04.S23` - Add the Art. 81.1 post-birth alta increment, 150 euros for the month completing the 30-day contribution period, raising that child cap to 1.350 euros for filing years from 2023 only, gated on a new operator-supplied fact naming that month; `src/cadrumo/core/external_constants.py, src/cadrumo/domain/contribuyente/_deduccion_maternidad.py`.
- [x] `P04.S24` - Collapse the two family-record reconstructions in _profile_binding onto their UNION rather than onto either one, because each carries what the other lacks, the guarderia path pre-checks every birth date and raises naming the row index while omitting the anualidades that suppress dependency assimilation, and the minimo and maternidad path carries the anualidades while having no pre-check, so collapsing onto the minimo variant silently loses the indexed diagnostic and collapsing onto the other silently over-grants for a filer paying judicial anualidades, and adding anualidades to the guarderia injector must be recorded as a stated no-op since the guarderia count does not read them; `src/cadrumo/application/modelo/_profile_binding.py, src/cadrumo/domain/contribuyente/family.py`.
- [ ] `P04.S25` - Escalate the stale ley-35-2006 art-81 corpus excerpt for operator refresh, because its apartado 1 carries the post-2023 widened supuestos while its apartado 2 still carries the cotizaciones ceiling the bundled AEAT manual states was removed from 2023, and the 150 euro post-alta increment is absent entirely, so the excerpt is a two-vintage hybrid that cannot gate the required_text for any clause S15 or S23 implement; `src/cadrumo/_data/corpus/normatives/html/ley-35-2006-art-81.html`.
- [x] `P04.S26` - Apply the pre-2023 cotizaciones ceiling to the computed casilla 0611 for filing years 2020 to 2022 only, or refuse to compute it for those years, because the law in force through 2022 additionally limited the deduction to the mother total Seguridad Social cotizaciones while the computation applies only the 1200 euro cap, and although the un-ceilinged arithmetic predates this campaign the wiring changed the exposed population from operators who explicitly typed the calculate flag to every operator with declared descendant months, so the defect is now reachable by default rather than newly created, and the registry declares the cotizaciones binding only in 2024 so it cannot express the ceiling for the affected years at all; `src/cadrumo/domain/contribuyente/_deduccion_maternidad.py, src/cadrumo/application/modelo/_profile_binding.py`.
- [x] `P04.S27` - Author the Art. 61 norma 4a flat minimo figure as its own registry money parameter across the served revisions with a legal-catalogue entry anchored to the bundled corpus, and do NOT bind it to the first birth-order tranche despite both being 2400 in every current revision, because they are legally distinct figures that merely coincide and binding them would silently move the death amount if a future reform moved the tranche; `src/cadrumo/_data/registry/aeat/modelos/100/revisions/*/parameters/, src/cadrumo/_data/registry/aeat/legal/`.
- [x] `P04.S28` - Clip the Art. 81.1 month union to the Art. 58.2 anchor so no month before the adopcion or acogimiento is granted, because the under-three limb runs from the BIRTH month for every relacion so the union reaches months in which the child was not yet the filer's, and replace the union test whose docstring claims neither limb alone reaches twelve while its own first assertion proves the infant case reaches twelve, so the test is green while blessing the over-grant; `src/cadrumo/domain/contribuyente/family.py, src/cadrumo/domain/contribuyente/tests/test_deduccion_maternidad_0611.py`.
- [x] `P04.S29` - Declare the Art. 81.1 population as its own closed set in core and gate the maternidad months on it, because the deduction is gated only on is_eligible_ordinary which is the Art. 58.1 test and deliberately assimilates temporal acogimiento, while the AEAT manual states the deduction no resulta aplicable to acogimientos familiares simples de urgencia o temporales nor to nietos y demas descendientes por consanguinidad distintos de los hijos; `src/cadrumo/core/_descendant_relacion.py, src/cadrumo/domain/contribuyente/family.py`.
- [x] `P04.S30` - Re-scope every operator-facing description of MESES_TRABAJO to state both Art. 81.1 limbs, because the wizard help the calculate flag help and the descendiente grammar all scope the question to a child under three so an operator answering as asked enters zero for an over-three adoptee and receives nothing, leaving the entry window reachable only by an operator who contradicts the prompt, updating the four catalogues through the locales CLI; `src/cadrumo/locales/, src/cadrumo/entrypoints/cli/_config/_descendiente.py, src/cadrumo/application/wizard/`.
- [x] `P04.S31` - Correct the withheld-maternidad advisory which states the deduction reaches only a descendant under three, falsified by the date-scoped window landed three commits later, and which closes by inviting the operator to correct the birth date when for an over-three adoptee with no inscription recorded the real gap is a missing entry date, so the advisory currently steers a filer toward altering a birth date to make a figure land; `src/cadrumo/application/modelo/_calculate_input.py, src/cadrumo/locales/`.
- [x] `P04.S32` - Fire the withheld and ceilings-unresolved advisories even when the calculate flag is supplied and refuse on the pre-filter declares_meses rather than the post-filter pairs, because pairs is already filtered to eligible months so a profile whose every declared month is withheld reaches neither the refusal nor the advisory and the flag wins silently, which is the one branch where the operator most needs to be told their records were rejected; `src/cadrumo/application/modelo/_calculate_input.py`.
- [x] `P04.S33` - Point the two-authorities refusal and the withheld advisory at a route that can actually edit a declared descendant, because both name descendiente add which only appends rows while the paged editing door refuses on a piped host, so the documented remedy is not actionable for the autonomous-agent operator this CLI is built for; `src/cadrumo/locales/, src/cadrumo/entrypoints/cli/_config/_descendiente.py`.
- [x] `P04.S34` - Retire the calculate-time maternidad flag so casilla 0611 has one authority, because the flag carries a free-form hijo id that no descendant record answers to and is today reconciled only by a mutual refusal, which contains the two-authority hazard without removing it, and the refusal is what currently blocks 0611 from becoming registry-computed like its 0613 sibling; `src/cadrumo/application/modelo/_calculate_input.py, src/cadrumo/entrypoints/cli/_modelo_work_calculate_cli.py, src/cadrumo/locales/`.
- [ ] `P04.S35` - Reopen the 0611 registry-computation question because its closure rested on a false premise, the claim that 0613 cap never varies per child being a description of the un-prorated formula rather than of the law, since the manual prorates that cap by each child qualifying months so both casillas do share a rule shape, and decide the question again once the proration defect is fixed rather than citing the earlier reasoning; `src/cadrumo/_data/registry/aeat/modelos/100/revisions/2024/formulas/`.
- [x] `P04.S36` - Restore the erased typing in the prorrata advisory test, replacing tuple of object with the typed diagnostic tuple and the kwargs splat with explicit keyword parameters, and delete all six type-ignore directives, because a peer commit titled as an index refresh degraded a campaign test to compile against a widened DescendantInfo rather than updating its fixtures, while a sibling test in the same surface was moved the OPPOSITE way on the same convention the same day; `src/cadrumo/application/modelo/tests/test_minimo_descendientes_prorrata_inferred_advisory.py`.
- [x] `P04.S37` - Add the judicial guarda y custodia relacion member, which is a distinct legal basis the authority names positively and which the whole-enum default keeps out of the Art. 81.1 set for free, and do NOT add a grandchild member because hijo and nieto differ by generational degree rather than legal basis so encoding degree on a relationship-type axis is the fragmentation this campaign removes; `src/cadrumo/core/_descendant_relacion.py, src/cadrumo/domain/contribuyente/family.py`.
- [x] `P04.S38` - Advise or confirm at the point working months are declared that the child is a hijo rather than a grandchild or a minor under judicial guarda, because the ordinary predicate never reads relacion so both populations compute correctly for Art. 58.1 and 58.2 while only Art. 81.1 over-grants, and the over-grant additionally requires declared months, so that narrow conjunction reaches every already-stored record which no new enum member can do; `src/cadrumo/application/modelo/_calculate_input.py, src/cadrumo/entrypoints/cli/_config/_descendiente.py, src/cadrumo/locales/`.
- [x] `P04.S39` - Model both limbs of the fallecimiento rule in one slice, the death date on the descendant record with its roundtrip and anti-tautology proof, the flat amount REPLACING THE TRANCHE ONLY while the menor-3 supplement still accrues on top because the manual states the increment applies where the descendant died in the period so a deceased-equals-2400-full-stop reading under-grants, the exclusion of the deceased from the survivor ordering which is conditioned on death BEFORE devengo where the flat amount is not, and an entry surface shipping with the field; `src/cadrumo/domain/contribuyente/family.py, src/cadrumo/domain/contribuyente/_descendant_facts.py, src/cadrumo/_data/registry/cadrumo/user_profile/schema.toml, src/cadrumo/entrypoints/cli/_config/_descendiente.py`.
- [ ] `P04.S40` - Prorate the Art. 81.2 guarderia increment per child by the intersection of the child age-eligible months, which are computable per month from the birth date, with the declared spend months where a monthly map exists, then bound by the mother qualifying-month count and by that child own non-subsidised spend, and for a child declaring only an annual total use the age-eligible month count as the proration basis rather than assuming twelve or refusing, disclosing the approximation as an advisory in both cases because the mother employment months are a count and their simultaneity cannot be verified until S44 gives them month identity; `src/cadrumo/_data/registry/aeat/modelos/100/revisions/2024/formulas/, src/cadrumo/domain/contribuyente/family.py, src/cadrumo/application/modelo/_profile_binding.py, src/cadrumo/application/modelo/_calculate_input.py`.
- [x] `P04.S41` - Bound the interpolated descendant list in both maternidad advisories the way the accepted-set hint in the same module already is, because their length is dynamic rather than static so each grows one entry per descendant and crosses the 512 character diagnostic cap at 13 and at 25 descendants respectively, surfacing a raw pydantic ValidationError to the operator and stopping the filing outright, and add tests constructing each above those counts rather than at a single index; `src/cadrumo/application/modelo/_calculate_input.py`.
- [ ] `P04.S42` - Add guided-walk pages for the alta-posterior completion month and the fallecimiento date, because both facts exist only in the descendiente flag grammar so an operator using the guided door or the setup flow is never asked, making the 150 euro increment and the 2400 euro flat minimo unreachable that way, and correct the S39 exec record which claims an entry surface while silently narrowing it to the flag; `src/cadrumo/application/wizard/_descendant_group.py, src/cadrumo/locales/`.
- [x] `P04.S43` - Amend the S16 exec record heading which still names the regional table as a blocker the plan retired in terms, and the Parallelization paragraph which says S16 is still open while its row is checked, because the exec record is now the surviving carrier of exactly the stale premise the plan warns readers not to reinstate; `.vault/exec/2026-08-04-minimo-descendientes-eligibility/, .vault/plan/2026-08-04-minimo-descendientes-eligibility-plan.md`.
- [ ] `P04.S44` - Give the Art. 81.1 qualifying months month identity rather than a bare count, because the guarderia increment prorates by the months in which 81.1 and 81.2 hold SIMULTANEOUSLY and only the 81.2 side records which months those are, so the intersection cannot be computed and the minimum of the two counts is an upper bound that over-grants whenever the two spans do not overlap, and this is a persisted-shape change carrying its own roundtrip, anti-tautology and entry-surface obligations; `src/cadrumo/domain/contribuyente/family.py, src/cadrumo/domain/contribuyente/_descendant_facts.py, src/cadrumo/_data/registry/cadrumo/user_profile/schema.toml, src/cadrumo/entrypoints/cli/_config/_descendiente.py, src/cadrumo/application/wizard/`.
- [ ] `P04.S45` - Author the Art. 81.2 annual cap as a registry money parameter across the served revisions with its legal-catalogue grounding, because the 1000 figure exists only as an inline literal inside the 0613 formula which registry TOML can read but the application layer cannot, so the injector that must call the prorated aggregate has no way to obtain it, and this is regulatory-value authoring with its own grounding obligations rather than wiring; `src/cadrumo/_data/registry/aeat/modelos/100/revisions/*/parameters/, src/cadrumo/_data/registry/aeat/legal/`.
- [x] `P04.S46` - Cut the prose of the two over-cap advisories, the Art. 58.2 anchor one whose static floor is 528 against a 512 cap so it cannot be constructed for any input and crashes calculate for a single adopted descendant with no entry date, and the guarderia spend-shape one which crosses at three affected descendants, because the domain layer documents the missing-entry-date state as VALID on the express promise of a visible advisory that cannot exist; `src/cadrumo/application/modelo/_minimo_descendientes_advisory.py`.
- [ ] `P04.S47` - Make the diagnostic cap structural rather than enumerated, either by truncating in the constructor or by a gate that builds every registered advisory factory at zero, one, three and fifty descendants and asserts validity, because sixty hand-written messages measured against a silent cap will drift again on the next copy edit and the bounded-list fix that already landed sits nineteen characters under the cap so one added clause re-crashes it; `src/cadrumo/application/aggregation/_source_mesh.py, src/cadrumo/application/modelo/tests/`.
- [ ] `P04.S48` - Stop the calculate boundary projecting an internal ValidationError to the generic CLI-validation refusal, because the operator is told to check arguments that are correct while the real cause reaches only the error log, which is the same defect S20 fixed for the descendiente add verb still live on calculate; `src/cadrumo/entrypoints/cli/, src/cadrumo/application/modelo/_calculate_input.py`.

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

`P04.S16` landed in two commits and its row is now checked; the sentence that once said
otherwise is corrected here rather than left to contradict the row it describes. The
first shipped the persisted shape and the engine month rules and
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

`S24` came from the axis-7 semantic-overlap pass, which this campaign had never actually
run. Every canonicalization before it was reactive — found while doing something else —
so the duplication set had never been enumerated independently of the work, and no
completeness claim over it was available. Searching by MEANING rather than by symbol
returned the record-reconstruction concept at three sites across two layers. Two are
sound and are worth recording as such: the wizard re-projection delegates to the
canonical `descendant_list_from_facts` and says so in its docstring, and the four
eligibility predicates share one home with documented reasons for staying apart. The
third is the finding. `_profile_binding` builds the same family record twice, and the
two constructions diverge in two independent ways — the guardería path pre-checks each
birth date by index but omits the anualidades that suppress dependency assimilation,
while the mínimo and maternidad path carries anualidades but skips the pre-check. One
half is live and operator-facing: the same malformed stored birth date names its row on
one path and not the other, decided purely by which wrapper the caller reaches. The
other half is latent rather than a wrong number, because `is_eligible_guarderia` reads
only cohabitation and age and cannot see the omission; it is recorded for its shape, not
its impact, since a record built two ways where one silently defaults a SUPPRESSING
field is precisely what bites when a predicate widens — and this campaign has now met
the widening-population shape three separate times. `S24` is held behind `S18` because
both move the same file and `S18` must move it atomically.

`S18` was attempted and stopped before its first edit, and two things it established
must not be lost. The first corrects this plan's own instruction. The dead-looking
binding-compatible property on the family record was to be deleted if dead and renamed
if live — but renaming it would be wrong even in the live case, because it delegates to
the STATUTORY Art. 58.2 count while the binding it names is fed the wider guardería
population. The two disagree about the VALUE, not merely the name, so a rename would
preserve a method computing the wrong count for the binding it serves. The live branch
is therefore "re-point at the guardería count", never a rename. The property was found
to have zero Python references and resolution to run entirely through the fact index,
so it is dead on static evidence; the dynamic confirmation is still owed.

The second is why `S18` cannot be forced. Its verification is a clean collect-only
observed immediately before its atomic commit, and the working tree could not produce
one: an uncommitted `descendiente` description of 554 characters against a 512 cap made
`load_user_profile_schema()` raise, so the profile schema did not load at all and every
profile-binding consumer failed on a length constraint that named nothing about the
change causing it. Re-measuring a baseline against that tree would have recorded a
peer's breakage as this Step's. Nor is the apply-cached route available: it stages one
agent's hunks while leaving the other's working tree stale, so the next pathspec commit
of the same file silently reverts the rename — and this rename degrades silently rather
than raising, which is exactly the half-reverted state `S18`'s atomicity requirement
exists to prevent.

The collision itself was a planning error rather than a discovery. `S23`'s scope clause
names only the constants module and the deducción helper, while the Step as briefed
required the family record, the profile-binding injector and the profile schema — the
three files `S18` must move. The scope line understated the work, and a file-set
disjointness proved before `S23` began was then relayed to `S18` as a standing fact.
`S18` is released only when those three files are clean and a fresh baseline is taken.

`S18`'s stated verification — a clean whole-tree collect immediately before the atomic
commit — became unsatisfiable by anyone while it waited, and the substitute is recorded
here rather than left to the executing agent's discretion. A broad peer checkpoint
commit stripped a constant from a registry test-support module while leaving its
consumer's import standing, so the whole-tree collect is red **at HEAD**. Narrowing the
gate to `S18`'s own packages does not rescue it: the broken module sits inside
`domain/calculations/registry`, which holds sixteen of the twenty-four consumer test
files, so that package cannot be dropped from the scope either. The workable gate is
therefore an IDENTITY requirement rather than a cleanliness one — scoped and whole-tree
collect captured immediately either side of the commit, with the error set required to
be identical in count and signature, the single member being the peer's missing
constant. Any second signature is the Step's. That preserves what the original gate was
for, which is proving the Step introduced nothing, and abandons only the part that
proves the tree is healthy — which is not currently in anyone's gift. It is weaker in
an absolute sense and the Step record must say so rather than let a green read as more
than it is.

Two consequences follow for how `S18` is evidenced. Because sixteen of twenty-four
consumers sit in one package, a scoped test run would look convincing while missing the
eight in `application/filing`, `application/modelo` and `entrypoints/cli`; so the
zero-hit `rg` check on both retired names stays the primary evidence and the test runs
stay secondary. And both lanes must run, because a marker-selected green over a rename
is worthless.

The `S24`-before-`S18` ordering holds, but not for the reason first given. `S18` renames
exactly one key-building site either way, so there was never a two-call-site version.
The real argument is adjacency: the key is built at `_profile_binding.py:273` and the
reconstruction it feeds is called five lines below at `:278`, inside the same function
body, while the other reconstruction is called elsewhere entirely. Ordering `S18` first
would mean two separate edits to one hunk and two chances to disturb it.

`S40` is being landed in coherent pieces rather than as one atomic commit, and the
contrast with `S39` is the point. `S39` had to be atomic because a persisted field
without a writer is a dead shape — half of it is a defect. Here the failure mode is the
opposite: the registry formula keeps its current behaviour until a binding feeds it, so
each piece is independently verifiable and none half-grants anything. Two pieces have
landed and neither changes a computed value, verified rather than asserted — the
formula is untouched at HEAD. Taken atomically the choice would have been between
rushing the piece that changes live behaviour and reverting the two that do not.
Atomicity is a property to argue for per change, not a default.

The proration basis mirrors the existing spend method rather than re-deriving the month
selection, because the two answer one question about one set of months, in euros and in
count; a test declaring spend only in months the turning-three extension excludes
catches a method that counts the right NUMBER of wrong months, which a count-only
assertion would pass. The per-child cap carries both manual oracles and two assertions
the oracles cannot supply: that the cap binds per child, since a household-wide minimum
hands a lightly-enrolled child's unused allowance to a heavily-enrolled sibling with no
entitlement to it, and the flat-cap delta pinned at its euro figure so a regression
fails with the number that motivated the fix rather than an opaque one.

`S45` exists because of a wrinkle the row did not anticipate: the annual cap figure
lives ONLY as an inline literal inside the formula, which registry TOML can read and
the application layer cannot. The injector that must call the prorated aggregate has no
way to obtain it, so it has to be authored as a money parameter with legal grounding
and per-year citations. That is regulatory-value authoring with its own obligations
rather than wiring, which is why it is a row rather than a step inside one.

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
