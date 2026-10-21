---
tags:
  - '#audit'
  - '#registry-temporal-coverage'
date: '2026-09-01'
modified: '2026-10-14'
body_schema: 'body-v2'
body_hash: 'sha256:dbeb7231fca3ee02afb304ceb64a31c3ed7624b8200e85ed9e759b376d0c003c'
related:
  - "[[2026-08-14-registry-temporal-coverage-authority-grade-coverage-adr]]"
  - "[[2026-08-14-registry-temporal-coverage-adr]]"
  - "[[2026-06-10-period-revision-resolution-adr]]"
  - "[[2026-08-31-period-revision-resolution-ad-hoc-operation-date-axis-adr]]"
---
# `registry-temporal-coverage` audit: `Live remeasurement of the registry coverage surface and the re-grounding the proposed coverage ADR now needs`

## Scope

This live remeasurement began on 2026-09-01 during import centralisation and continued
through the append-only entries in this audit. An orchestrating pass and an independent
pass measured the registry separately. Later entries correct or withdraw earlier
conclusions; the last supported state on a subject controls.

The audit covers temporal declarations and their site agreement, revision identity,
identifier grammar, continuity, derived export surfaces, wire types and monetary scale,
capability grade, provenance, and filing-export proof. It does not assess tax amounts
against AEAT or claim correctness for calculation-engine results. Four findings compare
internal readings with official AEAT designs; those comparisons corrected internal
counts and exposed the filing-byte defects described below. Tooling can identify a
candidate; the official design remains the authority.

## Findings

### Live baseline and evidence boundary

The proposed coverage ADR was stale at the live worktree: its private module paths no
longer resolved, its measured corpus was 97 revisions across 73 models with 66
open-ended, while the live first-pass population was 128 revisions across 58 models with 49 open-ended. The
audit later corrected this component to 54 open-ended / 28 filing-grade under the
no-closing-date-or-selector-year definition (finding 053). Finding 180 shows that 49 of those 54 have a
selector year_from and actually extend; five without selector bounds stop at their named year. The former
premises about model-specific schema
and applicability literals
had also been removed. The ADR therefore needs re-grounding before it can authorize
work; this audit does not alter accepted decisions.

The two-channel filing-export proof apparatus was present but enrolled no official
coordinates or conformance vectors. Offline closure reported one satisfied revision
and 127 refused, was not release-eligible, and refused the export limb for all 68
filing-grade revisions. The generated-provenance verifier also called a method its
source type did not define. No shipped byte was proven against an official record
design. Empty proof input is fail-closed by design; it is not evidence that the proof
channel is complete or that production output matches AEAT.

Temporal selection resolved 1,727 of 1,729 probes; two same-modelo coordinates were
ambiguous for filing year 2011. The registry declared 843 deadline windows. The first-pass count was 49
open-ended revisions, 27 filing-grade with fixed-width layouts. Finding 053 later remeasured 54/28 using the
definition that a revision has neither a closing date nor a closing selector year. Revision identity,
explicit bounds, period selectors, deadlines, source
applicability, legal dates, global horizon and enrolled years expressed temporal facts
at separate sites.

Three identifier grammars coexist—numeric, dotted and boxed—and 21 models mix grammars.
All 29,522 casillas were classifiable, but the schema's alias field was unused and the
numeric alias was restated. Provenance was repeated across eleven surfaces: 14,817
casillas restated revision legal references and 6,872 cited legal sources absent from
their revision manifest, 6,634 of those in one model. The later schema-led walk covered
all 19 declared families; the manifest is a summary of child citations, not a constraint
on them. No provenance reference in the completed walk was dangling.

Wire-type measurements changed between passes. The corrected loaded-authority count
was 3,349 of 8,075 fields, with 33 type transitions; money-to-decimal and
ratio-to-decimal dominated. Monetary-scale candidates narrowed from 3,069 to 156 and
then to 24 true unscaled fields after controls. Direct source comparison established
live filing defects, including Modelo 200 casilla 03594 and Modelo 353 casilla 10
(m353-2026.pagina01.f127). The earlier counts and root-cause claims are not current
facts. Six published export trees initially failed reproduction; after repair, 21 of 27
were byte-identical, four differed only in provenance and two had record drift. The
drift was real and must not be resolved by blind republication.

Capability screening initially overstated variable-envelope blockers. Reclassification
separated typed envelopes from record-spelled envelopes and found that the filing-
product identity requirement was absent for 31 records. Twenty-five layouts were below
filing grade, five filing revisions lacked deadlines, and two models carried published
filing bytes while declaring they could not file. Release eligibility lived in dev
tooling rather than the application. These are distinct conditions: a tree's presence,
a grade declaration, a deadline and official output proof do not imply one another.

### Stable finding register

The register below retains every stable finding ID exactly once, with its severity and
title, in original source order and under the source section where it appeared. The
chronology after Recommendations records major status changes, corrections, withdrawals
and measured outcomes. Later evidence supersedes an earlier title where the chronology
says so; no accepted ADR authority is changed.

##### Original Findings (source order 001–131)
- [001] adr-premises-overtaken-by-refactor | critical | The proposed coverage ADR rests on three premises that the live tree no longer exhibits
  Evidence: Three proposal premises no longer matched the live tree: schema branch absent, one residual applicability literal rather than 27, and matrix coverage. Disposition: status not explicit in this entry; see source-order
    chronology (source order 001).
- [002] adr-cites-renamed-private-modules | high | Every source path the proposed ADR cites has been renamed and no longer resolves
  Evidence: None of them exists in the live tree. Disposition: status not explicit in this entry; see source-order chronology (source order 002).
- [003] stale-population-figures | high | The revision and modelo populations underneath the proposed decision have moved materially
  Evidence: ADR: 97 revisions/73 models/66 open-ended; live first pass: 128/58/49. Finding 053 later corrects the open-ended part to 54/28. Disposition: partly corrected by finding 053; live counts 128/58 with open-ended count
    54/28 (source order 003).
- [004] filing-export-proof-channel-unenrolled | critical | The two-channel filing-export proof is fully built and contains zero enrolled coordinates
  Evidence: No proof coordinates or vectors; closure 1 satisfied/127 refused and all 68 filing-grade revisions refused the export limb. Finding 027 says empty is deliberate fail-closed; 028 records the missing official reference.
    Disposition: empty proof is an intentional refusal; independent reference acquisition remains blocked (source order 004).
- [005] generated-provenance-verifier-raises | high | The generated-source verifier calls a method its source type does not define
  Evidence: The call raises, which prevents the generated provenance path from verifying. Disposition: status not explicit in this entry; see source-order chronology (source order 005).
- [006] conformance-tool-unrunnable-and-ungated | high | The registry conformance tool cannot run as documented and no standing regression gate remains
  Evidence: Dead baseline and ratchet classes remain in the manager module. Disposition: open or blocked as titled (source order 006).
- [007] temporal-fact-declared-on-six-axes | high | The same temporal fact is declared at six or more sites reconciled by agreement validators
  Evidence: A revision's temporal validity is expressed through the revision directory name, an explicit valid-from and valid-to pair, a period selector carrying its own year bounds, per-year deadline windows numbering 843…
    Disposition: status not explicit in this entry; see source-order chronology (source order 007).
- [008] revision-directory-names-misstate-their-windows | medium | Directory names are read as temporal facts and several of them are wrong
  Evidence: Initial examples expanded to 14 mismatches in finding 026: four opening-year errors, seven open-ended names and three scheme IDs. Disposition: status not explicit in this entry; see source-order chronology (source
    order 008).
- [009] open-ended-revisions-claim-unbounded-future-validity | high | Forty-nine revisions assert validity for years no evidence covers
  Evidence: The 49/27 figure was the first-pass total. Finding 053 corrects it to 54/28; finding 180 shows only 49 of 54 actually extend, while five stop at their named year. Disposition: count and selectability clarified by
    findings 053/180; evidence horizon remains open (source order 009).
- [010] revision-selection-can-be-ambiguous | medium | Selection ignores declared validity bounds unless an operation date is supplied
  Evidence: Across 1729 probed coordinates, 1727 resolve and 2 refuse as genuinely ambiguous, both on one modelo at filing year 2011. Disposition: status not explicit in this entry; see source-order chronology (source order 010).
- [011] scheme-axis-occupies-the-revision-slot | medium | One modelo encodes a scheme rather than a period in its revision identifier
  Evidence: The revision slot is carrying a non-temporal axis, which the surrounding temporal machinery cannot represent honestly. Disposition: status not explicit in this entry; see source-order chronology (source order 011).
- [012] raw-fragment-reads-understate-export-wiring | medium | Two earlier findings were measurement artefacts of reading authored fragments instead of derived layouts
  Evidence: Derived layouts measured 88.8%, 88.9%, 93.4% and 95.6%; zero/filler claims were withdrawn, while a separate 17.4% result remained. Disposition: two claims withdrawn; distinct 17.4% result remains (source order 012).
- [013] cross-pass-figure-discrepancies | low | Two independent passes disagree on three counts, all resolved in favour of the second
  Evidence: The two measurement passes disagree on three figures: revisions carrying both a fixed-width layout and calculation grade, reported as 57 across 25 modelos and as 62 across 28; bound casillas, reported as 730 and as…
    Disposition: closed or resolved as titled (source order 013).
- [014] closure-predicate-does-not-ship | high | The release-eligibility predicate lives in contributor tooling, not in the application
  Evidence: The application registry package's closure module is 157 lines of pydantic models and defines no functions. Disposition: status not explicit in this entry; see source-order chronology (source order 014).
- [015] export-ref-symmetry-is-unenforced | medium | Eighteen casillas declare an export reference no derived field satisfies
  Evidence: The initial 18-reference residue was withdrawn by finding 021 after record-level row mapping; full resolved residue is zero. Disposition: withdrawn by finding 021; complete resolved residue is zero (source order 015).
- [016] casilla-identifier-grammar-is-unvalidated | high | Three identifier grammars coexist and twelve modelos mix two of them
  Evidence: Initial survey: three grammars/12 models; finding 029 completes the census at five grammars/21 models across 29,522 casillas; none unclassified. Disposition: remeasured by finding 029: five grammars, 21 models, no
    unclassified IDs (source order 016).
- [017] provenance-is-restated-at-eleven-sites | high | One citation is re-declared across eleven surfaces with no parent-to-child consistency check
  Evidence: Measurement found 14817 casillas restating their own revision's legal references verbatim, and 6872 casillas citing sources that do not appear in their revision's manifest, of which 6634 belong to one modelo.
    Disposition: status not explicit in this entry; see source-order chronology (source order 017).
- [018] applicability-sites-are-unreconciled | high | Seven surfaces express applicability and nothing checks them against each other
  Evidence: Nothing reconciles the rule, the schedule and the window against one another. Disposition: status not explicit in this entry; see source-order chronology (source order 018).
- [019] wire-type-divergence-is-undeclared | medium | Derived export fields commonly declare a different data type than the casilla they render
  Evidence: Initial 3,043/7,709 count was indicative; finding 023 remeasures 3,349/8,075 across 33 transitions, excluding row-mapped endpoints. Disposition: remeasured by finding 023: 3,349/8,075 across 33 transitions (source
    order 019).
- [020] second-pass-claims-requiring-correction | low | Three claims from the verification pass did not reproduce and are corrected here
  Evidence: A reported 384 casillas with unsatisfied export references reproduces as 18: the reported count for the largest contributing modelo was 366 and its true value is zero, because that modelo's linkage resolves through a…
    Disposition: corrected or remeasured as titled (source order 020).
- [021] export-ref-symmetry-finding-withdrawn | medium | The eighteen unsatisfied export references were also a resolution artefact and the true residue is zero
  Evidence: All 18 apparent misses are satisfied by record-level repeated-row mapping; full resolved residue is zero. Disposition: status not explicit in this entry; see source-order chronology (source order 021).
- [022] resolved-surface-has-no-single-accessor | high | Nothing in the tree returns the complete set of casillas an export layout carries
  Evidence: This is the same fragmentation the identity, provenance and applicability findings describe, appearing on the export edge, and it is the one instance where the cost has been measured directly in defective conclusions.
    Disposition: status not explicit in this entry; see source-order chronology (source order 022).
- [023] wire-type-divergence-remeasured | medium | The wire-type divergence is confirmed and larger than first reported, across thirty-three distinct transitions
  Evidence: Resolved surface: 3,349 of 8,075 transitions differ; 33 pairs, including 2,140 money-to-decimal and 619 ratio-to-decimal. Disposition: status not explicit in this entry; see source-order chronology (source order 023).
- [024] parity-gate-partial-surface-is-latent-not-live | low | The narrow surface reader is a real hazard with zero current instances
  Evidence: Measured across the whole corpus, the count of such casillas is zero: the 366 projection-only casillas all sit outside their revision's completeness manifest, and no manifest casilla anywhere is invisible to the…
    Disposition: status not explicit in this entry; see source-order chronology (source order 024).
- [025] closure-predicate-relocation-is-not-atomically-possible | medium | The release predicate cannot move while two of its consumers are held by another contributor
  Evidence: The work is ready and blocked on those two files, not on any unresolved design question. Disposition: open or blocked as titled (source order 025).
- [026] revision-name-mismatches-remeasured | medium | Fourteen revision names disagree with their declared window, not six
  Evidence: Four misstate their opening year: one names 2025 and opens in 2023, one names 2025 and opens in 2026, one names a span beginning 2008 and opens in 2022, and one names 2013 and opens in 2012. Disposition: remeasured by
    finding 026: 14 name/window mismatches (source order 026).
- [027] export-proof-emptiness-is-deliberate-and-fail-closed | medium | The empty proof enrolment is designed refusal, not an oversight, and the finding above is re-framed
  Evidence: Finding 027 reframes empty proof inputs as designed typed refusals; no byte is proven, and finding 028 leaves official-reference acquisition as the blocker. Disposition: empty input is deliberate fail-closed behavior;
    no byte is proven (source order 027).
- [028] export-proof-enrolment-is-blocked-on-evidence-not-engineering | high | No official emitted-byte reference exists in the corpus for any modelo
  Evidence: The consequence is that this work cannot be completed by engineering. Disposition: blocked on independent official emitted-byte reference acquisition (source order 028).
- [029] identifier-grammar-remeasured | high | Five grammars are in use and twenty-one modelos mix them, not three and twelve
  Evidence: Five grammars across 29,522 casillas; 21 models mix them and no shipped identifier is unclassified. Disposition: status not explicit in this entry; see source-order chronology (source order 029).
- [030] temporal-site-agreement-measured | high | Deadline declarations are the fragmented axis's weak point, and the earlier example was wrong
  Evidence: The example given in the applicability finding above is withdrawn. Disposition: status not explicit in this entry; see source-order chronology (source order 030).
- [031] continuity-integrity-is-sound-and-my-sequencing-claim-was-wrong | medium | No continuity chain crosses an identifier grammar, so the identifier decision does not gate continuity work
  Evidence: The corpus carries 1294 continuity chains over 6090 casillas, with 3122 evolution records. Disposition: status not explicit in this entry; see source-order chronology (source order 031).
- [032] monetary-scale-undeclared-on-156-fields | high | A monetary amount is emitted with no scale anywhere in the registry, concentrated in four modelos
  Evidence: The screen that measures this initially reported 3069 fields, because it counted every monetary casilla that declared no decimal count including those rendered as money, where the codec supplies the scale. Disposition:
    status not explicit in this entry; see source-order chronology (source order 032).
- [033] money-rendered-as-text-is-faithful-to-the-official-design | medium | The suspicious wire type is correct and the missing scale is the whole defect
  Evidence: Official-design comparison confirms the text wire type is correct; the missing scale is the defect. Disposition: status not explicit in this entry; see source-order chronology (source order 033).
- [034] monetary-scale-defect-is-24-fields-not-156 | high | Most of the apparent gap is the official part split, and the render profile cannot express the rest
  Evidence: The published figure for this condition has now been 3069, then 156, and is 24. Disposition: open or blocked as titled (source order 034).
- [035] one-casilla-emits-euros-where-its-siblings-emit-cents | critical | A filing-grade 2026 revision renders one amount unscaled beside five identical fields that are scaled
  Evidence: The design for the 2026 revision of the IVA group-of-entities aggregate declares six consecutive liquidation amounts at positions 1126, 1143, 1160, 1177, 1194 and 1211, each seventeen positions wide and each typed…
    Disposition: status not explicit in this entry; see source-order chronology (source order 035).
- [036] sibling-comparison-is-a-gate-class-nothing-else-covers | medium | Comparing declarations against each other finds what comparing them to a rule cannot
  Evidence: Its test says so explicitly and says what must replace it once the defect is corrected, at which point the condition becomes gateable at zero like the others. Disposition: open or blocked as titled (source order 036).
- [037] cross-revision-scale-drift-is-not-worth-gating | low | The only drift the corpus contains is legitimate design evolution, so the screen was not built
  Evidence: The property-record operation amount of one informativa reads as unscaled in the revision covering 2011 to 2024 and as cents in the revision from 2025 onward. Disposition: status not explicit in this entry; see
    source-order chronology (source order 037).
- [038] rendering-properties-other-than-scale-are-soundly-authored | low | Padding and justification never disagree between sibling amounts, and signedness varies correctly
  Evidence: No screen was built for either property. Disposition: status not explicit in this entry; see source-order chronology (source order 038).
- [039] scale-defect-root-cause-is-one-missing-anchor | high | The field is governed by no width rule, and the fix is blocked by a missing generator entry point
  Evidence: The second covers a long list of sibling ordinals including 121, 125, 126 and 128. Disposition: open or blocked as titled (source order 039).
- [040] missing-anchor-root-cause-withdrawn | high | The field is excluded from render-profile authority by design, not omitted from it
  Evidence: The root cause recorded immediately above is wrong and is withdrawn. Disposition: status not explicit in this entry; see source-order chronology (source order 040).
- [041] scale-defect-root-cause-proven-an-applicability-note-read-as-a-wire-fact | critical | A footnote reference in the design's content cell excludes the field from render-profile authority
  Evidence: Two earlier explanations in this audit are superseded: the missing-anchor claim, already withdrawn, and the reading that the field's content cell is blank, which was taken from column position rather than from the…
    Disposition: status not explicit in this entry; see source-order chronology (source order 041).
- [042] the-predicate-fix-is-correct-but-not-narrow | high | Thirty-six fields across four designs become newly eligible, so the remedy carries a migration
  Evidence: Before proposing it as a small change, the counterfactual was measured across every design the generator publishes, and it is not small. Disposition: status not explicit in this entry; see source-order chronology
    (source order 042).
- [043] the-footnote-fault-is-one-live-field-and-thirty-two-latent-ones | high | The corporate-tax exposure is real but unpublished, which changes when it must be fixed rather than whether
  Evidence: The migration the predicate fix carries is still thirty-six reviewed decisions, because the coverage gate counts eligibility rather than publication, and the thirty-two unpublished ones become eligible the moment the…
    Disposition: status not explicit in this entry; see source-order chronology (source order 043).
- [044] footnote-migration-surface-is-183-not-36 | high | The measurement stands, the screen was withdrawn, and the two facts are separate
  Evidence: The 36-field migration estimate was withdrawn; measured surface is 183 and the two underlying facts are separate. Disposition: withdrawn or superseded as titled (source order 044).
- [045] six-published-export-trees-do-not-reproduce-from-their-inputs | critical | Two carry record-level drift and four carry a stale provenance attestation
  Evidence: That is record-level drift in a published, filing-grade export tree, spanning revisions that cover filings from 2011 onward. Disposition: status not explicit in this entry; see source-order chronology (source order
    045).
- [046] the-shipped-declarado-record-is-correct-and-republishing-it-would-break-the-filing | critical | The drift direction is settled against the official design, and the obvious remedy is the dangerous one
  Evidence: Any republication of this modelo must be blocked until the inputs reproduce the repeat. Disposition: status not explicit in this entry; see source-order chronology (source order 046).
- [047] the-generated-corpus-reproduces-except-for-one-modelo | medium | Twenty-one of twenty-seven published trees are byte-identical to a fresh render
  Evidence: The sweep also corrected the comparison tool's own account of itself. Disposition: status not explicit in this entry; see source-order chronology (source order 047).
- [048] the-declarado-drift-was-already-known-and-guarded | medium | The codebase documents this defect and its remedy, so the contribution here is the census and the gate
  Evidence: A defect that is known, documented and guarded, and that is still present in shipped data across two revisions covering filings from 2011 onward, is a different problem from one nobody had noticed. Disposition: status
    not explicit in this entry; see source-order chronology (source order 048).
- [049] the-declarado-repair-is-the-first-use-of-a-vocabulary-nobody-has-used | high | Every value the repair needs is known except one, and there is no precedent to copy
  Evidence: No authoring was attempted. Disposition: status not explicit in this entry; see source-order chronology (source order 049).
- [050] the-map-regression-dropped-a-field-not-only-the-repeat | high | The declarado repair needs four changes, and one needs a design reading nobody has done
  Evidence: Declaring the repeat alone is refused: a record that repeats binding rows must carry binding fields, and the map attributes those nine positions to casillas rather than to bindings. Disposition: status not explicit in
    this entry; see source-order chronology (source order 050).
- [051] the-declarado-repair-is-blocked-by-a-map-schema-limit-not-by-missing-data | critical | Two design subdivisions of one PDF anchor cannot both be authored
  Evidence: The shipped tree instead carries two fields there: a two-position province code at 77 to 78 addressed as a casilla, and a two-position country code at 79 to 80 addressed as a binding. Disposition: open or blocked as
    titled (source order 051).
- [052] the-obstacle-is-the-design-parser-not-the-map-schema | critical | Only one parser field exists where the shipped tree carries two, so no anchor can address the second
  Evidence: An anchor names a parser field. Disposition: status not explicit in this entry; see source-order chronology (source order 052).
- [053] an-inherited-figure-reached-a-decision-record-unverified | medium | The open-ended count in the temporal decision was carried from the first pass and is wrong
  Evidence: Loaded-authority check corrects the temporal decision from 49/27 to 54/28 open-ended/filing-grade, defined as neither closing date nor selector year. Disposition: corrected to 54/28 under the stated
    no-closing-date/selector-year definition (source order 053).
- [054] decision-record-figures-cannot-be-gated-by-code | medium | The separation that keeps the vault removable also stops anything mechanical from keeping its numbers honest
  Evidence: The rule recorded above, that a figure which cannot be reproduced by running something does not belong in a decision record, was examined for whether it could be enforced rather than merely stated. Disposition: status
    not explicit in this entry; see source-order chronology (source order 054).
- [055] a-failing-gate-asserts-a-revision-that-never-existed | low | The static-inspection failure is a transposed year in the test, not a registry fault
  Evidence: The consequence is small but worth recording in an audit about declarations drifting from what is true: a gate that has never passed protects nothing, and its failure is indistinguishable from the background of a…
    Disposition: status not explicit in this entry; see source-order chronology (source order 055).
- [056] a-dead-gate-was-restored-and-its-staleness-had-one-cause | medium | Four assertions were stale together because a modelo was re-grounded and its test was not
  Evidence: The modelo it covers was re-grounded from the 2002 orden it originally cited onto an orden published in 2024. Disposition: corrected or remeasured as titled (source order 056).
- [057] eleven-tests-cover-a-filing-proof-surface-that-was-removed | high | A displaced single-channel proof kept its whole test suite after the two-channel one replaced it
  Evidence: This campaign spent fifty iterations reading around exactly such noise: the two static-inspection failures were dismissed repeatedly as background, and one of them turned out to be a real dead gate that had never
    passed. Disposition: status not explicit in this entry; see source-order chronology (source order 057).
- [058] the-wider-dev-failures-are-the-refactor-and-one-of-them-is-a-gate-working | low | The sweep stops at the boundary of this work, and the first failure it found is an example worth copying
  Evidence: The directory has now largely been deleted, and the gate fires. Disposition: status not explicit in this entry; see source-order chronology (source order 058).
- [059] the-guard-against-treating-an-empty-proof-as-evidence-is-not-running | critical | One removed method disabled the check that protects the claim this whole campaign is about
  Evidence: The behaviour it guards is still correct, and was confirmed by observation early in this audit, since the offline closure refuses the filing-export limb with missing evidence for every filing-grade revision.
    Disposition: status not explicit in this entry; see source-order chronology (source order 059).
- [060] the-broken-guard-is-a-test-holding-the-old-authority-not-a-broken-composer | high | The production code migrated to the two-channel proof and the tests kept constructing the single-channel one
  Evidence: The plan Step recorded for it named the wrong file and has been corrected. Disposition: status not explicit in this entry; see source-order chronology (source order 060).
- [061] the-empty-proof-guard-is-running-again | high | Restored by pointing three tests at the migrated authority and asserting the refusal instead of its wording
  Evidence: What it found was that the empty channel does refuse: the limb reports refused, the reason is missing evidence, the conformance channel reports evidence missing, and no evidence is attached. Disposition: status not
    explicit in this entry; see source-order chronology (source order 061).
- [062] every-registry-test-lane-is-now-accounted-for | medium | The not-running class is bounded, and the codebase had already met it twice
  Evidence: Registry tests use three lanes. Disposition: status not explicit in this entry; see source-order chronology (source order 062).
- [063] a-screen-label-drifted-from-what-its-count-means | low | The runner said one thing and counted another, and the gate covering it only checks the words exist
  Evidence: Both the runner and the contributor README have been corrected. Disposition: status not explicit in this entry; see source-order chronology (source order 063).
- [064] five-of-nine-screen-labels-described-only-one-of-the-kinds-they-count | medium | One inverted its meaning, and the runner is the surface a maintainer reads first
  Evidence: The worst inverted its sense. Disposition: status not explicit in this entry; see source-order chronology (source order 064).
- [065] two-screen-docstrings-never-named-the-kinds-they-emit | medium | Including the one condition that surfaces the corpus's only known filing-correctness defect
  Evidence: The gate observes 270 kind-rows live, and its teeth were proven rather than assumed: removing a single kind name from one docstring in memory is caught exactly once, naming that screen and that kind. Disposition:
    status not explicit in this entry; see source-order chronology (source order 065).
- [066] the-development-registry-tests-lane-is-red-and-its-runner-reported-success | high | Twenty-six failures, and a piped exit status that read as zero
  Evidence: The `dev/registry/tests` lane fails: **26 failed, 820 passed** in 6m47s. Disposition: status not explicit in this entry; see source-order chronology (source order 066).
- [067] the-eleven-dead-filing-proof-tests-are-dead-for-two-different-reasons | medium | The plan step named one cause; there are two, and the second is the sharper
  Evidence: The tests still name probes into `m200-2025.dp200001.f0001` and index `export_layouts[0]`. Disposition: status not explicit in this entry; see source-order chronology (source order 067).
- [068] the-developer-registry-package-was-a-re-export-facade | medium | Retired, with the test that enforced it
  Evidence: The affected tests pass (34 passed). Disposition: closed or resolved as titled (source order 068).
- [069] four-payload-acceptance-invariants-were-restored-by-re-siting-onto-modelo-151 | medium | The blocker in the previous finding was real but avoidable, and the reasoning that removed it is the useful part
  Evidence: Of the five candidates, 151 and 322 do; 202 requires its own producer profile and 353 its own profile facts. Disposition: status not explicit in this entry; see source-order chronology (source order 069).
- [070] twenty-four-filing-tests-demand-filing-grade-from-modelos-that-no-longer-declare-it | high | The same withdrawal that killed the payload tests is failing a whole suite
  Evidence: Twenty-one raise `modelo 200 revision 2025-y-siguientes declares 'calculation' authority grade, which cannot satisfy the requested 'filing' snapshot authority`; two raise it for modelo 038 and one for modelo 036,…
    Disposition: status not explicit in this entry; see source-order chronology (source order 070).
- [071] two-enrolled-generated-trees-render-but-were-never-published | medium | The remedy the failing gate names is a verb whose implementation exists and has no caller
  Evidence: Six of those eight match the six rows; `200/2025-y-siguientes` and `390/2022` do not, which read as the disposition file under-declaring by two. Disposition: status not explicit in this entry; see source-order
    chronology (source order 071).
- [072] the-pipeline-package-was-a-second-re-export-facade | low | Same defect one level down, retired the same way
  Evidence: The initialiser is now the docstring alone; the affected tests pass (39 passed). Disposition: closed or resolved as titled (source order 072).
- [073] every-open-step-target-was-checked-against-the-tree-and-forty-five-of-forty-eight-hold | low | A negative result, recorded because the checking was the point
  Evidence: Rather than meet the third one by accident, all forty-eight open steps were resolved against the live tree. Disposition: status not explicit in this entry; see source-order chronology (source order 073).
- [074] the-spent-applicability-migrator-is-retired | low | Its own retention rationale cited a step id from a plan that no longer exists
  Evidence: Its retention was justified in its own docstring by a future step that would reuse it for modelos 303 and 390. Disposition: status not explicit in this entry; see source-order chronology (source order 074).
- [075] an-in-flight-rename-left-a-stale-consumer-in-the-packaging-tooling | medium | Not this campaign's work, reported rather than edited
  Evidence: It is recorded rather than corrected here because the rename belongs to another contributor's in-flight work and they may still be sweeping consumers; a second writer on that surface would be the more expensive
    mistake. Disposition: status not explicit in this entry; see source-order chronology (source order 075).
- [076] correction-the-single-channel-authority-does-not-refuse-on-construction | medium | The finding above said construction; the refusal is conditional and sits one level in
  Evidence: One does: `test_real_closure_outcomes.py` builds the authority with a real modelo 151 entry and asserts a satisfied filing-export outcome over 11,618 emitted bytes. Disposition: status not explicit in this entry; see
    source-order chronology (source order 076).
- [077] the-conformance-test-directory-is-outside-every-lane-run-this-campaign-has-made | medium | A whole directory of real-authority tests whose state was simply unknown
  Evidence: Run directly, it gives 2 failed, 5 passed in 11m36s. Disposition: status not explicit in this entry; see source-order chronology (source order 077).
- [078] seven-package-initialisers-were-facades-and-the-condition-is-now-gated | medium | Two were fixed one at a time before anyone asked how many there were
  Evidence: All five were removable without touching a single caller. Disposition: status not explicit in this entry; see source-order chronology (source order 078).
- [079] the-lane-figure-was-wrong-again-for-the-same-reason-one-size-down | medium | Reported as seventeen, measured as eighteen: a file was run where a directory was meant
  Evidence: Measured over both directories the total is **eighteen**: `PYTEST_EXIT=1`, 18 failed against 833 passed in 15m05s. Disposition: status not explicit in this entry; see source-order chronology (source order 079).
- [080] five-code-boundary-violations-in-the-registry-tree-are-cleared | medium | A shipped check already existed for the rule; nobody had run it
  Evidence: These are shipped filing-grade declarations, so the change was verified rather than assumed safe: the diff is four files of one line each, the authority still compiles all five modelo 390 revisions and their 1,450…
    Disposition: status not explicit in this entry; see source-order chronology (source order 080).
- [081] the-facade-condition-was-not-peculiar-to-this-tree | low | Eleven of fifty-two initialisers elsewhere in the development tree carry exports
  Evidence: They are deliberately not touched. Disposition: status not explicit in this entry; see source-order chronology (source order 081).
- [082] the-closure-report-is-snapshot-bound-and-costs-211-seconds | high | Seventeen hundred isolated snapshots for one hundred and twenty-eight rows
  Evidence: The traceback points at deepcopy, so "snapshot isolation is the cost" is the obvious reading; timing snapshots individually gives 0.04s to 0.23s, which across 128 rows accounts for about 26 seconds, so the obvious…
    Disposition: status not explicit in this entry; see source-order chronology (source order 082).
- [083] the-temporal-coverage-phase-is-eleven-times-faster-and-provably-unchanged | high | Seventeen hundred deep copies were made to read seventeen hundred strings
  Evidence: `compose_temporal_coverage` made 1,727 such calls for 128 rows. Disposition: status not explicit in this entry; see source-order chronology (source order 083).
- [084] the-conformance-cli-test-now-passes-and-the-margin-says-the-work-is-not-finished | medium | 262 seconds against a 300 second budget is a pass nobody should rely on
  Evidence: With the temporal-coverage phase cut from 103.8s to 9.5s it now passes: `1 passed in 262.71s`. Disposition: status not explicit in this entry; see source-order chronology (source order 084).
- [085] all-five-classification-failures-are-refactor-collateral-and-four-need-an-owner-not-an-edit | high | The gates are working; they are reporting that adjudication ledgers were not carried through a rename
  Evidence: That gate now passes; the lane's classification failures fall from five to four, verified independently at 4 failed / 21 passed. Disposition: status not explicit in this entry; see source-order chronology (source order
    085).
- [086] the-static-load-closure-conflates-reachability-with-what-a-load-imports | medium | A function-scoped import is a graph edge but not a load-time import
  Evidence: The chain was traced to its last surviving link: a function-local deferred import inside `validate_m303_regimen_simplificado_annual_summary_revision`, sitting after an early return. Disposition: status not explicit in
    this entry; see source-order chronology (source order 086).
- [087] what-this-product-can-actually-file-is-now-stated-and-the-answer-is-small | critical | Sixty-eight revisions claim filing grade; fifty-two of them cannot be presented
  Evidence: - 5 modelos declare `calculation` only: 117, 126, 128, 136 and 200. Disposition: open or blocked as titled (source order 087).
- [088] the-shipped-code-boundary-check-misses-step-identifiers-and-declarations-carried-them | high | It reported the registry clean while filing-grade declarations cited a plan step
  Evidence: The detector proves the negative half too: a revision directory name like `2025-y-siguientes`, a casilla identifier like `DP200014:01033`, an Orden citation and a `2024-2025` span must all NOT match. Disposition:
    status not explicit in this entry; see source-order chronology (source order 088).
- [089] the-three-grade-withdrawals-were-deliberate-correct-and-evidenced | high | The accident was the filing claim, not its removal
  Evidence: The twenty-four filing tests demanding filing grade from modelos 200, 038 and 036 were investigated against the commit history. Disposition: status not explicit in this entry; see source-order chronology (source order
    089).
- [090] the-envelope-finding-was-mostly-noise-and-the-real-defect-was-hiding-inside-it | critical | Fifty-two reported, thirty-one real, and the real ones lose the mandatory developer identity
  Evidence: Its envelope record declares filler across most of the 328-byte prefix, and offsets 93-96 and 101-109 - the Version del Programa and NIF Empresa Desarrollo the design marks mandatory - are covered by **no field at
    all**. Disposition: status not explicit in this entry; see source-order chronology (source order 090).
- [091] two-revisions-ship-filing-bytes-while-declaring-they-cannot-file | high | And the honest response was a structural gate, not a prose correction
  Evidence: Modelo 185 does the same without the envelope. Disposition: status not explicit in this entry; see source-order chronology (source order 091).
- [092] the-contract-can-say-a-family-is-inapplicable-but-not-that-a-capability-is-withheld | high | Twenty-five revisions carry filing machinery below filing grade and none can say why in typed data
  Evidence: Three - modelos 189, 280 and 345 - carry no rationale of any kind, which is indistinguishable from oversight. Disposition: status not explicit in this entry; see source-order chronology (source order 092).
- [093] ninety-nine-percent-of-each-isolating-copy-is-data-the-caller-never-reads | high | Which makes the safe remedy cheaper than the one that needed a guard relaxed
  Evidence: The arithmetic is 884 x 127.5 ms against 884 x 1.4 ms. Disposition: status not explicit in this entry; see source-order chronology (source order 093).
- [094] the-conformance-audit-is-six-times-faster-and-every-ledger-is-byte-identical | high | 133.9s to 22.1s, without relaxing the guard that made the fast path look dangerous
  Evidence: - the whole conformance audit: **133.9s to 22.1s**, having been 66.3s after the first fix in this chain. Disposition: status not explicit in this entry; see source-order chronology (source order 094).
- [095] the-new-projection-is-gated-on-its-contract-and-not-on-its-speed | medium | The isolation it gives up the snapshot's copy for is proven by breaking it
  Evidence: A ledger built from either projection is byte-identical - the substitution the coverage audit performs 884 times, so a divergence would silently alter published coverage findings rather than fail loudly. Disposition:
    status not explicit in this entry; see source-order chronology (source order 095).
- [096] the-provenance-screen-reported-thirty-one-thousand-rows-for-three-hundred-and-fourteen-references | medium | Nineteen citation sites per thing to fix, and the same lesson as the envelope count
  Evidence: The 31,589 rows collapse to **1,389 outside references across modelo, revision and reference kind, and 314 distinct references overall** - roughly nineteen sites per thing anyone would actually fix. Disposition: status
    not explicit in this entry; see source-order chronology (source order 096).
- [097] the-lane-is-fifteen-failures-and-runs-in-a-third-of-the-time | high | Eighteen to fifteen, and fifteen minutes to six and a half
  Evidence: A full-scope run over both directories now gives **15 failed, 848 passed in 6m26s**, against 18 failed / 833 passed in 15m04s when the scope was first measured correctly. Disposition: status not explicit in this entry;
    see source-order chronology (source order 097).
- [098] the-twenty-four-grade-stale-filing-tests-are-re-sited-and-one-was-doubly-stale | high | No grade restored, and the invariants moved rather than being lowered
  Evidence: All twenty-four tests demanding filing grade from modelos 200, 038 and 036 now pass, with no grade restored and no test deleted, skipped or weakened. Disposition: status not explicit in this entry; see source-order
    chronology (source order 098).
- [099] the-suite-census-counted-sites-and-the-work-it-implied-was-two-orders-of-magnitude-too-large | high | Thirty-five thousand findings became one thousand seven hundred, and one step shrank from 3,349 items to 27
  Evidence: The provenance screen contributed 31,589, resolving to 1,389 outside references and 314 distinct ones. Disposition: status not explicit in this entry; see source-order chronology (source order 099).
- [100] the-census-counted-a-shape-the-screen-says-is-not-wrong | medium | A hundred and thirty-two of a hundred and fifty-eight, and the screen said so in its own docstring
  Evidence: With that, the suite census is 1,633 where it began at 35,287. Disposition: status not explicit in this entry; see source-order chronology (source order 100).
- [101] five-revisions-claim-they-can-be-filed-and-cannot-say-by-when | high | A filer asks two questions and these answer one
  Evidence: The other five reach filing grade with an export layout: modelos 145, 151, 165, 308 and 309. Disposition: status not explicit in this entry; see source-order chronology (source order 101).
- [102] fourteen-filing-revisions-carry-no-formula-and-ten-of-them-are-right-to | high | The distinction that separates them is declared, so the finding is four
  Evidence: Modelos 347, 184, 720, 165 and others are exactly that. Disposition: status not explicit in this entry; see source-order chronology (source order 102).
- [103] naming-every-kind-was-not-enough-because-the-count-above-them-can-still-lie | medium | Two stale counts, one introduced by the edit that fixed the names
  Evidence: Both counts are corrected and the claim is now gated: a docstring stating "N conditions are reported" must match the bullets it introduces and must not understate the kinds the screen emits live. Disposition: status
    not explicit in this entry; see source-order chronology (source order 103).
- [104] four-filing-claims-fail-more-than-one-capability-axis-and-one-fails-three | critical | The same revisions keep appearing, which is the answer to which claims to distrust
  Evidence: - **145/2012-01-31-y-siguientes** and **165/2016-2022** each fail two: no deadline, and a grade the prerequisites do not support. Disposition: status not explicit in this entry; see source-order chronology (source
    order 104).
- [105] two-feature-documents-fail-their-own-attested-body-schema | low | Not this work's documents, so reported rather than filled in
  Evidence: A modelo 353 audit from 26 August is missing the `## Scope` section its attested body schema requires, and a registry temporal coverage reference from 31 August is missing `## Summary`. Disposition: status not explicit
    in this entry; see source-order chronology (source order 105).
- [106] the-file-blocking-the-filing-defect-is-free-and-the-work-is-still-not-unblocked | high | 183 fields measured exactly, 149 of them due immediately
  Evidence: Of those, **exactly 183 would become newly eligible** once the other eligibility conditions are applied - independently reproducing the figure the plan carried, and now resolved per modelo: 390 has 80, 200 has 60,…
    Disposition: status not explicit in this entry; see source-order chronology (source order 106).
- [107] the-note-behind-the-filing-defect-says-nothing-about-the-wire-and-now-says-so-in-quotation | high | The design's own words, not a characterisation of them
  Evidence: The field that renders unscaled in modelo 353 carries `Nota 4.` in the cell where the design states a wire fact. Disposition: status not explicit in this entry; see source-order chronology (source order 107).
- [108] the-one-hundred-and-eighty-three-due-rules-are-triaged-and-one-hundred-and-seventy-five-are-unconstrained | high | Only six point at a note that says anything about the wire
  Evidence: - **6 point at a note that does bear on the wire**, all in modelo 131. Disposition: status not explicit in this entry; see source-order chronology (source order 108).
- [109] thirteen-bundled-record-designs-have-no-transcription | medium | Evidence tooling is blind to them, and three belong to a modelo already failing three capability axes
  Evidence: The same sweep found that thirteen bundled record designs across eight modelos - 126, 128, 165, 194, 270, 308, 309 and 341 - ship the original workbook or PDF with no extracted text beside it. Disposition: status not
    explicit in this entry; see source-order chronology (source order 109).
- [110] the-triage-is-now-repeatable-and-deliberately-stops-short-of-the-eligibility-predicate | medium | The mistake that produced a plausible wrong answer is now the thing the tool cannot make
  Evidence: That is the bug from the first triage pass elevated into a function: searching returns an arbitrary sibling, modelo 303 bundles fifteen designs, and resolving a note against the wrong year's design still produces an…
    Disposition: open or blocked as titled (source order 110).
- [111] the-plan-was-held-to-the-gate-the-plan-added | low | Its own gate count was stale, and the first correction was wrong too
  Evidence: Correcting it produced a second error, which is why this is recorded rather than fixed quietly. Disposition: status not explicit in this entry; see source-order chronology (source order 111).
- [112] the-private-module-breach-is-fourteen-imports-not-one-hundred-and-eleven | medium | The split between tests and production changes what the remedy is
  Evidence: Measured across the registry development tree, **111 imports reach 22 such modules from outside their package** - which reads as the underscore naming having stopped describing reality entirely, and as a rename of…
    Disposition: status not explicit in this entry; see source-order chronology (source order 112).
- [113] the-plan-cannot-be-gated-the-way-the-screens-are | low | And the rule that prevents it is one this campaign has been enforcing
  Evidence: The rule is right and the consequence is real: vault prose is checked by the person writing it or not at all. Disposition: status not explicit in this entry; see source-order chronology (source order 113).
- [114] an-entire-module-was-left-behind-by-its-own-split-and-duplicated-fifty-nine-definitions | critical | Two thousand one hundred and thirty-nine lines, zero importers
  Evidence: Verification: the registry compiles, the bindings module imports, and 614 of 615 ledger and binding tests pass. Disposition: status not explicit in this entry; see source-order chronology (source order 114).
- [115] three-copies-of-one-type-guard-and-two-of-one-predicate | medium | And a fourth apparent duplicate that is a legitimate boundary wrapper
  Evidence: `sha256_file` exists twice with genuinely different bodies, which looks like the worst case - one concept, two behaviours - and is not. Disposition: status not explicit in this entry; see source-order chronology
    (source order 115).
- [116] a-module-was-serving-as-a-re-export-path-and-only-deleting-the-duplicate-revealed-it | medium | The consumer reached a type guard through a module that merely happened to define it
  Evidence: Both are now pointed at the core type-guard module. Disposition: status not explicit in this entry; see source-order chronology (source order 116).
- [117] the-deleted-module-was-cleared-by-three-independent-a-b-tests | medium | A large deletion beside a red suite needs causation established, not asserted
  Evidence: Aggregation alone is 5 failed against 1,049 passed, so the weight sits in the ledger suite, and the sampled failures there are the other contributor's in-flight module renames and unenrolled split-out resolvers.
    Disposition: status not explicit in this entry; see source-order chronology (source order 117).
- [118] one-schema-construction-had-five-spellings-in-one-package | medium | Four identical private helpers and a fifth built inline
  Evidence: The CLI spec suite reports 10 failed and 394 passed both before and after, proved by restoring the four originals, re-running, and putting the change back. Disposition: status not explicit in this entry; see
    source-order chronology (source order 118).
- [119] two-functions-that-look-identical-to-an-ast-scan-are-not-duplicates | medium | Same syntax, different module constants, and the shared mechanism already exists
  Evidence: Both files are also held by another contributor, so this would have been reported rather than changed in any case. Disposition: status not explicit in this entry; see source-order chronology (source order 119).
- [120] a-function-describing-itself-as-the-single-projection-existed-twice | medium | And modelo 390 resolves to no revision for the current filing year
  Evidence: Separately, running the affected suites surfaced a registry coverage hole worth recording on its own: **modelo 390 declares revisions 2021 through 2025 and resolves to nothing for filing year 2026**, which is the…
    Disposition: status not explicit in this entry; see source-order chronology (source order 120).
- [121] the-a-b-method-was-wrong-and-is-corrected | high | Restoring a file from git is not the same as undoing an edit, and it risks other people's work
  Evidence: With hundreds of uncommitted changes in the tree that is a different and older world, which is exactly why one such attempt produced 534 failures and no usable comparison. Disposition: status not explicit in this
    entry; see source-order chronology (source order 121).
- [122] uncommitted-canonicalisation-was-reverted-by-another-contributor-s-commits | high | The definitions survived and the consumer repointing did not, which is the worse half
  Evidence: The asymmetry is what matters. Disposition: status not explicit in this entry; see source-order chronology (source order 122).
- [123] five-of-the-nine-remaining-duplicates-are-not-duplicates | medium | Same syntax over a per-module constant, verified by reading rather than by pattern
  Evidence: It finds candidates. Disposition: status not explicit in this entry; see source-order chronology (source order 123).
- [124] the-duplicate-body-sweep-is-finished-and-every-survivor-is-a-false-positive | high | Twenty-seven bodies to five, and the five must not be collapsed
  Evidence: The largest single item was a module left behind by its own split - 2,139 lines, 59 of 60 definitions duplicated in the modules that replaced it, zero importers. Disposition: status not explicit in this entry; see
    source-order chronology (source order 124).
- [125] three-instruments-and-three-different-blind-spots | medium | Traded with a peer session working the same tree
  Evidence: It is reported to them with the commit that introduced it. Disposition: status not explicit in this entry; see source-order chronology (source order 125).
- [126] the-alias-sweep-found-eleven-second-names-and-only-two-were-wrong | medium | Naming a primitive after the domain is the opposite of duplication
  Evidence: `ContentDigest = Hex64Str`, `BucketEventId = Hex64Str`, `M145CommunicationRecordId = Hex64Str`, `ModeloDraftContentAddress = Hex16Str` - these give a domain name to a primitive shape, and a reader of `ContentDigest`…
    Disposition: status not explicit in this entry; see source-order chronology (source order 126).
- [127] two-classes-shared-a-name-and-only-one-of-them-could-be-collapsed | medium | The other had to be renamed, because the architecture forbids merging it
  Evidence: All three now resolve to one protocol. Disposition: status not explicit in this entry; see source-order chronology (source order 127).
- [128] a-redaction-token-was-declared-eight-times | high | Eight places had to agree, and disagreement leaks a taxpayer's filename with nothing failing
  Evidence: The two packages that exercise it pass 194 tests. Disposition: status not explicit in this entry; see source-order chronology (source order 128).
- [129] a-shared-value-is-not-always-a-shared-fact | medium | Three manifests at version one are three facts that agree, not one fact repeated
  Evidence: `_MANIFEST_VERSION = 1` appears in three modules - an attachment envelope, an evidence service and a modelo workspace manifest. Disposition: status not explicit in this entry; see source-order chronology (source order
    129).
- [130] the-constant-sweep-is-judged-rather-than-swept | medium | Twenty-three to sixteen, and the seven removed were chosen one at a time
  Evidence: Collapsed as one fact: the PDF redaction token declared eight times; a wizard section identifier declared three times, now owned by the catalogue that defines the section; the modelo edit responsible owner declared…
    Disposition: status not explicit in this entry; see source-order chronology (source order 130).
- [131] the-collapsed-concepts-are-now-gated-because-a-sweep-already-undid-them-once | high | A canonicalisation is undone silently, and the duplicate that returns works
  Evidence: A gate that refused those would be refusing the codebase's own judgement, and would be argued down within a week. Disposition: status not explicit in this entry; see source-order chronology (source order 131).
##### Original Recommendations (source order 132–356)
- [132] serializer-change-filled-the-drift-class-with-correct-records | high | A quote-style change put 141 semantically unchanged records into the class that means unsafe to republish
  Evidence: The regression is commit `2606941009`, the failure count moved from 15 to 46 across the two registry test directories, and 30 of the 31 new failures are this single field. Disposition: status not explicit in this
    entry; see source-order chronology (source order 132).
- [133] ambiguity-was-never-measured-only-duplication | medium | Every duplication measure counted things said twice; none counted one word meaning two things
  Evidence: That leaves 12 names claimed across architectural layers and 9 claimed inside a single layer. Disposition: status not explicit in this entry; see source-order chronology (source order 133).
- [134] drift-screen-separates-serializer-from-value | medium | record_drift now means a record whose meaning moved, proven at 25 provenance-only against 2 real
  Evidence: Across every published generated tree the screen now reports 25 in `provenance_only` and 2 in `record_drift`, and the two are exactly modelo 347's revisions - the genuine defect this audit already documents, whose…
    Disposition: status not explicit in this entry; see source-order chronology (source order 134).
- [135] disposition-gate-fails-accurately | medium | Re-keyed onto the explained state, the gate names 21 stale attestations instead of an undifferentiated diff
  Evidence: The remedy is republication, which is safe for all twenty-five `provenance_only` trees and must never be applied to 347's two. Disposition: status not explicit in this entry; see source-order chronology (source order
    135).
- [136] one-definition-of-record-sameness | medium | The generated-tree suite carried a second byte comparison; both now call the same parse helper
  Evidence: Across the three affected modules the failure count fell from 46 to 28, and every remaining failure has one cause and one remedy. Disposition: status not explicit in this entry; see source-order chronology (source
    order 136).
- [137] signature-declared-the-enum-and-returned-strings | medium | An annotation had been wrong since it was written, hidden because a StrEnum compares equal to its value
  Evidence: The same is true of the three fixtures spelling the encoding as `latin-1`: the token was never canonical, and only a typed field refused it. Disposition: status not explicit in this entry; see source-order chronology
    (source order 137).
- [138] green-run-selected-nothing | high | A change was verified against a run that deselected all 24 tests exercising it, and exited zero
  Evidence: Verifying that change first produced "3 passed" over two test modules, and the number was the finding. Disposition: verification run selected none of the 24 relevant tests; no closure claim (source order 138).
- [139] determinism-and-shipped-equality-conflated | medium | One assertion carried two claims; rendering twice stays byte-exact while shipped-tree equality is semantic
  Evidence: The m303 envelope proof asserted `first == second == committed` in a single chain. Disposition: status not explicit in this entry; see source-order chronology (source order 139).
- [140] invisible-test-condition-now-reported | medium | Lane visibility is a screen rather than a reader noticing a low collected count
  Evidence: Corrected, the tree reports zero modules carrying no execution marker. Disposition: status not explicit in this entry; see source-order chronology (source order 140).
- [141] same-layer-collisions-adjudicated | medium | Three are correct, four want a rename or merge, one is a contract conflict no rename settles
  Evidence: A layer restating a concept in its own vocabulary is what the boundary is for, and demanding a written reason for each of the twelve would bury these nine - which is the same mistake, in a different costume, as the…
    Disposition: status not explicit in this entry; see source-order chronology (source order 141).
- [142] constant-value-conflicts-are-all-private | low | Sixteen constants carry two values under one name and none of them is public, so the underscore holds
  Evidence: `_MODULE` naming its own module, `_PAYLOADS` naming its own payload module, `_SUBMIT_SELECTORS` carrying one page's selectors, `_MAX_REPLY_TOKENS` tuned per prompt at 1024 and 200: each is correct where it sits and…
    Disposition: status not explicit in this entry; see source-order chronology (source order 142).
- [143] size-baseline-caught-this-campaigns-growth | low | A four-line growth was shrunk to fit rather than raising another contributor's reviewed ceiling
  Evidence: The evidence-tier repair grew `_workbook_parity.py` from 1399 to 1403 lines and tripped a reviewed-size baseline. Disposition: status not explicit in this entry; see source-order chronology (source order 143).
- [144] load-census-does-not-survive-a-rename | medium | A classification keyed on a module path follows neither side of a rename, and nothing reports the drift
  Evidence: `run_census` reports 21 registry modules carrying no classification and 14 rules naming modules that are no longer in the universe. Disposition: status not explicit in this entry; see source-order chronology (source
    order 144).
- [145] shape-identity-is-not-concept-identity | low | Eighty-one type declarations share a field shape and every one of the seven sharpest is correct
  Evidence: Across the shipped package there are 81 such shapes - 39 spanning layers, 35 inside one layer, and 7 inside a single module. Disposition: status not explicit in this entry; see source-order chronology (source order
    145).
- [146] conformance-closure-tests-are-outside-every-lane | critical | Sixteen tests proving real filing outcomes are named by no lane, and one of them fails
  Evidence: Measured against the same tree, it reports 73 marker-unreachable tests and two files outside every lane path. Disposition: status not explicit in this entry; see source-order chronology (source order 146).
- [147] campaign-removed-its-own-duplicate-check | low | A reachability assertion duplicating a stronger per-test gate was deleted rather than defended
  Evidence: What remains is the part the gate has no reason to answer: given a module that IS reachable, why did the default lane not select it. Disposition: status not explicit in this entry; see source-order chronology (source
    order 147).
- [148] location-note-forbade-the-move-already-made | medium | A load-bearing docstring insisted on a directory the module had deliberately been moved out of
  Evidence: Measured from where the module actually is, `dev/tests` is named by five justfile recipes and four workflow invocations, and the note asks the next mover to count the lanes naming the destination and confirm the…
    Disposition: status not explicit in this entry; see source-order chronology (source order 148).
- [149] conformance-suite-omitted-from-every-recipe | critical | Three sibling registry directories are named by the dev tooling lane and the conformance one is not
  Evidence: Seventy-three carry no such marker and are therefore unexplained, concentrated in three subsystems: 39 in the TUI, 18 in packaging, and 16 in the registry. Disposition: status not explicit in this entry; see
    source-order chronology (source order 149).
- [150] the-unrun-conformance-suite-is-fifteen-green-one-red | high | Run by hand: fifteen pass and one fails, and a later collection error was another writer's mid-edit state
  Evidence: A second measurement taken minutes later reported something different and alarming: a collection error, `NameError`, only 7 of the 16 tests collected. Disposition: status not explicit in this entry; see source-order
    chronology (source order 150).
- [151] static-closure-and-real-load-answer-different-questions | high | A closure states what a load can reach and sys.modules what it did; the test demanded they be equal
  Evidence: It discriminates, and that was checked in both directions rather than assumed: `_withholding_rows` has zero module-level importers, and a control module in the same package has 115. Disposition: status not explicit in
    this entry; see source-order chronology (source order 151).
- [152] monetary-scale-gated-before-emission | medium | 3,385 decimal fields all declare a scale, pinned by a gate that refuses at declaration not at render
  Evidence: Measured across the corpus before the gate was written, because a gate authored against an unknown state is either red on arrival or unproven: 18,231 export fields, of which 3,385 are `decimal` and 4,028 are `money`.
    Disposition: status not explicit in this entry; see source-order chronology (source order 152).
- [153] operator-path-committed-in-a-sibling-audit | high | A committed vault document carries an absolute path under a named user's home directory
  Evidence: The full lane surfaced a privacy gate failing on `2026-08-27-calculation-correctness-campaign-restrictive-default-sweep-audit.md`, which carries an absolute path under a named user's home directory including an agent…
    Disposition: status not explicit in this entry; see source-order chronology (source order 153).
- [154] retired-audit-command-models-removed | medium | 279 lines of ratchet apparatus with no importer, whose only external reference was a docstring bullet
  Evidence: 279 lines of a 1,781-line module, now 1,502. Disposition: status not explicit in this entry; see source-order chronology (source order 154).
- [155] development-vocabulary-restated-the-applications | medium | All seven application refusal reasons were copied rather than composed, so an eighth would never arrive
  Evidence: Constructing the model with each of the twelve reasons in turn accepts all twelve, and an invented reason is still refused, which is the property that actually matters. Disposition: status not explicit in this entry;
    see source-order chronology (source order 155).
- [156] constants-orphaned-by-this-campaigns-deletion | low | A deletion left three module-private constants referenced by nothing, found by a sweep that should have run first
  Evidence: They are gone, with their comments, bringing the module to 1,489 lines from the 1,781 it started at. Disposition: status not explicit in this entry; see source-order chronology (source order 156).
- [157] composed-vocabulary-gate-overclaimed-its-teeth | medium | The gate detects staleness, not the act of copying, and its first docstring claimed otherwise
  Evidence: Separately, the closure suite was re-run after the vocabulary change and reports 15 passing with the single pre-existing failure, unchanged. Disposition: status not explicit in this entry; see source-order chronology
    (source order 157).
- [158] private-import-step-named-the-wrong-surface | medium | Eleven violations run from dev into src, not out of dev/registry/pipeline as the Step described
  Evidence: The existing production gate holds this invariant at zero over `src/cadrumo` with detector teeth and no exemption list, and its own text explains why it carries no baseline: a hand-maintained list of accepted…
    Disposition: status not explicit in this entry; see source-order chronology (source order 158).
- [159] campaign-authored-a-duplicate-step | low | A timed-out add had succeeded; the retry created a second identical Step that then absorbed a closure
  Evidence: The count is 126 closed of 187. Disposition: status not explicit in this entry; see source-order chronology (source order 159).
- [160] publication-limb-had-no-caller-because-inputs-had-no-name | medium | Seven values were assembled inside a comparison, so any second consumer had to re-derive them
  Evidence: Both screened revisions report byte-identical summaries to before the extraction - modelo 303 at zero record drift with nine serialization-only differences, modelo 347 at one record drift - and the two owning suites…
    Disposition: status not explicit in this entry; see source-order chronology (source order 160).
- [161] derivation-publication-seam-is-gated | medium | A gate asserts the derived inputs still supply every revision-describing value publication needs
  Evidence: The suite runs 19 tests, all passing. Disposition: status not explicit in this entry; see source-order chronology (source order 161).
- [162] pending-diff-rule-caught-a-file-that-changed-hands | medium | A diff assumed to be this campaign's was another writer's, because the earlier edits had been committed
  Evidence: The diff has to be read. Disposition: status not explicit in this entry; see source-order chronology (source order 162).
- [163] two-of-this-campaigns-gates-could-pass-over-nothing | high | The empty-population defence this audit argues for was met by three of five gates written here
  Evidence: Both now assert their population before asserting their invariant, and the thresholds were set against measured reality rather than picked: 4,462 public definitions against a floor of 500, 101 classified modules…
    Disposition: status not explicit in this entry; see source-order chronology (source order 163).
- [164] empty-filing-export-proof-refuses-rather-than-passes | medium | Zero enrolled vectors, and a declared layout is refused as missing evidence rather than read as proven
  Evidence: So the Step is not blocked on plumbing, and describing it as loading vectors from registry data understated what it needs. Disposition: status not explicit in this entry; see source-order chronology (source order 164).
- [165] closure-test-repair-is-blocked-behind-vector-enrolment | high | Rewriting onto the two-channel authority changes what the test fails on, because the vectors are empty
  Evidence: The one conformance failure this audit has carried throughout fails with an `AttributeError`: the modelo 151 test builds `LiveFilingExportProofAuthority` and the closure report calls `assess_for` on it, which that…
    Disposition: status not explicit in this entry; see source-order chronology (source order 165).
- [166] crashed-worker-reported-as-a-failing-test | high | A summary line was trusted over the log beneath it, and the run's results were unusable
  Evidence: The filing suites were run and reported "1 failed, 7 passed", and that was recorded here as a failure. Disposition: status not explicit in this entry; see source-order chronology (source order 166).
- [167] campaign-runs-swept-for-lost-worker-markers | low | Eight runs carrying this audit's figures were re-read for crash markers and none carries one
  Evidence: The three full-lane measurements that carry this campaign's headline numbers - 46 failures, then 36, then 36 against 978 passing - are clean, as are the conformance, declaration-gate, publication and generated-tree
    runs. Disposition: status not explicit in this entry; see source-order chronology (source order 167).
- [168] measurement-integrity-criterion-added | low | Four measurement failures that all looked like success are made an acceptance term of the plan
  Evidence: The criterion is met by evidence rather than assertion: all four failures are recorded here with what they cost, the gates now assert measured floors, and every run quoted by this plan has been swept for lost-worker…
    Disposition: status not explicit in this entry; see source-order chronology (source order 168).
- [169] serial-rerun-shows-the-test-passes | medium | Three collected, three passed: the parallel run's failure was the crashed worker and nothing else
  Evidence: The parallel run's "1 failed, 7 passed" was the crashed worker and nothing else, which is precisely what the hook's warning says such a line means. Disposition: serial rerun passed; parallel failure attributed to a
    crashed worker (source order 169).
- [170] feature-health-warning-belongs-to-another-writer | low | Three body-section warnings fall on an untracked scaffold created under this feature's tag
  Evidence: They fall on an audit scaffolded under this feature's tag for a modelo 200 publication review, whose Scope, Findings and Recommendations are still template placeholders. Disposition: status not explicit in this entry;
    see source-order chronology (source order 170).
- [171] footnote-sizing-measured-an-absent-attribute | medium | A confident zero came from reading content off an object that does not carry it
  Evidence: Of the 416 fields in the first design, the number carrying any non-empty content at all is also zero. Disposition: status not explicit in this entry; see source-order chronology (source order 171).
- [172] footnote-sizing-retaken-from-a-real-population | low | 845 content cells actually read across four designs, and the zero now says something
  Evidence: Read correctly across four designs: 1,649 fields, of which 845 carry a non-empty Contenido cell. Disposition: status not explicit in this entry; see source-order chronology (source order 172).
- [173] bare-footnote-pointer-does-not-occur | medium | 20,776 content cells, 26 carrying a pointer inside prose and none consisting only of one
  Evidence: The four-design spot check has been replaced by a sweep of every record design the registry can reach: 111 designs loaded, one refusing to load, 73,040 fields, and 20,776 carrying a non-empty Contenido cell.
    Disposition: status not explicit in this entry; see source-order chronology (source order 173).
- [174] lane-measurement-reconciles-against-its-own-collection | low | 1,091 collected against 35 failed plus 1,056 passed, from one invocation and with no lost worker
  Evidence: The first measurement taken that way reconciles: 1,091 tests collected of 1,125 with 34 deselected, and 35 failed plus 1,056 passed, which is 1,091 exactly. Disposition: status not explicit in this entry; see
    source-order chronology (source order 174).
- [175] step-scopes-appeared-stale-withdrawn | low | WITHDRAWN: all fifteen were correct, nine recording where work happened and six naming files to create
  Evidence: This is the plan committing the defect the plan exists to remove. Disposition: withdrawn or superseded as titled (source order 175).
- [176] stale-scope-finding-withdrawal | medium | The check measured file existence and never asked what a scope clause is for
  Evidence: The remaining six belong to open Steps, and every one names a file the Step exists to create: "author the conformance vector for the modelo 303 revision" scoped to the vector file, "record the satisfied… Disposition:
    status not explicit in this entry; see source-order chronology (source order 176).
- [177] modelo-720-opening-year-makes-its-design-unloadable | high | valid_from 2012 against a design applying from 2013 leaves one design no sweep can read
  Evidence: Diagnosed, it is `720/2013-y-siguientes`, and the refusal is precise: the record-design source `aeat-dr-720` does not apply to filing year 2012. Disposition: status not explicit in this entry; see source-order
    chronology (source order 177).
- [178] four-misstated-openings-are-three-defects | medium | Two names to correct, one declaration to author, one axis decision to take
  Evidence: Modelo 151's `2025-y-siguientes` declares `valid_from` 2023-01-01 and a selector opening in 2023, while `2015-2022` ends in 2022 - again continuous, and the name is two years late. Disposition: status not explicit in
    this entry; see source-order chronology (source order 178).
- [179] selector-window-condition-withdrawn-same-iteration | low | Thirty-five of thirty-six members were correct, so the condition was removed rather than shipped
  Evidence: Checking the members before believing the count: modelo 100's 2023 and 2024, modelo 714's 2023 and modelo 390's 2024 each admit themselves through the live authority. Disposition: status not explicit in this entry; see
    source-order chronology (source order 179).
- [180] unselectable-open-ended-window-condition | medium | Five revisions declare an open-ended valid_to their selector does not carry, and all five stop at their year
  Evidence: Of 54 revisions without valid_to, 49 carry year_from and extend; five have no selector bounds and refuse the next year. The 194/2024 and 721/2024 revisions do extend. Disposition: condition narrowed and verified on all
    five bounded cases (source order 180).
- [181] two-conditions-contradicted-each-other | medium | One row said the window does not extend while another said the name omits years it serves
  Evidence: The single-year condition now excludes a revision whose open-endedness is unselectable, and its membership falls from seven to two - modelo 194's 2024 and modelo 721's 2024, the pair verified to admit filing year…
    Disposition: status not explicit in this entry; see source-order chronology (source order 181).
- [182] modelo-369-schemes-disambiguate-by-period-family | medium | Two alarming readings were both artefacts of asking with a period code the scheme does not declare
  Evidence: The first: all three declare identical temporal windows - `valid_from` 2021-07-01, no `valid_to`, selector opening in 2021 - and asking for filing year 2024 with period `1T` returned `esquema-union` every time.
    Disposition: status not explicit in this entry; see source-order chronology (source order 182).
- [183] selection-probe-asks-with-declared-codes-only | medium | The probe reads each revision's own period codes, so a refusal is a refusal of a well-formed question
  Evidence: Asked with its own monthly code it serves 2022 and refuses 2008, 2015 and 2021 - so the name really does claim fourteen years the revision does not serve, and the finding now rests on evidence rather than on a…
    Disposition: status not explicit in this entry; see source-order chronology (source order 183).
- [184] shared-registry-invalid-for-a-window | high | Modelo 200 casillas referenced absent export fields in committed state, blocking every consumer
  Evidence: Three of the four tests errored mid-iteration with the registry refusing to validate: modelo 200 revision 2024 carried casillas referencing export fields that did not exist. Disposition: status not explicit in this
    entry; see source-order chronology (source order 184).
- [185] no-revision-is-unreachable-when-asked-correctly | low | 441 well-formed probes and every one resolves, including the mid-year split once given a date
  Evidence: The declared-code probe was run across every modelo: 441 probes, and exactly one did not resolve to itself - modelo 308's `2011-julio-2015`, refused as ambiguous. Disposition: status not explicit in this entry; see
    source-order chronology (source order 185).
- [186] crashed-worker-read-correctly-second-time | low | The word crashed was hidden by terminal escape codes until the log was stripped
  Evidence: The corrected test suite then reported a failure on the modelo 369 test. Disposition: status not explicit in this entry; see source-order chronology (source order 186).
- [187] date-retry-narrowed-to-ambiguity | medium | Retrying every refusal doubled the work and made the timeout crash likelier; suite runtime halved
  Evidence: Behaviour is unchanged where it matters and was checked in both directions: modelo 308's four probes still resolve to themselves, and modelo 322 at 2015 still reports twelve refusals with none of them retried into a…
    Disposition: status not explicit in this entry; see source-order chronology (source order 187).
- [188] plan-declares-each-section-several-times | high | Three Descriptions, two Parallelizations and three Verifications against a template declaring one each
  Evidence: The three Descriptions run 54, 36 and 45 non-blank lines; only the third carries the paragraph recording how this work extended from the registry into the codebase. Disposition: status not explicit in this entry; see
    source-order chronology (source order 188).
- [189] plan-sections-merged-without-loss | medium | 126 paragraphs to 107 with no-loss made structural rather than checked after the first attempt refused
  Evidence: The document went from 126 prose paragraphs to 107, the nineteen removed being near-duplicates, and the Steps were untouched at 212 rows with 151 closed before and after. Disposition: status not explicit in this entry;
    see source-order chronology (source order 189).
- [190] criteria-were-being-appended-to-parallelization | high | The duplicated structure made the block before a Verification heading look like Verification
  Evidence: The block from the criteria opener to the end of Parallelization is now inside Verification, merged with what was there under the same no-loss construction: 28 paragraphs to 25, none lost. Disposition: status not
    explicit in this entry; see source-order chronology (source order 190).
- [191] parity-gate-caught-its-own-author | medium | The screen said six conditions while emitting eight, invisible to every check but this one
  Evidence: The full lane reconciles: 1,281 collected, 41 failed plus 1,240 passed, and no lost-worker marker. Disposition: status not explicit in this entry; see source-order chronology (source order 191).
- [192] four-paragraphs-no-threshold-could-judge | low | Two subsumed, one carrying a lost clause, one longer than its replacement, one not a duplicate at all
  Evidence: Twenty-four paragraphs to twenty, 215 Step rows unchanged, seventeen vault checks clean. Disposition: status not explicit in this entry; see source-order chronology (source order 192).
- [193] two-descriptions-disagreed-on-the-screen-count | medium | The longer, later-sounding paragraph carried the stale count; the entry point settled it
  Evidence: Both paragraphs carried unique material: one the sixteen gates and the detail that several gates caught their own author, the other that each screen proves its detection against a constructed defect, that several…
    Disposition: status not explicit in this entry; see source-order chronology (source order 193).
- [194] name-window-findings-were-already-stepped | medium | Eight open Steps named the same revisions; what this work added was consequence, not discovery
  Evidence: Phase `W05.P12` carries eight Steps naming the exact revisions the name-window screen reports: modelo 151 claiming 2025 while opening in 2023, modelo 185 claiming 2025 while opening in 2026, modelo 720 claiming 2013…
    Disposition: open or blocked as titled (source order 194).
- [195] two-screen-conditions-had-never-fired | high | A condition never emitted is indistinguishable from one that cannot be reached, and two were untested
  Evidence: This is the same defect as the stated condition count corrected two iterations ago, one level down. Disposition: open or blocked as titled (source order 195).
- [196] unfired-condition-defect-confined-to-one-screen | low | Six screens declare condition bullets and all six agree with what they emit; four sweep hits were artefacts
  Evidence: The result stands as a negative one. Disposition: status not explicit in this entry; see source-order chronology (source order 196).
- [197] twenty-one-modules-ruled-by-measurement | medium | Live when sys.modules holds it after a load, conditionally reachable when it does not
  Evidence: What remains is authoring each rule's trigger and reason, which is prose about why a module loads rather than a decision about whether it does. Disposition: status not explicit in this entry; see source-order
    chronology (source order 197).
- [198] registry-load-failure-was-stale-bytecode | medium | An error listing permitted values without the one a revert had restored is a module older than its file
  Evidence: The measurement first failed with modelo 100's 2021 revision declaring an extraction surface outside the permitted set. Disposition: status not explicit in this entry; see source-order chronology (source order 198).
- [199] most-stale-rules-were-not-stale | medium | Twelve named core modules outside the census universe and one named a genuinely renamed module
  Evidence: `_validate_references` became `validate_references` when the concurrent campaign dropped the leading underscore, the successor is in the census universe, and the member is repointed - the stale count falls from…
    Disposition: status not explicit in this entry; see source-order chronology (source order 199).
- [200] load-classifications-grounded-in-the-loader | medium | Five rules cover every unruled module, and the table caught a member this campaign misprefixed
  Evidence: They group by the importers the census reports, which is what the triggers name: the record-design parse chain, nine modules that the PDF orchestration, workbook reader and shared layout markers were split into; the…
    Disposition: status not explicit in this entry; see source-order chronology (source order 200).
- [201] one-stale-count-three-defects | high | Six members a load imports, three a rule over-claims, one renamed module: three owners, one number
  Evidence: Measured against a real load, they are three separate things and the rules are right about most of them. Disposition: status not explicit in this entry; see source-order chronology (source order 201).
- [202] census-universe-omitted-ancestor-packages | high | An import graph records no edge to a parent package, so the universe missed packages every load holds
  Evidence: The census returns to zero unclassified. Disposition: status not explicit in this entry; see source-order chronology (source order 202).
- [203] in-process-load-measurement-was-inverted | high | One module reported absent that a clean subprocess holds, an error running opposite to contamination
  Evidence: Three measurements in this campaign have now been taken in a process that had already imported the thing being measured - the stale bytecode twice, and this. Disposition: status not explicit in this entry; see
    source-order chronology (source order 203).
- [204] cold-and-warm-regimes-differ-by-forty-three-modules | high | 378 modules cold against 335 warm, a strict subset, and one live claim held only in the cold regime
  Evidence: A cold load holds 378 first-party modules and a warm load 335 - forty-three modules loaded only when the caches are empty, and none loaded only when they are full. Disposition: status not explicit in this entry; see
    source-order chronology (source order 204).
- [205] scratch-file-committed-before-removal | medium | A create-and-delete in one command left a tracked file, because another writer commits on a timer
  Evidence: That was true then and is not a property of the practice. Disposition: status not explicit in this entry; see source-order chronology (source order 205).
- [206] forty-live-claims-are-unsupported | critical | Eleven load in no regime and twenty-nine only cold, in rules the census had no way to check
  Evidence: Of 225 members claimed live, 40 fail in at least one regime, and they fail in two distinct ways. Disposition: status not explicit in this entry; see source-order chronology (source order 206).
- [207] unsupported-live-claims-are-reproducible | medium | A screen probes both regimes in clean subprocesses and raises rather than returning an empty set
  Evidence: `load_claim_verification` asks that question and reproduces the finding exactly: 378 modules cold, 335 warm, forty unsupported, eleven never loaded and twenty-nine cold only. Disposition: status not explicit in this
    entry; see source-order chronology (source order 207).
- [208] two-tools-sit-outside-the-single-registry-entry-point | low | A coordinate probe and a subprocess screen cannot run over one loaded registry without losing their point
  Evidence: Both tools' tests are selected by the default lane, confirmed by collection rather than assumed - thirty tests across the four newest modules - and the lane-visibility screen reports no module in the tree carrying no…
    Disposition: open or blocked as titled (source order 208).
- [209] campaign-findings-use-a-second-heading-format | high | Seventy-seven findings appended here cannot be cited, because they abandoned the format the preceding hundred and thirty-one use (count corrected by campaign-findings-count-corrected)
  campaign-findings-count-corrected)
  Evidence: The 131 findings before line 3279 carry `slug | severity | summary`. Disposition: corrected or remeasured as titled (source order 209).
- [210] campaign-findings-count-corrected | low | Seventy-seven of the eighty unstructured headings are findings; three are section headers that never needed a slug
  Evidence: The corrected figure is seventy-seven, and the shape of the document is sharper than the first count suggested. Disposition: status not explicit in this entry; see source-order chronology (source order 210).
- [211] campaign-findings-conversion-complete | low | All seventy-seven findings now carry a slug and a severity, and the distribution says something about the campaign
  Evidence: Severity was assigned by reading each finding rather than by rule, and the distribution across all 210 is 16 critical, 68 high, 92 medium and 34 low. Disposition: status not explicit in this entry; see source-order
    chronology (source order 211).
- [212] warm-probe-was-not-guaranteed-warm | high | A warm measurement against empty caches is a cold measurement wearing the wrong label
  Evidence: Running the claim screen minutes later returned 380 and 337, the gap intact. Disposition: status not explicit in this entry; see source-order chronology (source order 212).
- [213] third-import-graph-blind-spot-is-a-string-class-path | medium | The last stale member is reached by a dotted class path in a table, which no import edge records
  Evidence: What reaches them is a string: `cadrumo.core.errors.registry._core` carries the literal `"cadrumo.core.errors.not_found.CoreNotFoundError"` in an error table, resolved at runtime. Disposition: status not explicit in
    this entry; see source-order chronology (source order 213).
- [214] lane-figures-describe-a-selection-ci-does-not-run | high | Every lane number in this audit comes from a path overlapping the CI recipe in one directory of eighteen
  Evidence: This campaign has quoted a "development registry lane" figure in a dozen findings - 46 failures, then 36, then 41, then 42 - and treated the movement as the tree's state. Disposition: status not explicit in this entry;
    see source-order chronology (source order 214).
- [215] three-dev-test-directories-are-named-by-nothing | critical | 163 tests sit in directories no recipe and no workflow names, and the conformance suite is only the smallest of them
  Evidence: The other three hold tests: `dev/source_connectivity/tests` carries 105 across sixteen files, `dev/tui/tests` carries 39 in one, and `dev/registry/conformance/tests` carries 19 in two. Disposition: status not explicit
    in this entry; see source-order chronology (source order 215).
- [216] never-run-tui-suite-reports-this-campaigns-own-defect | high | A coverage table names two interfaces the tree does not define, in a suite nothing runs
  Evidence: The three uncovered directories cannot be wired into a lane without knowing what they say, so the smallest was run: 33 passed, 5 skipped, 1 failed, in fifteen seconds. Disposition: status not explicit in this entry;
    see source-order chronology (source order 216).
- [217] never-run-source-connectivity-suite-splits-three-ways | high | 101 pass, 20 error on absent custody infrastructure, and 9 drift - eight frozen hashes and one locator, per transient-syntax-error-masked-a-real-locator-drift
  Evidence: The census asserts a recorded sha256 per capability and reports `capability coverage drift for coverage.remaining-calculation-helpers: expected sha256:cf1081c0... Disposition: status not explicit in this entry; see
    source-order chronology (source order 217).
- [218] ninth-source-connectivity-failure-is-a-mid-edit-syntax-error | medium | SUPERSEDED by transient-syntax-error-masked-a-real-locator-drift: the IndentationError was hiding a real failure, not causing it
  Evidence: The failure left unclassified in the previous finding is `test_final_census_has_no_expired_ disappearance_or_unsupported_connection`, and it fails on an `IndentationError` at… Disposition: withdrawn or superseded as
    titled (source order 218).
- [219] transient-syntax-error-masked-a-real-locator-drift | high | The ninth failure was not the IndentationError; the IndentationError was hiding it
  Evidence: They finished - a sweep now parses all 5,837 files under `src` with none unparseable - and the test still fails. Disposition: status not explicit in this entry; see source-order chronology (source order 219).
- [220] ci-selection-run-rejected-by-its-own-reconciliation | high | 3,881 collected against 3,618 reported: 263 tests vanished and the result is unusable
  Evidence: The run reported 142 failed, 3,416 passed and 60 errors, which is 3,618. Disposition: status not explicit in this entry; see source-order chronology (source order 220).
- [221] ci-selection-retry-launched-with-a-piped-exit-status | low | The retry captures tail's status, not pytest's, which is the first trap this campaign documented
  Evidence: The CI selection is being retried at two workers rather than automatic, on the reasoning that the forty-seven-minute run lost 263 tests to worker deaths under contention this campaign's own measurements were…
    Disposition: status not explicit in this entry; see source-order chronology (source order 221).
- [222] empty-test-package-outlived-its-only-test | low | A test package survives with a docstring describing tests deleted in 2026-08
  Evidence: One is empty for a traceable reason, and the other three hold 163 tests that no lane runs, of which two were examined and both reported real defects on first contact. Disposition: status not explicit in this entry; see
    source-order chronology (source order 222).
- [223] corrected-findings-now-point-at-their-corrections | medium | Three headings asserted figures or conclusions this campaign later revised, with the revision recorded only further down
  Evidence: An audit read by grepping for a slug does not, and 222 findings is well past the length anyone reads through. Disposition: status not explicit in this entry; see source-order chronology (source order 223).
- [224] vacuity-screen-tests-broken-since-august-in-a-lane-ci-runs | critical | Sixteen tests fail on git exit 128 because a fix added a repository dependency their fixtures cannot satisfy
  Evidence: returned non-zero exit status 128`. Disposition: open or blocked as titled (source order 224).
- [225] tui-boundary-proofs-fail-while-the-boundaries-hold | high | Seven tests that prove the import contracts bite are broken, and import-linter itself passes eleven contracts cleanly
  Evidence: Run directly they fail in about a second, and the contracts they guard are fine: `lint-imports` against the real configuration reports eleven kept, zero broken, exit zero, over 5,749 files. Disposition: status not
    explicit in this entry; see source-order chronology (source order 225).
- [226] crashed-run-lower-bound-is-fifty-two-modules | medium | 142 reported failures across 52 modules, three examined and the rest left named rather than mined
  Evidence: Reported, it names 142 failures across 52 modules - 37 under `dev/registry`, 27 directly under `dev`, 20 under `dev/docs`, 17 under `dev/audit`. Disposition: status not explicit in this entry; see source-order
    chronology (source order 226).
- [227] second-live-monetary-scale-defect-in-modelo-353 | critical | A second field emits unscaled where its siblings emit cents, and the gate proving the first now fails on the count
  Evidence: The new one is modelo 353, revision 2026-desde-02, casilla 10, field `m353-2026.pagina01.f127`: unscaled where 7 sibling amounts of width 17 in `m353-declaracion` emit cents. Disposition: status not explicit in this
    entry; see source-order chronology (source order 227).
- [228] monetary-criterion-figures-mapped-to-their-screen-conditions | medium | The criterion's two counts are 26 and 2, and the five unexpected-scale fields it does not count are a separate concern
  Evidence: That count is 26, where the criterion said 24. Disposition: status not explicit in this entry; see source-order chronology (source order 228).
- [229] modelo-353-defect-is-not-new-its-classification-changed | high | The field was already recorded as unscaled; what is new is that it now also disagrees with its siblings
  Evidence: An existing finding, `the-note-behind-the-filing-defect-says-nothing-about-the-wire-and-now-says- so-in-quotation`, records that the modelo 353 field renders unscaled and quotes the design note behind it - `Nota 4:…
    Disposition: status not explicit in this entry; see source-order chronology (source order 229).
- [230] sibling-count-assertion-was-false-before-this-campaign-measured-it | medium | Nothing changed in modelo 353; the test asserting one disagreement has failed in every lane run since the module appeared
  Evidence: The 2026 export's recent history is an encoding spelling corrected from `latin-1` to `iso-8859-1` in three lines, a provenance refresh and a design-epoch bounding - no `data_type` touched. Disposition: status not
    explicit in this entry; see source-order chronology (source order 230).
- [231] registry-failures-dated-against-the-lane-logs | medium | Eight failures predate every measurement here and five arrived mid-campaign, two of them from commits to the module they test
  Evidence: Eight appear in all six runs: the generated export trees, the load census classification, the real closure outcomes, the render check, the m303 envelope proof, the static inspection, the modelo-specific embed…
    Disposition: status not explicit in this entry; see source-order chronology (source order 231).
- [232] inspection-authority-crossed-into-the-application-layer-by-decision | high | Four application modules reach the static inspection API a gate forbids, and a commit message says the crossing was decided
  Evidence: Dated against the tree rather than reasoned about, the crossings arrive on 26 and 27 August, and the commit that introduces the first says what it is doing in its subject line: "decide(tui- architecture): S278, root…
    Disposition: status not explicit in this entry; see source-order chronology (source order 232).
- [233] embed-classification-failure-is-three-conditions-not-one | medium | Twenty-one reconciliation failures split into seven unclassified modules, nine stale dispositions and three undispositioned literals
  Evidence: Seven modules carry no classification: `_invoice_row_materialization` for modelos 347 and 349, `_withholding_rows` for 190 and 193, `formula_runtime_m100`, three ledger binding families for 100, 130 and 131, and the…
    Disposition: status not explicit in this entry; see source-order chronology (source order 233).
- [234] this-campaign-was-one-of-the-four-undeclared-prose-parsers | high | A screen written here read design prose without enrolling in the channel, and the failure was filed as inherited for six lane runs
  Evidence: It was, in part: two of the four modules date from 31 August. Disposition: status not explicit in this entry; see source-order chronology (source order 234).
- [235] collision-gate-caught-a-deleted-adjudication-and-a-new-collision | high | One row was removed correctly and one was removed while its collision remained, and this campaign missed both for a day
  Evidence: `declared_destination_ids` is defined in the TUI's routes and in its navigation module, both reading a closed set from a type alias through `get_args` - and reading different aliases, the modelo workspace's…
    Disposition: status not explicit in this entry; see source-order chronology (source order 235).
- [236] adjudication-was-acted-on-and-the-collapse-is-now-watched | medium | The duplicate this campaign named as owed a merge was merged into the home it named, and the result is held at one definition
  Evidence: Also confirmed this iteration: all eight gate modules written here pass, fifty-three tests, exit zero - checked after finding that the sweep which dated the registry failures had excluded this campaign's own…
    Disposition: status not explicit in this entry; see source-order chronology (source order 236).
- [237] second-adjudication-acted-on-and-the-vanishing-guard-is-gone | medium | The contract conflict's most dangerous property was removed; the conflict itself remains and the row now says so
  Evidence: The disposition row is updated rather than closed, because the row exists to say a decision is owed about which contract is right, and that decision has not been taken. Disposition: open or blocked as titled (source
    order 237).
- [238] ci-selection-measured-at-167-failures-and-72-errors | critical | The lane CI actually runs carries 239 failing or erroring tests of 3,881, measured cleanly at last
  Evidence: 3,881 tests collected; 167 failed, 3,640 passed, 2 skipped and 72 errored, which is 3,881 exactly. Disposition: status not explicit in this entry; see source-order chronology (source order 238).
- [239] lane-criterion-named-a-lane-nobody-runs | high | The acceptance criterion quoted fifteen failures over a path sharing one directory of eighteen with the lane CI invokes
  Evidence: Over the eighteen-directory selection CI invokes, measured once to a reconciling total, it is 167 failures and 72 errors of 3,881 tests. Disposition: status not explicit in this entry; see source-order chronology
    (source order 239).
- [240] criterion-claimed-no-failure-belonged-to-this-plan | high | The accounting summed to a fifteen-failure state that no longer exists and asserted an ownership that was wrong
  Evidence: That sums to fifteen, which is the state the adjacent sentence described before it was corrected, and the lane has since been at forty-two over the registry directories and 239 over the selection CI runs. Disposition:
    status not explicit in this entry; see source-order chronology (source order 240).
- [241] the-obvious-fix-for-stale-criteria-is-forbidden-and-rightly | medium | A gate checking the plan's figures would make code depend on the vault, which the project explicitly forbids
  Evidence: The cost of that inversion is paid later and by someone else, which is the same trade this campaign has refused four times in the form of baselined gates. Disposition: status not explicit in this entry; see
    source-order chronology (source order 241).
- [242] a-figure-recording-history-does-not-go-stale | medium | Only one of the Verification section's remaining counts needed retiring; the others describe past events and are correct as written
  Evidence: Four criteria were corrected for quoting figures that stopped being true, and the reflex it leaves is to treat every number in a document as a liability. Disposition: status not explicit in this entry; see source-order
    chronology (source order 242).
- [243] refusal-test-was-invalidated-by-someone-fixing-the-thing-it-relied-on | medium | A fixture pinned to a revision with no generated layout broke when that layout was published
  Evidence: The render-check suite gained a second failure, and its cause is the most benign one available: `test_a_revision_without_a_generated_layout_is_refused_by_name` named modelo 200's 2025 revision as an example of a…
    Disposition: status not explicit in this entry; see source-order chronology (source order 243).
- [244] a-pin-to-a-live-defect-owes-its-replacement-in-writing | medium | Two of this campaign's tests pin revisions the plan has open Steps to rename, and neither said what happens when they are
  Evidence: The name-window tests are the other kind: they pin modelo 151 and modelo 185 because those revisions genuinely misstate their windows, and the plan carries open Steps to rename both. Disposition: open or blocked as
    titled (source order 244).
- [245] every-pin-to-a-stepped-defect-now-carries-its-replacement | medium | The three name-window tests pinned to defects the plan still owes a rename now each say what their failure means and what replaces them
  Evidence: All three now carry one: `name_opens_before_window` (modelo 185), `name_opens_after_window` (modelo 151), and the open-end condition (modelo 721, replaced by modelo 194, which sits in the same state for the same
    reason). Disposition: status not explicit in this entry; see source-order chronology (source order 245).
- [246] a-generator-refactor-left-twenty-one-attestations-stale | high | Twenty-one published export trees stopped reproducing on 2026-09-03; all sampled differ only in the manifest, so the records are correct and the attestations are not
  are not
  Evidence: The newly non-reproducing trees are `151`, `202`, `210`, `222`, `232`, `303`, `322` and `353` - twenty-one revisions in all. Disposition: status not explicit in this entry; see source-order chronology (source order
    246).
- [247] a-ledger-of-a-mechanical-mass-state-is-churn-not-explanation | high | The generated-tree gate demanded a written reason per tree for a condition that arrives twenty-one at a time, so it was split by class
  Evidence: That was tolerable while both classes were small. Disposition: status not explicit in this entry; see source-order chronology (source order 247).
- [248] a-successor-that-is-itself-scheduled-for-correction-is-not-a-replacement | medium | All three name-window pins named live successors, and every one of those successors carries its own open rename Step
  Evidence: But the plan carries an open rename Step for every one of them - 151, 185, 720, 322, 194 and 721 - so each named successor leaves at the same time as the coordinate it was offered to replace. Disposition: open or
    blocked as titled (source order 248).
- [249] a-directory-ci-never-runs-held-a-stale-interface-table | high | dev/tui/tests reports 39 tests and one failure: the coverage table named two classes a refactor had removed
  Evidence: The corrected entry is a single interface with a comment saying why one is the whole of it; naming the pane would have kept the gate red while looking like a fix. Disposition: status not explicit in this entry; see
    source-order chronology (source order 249).
- [250] the-source-connectivity-step-quoted-a-count-nobody-had-recollected | medium | The Step said a hundred and five never-run tests; a live collection reports a hundred and thirty, of which the default lane selection admits a hundred and eight
  hundred and eight
  Evidence: What the timing does show is a startup shape worth knowing: the first authority build costs 103 seconds, a further one-time 18 seconds is spent on the call after it, and every call thereafter is 0.21. Disposition:
    status not explicit in this entry; see source-order chronology (source order 250).
- [251] the-repository-already-answers-which-tests-no-lane-reaches | high | A hard gate computes the unreached set with no allowlist, and it disagreed with both my hand analysis and the plan
  Evidence: Two corrections follow. Disposition: status not explicit in this entry; see source-order chronology (source order 251).
- [252] the-source-connectivity-failures-are-a-stale-reviewed-set-not-a-stale-count | high | Nine tests fail on a selector digest that no longer matches the live helper set, and they fail in the default CI lane rather than in silence
  silence
  Evidence: A test is called `test_s115_freezes_reviewed_s112_helper_set_by_secondary_count`, embedding two plan Step identifiers in a test name. Disposition: status not explicit in this entry; see source-order chronology (source
    order 252).
- [253] the-conformance-directory-timed-out-on-a-host-that-was-already-saturated | medium | A closure test hit the 300-second per-test ceiling while the machine carried a hundred and sixty python processes at full CPU
  Evidence: The harness banner recorded the host at 100% CPU across twenty-four cores with a thousand processes and a hundred and sixty of them python, which is this tree being worked by several sessions at once. Disposition:
    status not explicit in this entry; see source-order chronology (source order 253).
- [254] a-deleted-gate-left-its-pattern-table-orphaned-and-its-violations-standing | high | The marker-integrity gate was deleted with 1770 lines; its declarative half survives with no consumer, and two test names it forbade are back
  back
  Evidence: Two failing test names carrying plan Step identifiers - `test_s115_freezes_reviewed_s112_helper_set_by_secondary_count` and `test_s44_runner_observes_every_live_no_recovery_outcome` - raised the question of which…
    Disposition: status not explicit in this entry; see source-order chronology (source order 254).
- [255] the-src-to-dev-boundary-survived-that-deletion-and-a-third-hypothesis-died-checking-it | medium | The same sweep deleted the dev-path isolation gate, but its rule moved rather than lapsed, and the surviving gate's docstring is what misled
  docstring is what misled
  Evidence: Read together those facts say a `dev/` path literal in a shipped module is caught by nothing, and a probe confirmed the governance scan is silent on one while catching a `.vault/` literal in the same file. Disposition:
    status not explicit in this entry; see source-order chronology (source order 255).
- [256] the-orphaned-pattern-table-has-a-consumer-again-and-a-case-it-was-missing | high | Restoring the walk unchanged would have been green over sixteen files carrying a step id in a test name
  Evidence: Measured over every tracked test module, it finds thirty-seven names in sixteen files: four under `dev/`, twelve under `src/`, one of them a whole module named `test_s423_selected_language_cli.py`. Disposition: status
    not explicit in this entry; see source-order chronology (source order 256).
- [257] the-development-tree-step-id-names-are-gone-and-the-pin-redeemed-itself | high | Four test symbols renamed, the gate's expectation is now the empty set, and the rename changed no behaviour
  Evidence: Behaviour is unchanged, which the run shows rather than asserts: eight passed and one failed, and the failure is the census digest drift already recorded here, reporting the identical expected and observed sha256…
    Disposition: status not explicit in this entry; see source-order chronology (source order 257).
- [258] the-registry-tooling-prose-cited-plan-steps-as-if-they-were-components | high | Thirteen sites named a step where they meant a boundary; the subtree now carries only the fixtures a detector must contain
  Evidence: The pipeline modules called a loader boundary "the S10 loader boundary", said "S10 validates it", described a candidate as "the S10 candidate", and gated publication "before S11 is allowed to publish it". Disposition:
    status not explicit in this entry; see source-order chronology (source order 258).
- [259] the-conformance-closure-test-passes-in-three-minutes-and-was-never-hung | medium | It exits 0 in 182 seconds under a host at 98.8% CPU; the earlier timeout was the ceiling being struck, not a deadlock
  Evidence: It passed in 182.58 seconds, exit 0, on a host carrying a hundred and eighty-nine python processes at 98.8% CPU - worse contention than the run that timed out. Disposition: status not explicit in this entry; see
    source-order chronology (source order 259).
- [260] the-marker-scan-now-tells-a-suppression-from-a-step-id | medium | A module's own lint vocabulary excuses prose naming it, and the exemption is keyed per module so it cannot be borrowed
  Evidence: That limitation is now closed rather than noted. Disposition: open or blocked as titled (source order 260).
- [261] the-largest-marker-population-is-a-provenance-field-nothing-reads | high | Seventy-six rows name a plan phase pair as their owning authority, validated only for being non-empty and consumed by nothing
  Evidence: Seventy-six of them read `tui-interface W05.P10/W05.P11` or a sibling phase pair. Disposition: status not explicit in this entry; see source-order chronology (source order 261).
- [262] the-conformance-directory-holds-nineteen-tests-and-one-blocked-failure | high | Eighteen pass and one fails on a broken edge, in eight minutes fifty-seven seconds serial
  Evidence: With the ceiling raised past the three-minute test, the directory completes: nineteen tests, eighteen passed, one failed, exit 1, in 536.76 seconds. Disposition: status not explicit in this entry; see source-order
    chronology (source order 262).
- [263] the-plan-restated-its-own-sequencing-three-times | medium | A document arguing against declaring one fact in many places was doing it, and the copies had drifted
  Evidence: Afterwards the plan holds fifty-nine prose paragraphs with no exact restatement and a highest pairwise similarity of 0.42, down from 0.74. Disposition: status not explicit in this entry; see source-order chronology
    (source order 263).
- [264] three-sections-claimed-to-be-the-current-position-and-only-one-was | medium | The first two consolidated positions asserted precedence with no forward pointer; a reader arriving at either was told the wrong thing
  Evidence: It reports something better: two hundred and sixty-six findings and no near-duplicate pair, with the similarity distribution topping out at 0.33 against the plan's 0.74 before repair. Disposition: status not explicit
    in this entry; see source-order chronology (source order 264).
- [265] the-selection-probe-erased-the-one-case-it-was-built-to-show | high | A retry that rescued the answer also cleared the refusal, so the single undecidable coordinate reported like any other row
  Evidence: Asking the authority directly for modelo 308 at filing year 2011 raises `AmbiguousRevisionSelectionError` at every grade, exactly as it should - the windows split at the end of June, so the year alone cannot choose -…
    Disposition: status not explicit in this entry; see source-order chronology (source order 265).
- [266] a-pin-held-by-count-failed-when-its-screen-succeeded | high | The sibling-scale gate went red because it found a second defect, which is the one outcome a detector proof must not punish
  Evidence: Two now do: modelo 200's casilla 03594 and modelo 353's casilla 10, each emitting unscaled beside siblings emitting cents. Disposition: status not explicit in this entry; see source-order chronology (source order 266).
- [267] the-count-rule-applied-to-this-campaign-s-own-screen-tests | medium | Two more frozen live-corpus counts found and replaced by identity; the other three were relational and already correct
  Evidence: The chain is now named (`dr303-112`) with the instruction its pin owes, and the revision-count assertion is replaced by the part of the detail that carries the claim: that no casilla carries a chain. Disposition:
    status not explicit in this entry; see source-order chronology (source order 267).
- [268] two-criteria-verified-live-and-two-figures-in-my-own-prose-found-stale | medium | The monetary criterion reproduces exactly; the explanation beside it had drifted, and the eligibility figure has no reproducer at all
  Evidence: The runner's docstring said the split was "132 of the 158 rows"; the live totals are 132 of 165. Disposition: status not explicit in this entry; see source-order chronology (source order 268).
- [269] the-nine-screen-property-gates-exist-and-the-gate-total-had-moved | medium | The named criterion verifies function by function; the figure beside it was three behind
  Evidence: Twenty-one pass, exit 0, in two minutes fifteen. Disposition: status not explicit in this entry; see source-order chronology (source order 269).
- [270] the-accessor-criterion-claimed-three-drop-proofs-and-two-exist | medium | Both are the right two, and naming them is stronger than the sentence that rounded up
  Evidence: The criterion protecting the resolved export surface said the accessor is proven by a test asserting it fails if any of its three linkage paths is dropped. Disposition: status not explicit in this entry; see
    source-order chronology (source order 270).
- [271] the-restatement-count-this-plan-rests-on-is-now-data-instead-of-prose | high | Six year-level temporal sites are declared, each gated against the live schema, with the boundary stated
  Evidence: Seven tests pass, exit 0. Disposition: status not explicit in this entry; see source-order chronology (source order 271).
- [272] the-validator-family-is-not-all-reconciliation-and-one-screen-condition-is-a-canary | high | The fifty-one figure verifies exactly, but only a minority of the family exists because a fact is stated twice
  Evidence: `_validate_revision_id_window_agreement` refuses an id asserting open-endedness over a window closed on either axis, at build time. Disposition: status not explicit in this entry; see source-order chronology (source
    order 272).
- [273] one-declared-condition-was-silent-and-unexercised-and-is-now-proven | high | Four of the five silent conditions already had constructed proofs; the fifth had none, and it works
  Evidence: `money_split_representation` appeared silent because the measurement ran through the census wrapper, which filters that kind deliberately; the screen emits 132 of them. Disposition: status not explicit in this entry;
    see source-order chronology (source order 273).
- [274] two-detector-proofs-were-named-for-the-screen-and-never-ran-it | high | They asserted the index beneath the screen, which shows a defect is visible without showing the screen reports it
  Evidence: Six tests pass, exit 0. Disposition: status not explicit in this entry; see source-order chronology (source order 274).
- [275] a-gate-recovered-its-own-subject-with-four-regexes-and-now-reads-a-declaration | high | Each regex was added when a new assignment shape appeared, which is the failure the sibling gates refuse by design
  Evidence: Fourteen tests pass, exit 0, and the census is unchanged at fourteen findings across five kinds. Disposition: status not explicit in this entry; see source-order chronology (source order 275).
- [276] the-central-invariant-was-guarded-by-a-substring-that-punished-documentation | high | A module explaining why it must not call the binding derivation would have failed the gate protecting that rule
  Evidence: The gate holding this campaign's central invariant - no screen rebuilds the resolved export surface - detected a reach by searching each module's text for the derivation's name. Disposition: status not explicit in this
    entry; see source-order chronology (source order 276).
- [277] the-ci-lane-selection-re-measured-to-a-reconciling-total | high | 177 failures and 109 errors of 3,941 collected, and the duration is not comparable
  Evidence: It reports 177 failed, 3,653 passed, 2 skipped and 109 errors, which sum to the 3,941 collected - the reconciliation being the point, since a headline that does not add up to its own collection is the defect this…
    Disposition: status not explicit in this entry; see source-order chronology (source order 277).
- [278] fourteen-of-the-lane-errors-are-one-authority-that-never-finishes-compiling | high | A 2.5 MB input takes more than ten minutes, which no amount of host contention explains
  Evidence: Of the 109 errors, 21 sit in terminology resolution, 17 in deployment search parity and 14 in the registry tree, the rest scattered; the registry fourteen are this plan's to account for. Disposition: status not
    explicit in this entry; see source-order chronology (source order 278).
- [279] the-recompile-shape-is-in-three-sibling-modules-and-a-collision-gate-caught-a-new-name | high | One anti-pattern written three times, and a gate red for exactly the reason it exists
  Evidence: The gate's own failure message showed a populated set and corrected me before the mistake reached this record. Disposition: status not explicit in this entry; see source-order chronology (source order 279).
- [280] the-documentation-privacy-gate-was-red-on-two-operator-home-paths | high | Committed audit prose carried the operator's home directory; the quality directory is green again at 335 tests
  Evidence: The directory now passes at 335, exit 0. Disposition: status not explicit in this entry; see source-order chronology (source order 280).
- [281] the-step-id-gate-fired-on-a-name-that-arrived-hours-after-it-was-written | high | It is red, correctly, and the right repair is not the one that makes it green
  Evidence: Renaming that test would make the gate green and remove nothing: the owning module calls the same thing "the reviewed, disjoint M200/2024 S14/S15 compiler" in its module docstring, "the closed S14/S15 declarations"…
    Disposition: status not explicit in this entry; see source-order chronology (source order 281).
- [282] this-campaign-added-eight-of-the-violations-it-was-triaging | high | The UTF-8 gate was flagging my own files, and truncated output hid it from me twice
  Evidence: The UTF-8 enrolment gate reports 83 bare literals across non-ratcheted `dev/` files. Disposition: status not explicit in this entry; see source-order chronology (source order 282).
- [283] the-held-file-constraint-has-lifted-and-was-hiding-a-different-one | high | Seven pending paths in the whole worktree; what blocks the remaining Steps now is this executor's scope, not another contributor's diff
  Evidence: The worktree carries seven pending paths in total, one of them under `src/`, and every path those Steps name is clean: the application closure module, the export schema, the filing export proof, the modelo 151 and…
    Disposition: status not explicit in this entry; see source-order chronology (source order 283).
- [284] the-screens-package-declared-one-helper-ten-times | high | Byte-identical copies in all ten screen modules, now one defining module, census unchanged at 1,651
  Evidence: The runner reports the same 1,651 findings across the same ten screens, and the twenty-two declaration invariant gates pass, exit 0 - including the ones that discover screens by signature, list them against the…
    Disposition: status not explicit in this entry; see source-order chronology (source order 284).
- [285] the-pipeline-duplicated-two-guards-and-one-algorithm-and-only-the-guards-were-collapsed | high | A drifting sum is a wrong number; a drifting guard is a route into the tree that stops refusing
  Evidence: Two are refusals: the check and validation paths both refused a link-like or absent location, and the check and publication paths both asked whether one location sits inside another. Disposition: status not explicit in
    this entry; see source-order chronology (source order 285).
- [286] one-filename-three-declarations-and-one-value-under-two-names | high | The inverse of the constant-agreement gate: not one name with two values, but one value with several names
  Evidence: A manual-source sha256 declared in three modelo 200 modules under one name. Disposition: status not explicit in this entry; see source-order chronology (source order 286).
- [287] the-registry-tooling-now-states-each-of-those-values-once | high | Three more restatements collapsed, and the digest one is the reason the class matters
  Evidence: Two modules deciding separately what a sha256 looks like is different in kind: a relaxation applied to one leaves the other still refusing, so the tree gains a route that accepts a digest another route rejects, and…
    Disposition: status not explicit in this entry; see source-order chronology (source order 287).
- [288] the-seven-stale-rules-are-not-stale-the-census-went-blind | high | Six of the seven targets still exist; the resolver stopped following a dynamic import and the symptom surfaced a directory away
  Evidence: The rules are correct. Disposition: status not explicit in this entry; see source-order chronology (source order 288).
- [289] the-census-can-follow-the-snapshot-edge-again-by-asking-instead-of-parsing | high | The resolver evaluates the declaration in a separate interpreter; renta is back in the universe and the stale count fell from seven to six
  Evidence: Finding the import sites first and evaluating only when one exists takes 17.4 seconds over sixteen sites. Disposition: status not explicit in this entry; see source-order chronology (source order 289).
- [290] the-census-is-clean-and-the-six-were-stale-after-all-but-only-provably-so-afterwards | high | Eight tests pass; the same deletion refused two iterations ago is now the right one, for a reason that did not exist then
  Evidence: The six classification entries left standing last iteration are retired and the load census is clean: eight tests pass, exit 0, no unclassified module, no stale rule. Disposition: status not explicit in this entry; see
    source-order chronology (source order 290).
- [291] the-evaluator-is-proven-and-the-four-remaining-unresolved-sites-are-correctly-unresolvable | medium | Ten tests pass; every refusal path is exercised, and the residue is accounted for rather than left open
  Evidence: Ten tests pass in that module, exit 0. Disposition: open or blocked as titled (source order 291).
- [292] the-load-census-now-has-a-criterion-and-it-carries-the-instrument-condition | medium | A coverage number means nothing unless the thing counting can see, and the plan now says so where the number is quoted
  Evidence: The first is the coverage: every module the registry load reaches carries exactly one reviewed classification, which holds today at 411 modules in the universe, none unclassified and no stale rule. Disposition: status
    not explicit in this entry; see source-order chronology (source order 292).
- [293] the-consolidations-are-verified-against-every-screen-and-the-census-is-byte-stable | high | 79 tests pass across the ten screen modules, exit 0, and the corpus still reports 1,651 findings
  Evidence: The runner reports the same 1,651 findings across the same ten screens it reported before any of it, and the declaration invariant gates - which discover screens by signature, hold them against the contributor…
    Disposition: status not explicit in this entry; see source-order chronology (source order 293).
- [294] the-gate-that-excluded-fact-bullets-left-a-miscount-standing-in-them | high | A screen said four facts decided its answer and listed five; twenty-three gates pass now
  Evidence: Twenty-three tests pass in that module, exit 0. Disposition: status not explicit in this entry; see source-order chronology (source order 294).
- [295] the-count-gate-was-keyed-to-one-spelling-and-read-four-screens-of-five | high | A screen saying "disagreements" instead of "conditions" was never checked
  Evidence: A gate that asserts it found something to check is worth the extra line every time; without it the broadened pattern would have passed silently while reading zero screens. Disposition: status not explicit in this
    entry; see source-order chronology (source order 295).
- [296] two-absence-gates-could-not-prove-they-had-looked-and-most-already-could | medium | The sweep flagged thirteen, then nine, and the answer was two
  Evidence: The second flagged nine by looking for absence assertions without a truthiness guard, and missed the comparison form: the package-initialiser gate proves it looked with `checked > 1`, and the vault citation gate with…
    Disposition: status not explicit in this entry; see source-order chronology (source order 296).
- [297] the-phase-heading-described-half-its-contents-and-my-first-correction-said-a-tenth | medium | Counted: 80 records, 83 tooling Steps, two source, three other
  Evidence: Counting them says otherwise: 80 name a decision or record under `.vault`, 83 name development tooling, two name `src` and three name something else. Disposition: status not explicit in this entry; see source-order
    chronology (source order 297).
- [298] the-two-modules-this-session-created-had-no-tests-and-no-gate-asked-for-any | high | The screen-test gate requires a test module of screens only, so a defining module slips past it
  Evidence: A real directory passes, so the refusals are not vacuous; a missing path is refused by subject name; and a symlink is refused THOUGH IT EXISTS, which is the case a guard checking only `exists()` would admit and the…
    Disposition: status not explicit in this entry; see source-order chronology (source order 298).
- [299] eighteen-twelve-eight-one-and-only-the-last-was-true | high | Three wrong ways of asking which modules lack tests, and the answer was one module
  Evidence: It runs now, in 9.6 seconds, exit 0, so the committed manifest and census artefact are proved to reproduce from their pinned sources. Disposition: status not explicit in this entry; see source-order chronology (source
    order 299).
- [300] the-coverage-question-is-now-a-gate-rather-than-a-sweep-somebody-remembers-to-run | high | Twenty-five gates pass; the measure that took four attempts is now standing, with a planted proof
  Evidence: Both directions matter. Disposition: status not explicit in this entry; see source-order chronology (source order 300).
- [301] the-proof-i-wrote-two-iterations-ago-was-proving-its-own-copy | high | The principle stated last iteration indicted it immediately; one shared walk now serves both
  Evidence: Twenty-five tests pass, exit 0. Disposition: status not explicit in this entry; see source-order chronology (source order 301).
- [302] every-constructed-screen-proof-asserts-through-its-screen-and-the-readme-needs-nothing | medium | Two negative results, one of which is a decision not to write documentation
  Evidence: The second result is a decision not to act. Disposition: status not explicit in this entry; see source-order chronology (source order 302).
- [303] the-plan-s-opening-figures-cite-this-audit-and-this-audit-does-not-contain-them | high | Searching finds them only where a later entry quotes the sentence that cites them
  Evidence: The figures are not withdrawn. Disposition: status not explicit in this entry; see source-order chronology (source order 303).
- [304] the-grade-figure-cannot-be-re-derived-and-the-grade-looks-declared-once-today | high | One optional field, a documented reading and a documented distinction - the shape this plan recommends, not the defect it alleges
  Evidence: So the figure is recorded as unre-derivable rather than confirmed or withdrawn. Disposition: status not explicit in this entry; see source-order chronology (source order 304).
- [305] the-citation-surface-is-25-types-and-48-fields-where-the-plan-said-eleven | high | Re-derivation moved this figure the other way, and the symmetry it exposed is the more useful half
  Evidence: That is not one concept restated 48 times; it is one PAIR of concepts declared 24 times, which is a different defect with a different remedy. Disposition: status not explicit in this entry; see source-order chronology
    (source order 305).
- [306] applicability-is-three-or-ten-and-the-plan-said-seven | high | The clearest of the four re-derivations, because both defensible answers are defensible and neither is the one on record
  Evidence: All four re-derivable figures now behave the same way. Disposition: status not explicit in this entry; see source-order chronology (source order 306).
- [307] the-last-figure-matches-and-the-match-is-the-least-informative-thing-about-it | high | Six declared fields, two under a stricter boundary, and the fact that decides a monetary scale is declared in none of them
  Evidence: It is not a field, so no count of declared places can include it - and it is the semantic behind both live filing-correctness defects this campaign has pinned, modelo 200's casilla 03594 and modelo 353's casilla 10,…
    Disposition: status not explicit in this entry; see source-order chronology (source order 307).
- [308] the-undeclared-scale-cannot-be-pinned-from-here-either-and-the-attempt-is-the-finding | high | A gate for it needs a hand-built field stub or a private renderer import, both of which this project refuses
  Evidence: The attempt was withdrawn rather than completed; nine tests pass in that module, exit 0, and no partial gate was left behind. Disposition: status not explicit in this entry; see source-order chronology (source order
    308).
- [309] the-step-id-leak-is-a-public-api-migration-not-a-test-rename | high | Five files, two exported function names, five refusal messages, seven docstrings and one test name
  Evidence: `S14/S15` names the cohort across five files: two exported function names - `check_m200_2024_s14_s15` and `publish_m200_2024_s14_s15` - five refusal messages, seven docstrings, and the one test name the gate can see.
    Disposition: status not explicit in this entry; see source-order chronology (source order 309).
- [310] i-closed-a-step-nobody-had-done | high | The codec-side scale gate was marked complete in the same breath as being authored, and is re-opened
  Evidence: A Step authored this iteration - pin the money wire type's hundredfold scale beside the codec that applies it - was marked closed minutes after being written. Disposition: reopened: gate was authored but its Step was
    not completed (source order 310).
- [311] the-false-closure-was-isolated-and-four-sampled-closures-verify | medium | Twenty-three Steps closed outside this execution's reach; the sample holds against the tree
  Evidence: The plan step identifiers a closed Step says were removed from the modelo 200 revision declarations are gone. Disposition: four sampled closures verified; 23 related Steps are outside this execution scope (source order
    311).
- [312] the-largest-screen-already-reports-the-unit-somebody-acts-on | medium | 1,389 of the corpus's 1,651 findings come from one screen, and the number is the collapsed one, not the raw one
  Evidence: Provenance consistency contributes 1,389 of the 1,651 findings the runner reports - eighty-four per cent of the total - which is exactly the shape that turned out to be a reporting artefact when the monetary screen's…
    Disposition: status not explicit in this entry; see source-order chronology (source order 312).
- [313] no-screen-hides-a-raw-count-behind-an-actionable-one-and-the-two-that-looked-like-it-were-my-key | medium | The finding shapes differ because the screens do, which is correct and which a generic check cannot assume
  Evidence: Keying every finding on modelo, revision and kind reported wire-type compatibility and provenance as collapsing twenty-nine and 1,389 rows onto one coordinate each, which would have been a spectacular gap. Disposition:
    open or blocked as titled (source order 313).
- [314] the-contract-i-wrote-was-wrong-and-its-own-gate-said-so-within-a-minute | high | A runner row is not a finding, and writing the contract as though it were is what seven mis-reads had in common
  Evidence: The gate reads the finding types rather than the rows, because a caller keying on a field wants to know the type declares it, and twenty-six tests pass in that module, exit 0. Disposition: status not explicit in this
    entry; see source-order chronology (source order 314).
- [315] the-runner-called-every-row-a-finding-including-the-two-that-are-reports | medium | One word in two output lines, and it was the conflation the contract had just been written to separate
  Evidence: The summary reads `screens=10 rows=1651`. Disposition: status not explicit in this entry; see source-order chronology (source order 315).
- [316] two-labels-named-revisions-and-counted-disagreements | medium | 67 rows over 53 revisions, and 36 over 34, each label promising the smaller number
  Evidence: The grade label said "declared grades that do not match what their prerequisites support" and counted 36 across 34. Disposition: status not explicit in this entry; see source-order chronology (source order 316).
- [317] the-readme-taught-the-conflation-too-and-a-gate-for-it-was-declined | medium | One sentence corrected; the label check is left to a person because gating it means parsing prose
  Evidence: The contributor README opens its screens section by saying each one "prints one greppable row per finding" - the wording corrected in the runner an iteration ago, in the document a contributor reads first. Disposition:
    corrected or remeasured as titled (source order 317).
- [318] the-screens-criterion-listed-nine-properties-and-there-are-twelve | medium | Written properties-first this time, because the total has moved twice while the properties have not
  Evidence: None was designed; each was the shape of a specific mistake, made durable. Disposition: status not explicit in this entry; see source-order chronology (source order 318).
- [319] i-added-three-properties-and-left-the-nine-in-front-of-them | high | The same stale-count defect, committed inside the edit correcting it, plus two ordinals pointing at positions that had moved
  Evidence: They now name the gates: the kind-naming gate and the condition-count gate. Disposition: status not explicit in this entry; see source-order chronology (source order 319).
- [320] one-more-positional-reference-into-a-list-that-can-grow-and-the-rest-are-safe | medium | "The tenth screen" now names itself; the other ordinals are local pairs and stay
  Evidence: Having broken two ordinal references by appending to the list they indexed, the plan was swept for the same shape. Disposition: status not explicit in this entry; see source-order chronology (source order 320).
- [321] three-capability-figures-drifted-by-one-each-and-a-qualifier-went-vacuous | medium | 23 not 22, 4 not 5, 69 not 68, and every filing-grade revision now carries a layout
  Evidence: Re-derived by running it: 58 modelos holds, 31 layouts spelling an envelope as a record holds, and three have moved by exactly one each - 23 modelos declaring applicability only where the plan said 22, 4 declaring…
    Disposition: status not explicit in this entry; see source-order chronology (source order 321).
- [322] the-step-s-population-holds-at-twenty-five-and-two-of-them-have-shipped-bytes | high | Modelos 185 and 222 carry a committed export tree while declaring applicability
  Evidence: Modelo 185's and modelo 222's 2025 revisions each carry a COMMITTED generated tree while declaring applicability. Disposition: status not explicit in this entry; see source-order chronology (source order 322).
- [323] two-more-step-premises-hold-and-one-of-them-only-under-the-boundary-it-never-stated | high | Five deadline-less filing revisions exactly; four formula-less filing claims under a narrow reading and thirty-five under a wide one
  one
  Evidence: The Step now carries their revision identifiers, which it did not - modelo 145's 2012-01-31-y-siguientes, 151's 2015-2022, 165's 2016-2022, 308's 2019-y-siguientes and 309's 2023-y-siguientes - because a Step naming…
    Disposition: status not explicit in this entry; see source-order chronology (source order 323).
- [324] the-multi-axis-step-said-four-and-three-and-the-live-answer-is-one-and-two | high | Fourteen revisions fail several axes; exactly one of them reaches filing grade
  Evidence: Exactly one of them reaches filing grade - modelo 308's 2019-y-siguientes - and it fails two axes, not three: it claims a calculation class with no formulas, and it files without a deadline window. Disposition: status
    not explicit in this entry; see source-order chronology (source order 324).
- [325] the-registry-suite-after-the-session-s-changes-introduced-nothing | high | 35 failed, 1,048 passed, one failure cleared and none new by identity
  Evidence: It reports 35 failed and 1,048 passed. Disposition: status not explicit in this entry; see source-order chronology (source order 325).
- [326] twenty-eight-of-the-thirty-five-registry-failures-were-attributed-and-two-more-now-are | high | Both new ones are other campaigns' work tripping this campaign's gates, which is the gates working
  Evidence: All four sit on surfaces belonging to the modelo 200 and 303 work, which has been committing throughout this session. Disposition: status not explicit in this entry; see source-order chronology (source order 326).
- [327] every-registry-failure-is-now-attributed-and-three-of-the-last-four-are-this-campaign-s-own-anti-patterns | high | Two frozen counts, one refusal pinned by its prose, one manifest-stale tree
  Evidence: The modelo 200 semantic casilla candidates assert `map_owner_mismatches` at 185 where the corpus now yields 181, `orphaned_declarations` at 2 where it yields 154, and a zero-padding disposition count that has moved…
    Disposition: status not explicit in this entry; see source-order chronology (source order 327).
- [328] the-lane-criterion-now-carries-causes-instead-of-a-range | medium | "Between fifteen and forty-two, dated and attributed" replaced by what the thirty-five actually are
  Evidence: Dating answers whether a failure is yours. Disposition: status not explicit in this entry; see source-order chronology (source order 328).
- [329] the-publication-limb-is-reachable-and-has-been-since-september-second | high | The constraint blocking the twenty-seven-failure repair was true when written and false the next day
  Evidence: The commit that added it - "add the operator invocation surface for one generated export tree" - landed on 2026-09-02, the day after the constraint was written and the day this plan was authored. Disposition: status
    not explicit in this entry; see source-order chronology (source order 329).
- [330] the-other-absence-claim-is-real-and-now-says-what-is-present | high | Nine official corpus directories, none of them a filled fichero
  Evidence: So the chain this campaign has been recording as blocked - the official reference, then vector enrolment, then the modelo 151 closure rewrite, then the single-channel authority's deletion - is blocked on evidence…
    Disposition: status not explicit in this entry; see source-order chronology (source order 330).
- [331] three-absence-claims-checked-two-stale-and-the-pattern-is-the-same-each-time | high | A blocker recorded once outlives the condition that made it true
  Evidence: It became reachable on 2026-09-02 and the claim survived a day past its truth, blocking the repair behind twenty-seven of this directory's thirty-five failures. Disposition: status not explicit in this entry; see
    source-order chronology (source order 331).
- [332] the-deferral-step-asks-for-a-rationale-and-there-is-nowhere-to-put-one | high | Seven reason fields exist in the schema and none of them is on a revision
  Evidence: Its population holds exactly: modelos 189, 280 and 345 each have a 2025 revision carrying one export layout at applicability grade, with no committed tree. Disposition: status not explicit in this entry; see
    source-order chronology (source order 332).
- [333] the-714-envelope-offsets-are-not-gaps-in-a-record-they-are-past-its-end | high | The footer declares one field over offsets 1 to 18 and no length at all
  Evidence: The Step naming modelo 714's envelope fields at offsets 93 to 96 and 101 to 109 holds, and holds differently than it reads. Disposition: status not explicit in this entry; see source-order chronology (source order
    333).
- [334] no-export-record-declares-a-length-and-my-previous-entry-asked-for-one | high | All 419 records omit it by design, because the official design is the authority on extent
  Evidence: What survives from the previous entry is the part that was measured rather than inferred: the footer's single field spans offsets 1 to 18, the two spans the Step names lie well beyond it, and the ten page records of…
    Disposition: status not explicit in this entry; see source-order chronology (source order 334).
- [335] the-coverage-validator-accepts-modelo-714-while-its-own-design-declares-an-uncovered-required-position | high | Position 93 is "Versión del Programa" in the 2025 design the layout cites, and no authored field covers it
  Evidence: Established by reading: the 2025 layout cites source `aeat-dr-714-2025`, which resolves to `DR714_2025.xls` in the bundled corpus. Disposition: status not explicit in this entry; see source-order chronology (source
    order 335).
- [336] the-714-step-asked-for-a-field-the-product-must-not-write | high | The coverage validator classifies it omissible for a reason the Step contradicts, and reading the validator settled it
  Evidence: Position 93 in the 2025 design is "Versión del Programa" carrying the footnote "A cumplimentar por las entidades desarrolladoras (EEDD)". Disposition: status not explicit in this entry; see source-order chronology
    (source order 336).
- [337] one-step-s-symptom-is-another-step-s-cause-and-the-plan-does-not-connect-them | high | 31 record-spelled envelopes against 20 typed ones, and modelo 714 is in the first group
  Evidence: Modelo 714 is in the second group, which explains the Step that has occupied the last three iterations. Disposition: status not explicit in this entry; see source-order chronology (source order 337).
- [338] the-description-now-carries-an-example-that-can-be-counted-today | medium | Twenty typed envelopes against thirty-one record-spelled ones, with the cost of the difference measured in this campaign's own iterations
  Evidence: Three iterations went into whether four bytes at position 93 of modelo 714's envelope should be authored - a question that only exists because that envelope is record-spelled, and whose answer is a single field in…
    Disposition: status not explicit in this entry; see source-order chronology (source order 338).
- [339] the-typed-envelope-s-advantage-is-declared-eighteen-times-not-merely-available | high | A field that exists and nobody uses would have made the whole argument theoretical
  Evidence: Eighteen typed envelopes declare `aeat-product-software-identity-v1` as their product-identity requirement, across modelos 151, 200, 202 and others. Disposition: status not explicit in this entry; see source-order
    chronology (source order 339).
- [340] one-revision-field-of-thirty-five-has-never-been-populated | high | The governance stamp's other three members are used by 122 of 128 revisions
  Evidence: Its siblings are used: `reviewed_by` and `reviewed_at` are set on 122 of 128 revisions, and `review_status` reads `agent_reviewed` on the same 122 and `pending_review` on the remaining six, which is the fail-closed…
    Disposition: status not explicit in this entry; see source-order chronology (source order 340).
- [341] the-unused-alias-field-is-unused-on-all-29678-casillas-and-the-export-field-is-fully-used | high | A retirement Step's premise verified independently, and a second sweep that found nothing
  Evidence: That Step asks to retire "the restated casilla number field and the unused alias field", and "unused" was an assertion nobody had counted; it is now 0 of 29,678, and the Step carries the figure. Disposition: status not
    explicit in this entry; see source-order chronology (source order 341).
- [342] the-restated-casilla-number-is-a-restatement-on-24524-casillas-and-load-bearing-on-5154 | high | Retiring it as the Step asked would have deleted a fact for one casilla in six
  Evidence: On 5,154 it is not derivable, and the reason is visible in any of them: a casilla identified semantically, like `act.actividad-descripcion`, carries number 400, and nothing in the identifier encodes 400. Disposition:
    status not explicit in this entry; see source-order chronology (source order 342).
- [343] the-two-casilla-number-fields-are-two-facts-and-the-defect-is-the-name | high | Both set on 138 casillas, 134 of them different, because one holds a range and the other a printed box
  Evidence: On 134 of those they differ, and the examples say why in one line: `conyuge.deduccion` carries `number=238-254` and `form_number=574`. Disposition: status not explicit in this entry; see source-order chronology (source
    order 343).
- [344] the-casilla-number-field-holds-three-different-kinds-of-value | high | 25,615 box numbers, 2,002 position ranges, and 2,061 slugs that are not numbers
  Evidence: The casilla `number` field carries three shapes across 29,678 declarations: 25,615 plain digit strings, which are box numbers; 2,002 ranges like `238-254`, which are spans of positions; and 2,061 values that are…
    Disposition: status not explicit in this entry; see source-order chronology (source order 344).
- [345] five-fields-looked-heterogeneous-and-one-is | high | A segment identifier of the form 714-02 matched a range pattern, which is the eighth instrument error of this campaign
  Evidence: Its 530 apparent ranges are values like `714-02`, which is modelo 714's page-02 segment identifier and matches `digits-digits` for the same reason a date matches it. Disposition: status not explicit in this entry; see
    source-order chronology (source order 345).
- [346] the-two-tails-are-one-artefact-and-one-accented-identifier | high | 415 became 6, and the six are a single role name that kept an accent its own transliteration dropped
  Evidence: Its values look like `modelo-232-2018.page_01.144-158.vinculada-1-nif` - a structured path mixing dots, underscores, dashes and a position range - and no single character class I chose would have admitted it.
    Disposition: status not explicit in this entry; see source-order chronology (source order 346).
- [347] exactly-one-accented-identifier-in-the-corpus-and-the-rest-of-the-non-ascii-is-correct-prose | high | Two fields carry non-ASCII; one is a reason written in Spanish and the other is the defect already found
  Evidence: So the finding is bounded: across 29,678 casillas and every string field they declare, exactly one identifier retains an accent, and every other non-ASCII character in the casilla surface is prose doing its job.
    Disposition: status not explicit in this entry; see source-order chronology (source order 347).
- [348] the-export-surface-sweeps-clean-on-every-question-asked-of-it | high | No non-ASCII in 25,031 fields, one encoding across 419 records, no layout mixing line endings, and six record-less layouts explained by their format
  Evidence: Six layouts declare no records, and all six are modelo 100's XML dictionary layouts for 2020 through 2025. Disposition: status not explicit in this entry; see source-order chronology (source order 348).
- [349] the-three-clean-export-properties-are-gated-now | high | Twenty-nine gates pass; a clean sweep that nothing holds is a fact about one afternoon
  Evidence: No export declaration carries a character outside ASCII, over 25,031 fields. Disposition: status not explicit in this entry; see source-order chronology (source order 349).
- [350] the-three-export-gates-now-have-the-teeth-the-plan-requires-of-them | high | Thirty gates pass, and the proof calls the same helpers the gates do
  Evidence: The encoding gate is proven by the same layout fixture agreeing with itself; a modelo declaring two encodings cannot be constructed by copy without building a second revision, and the agreement assertion over 419…
    Disposition: status not explicit in this entry; see source-order chronology (source order 350).
- [351] the-export-gates-are-in-the-criterion-that-governs-them | medium | A gate not named by any criterion is a gate nobody is accountable for
  Evidence: What the criterion now says is the pair of facts a reader needs: the properties gated, with the populations they were measured over, and the one skip the line-ending gate depends on. Disposition: status not explicit in
    this entry; see source-order chronology (source order 351).
- [352] the-deadline-windows-sweep-clean-and-the-one-apparent-duplicate-was-my-key | high | 843 windows, no inverted span, no stray cutoff, and modelo 210's four windows per coordinate are four different results
  Evidence: Two coordinates - modelo 210's annual periods for 2025 and 2026 - each carry four deadline windows, which keyed on year, period and period kind reads as a fourfold ambiguity about when one filing is due. Disposition:
    status not explicit in this entry; see source-order chronology (source order 352).
- [353] the-keying-rule-is-in-the-readme-now-with-the-nine-errors-that-bought-it | high | Two rules kept that suite honest; the third is the one this campaign paid for
  Evidence: The evidence is the nine errors themselves, three of them named: a key over modelo and revision that reported two screens collapsing every row onto one coordinate, a shape pattern that read `714-02` as a numeric…
    Disposition: status not explicit in this entry; see source-order chronology (source order 353).
- [354] 156-declared-localization-keys-resolve-in-no-locale | high | Every one is a modelo 200 2024 casilla, and the gap is identical in Spanish, English, Catalan and Hungarian
  Evidence: The 156 are all modelo 200's 2024 revision, plain casilla identifiers like `00067`, `00093` and `00814`, and the shortfall is identical in all four locales: 3,329 keys declared for that revision, 156 unresolved in…
    Disposition: status not explicit in this entry; see source-order chronology (source order 354).
- [355] the-localization-crossing-is-complete-and-only-the-casilla-labels-are-short | high | 58 official names, 58 titles, 128 revision keys and 181 construct keys all resolve; 156 casilla labels do not
  Evidence: The casilla keys answer 35,612 times out of 35,768, and the 156 that do not are the modelo 200 2024 labels already recorded. Disposition: status not explicit in this entry; see source-order chronology (source order
    355).
- [356] the-casilla-labels-are-restated-per-revision-11286-times-and-the-fix-is-derivation-not-translation | high | 38 per cent of the Spanish label corpus is the same text under a second revision, and the operator said so before the measurement did
  the measurement did
  Evidence: The 280 is checkable and checks: modelo 390 carries 102 labelled casillas spread over up to five revisions, distributed 10 at five revisions, 72 at four, 4 at three and 16 at two, and the surplus of a population like…
    Disposition: status not explicit in this entry; see source-order chronology (source order 356).

### Corrected interpretation

The internally measured export-reference residue was 18, not the second pass's 384;
the largest apparent contribution dissolved when the loaded binding projection was
followed. A separate finding that one modelo had zero export wiring and another only
filler fields was withdrawn after measurement through derived layouts produced 88.8%,
88.9%, 93.4% and 95.6% coverage; a different 17.4% result survived. Authored fragments
are not the export surface.

The original wire-type result of 3,043/7,709 was indicative and not independently
reproduced. The final loaded-authority count was 3,349/8,075. A broad unscaled-money
count was also reduced twice; preserve only the 24-field control result and the two
source-grounded filing defects as current. Row-mapped fields were excluded from the
scale defect after a false attribution was measured and withdrawn.

The capability survey likewise separated missing envelopes, invalid grade claims,
missing product identity, insufficient deadlines and source gaps. Two models with
published bytes but no filing claim demonstrate that export presence cannot be used as
a proxy for applicability or grade. A declared applicability grade cannot make a
runtime filing snapshot safe when the layout is missing.

## Recommendations

Re-ground the proposed temporal coverage ADR against the current public modules,
populations and application boundaries before relying on its old premises. Keep its
decision authority unchanged. Do not turn internal registry agreement, an empty proof
vector or a passing development test into official emitted-byte evidence.

Retain one canonical source for each fact and validate agreement at the boundaries:
temporal reach, identifier grammar, source/legal provenance, grade prerequisites,
derived export references and output reproduction. Follow the registry schema's full
family declaration rather than a partial hand-maintained list. Keep child citations
visible even when absent from the manifest summary.

For export correctness, preserve the corrected 24-field monetary-scale inventory and
the direct Modelo 200 and 353 evidence. Do not use candidate screens as proof of a tax
or wire defect; compare the exact field and design before changing a policy. Do not
republish the two record-drift trees without resolving their changed source rows.

Carry translations from canonical per-modelo labels only when official text is identical.
Retain per-revision overrides where it differs. Do not land the derived label shape in
registry runtime without its own accepted decision and lossless reconstruction checks.
The audit showed how to reduce duplication without erasing real differences.

Keep development tools measurable and runnable. Every gate must enroll the condition
it claims to protect, exercise both positive and negative controls, and appear in an
actually invoked lane. Default pytest is marker-filtered; report the exact collection
scope. Environmental refusals, setup errors, product failures and official-evidence
blockers remain different outcomes.

### Unresolved evidence and lane limits

The official-byte proof remains unenrolled. The test
test_real_live_filing_success_cannot_invent_a_complete_source_limb fails with
AttributeError because LiveFilingExportProofAuthority has proof_for but no assess_for.
The object is transitional and slated for deletion under S109 once an official vector
allows the two-channel path to satisfy; adding the missing method would repair the
symptom while defeating that transition. No official emitted-byte reference is recorded
as available in the bundled corpus.

The registry conformance closure suite remained outside CI and had one evidence-blocked
test. Repeated broad pytest totals were affected by contention and peer edits; they are
not directly comparable. Several test directories also require external passphrase,
keychain or built-documentation preconditions. These limits must accompany any reported
pass rate.

## Chronology and corrections

Sections below follow the original order. The source does not provide a separate date
for every appended subsection, so this condensation preserves that order and keeps
explicit dates, revision years, model numbers and run outcomes without inventing dates.

### Opening measurement and independent-pass corrections

The initial proposal was measured against the live tree rather than accepted from its
description. The registry was 128 revisions across 58 models, not 97/73, with 49
open-ended revisions rather than 66. The cited private modules had moved to public
names; the old model-specific construction branch and 27-literal applicability claim
were gone. These changes invalidate the proposal's original problem statement but do
not settle the remaining temporal and release questions.

The two independent passes disagreed on several figures. The authority-derived second
pass was preferred over authored-fragment counts: both fixed-width and calculation
grade was 62 revisions across 28 models, bound casillas were 720, and explicitly
out-of-scope obligations were 94. An earlier false reference count of 384 was corrected
to 18, and a zero-wiring claim was withdrawn after deriving export fields through loaded
bindings. The audit records the corrections because the first figures had circulated.

The proof channel was empty at both committed head and worktree. Closure was one
satisfied against 127 refused; all 68 filing-grade revisions refused the export limb.
The verifier's bad method call and renamed conformance import were independently
reproduced. The proposed old ratchet was not restored: frozen counts do not establish
completeness, and the replacement closure command was not in CI.

### Temporal, identity and provenance measurements

The audit found the same temporal fact expressed at six or more sites, reconciled only
after the fact. It measured 843 deadline windows, 54 open-ended revisions (28 filing-grade, per finding 053), 1,727/1,729
temporal probes resolved, and two genuinely ambiguous 2011 coordinates in one model.
Several directory names misstated their declared windows; a scheme axis also occupied
a revision slot. The sibling operation-date decision already targeted the ambiguity, so
this audit bounded the case rather than claiming that decision.

Three identifier grammars coexist; 21 models mix two. The numeric alias was repeated
on all 29,522 casillas while the schema alias field was unused. Provenance was declared
at eleven surfaces, with 14,817 mirror citations and 6,872 citations absent from the
manifest (6,634 in one model). The first provenance scan covered only eight of the
schema's 19 families. The later walk followed all 19, found that the manifest summarizes
children rather than constraining them, and found no dangling reference. Initial
eligibility and citation findings were narrowed when note scope and family coverage were
measured directly.

Coverage continuity checks were added for holes and overlaps. The complete registry
had no interior coverage gap or overlap; Modelo 322's apparent gap was a misnamed
revision. Two invariants were enrolled so future changes can fail on either condition.
A separate failure mode was measured and absent. This is evidence about the current
corpus, not proof of future coverage.

### Official design comparisons: wire type, scale and notes

A source-grounded pass revised wire-type counts from 3,043/7,709 to 3,349/8,075 and
recorded 33 transitions. Money-to-decimal accounted for 2,140 and ratio-to-decimal for
619. Row-mapped values were excluded. The mappings still need a declared vocabulary
boundary; a differing casilla and wire type is not by itself a filing defect.

Unscaled numeric candidates fell from 3,069 to 156 to 24 after checking field scope,
eligibility and official notes. A proposed broad guard would have misclassified fields;
controls corrected it before landing. Direct official-design evidence retained the
Modelo 200 03594 and Modelo 353 casilla 10 defects. The second location is
m353-2026.pagina01.f127. A separate root-cause explanation based on row mappings was
withdrawn. These exact field findings are the proven wire defects; the candidate totals
are not.

The footnote and note work corrected a design-reading boundary. An initial 149-field
authoring premise was retired. Forty-one fields across five models were screened;
the corpus had 58 notes across eight models, and the schema's 19 source families had
to be traversed to establish scope. Seventeen of 31 designs expressed type conventions.
Direct reading settled 12 of 41 candidate fields; the other 29 remained unresolved.
The audit did not infer a convention from a note whose scope was uncertain, nor treat a
reader-aid label as design evidence. Corrections also kept sheet-scoped notes from
leaking across a whole model.

### Grade, capability and generated-tree reproduction

The filing-grade population moved through successive measurements (68, then 69).
An initial 52-envelope screen was mostly a false classification; the corrected survey
separated record-spelled envelopes from typed ones. It found 31 records without a
filing-product identity, 25 layouts below filing grade, five filing revisions lacking
deadlines and two models with published filing bytes but no filing claim. Five revisions
claimed prerequisites their grade did not support. The release predicate remained in
development tooling; the application did not evaluate it.

Six committed generated trees initially failed byte reproduction. Repairs improved the
result to 21 of 27 byte-identical, four provenance-only differences and two record-drift
cases. One model's authored render content had no validator. Four enrolments were
cross-checked; both provenance screens were expanded to a missing citation family.
The later schema-led provenance walk replaced earlier partial counts rather than adding
the totals together.

The capability and ordering screens were tested against their own premise. Duplicate
screens were collapsed, a helper that narrowed a gate was corrected, and dead
ordering constraints were declined after remeasurement. Each refusal was tied to a
control; empty correlation results were not promoted into findings.

### Label derivation, facades and campaign gates

The label study corrected a repeated-string estimate and separated identical official
text from true per-revision divergence. Spanish stored 27,569 labels; Catalan 19,953;
English 19,917; Hungarian 19,859. Across four locales, lossless derivation reduced
87,298 stored strings to 57,249, removing 30,049. The retained override counts are
1,091 Spanish, 1,620 Catalan, 1,800 English and 1,933 Hungarian casillas.

The pure restatement surplus was 10,586 Spanish and 28,129 across locales. But
translation divergence exceeded source divergence: Spanish had 1,091 divergent
casillas, while the other catalogues had 1,620/1,800/1,933. Direct comparison found
translations diverging where Spanish was identical on 687 Catalan, 807 English and
931 Hungarian casillas. The derivation is evidence for a possible shape change only;
runtime schema is outside this audit's scope, and overrides must preserve source
differences.

Nine forwarding facades with 388 forwarding exports were retired through staged
promotion. Instrumentation measured them before replacing repeated scans with an
invariant. The work exposed promoter bugs and tests that were inert or self-exempting;
the final gate followed declared reach rather than a hand-written list. Sixty-three
initialiser paths were examined, and the duplicate facade finding was kept distinct
from source-package boundaries.

### Test reachability, runner integrity and dev tooling

The default pytest invocation filters by markers. Seventy-eight tests ran only by
manual command. The conformance closure suite was located but no CI lane reached it;
its run had 19 tests, 18 passing and one evidence-blocked failure, taking 537 seconds.
Broad suite snapshots included 3,881 collected with 167 failures and 72 errors, then
3,941 with 177 failures and 109 errors. Those totals came from different, contended
worktrees and are not trend measurements.

A module reach audit corrected its own denominator from 42 by about 30%, ranked modules
by what they could do, then added tests and a runnable report. One suite's remaining
failure was opened precisely: the live proof object lacks the protocol's assess_for
method and is a transitional class scheduled for deletion once official vectors exist.
Failure and cross-package correlators were measured and declined because the enrolled
populations did not contain the needed shared identifiers; only one of 37 failure lines
had modelo=, and the relevant worklists were not registered screens.

A relative-import defect in import_hygiene_scan was fixed. Its codemods cannot safely
exercise apply mode because their paths target the real source tree and do not accept
an injected root; tests therefore pin dry-run behavior and refusal boundaries. The
locale scanner learned four positional key factories. Seventy-seven keys stopped being
reported unused: extra-key reports fell from 520 to 443 while the missing count stayed
339.

Two test moves exposed missing session-scoped runtime composition. Importing the shared
fixtures reduced setup errors in dev/ci from 12 to zero. In dev/agent_eval, errors fell
from 13 to zero, passing rose from 108 to 111 and failures rose from 8 to 18: ten tests
now report the honest no-passphrase environmental refusal, while three pass. That is a
harness correction, not a new product regression. A newly reachable scale test measured
M130 at 3.031 CPU seconds against a 3.0-second budget at 30,000 ledger rows. Four
remaining dev/deploy errors were explicit missing-built-documentation preconditions.

The final appendices continue to distinguish measured defects from good refusals. The
composition-gap sweep found only the two directories above missing runtime composition.
Stale screens, attribution lists and correlators were declined where controls found no
matching population. The report ends with source-order findings rather than claiming
that unrun lanes or empty analyses are green.
