---
tags:
  - '#plan'
  - '#aeat-design-relayout-boundary'
date: '2026-08-08'
modified: '2026-08-08'
body_hash: 'sha256:04d88d3fe226bdf28a35f85b8202eff81bf1388004dbf7ce5f73c6d9e71383e5'
tier: L3
related:
  - '[[2026-08-07-aeat-design-relayout-boundary-adr]]'
  - '[[2026-08-07-aeat-design-relayout-boundary-sub-year-epoch-adr]]'
  - '[[2026-08-07-aeat-design-relayout-boundary-research]]'
---

# `aeat-design-relayout-boundary` plan

Split every registry revision whose span crosses an AEAT record-design re-layout, so no filing year is written at another year's byte offsets.

## Description

Two accepted decision records govern this plan and neither is self-executing. `2026-08-07-aeat-design-relayout-boundary-adr` ratifies the property that no registry revision may span an AEAT design re-layout, rules that a year with no correct layout must refuse rather than degrade, bounds the authoring scope to the prescripcion-reachable filing window, and authorizes the split as follow-on plan work while making no registry edit itself. It governs every Wave. `2026-08-07-aeat-design-relayout-boundary-sub-year-epoch-adr` supplies the one mechanism the first record needs and does not name: a design epoch narrower than a filing year is expressed by partitioning the AEAT period tokens between two same-year revisions, with no schema change. It governs `W01.P03` and every Step in `W02`. `2026-08-07-aeat-design-relayout-boundary-research` supplies the measurement method, the Modelo 123 shipped pattern to copy, and the union-of-signals doctrine, and grounds every Wave.

The defect is live and it is a filing-output correctness defect, not hygiene. A revision carries exactly one export layout, so a revision claiming years on both sides of a re-layout writes at least one of those years at the wrong byte offsets, producing a byte-valid, length-valid, digest-valid artefact that declares wrong quantities at wrong positions. The landed span gate `test_revision_span_matches_published_designs.py` is red at HEAD and names the violations as its own specification. Its verdict was re-run for this plan on 2026-08-08 and reports four spanning revisions across three modelos: Modelo 200 `2024-y-siguientes` spans 1 re-layout and needs 2 revisions, Modelo 303 `2009-y-siguientes` spans 4 and needs 5, Modelo 303 `2023-y-siguientes` spans 3 and needs 4, Modelo 390 `2010-y-siguientes` spans 6 and needs 7. That is 14 named boundaries and 18 revisions where 4 exist today.

Three things about that verdict are load-bearing and are not the same as the numbers in either decision record. First, the gate understates Modelo 303 `2023-y-siguientes` by one boundary and one revision, because its per-signal design inventories still keep one design per year while AEAT split three Modelo 303 ejercicios mid-course, so the corrected requirement for that revision is 5 revisions covering 4 design epochs per the sub-year record, not the 4 the gate reports. The instrument measuring this defect therefore carries the same year-keyed blind spot as the registry it measures, and a reader who takes the gate's count as the requirement will under-split by exactly one revision; `W01.P02` closes that blind spot and no split may be certified against the gate before it lands. Second, the gate's boundary labels have already moved against the research snapshot, which named 2015/2017 and 2019/2021 inside `2009-y-siguientes` where the current run names 2016/2017 and 2020/2021, confirming the boundary set is data to be re-derived at execution time and never copied. Third, the first decision record rules no implementation action for Modelo 200 on the ground that its two-design span is offset-identical, and that ruling is now overtaken by evidence: the gate reds on Modelo 200 with a RECORD SET CHANGED signal, 75 records against 77, which is not an offset shift and which the record's offset-identity reasoning does not cover. `W04` therefore acts on Modelo 200, and `W05.P11` records the divergence from the record's stated no-action posture.

Split at every named boundary, never at the first one a single signal saw. The gate's own failure text states this: splitting at only the boundaries one signal saw leaves the rest live, and a plan closing the gate by splitting once per modelo would produce a green gate over a still-wrong tree, which is strictly worse than the current honest red. Three distinct signals contribute to the boundary set and none subsumes the others. Box-offset movement finds relocations such as the 127-of-182 Modelo 303 2025 to 2026 shift. Per-page byte-length growth finds boundaries the box key cannot see, such as Modelo 303 2014/2015 and 2024/2025, where the growth lands in unnumbered fields. Slot occupancy finds boundaries neither of the other two sees, such as Modelo 303 2023/2024 with 4 slots retired into reserved space and Modelo 390 2024/2025 with 3, where no box moved and no page length changed. A fourth pass, description-keyed, is needed for unnumbered slots whose meaning flips at a fixed offset, which is how the Modelo 303 complementaria to rectificativa flip was found and which the numbered key structurally cannot see.

Every split is proved by emitted bytes, never by structure. A test asserting that a revision count changed, or that a period selector resolves, proves nothing about output: the defect is that filings write declared values at wrong positions, so the proof obligation is emitted bytes at the affected positions for a filing period on each side of every boundary, taken through the production export path rather than through a layout table read directly. Structural assertions are permitted only as preconditions of a byte assertion, never in place of one.

Scope is bounded by the reachable filing window, per the first record's adopted default posture, and that bound is a narrowing this plan records about itself rather than a change to the standing goal. The standing goal is that no filing year is written at wrong offsets. This plan delivers that for years inside the prescripcion-reachable window computed at execution date in `W01.P01`, and delivers a named refusal rather than a correct export for years before the earliest split boundary. Under the working window this plan assumes, subject to `W01.P01` recomputing it, five gate-named boundaries fall outside and are excluded: Modelo 303 2014/2015, 2016/2017 and 2020/2021, and Modelo 390 2017/2018 and 2020/2021, along with the mid-course Modelo 303 ejercicios 2018 and 2021. What the standing goal still asks for that this excludes is a correct export for filing years 2009 through 2021 on Modelo 303 and 2010 through 2021 on Modelo 390; after this plan those years refuse by name instead. `W01.P01` recomputes the window and `W01.P01.S03` reconciles this plan's own row set to it, adding rows if the window is wider than assumed and removing them if narrower.

What a split must not change is settled in part and open in part. The sub-year record rules explicitly that the transitional rate rungs pinned to 2024 belong to the 2024-covering revisions only and that copying them into every post-split revision is the obvious and wrong resolution, which `W02.P04.S20` implements. The first record's constraint establishes that revision ids do change and that every carried cross-year observation stamped against an old id must be re-confirmed, which `W05.P10.S47` implements. Neither record rules on whether casilla ids, formula ids or continuidad stamps carry across a re-layout boundary unchanged, so this plan does not assume they do: `W01.P01.S05` settles that question against the bundled designs and records the ruling before any revision is authored, and `W05.P11.S62` treats an unrecorded ruling as an open honesty item rather than a silent assumption.

Neither record names the localization consequence, and measured rather than estimated it is very likely the single largest cost in this plan. Modelo and casilla labels resolve through derived dotted locale keys carrying the revision id, so every new revision id mints a whole new key set that must exist with a real value in all four catalogues, with no sanctioned untranslated state and a shipped gate refusing the scaffold's self-referencing placeholder. Counted against the Spanish catalogue at HEAD, the affected revisions carry 260 keys for the open Modelo 303 revision, 238 for its bounded sibling, 178 for Modelo 390, and 6502 for Modelo 200. Modelo 200 alone therefore mints roughly 6500 new keys, and across the three modelos the new revisions come to something on the order of 8000 keys per catalogue and 32000 across all four, with Spanish required as a real source value rather than a copy. An executor sizing this work from the split rows alone would underestimate it by an order of magnitude, and Modelo 200 is the narrowest split in the plan but by far the widest localization cost, so the sizing does not follow the split sizing at all. `W05.P10` carries one row per modelo plus the drift and honesty gates; if that cost proves prohibitive it is a scope decision for the campaign owner, not something an executor may quietly resolve by leaving a catalogue short or reaching for the allowlist.

Sequencing is by risk and by mechanism dependency, not by modelo id. `W01` is a hard precondition for every later Wave: the gate cannot certify a mid-year split until it reads more than one design per year, and the year-only selector must have a defined answer for a split year before a split year exists, or three read-only discovery surfaces begin raising an ambiguity error one of them does not catch. `W02` takes Modelo 303 first as the proving pass, because it carries the highest live severity and the only sub-year epoch: its `2023-y-siguientes` revision already claims Q1 and Q2 2026, both closed, while encoding 2025-era offsets, and its 2025 to 2026 transition relocates 127 of 182 shared boxes and flips four fixed slots. `W03` takes Modelo 390 second, with the most boundaries and an independently proved live export mis-write at filing year 2023. `W04` takes Modelo 200 last, as the newest finding and the narrowest split. `W05` sweeps the consumers every revision-id change reaches and closes the campaign.

Each modelo lands as one atomic commit, which constrains how the per-revision rows are executed. Registry TOML validates as one coherent tree at load, and a half-split modelo leaves a period gap or overlap that breaks suite collection for every concurrent agent on this shared worktree, so the first record's constraint requires the split for each modelo to land as one commit rather than incrementally per boundary. The per-revision rows in `W02.P04`, `W02.P05`, `W03.P07` and `W04.P09` are therefore authoring rows: each is authored and locally proved in the working tree, and the modelo's landing row commits the whole revision set with an explicit pathspec. That is the reconciliation between one-row-per-revision auditability and the atomic-commit constraint, and it is deliberate rather than an oversight.

## Steps

## Wave `W01` - Preconditions - re-derive the authority data and make the instruments able to certify a split

Establish the three facts every later Wave consumes and cannot safely assume: the boundary set re-derived as the union of four passes over the bundled designs, the prescripcion-reachable filing window computed at execution date, and the ruling on what a split must not change. Harden the span gate so it reads every bundled design rather than one per year, since a green gate is not evidence of a mid-year split until it can see one, and give the year-only selector a defined answer for a split year before a split year exists. Blocks every other Wave. Governed by both accepted decision records and the research measurement method.

### Phase `W01.P01` - Re-derive the authority data

Produce the three facts every later Wave consumes: the boundary set, the reachable window, and the ruling on invariants across a boundary.

- [ ] `W01.P01.S01` - Re-derive the full boundary set as the UNION of four passes over the bundled designs - box-number-keyed movement, per-sheet total-positions growth, slot occupancy into reserved space, and a description-keyed pass for unnumbered slot meaning flips - and record every named boundary per modelo in the Step Record, taking no single pass for the whole answer; `src/cadrumo/_data/corpus/aeat_official/disenos_registro/`.
- [ ] `W01.P01.S02` - Compute the prescripcion-reachable filing window per modelo at the execution date from each period's voluntary filing deadline plus four years, ground the rule against the bundled BOE corpus rather than reusing the record's approximate figure, and record the earliest in-window boundary per modelo; `src/cadrumo/_data/corpus/normatives/html/`.
- [ ] `W01.P01.S03` - Reconcile this plan's per-revision row set against the boundary set and the reachable window just computed, adding rows through the plan step verbs where the window is wider than assumed and removing them where narrower, and record in the Step Record which filing years the reconciled scope leaves refusing; `.vault/plan/2026-08-08-aeat-design-relayout-boundary-plan.md`.
- [ ] `W01.P01.S04` - Settle whether the 2023 and 2024-early Modelo 303 designs are layout-identical, since the occupancy signal reports 4 slots retired at that boundary while the sub-year record's box-number and page-length passes report zero movement, and record which reading holds before any revision is authored; `src/cadrumo/_data/corpus/aeat_official/disenos_registro/modelo_303/`.
- [ ] `W01.P01.S05` - Settle and record what a split must not change - whether casilla ids, formula ids and continuidad stamps carry unchanged across a re-layout boundary - by diffing the bundled designs on each side, treating an unrecorded answer as blocking rather than assuming continuity; `src/cadrumo/_data/registry/aeat/modelos/303/revisions/`.

### Phase `W01.P02` - Make the span gate able to certify a mid-year split

Re-key every per-signal design inventory on the design file rather than the parsed year, and add the companion check for unnumbered slots that flip meaning at a fixed offset.

- [ ] `W01.P02.S06` - Re-key the box-offset design inventory on the design file rather than the year parsed from its filename, so a year carrying two incompatible AEAT designs contributes both to the comparison instead of whichever sorts first; `src/cadrumo/domain/calculations/registry/tests/test_revision_span_matches_published_designs.py`.
- [ ] `W01.P02.S07` - Re-key the per-sheet page-length inventory on the design file rather than the parsed year, for the same reason and independently, since this signal is the only one that sees growth landing in unnumbered fields; `src/cadrumo/domain/calculations/registry/tests/test_revision_span_matches_published_designs.py`.
- [ ] `W01.P02.S08` - Re-key the slot-occupancy inventory on the design file rather than the parsed year, since this is the only signal that sees a slot retired into reserved space with no box moved and no page length changed; `src/cadrumo/domain/calculations/registry/tests/test_revision_span_matches_published_designs.py`.
- [ ] `W01.P02.S09` - Add the description-keyed companion check for unnumbered slots whose meaning changes at a fixed offset and length, so the complementaria to rectificativa flip the box-number key structurally cannot see becomes a named boundary; `src/cadrumo/domain/calculations/registry/tests/test_revision_span_matches_published_designs.py`.
- [ ] `W01.P02.S10` - Prove the hardened gate by mutation from outside the repository - confirm it now names the mid-2024 Modelo 303 boundary that the one-design-per-year inventory hid, and confirm it reds when a design file is withheld from the inventory; `src/cadrumo/domain/calculations/registry/tests/test_revision_span_matches_published_designs.py`.

### Phase `W01.P03` - Give the year-only selector a defined answer for a split year

Make the year-only revision selector refuse instructively for a year carrying a mid-year design boundary, and make all three of its callers handle that refusal.

- [ ] `W01.P03.S11` - Make the year-only revision selector refuse instructively when more than one revision covers a filing year, naming both candidate revision ids and stating that the year carries a mid-year design boundary so the caller must supply a period or an as-of date; `src/cadrumo/domain/calculations/registry/_temporal.py`.
- [ ] `W01.P03.S12` - Widen the binding-readiness helper's refusal handling so the ambiguity error is handled the way a missing revision for a period already is, rather than propagating out of a read-only discovery surface; `src/cadrumo/application/modelo/_binding_readiness.py`.
- [ ] `W01.P03.S13` - Handle the ambiguity refusal in the registry revision diff surface alongside its existing missing-revision handling; `src/cadrumo/application/registry/_diff.py`.
- [ ] `W01.P03.S14` - Handle the ambiguity refusal in the profile inspect surface alongside its existing missing-revision handling; `src/cadrumo/entrypoints/cli/_config/_profile_inspect.py`.

## Wave `W02` - Modelo 303 - the proving pass and the only sub-year epoch

Replace Modelo 303's two spanning revisions with the full in-window revision set, including the period-token partition that expresses the mid-2024 design epoch per the sub-year decision record. Taken first because it carries the highest live severity: its open-ended revision already claims Q1 and Q2 2026, both closed, while encoding 2025-era offsets, and its 2025 to 2026 transition relocates 127 of 182 shared boxes and flips four fixed slots at unchanged offsets. Lands as one atomic commit. Depends on Wave W01.

### Phase `W02.P04` - Author the Modelo 303 successors to the open revision

Author the five revisions covering the four design epochs the current open-ended revision spans, including the period-token partition for 2024.

- [ ] `W02.P04.S15` - Author the Modelo 303 revision covering filing year 2023 in full, with its own revision.toml carrying valid_from and valid_to, its own export fragment tree parsed from the bundled 2023 design rather than hand-transcribed, and source_refs naming that design alone, following the Modelo 123 two-revisions-two-designs pattern; `src/cadrumo/_data/registry/aeat/modelos/303/revisions/`.
- [ ] `W02.P04.S16` - Author the Modelo 303 revision covering the early 2024 epoch, declaring in its period_selector only the AEAT period tokens through 08 and 2T, with its own export fragment tree from the bundled early-2024 design and source_refs naming the early-2024 design entry the existing manifest already knows; `src/cadrumo/_data/registry/aeat/modelos/303/revisions/`.
- [ ] `W02.P04.S17` - Author the Modelo 303 revision covering the late 2024 epoch, declaring in its period_selector only the tokens 3T, 4T and 09 through 12, with its own export fragment tree from the bundled late-2024 design including the eight numbered boxes the earlier design has no room for, and source_refs naming the late-2024 design entry; `src/cadrumo/_data/registry/aeat/modelos/303/revisions/`.
- [ ] `W02.P04.S18` - Author the Modelo 303 revision covering filing year 2025, with its own export fragment tree from the bundled 2025 design and source_refs naming that design, noting that its sheet grew relative to the 2024 design in unnumbered fields that no box-number signal reports; `src/cadrumo/_data/registry/aeat/modelos/303/revisions/`.
- [ ] `W02.P04.S19` - Author the open-ended Modelo 303 revision covering 2026 onward, with its own export fragment tree from the bundled 2026 design encoding the relocated positions for the 127 boxes that moved and the four fixed slots whose declared meaning changed at unchanged offset and length; `src/cadrumo/_data/registry/aeat/modelos/303/revisions/`.
- [ ] `W02.P04.S20` - Confine the transitional rate rungs pinned to 2024 to the two 2024-covering revisions only, rather than copying them into every post-split revision, per the sub-year record's explicit ruling that the copy is the obvious and wrong resolution; `src/cadrumo/_data/registry/aeat/modelos/303/revisions/`.
- [ ] `W02.P04.S21` - Retire the spanning open-ended Modelo 303 revision directory outright once its successors carry every period it claimed, deleting rather than bridging since no released data depends on the old identifier; `src/cadrumo/_data/registry/aeat/modelos/303/revisions/2023-y-siguientes/`.

### Phase `W02.P05` - Author the Modelo 303 window edge for the bounded revision

Replace the bounded historical revision with the in-window revision and the refusal edge below it.

- [ ] `W02.P05.S22` - Author the Modelo 303 revision covering the earliest in-window filing year the reachable-window computation named, with valid_from at that year and no earlier sibling, so the resolver's existing no-revision-covers-this-triple refusal fires for every year below it; `src/cadrumo/_data/registry/aeat/modelos/303/revisions/`.
- [ ] `W02.P05.S23` - Retire the spanning bounded historical Modelo 303 revision directory outright, so the registry stops claiming the pre-window filing years it cannot correctly serve; `src/cadrumo/_data/registry/aeat/modelos/303/revisions/2009-y-siguientes/`.

### Phase `W02.P06` - Land Modelo 303 atomically and prove the bytes

Commit the whole Modelo 303 revision set in one explicit-pathspec commit and prove every boundary by emitted bytes rather than by structure.

- [ ] `W02.P06.S24` - Land the whole Modelo 303 revision set as one explicit-pathspec commit, never a bare commit, verifying afterwards with a numstat over the resulting sha that no peer path entered the change; `src/cadrumo/_data/registry/aeat/modelos/303/revisions/`.
- [ ] `W02.P06.S25` - Prove the 2025 to 2026 boundary by emitted bytes - export a draft for a 2025 period and a 2026 period through the production export path and assert the differing declared value positions for the relocated boxes, with a mutation proof that swapping the two revisions' export layouts reds the test; `src/cadrumo/application/filing/tests/`.
- [ ] `W02.P06.S26` - Prove the 2024-early to 2024-late boundary by emitted bytes - export a 2T 2024 draft and a 3T 2024 draft and assert the eight boxes present only in the later record appear at their declared positions in the later output and nowhere in the earlier; `src/cadrumo/application/filing/tests/`.
- [ ] `W02.P06.S27` - Prove the four fixed slots whose meaning changed between 2025 and 2026 by emitted bytes at unchanged offsets, since no offset check, length check or digest detects a slot that keeps its position while declaring a different quantity; `src/cadrumo/application/filing/tests/`.
- [ ] `W02.P06.S28` - Prove the 2023 to 2024 boundary by emitted bytes at the slot positions the occupancy signal reported retired into reserved space, asserting the later output writes no declared value where the earlier one did; `src/cadrumo/application/filing/tests/`.
- [ ] `W02.P06.S29` - Prove the earliest in-window Modelo 303 filing year by emitted bytes against its own bundled design, so the window-edge revision is verified rather than assumed correct by construction; `src/cadrumo/application/filing/tests/`.
- [ ] `W02.P06.S30` - Prove that every Modelo 303 filing year below the window edge refuses by name and produces no bytes, asserting the refusal names the unmodelled year rather than crashing or emitting a thin draft; `src/cadrumo/application/filing/tests/`.

## Wave `W03` - Modelo 390 - the widest span and a proved live mis-write

Replace Modelo 390's single revision with the full in-window revision set. Taken second because it carries the most named boundaries and an independently proved live export mis-write at filing year 2023, where export_draft produced 7698 bytes with the total cuota written at byte 1628 past the 2023 record's declared end at 1526. Includes the 2024/2025 boundary that no box-offset or page-length signal sees, only slot occupancy. Lands as one atomic commit. Depends on Wave W01.

### Phase `W03.P07` - Author the Modelo 390 in-window revisions

Author one revision per in-window design epoch and the refusal edge below the earliest.

- [ ] `W03.P07.S31` - Author the Modelo 390 revision covering the earliest in-window filing year the reachable-window computation named, with valid_from at that year and no earlier sibling so every year below it refuses, and its own export fragment tree parsed from that year's bundled design; `src/cadrumo/_data/registry/aeat/modelos/390/revisions/`.
- [ ] `W03.P07.S32` - Author the Modelo 390 revision covering the next in-window filing year, with its own export fragment tree from that year's bundled design and source_refs naming it, noting the boundary below it moved 131 of 265 shared boxes; `src/cadrumo/_data/registry/aeat/modelos/390/revisions/`.
- [ ] `W03.P07.S33` - Author the Modelo 390 revision covering the following in-window filing year, whose boundary below it moved 13 of 307 shared boxes alongside a page byte-length change; `src/cadrumo/_data/registry/aeat/modelos/390/revisions/`.
- [ ] `W03.P07.S34` - Author the Modelo 390 revision covering the next in-window filing year, whose boundary below it moved 189 of 311 shared boxes and changed the record decomposition rather than shifting a ladder; `src/cadrumo/_data/registry/aeat/modelos/390/revisions/`.
- [ ] `W03.P07.S35` - Author the open-ended Modelo 390 revision covering the newest bundled design onward, whose boundary below it is visible only to the occupancy signal - three slots retired into reserved space with no box moved and no page byte-length change; `src/cadrumo/_data/registry/aeat/modelos/390/revisions/`.
- [ ] `W03.P07.S36` - Retire the spanning Modelo 390 revision directory outright once its successors carry every in-window period, so the registry stops claiming filing years back to 2010 that it cannot correctly serve; `src/cadrumo/_data/registry/aeat/modelos/390/revisions/2010-y-siguientes/`.

### Phase `W03.P08` - Land Modelo 390 atomically and prove the bytes

Commit the whole Modelo 390 revision set in one explicit-pathspec commit and prove every boundary by emitted bytes.

- [ ] `W03.P08.S37` - Land the whole Modelo 390 revision set as one explicit-pathspec commit, never a bare commit, verifying afterwards with a numstat over the resulting sha; `src/cadrumo/_data/registry/aeat/modelos/390/revisions/`.
- [ ] `W03.P08.S38` - Reproduce the proved live mis-write as a regression - export a draft at Modelo 390 filing year 2023 and assert the total cuota is written inside that year's declared record extent rather than past its end, which the pre-split tree violated by writing at byte 1628 against a record ending at 1526; `src/cadrumo/application/filing/tests/`.
- [ ] `W03.P08.S39` - Prove each remaining Modelo 390 in-window boundary by emitted bytes for a filing year on each side, asserting the differing declared value positions, with a mutation proof that swapping adjacent revisions' export layouts reds the test; `src/cadrumo/application/filing/tests/`.
- [ ] `W03.P08.S40` - Prove the occupancy-only Modelo 390 boundary by emitted bytes at the three retired slot positions, since neither the box-offset nor the page-length signal detects it and a structural assertion would pass over it; `src/cadrumo/application/filing/tests/`.
- [ ] `W03.P08.S41` - Prove that every Modelo 390 filing year below the window edge refuses by name and produces no bytes; `src/cadrumo/application/filing/tests/`.

## Wave `W04` - Modelo 200 - the finding that overtook the record's no-action ruling

Split Modelo 200's single revision at its 2024/2025 boundary. The first accepted record rules no implementation action here on the ground that the span is offset-identical, and the re-run gate overtakes that ruling with a RECORD SET CHANGED signal of 75 records against 77, which is not an offset shift. Taken last as the newest and narrowest finding. Lands as one atomic commit. Depends on Wave W01.

### Phase `W04.P09` - Author and land the Modelo 200 split

Author the two Modelo 200 revisions, land them atomically, and prove the record-set change by emitted bytes.

- [ ] `W04.P09.S42` - Author the Modelo 200 revision covering filing year 2024, with valid_to at that year and its own export fragment tree parsed from the bundled 2024 design, since the gate reports the record decomposition differs across the boundary rather than the offsets shifting; `src/cadrumo/_data/registry/aeat/modelos/200/revisions/`.
- [ ] `W04.P09.S43` - Author the open-ended Modelo 200 revision covering 2025 onward, with its own export fragment tree from the bundled 2025 design carrying the 77-record decomposition rather than the 75-record one; `src/cadrumo/_data/registry/aeat/modelos/200/revisions/`.
- [ ] `W04.P09.S44` - Retire the spanning Modelo 200 revision directory outright once both successors are authored; `src/cadrumo/_data/registry/aeat/modelos/200/revisions/2024-y-siguientes/`.
- [ ] `W04.P09.S45` - Land the whole Modelo 200 revision set as one explicit-pathspec commit, never a bare commit, verifying afterwards with a numstat over the resulting sha; `src/cadrumo/_data/registry/aeat/modelos/200/revisions/`.
- [ ] `W04.P09.S46` - Prove the Modelo 200 record-set change by emitted bytes - export a 2024 draft and a 2025 draft and assert the record decomposition each produces, since a record-set change writes declared values into space the other design does not carry at all and no offset comparison detects it; `src/cadrumo/application/filing/tests/`.

## Wave `W05` - Consumer sweep and campaign close

Sweep every surface a revision-id change reaches and close the campaign honestly. Revision ids change, so carried cross-year observation stamps, deadline-window derivation, year-only query surfaces, per-revision completeness and parity manifests, and the four locale catalogues that key modelo and casilla labels on the revision id all move. Requires all three modelo Waves landed, because a sweep over a partially split registry reports a moving target.

### Phase `W05.P10` - Sweep every surface a revision id reaches

Re-confirm carried observation stamps, deadline windows, year-only query surfaces, per-revision manifests, and the four locale catalogues against the new revision ids.

- [ ] `W05.P10.S47` - Re-confirm every carried cross-year observation stamped against a retired revision id against the law-determined selection for its source context, treating a divergent or unreconfirmable stamp as a blocker rather than a warning, since a revision-id change reaches every carry path and the split is not export-layout-only; `src/cadrumo/domain/calculations/registry/`.
- [ ] `W05.P10.S48` - Sweep deadline-window derivation for the assumption that one revision covers a modelo's full history, since each split modelo now declares several and a derivation reading only the newest silently narrows the schedule; `src/cadrumo/_data/registry/aeat/modelos/`.
- [ ] `W05.P10.S49` - Sweep the year-only query surfaces and the registry describe and bindings surfaces for the assumption that a filing year resolves to exactly one revision, now false for every year carrying a mid-year boundary; `src/cadrumo/domain/calculations/registry/_queries.py`.
- [ ] `W05.P10.S50` - Author the completeness manifest and workbook parity refs for each new Modelo 303 revision, since these are per-revision fragments and an absent manifest makes the export completeness gate pass vacuously; `src/cadrumo/_data/registry/aeat/modelos/303/revisions/`.
- [ ] `W05.P10.S51` - Author the completeness manifest and workbook parity refs for each new Modelo 390 revision; `src/cadrumo/_data/registry/aeat/modelos/390/revisions/`.
- [ ] `W05.P10.S52` - Author the completeness manifest and workbook parity refs for each new Modelo 200 revision; `src/cadrumo/_data/registry/aeat/modelos/200/revisions/`.
- [ ] `W05.P10.S53` - Mint the four-catalogue locale entries for every new Modelo 303 revision id through the locales CLI, since modelo titles and every casilla label and help string resolve through derived dotted keys carrying the revision id and a new id mints a whole new key set with no sanctioned untranslated state; `src/cadrumo/locales/`.
- [ ] `W05.P10.S54` - Mint the four-catalogue locale entries for every new Modelo 390 revision id through the locales CLI; `src/cadrumo/locales/`.
- [ ] `W05.P10.S55` - Mint the four-catalogue locale entries for every new Modelo 200 revision id through the locales CLI; `src/cadrumo/locales/`.
- [ ] `W05.P10.S56` - Run the locale scaffold drift gate and the translation honesty gate, confirming no new key carries the self-referencing placeholder and no locale is missing a key the others carry; `src/cadrumo/locales/`.

### Phase `W05.P11` - Close the campaign honestly

Run the hardened gate and the full tree with owner triage, record the divergences this plan found against its authorizing records, and submit to a fresh-context honesty review.

- [ ] `W05.P11.S57` - Run the hardened span gate at HEAD and record its verdict, then prove it non-vacuous by withholding one authored revision from the tree through a runtime mutation from outside the repository and confirming it reds again; `src/cadrumo/domain/calculations/registry/tests/test_revision_span_matches_published_designs.py`.
- [ ] `W05.P11.S58` - Run the per-modelo export completeness, workbook parity and fichero-BOE parity gates for every authored revision and record each verdict, treating a vacuous pass over an absent manifest as a failure; `src/cadrumo/tests/`.
- [ ] `W05.P11.S59` - Run the full-tree suite sequentially, capture the complete output to a log file read back from disk rather than a truncated pipe, and record owner-surface failures separately from unrelated peer churn; `src/cadrumo/`.
- [ ] `W05.P11.S60` - Record in the campaign audit document that the first accepted record's no-implementation-action ruling for Modelo 200 was overtaken by a record-set-change finding, so a later reader does not read the record as still in force on that point; `.vault/audit/`.
- [ ] `W05.P11.S61` - Record in the campaign audit document every filing year this plan deliberately leaves refusing rather than correctly exported, stated beside what the standing goal still asks for that the narrowing excludes; `.vault/audit/`.
- [ ] `W05.P11.S62` - Submit this plan's closure summary to a fresh-context honesty review by an independent reviewer given the two accepted records and the commit ranges, and open a Step with a verification gate for every item it returns; `.vault/audit/`.

## Parallelization

`W01` blocks every other Wave and its three Phases carry no interdependency among themselves, so `W01.P01`, `W01.P02` and `W01.P03` may run in parallel. Within `W01.P02` the three inventory-rekeying Steps touch one module and should run sequentially to avoid a contended file. `W02`, `W03` and `W04` are independent of each other once `W01` lands, because each touches a disjoint registry subtree, and may run in parallel by separate agents provided each holds to its own atomic landing commit and pathspec. Within a modelo Wave the authoring Phase is strictly ordered before the landing Phase, and the authoring rows inside a Phase may proceed in parallel. `W05` requires all three modelo Waves landed, because a consumer sweep over a partially split registry would report a moving target. `W05.P10` rows may run in parallel; `W05.P11` is strictly last.

## Sequencing hazards

A green span gate is not evidence of a correct split until `W01.P02` lands, because the gate keeps one design per year today and is structurally blind to the mid-year Modelo 303 boundary. Any Wave certified against the unhardened gate must be re-certified after `W01.P02`. Landing a split before `W01.P03` makes three read-only discovery surfaces raise an ambiguity error the binding-readiness helper does not catch, so a split year must not exist before the selector has its defined answer. Editing `test_revision_span_matches_published_designs.py` to make a modelo pass, other than the inventory-rekeying and companion-check work `W01.P02` authorizes, is a signal the split missed a boundary rather than a fix. Copying the boundary counts from this document instead of re-running the gate reproduces the exact staleness this plan documents in its own Description.

## Verification

The plan is complete when every Step is closed and each of the following holds. `test_revision_span_matches_published_designs.py` passes at HEAD with its inventories keyed on the design file rather than the year, and a deliberate mutation removing one authored revision reds it again. For every boundary this plan splits, a byte-level test emits a draft for a filing period on each side through the production export path and asserts the differing declared value positions, with a mutation proof that swapping the two revisions' export layouts reds it. For every filing year this plan deliberately leaves unmodelled, a test asserts the resolver refuses by name and that no bytes are produced. `select_revision_for_year` refuses instructively for a split year, naming both candidate revision ids and the mid-year boundary, and all three of its callers handle that refusal. `python -m dev.locales scaffold --check` passes, and the four catalogues carry a real value for every new revision id key. The per-modelo completeness, workbook-parity and fichero-BOE parity gates pass for every authored revision. The full-tree suite runs with owner triage recorded, and a fresh-context honesty review runs against this plan's closure summary before the campaign is declared complete.
