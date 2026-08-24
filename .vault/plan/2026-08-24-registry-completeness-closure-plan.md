---
tags:
  - '#plan'
  - '#registry-completeness-closure'
date: '2026-08-24'
modified: '2026-08-24'
body_hash: 'sha256:5e3de995420f0b0d9cdba4f9483b4d2740728400dac3f9c70863cc6dcb86ad3c'
tier: L3
related:
  - '[[2026-08-24-registry-completeness-closure-adr]]'
  - '[[2026-08-24-registry-completeness-closure-research]]'
  - '[[2026-08-14-registry-temporal-coverage-plan]]'
  - '[[2026-08-10-aeat-export-fragment-generator-authority-plan]]'
  - '[[2026-08-22-source-casilla-integration-plan]]'
---

# `registry-completeness-closure` plan

## Description

Execute the accepted registry-completeness closure decision as a roll-up over the
existing temporal-coverage, source-casilla-integration, and export-fragment plans.
Wave W01 establishes the cross-authority predicate and repairs implementation-versus-
tracking drift. Wave W02 adjudicates the fourteen live filing gaps one revision at a
time and enrolls each remedy under its existing owner. Wave W03 verifies every semantic
layer, closes the predicate-relevant predecessor work with durable evidence, and runs
the mandatory fresh-context honesty review. This plan owns orchestration and release
proof only; it does not create a second registry authoring path.

## Steps

## Wave `W01` - closure contract and tracking reconciliation

Establish the one derived release predicate, reconcile already-landed coverage work with its temporal plan records, and provide the typed report every later adjudication and close gate consumes.

### Phase `W01.P01` - coverage-contract reconciliation

Independently review the landed schema-family and authority-grade contract, restore missing execution evidence, and reconcile its owning temporal-plan rows through canonical plan verbs.

- [x] `W01.P01.S01` - Independently review the landed schema-family coverage manifest against W01.P01.S02 and record every still-live finding; `.vault/audit/`.
- [x] `W01.P01.S02` - Reconcile temporal-coverage W01.P01.S02 through its existing execution record and canonical plan state after review passes; `.vault/plan/2026-08-14-registry-temporal-coverage-plan.md`.
- [x] `W01.P01.S03` - Author the missing temporal-coverage W01.P01.S03 execution record from verified authority-grade ladder evidence; `.vault/exec/2026-08-14-registry-temporal-coverage/`.
- [x] `W01.P01.S04` - Independently review the authority-grade ladder and its registry-build enrollment against W01.P01.S03; `.vault/audit/`.
- [x] `W01.P01.S05` - Reconcile temporal-coverage W01.P01.S03 through canonical plan state after its record and review pass; `.vault/plan/2026-08-14-registry-temporal-coverage-plan.md`.
- [x] `W01.P01.S40` - Enforce requested authority grade at the selected-revision snapshot boundary and prove lower-grade escalation refuses; `src/cadrumo/domain/calculations/registry/`.
- [x] `W01.P01.S41` - Align the authority snapshot cache-key type with its grade-separated runtime key; `src/cadrumo/domain/calculations/registry/_authority.py`.

### Phase `W01.P02` - derived closure report

Compose one typed cross-authority report from validated registry coverage, source-connectivity dispositions, and filing export capability, with fail-closed reasons per revision.

- [ ] `W01.P02.S06` - Define strict typed per-revision closure-limb and refusal models on the application registry boundary; `src/cadrumo/application/registry/`.
- [x] `W01.P02.S07` - Compose the temporal coverage and authority-grade limb from validated law-selected registry revisions; `src/cadrumo/application/registry/`.
- [ ] `W01.P02.S08` - Compose the source-connectivity limb from the canonical evidence-backed census authority; `src/cadrumo/application/registry/`.
- [ ] `W01.P02.S09` - Compose the filing-export limb from exact layout capability and official-byte evidence; `src/cadrumo/application/registry/`.
- [ ] `W01.P02.S10` - Publish the derived cross-authority closure report and blocking release predicate through registry conformance; `dev/registry/conformance/`.
- [ ] `W01.P02.S11` - Prove complete, refused, stale-evidence, below-filing-grade, and cross-limb disagreement outcomes with mutation tests; `src/cadrumo/application/registry/tests/`.

## Wave `W02` - filing-gap adjudication and owner routing

Adjudicate every live non-emitting revision separately against official evidence, then route each bounded remedy into the existing temporal, source-casilla, or export authority without creating a parallel writer.

### Phase `W02.P03` - revision-by-revision authority adjudication

Classify each of the fourteen live filing gaps independently so missing authority remains a refusal and authorable gaps receive an exact owner and reconsideration condition.

- [ ] `W02.P03.S12` - Adjudicate Modelo 036 revision 2025-02-03-y-siguientes producer vocabulary and official filing authority; `.vault/reference/`.
- [ ] `W02.P03.S13` - Adjudicate Modelo 038 revision 2002-y-siguientes design extraction trust and fileability; `.vault/reference/`.
- [ ] `W02.P03.S14` - Adjudicate Modelo 136 revision 2026 record-design availability and supported filing boundary; `.vault/reference/`.
- [ ] `W02.P03.S15` - Adjudicate Modelo 182 revision 2007-y-siguientes design-era coverage and donor-row prerequisites; `.vault/reference/`.
- [ ] `W02.P03.S16` - Adjudicate Modelo 185 revision 2003-2025 exact historical design authority; `.vault/reference/`.
- [ ] `W02.P03.S17` - Adjudicate Modelo 187 revision 2019-y-siguientes design-era coverage; `.vault/reference/`.
- [ ] `W02.P03.S18` - Adjudicate Modelo 188 revision 2019-y-siguientes design-era coverage; `.vault/reference/`.
- [ ] `W02.P03.S19` - Adjudicate Modelo 194 revision 2019-y-siguientes design-era coverage; `.vault/reference/`.
- [ ] `W02.P03.S20` - Adjudicate Modelo 220 revision 2024 producer vocabulary and exact design authority; `.vault/reference/`.
- [ ] `W02.P03.S21` - Adjudicate Modelo 220 revision 2025-y-siguientes open-window design coverage; `.vault/reference/`.
- [ ] `W02.P03.S22` - Adjudicate Modelo 390 revision 2021 casilla surface and exact annual filing authority; `.vault/reference/`.
- [ ] `W02.P03.S23` - Adjudicate Modelo 721 revision 2023-y-siguientes record-design availability and supported filing boundary; `.vault/reference/`.
- [ ] `W02.P03.S24` - Adjudicate Modelo 763 revision 2011-y-siguientes design-era coverage; `.vault/reference/`.
- [ ] `W02.P03.S25` - Adjudicate Modelo 840 revision 2003-y-siguientes record-terminator semantics and official extent; `.vault/reference/`.

### Phase `W02.P04` - predecessor owner enrollment

Add or reconcile the adjudicated remedies in each existing owning plan and prove no gap is orphaned, duplicated, or tracked only by the roll-up.

- [ ] `W02.P04.S26` - Enroll every temporal-window and authority-grade remedy in registry-temporal-coverage without duplicating closed work; `.vault/plan/2026-08-14-registry-temporal-coverage-plan.md`.
- [ ] `W02.P04.S27` - Enroll every source and casilla remedy in source-casilla-integration without duplicating closed work; `.vault/plan/2026-08-22-source-casilla-integration-plan.md`.
- [ ] `W02.P04.S28` - Enroll every official-layout and emitted-byte remedy in aeat-export-fragment-generator-authority without duplicating closed work; `.vault/plan/2026-08-10-aeat-export-fragment-generator-authority-plan.md`.
- [ ] `W02.P04.S29` - Prove every live filing gap has exactly one terminal refusal or one existing-plan owner and reconsideration condition; `src/cadrumo/domain/calculations/registry/tests/test_filing_capability_worklist.py`.

## Wave `W03` - semantic proof and predecessor closure

Prove localization, binding, continuity, calculation, and export semantics across the supported umbrella, close the predicate-relevant predecessor plans with execution evidence, and finish with an independent honesty review.

### Phase `W03.P05` - cross-layer semantic verification

Exercise the supported revision umbrella through localization, casilla continuity, binding and calculation resolution, and official export layout semantics.

- [ ] `W03.P05.S30` - Verify every shipped modelo and revision localization key across supported output locales; `dev/locales/`.
- [ ] `W03.P05.S31` - Verify casilla identity, semantic linkage, and continuity chains across every supported revision boundary; `src/cadrumo/domain/calculations/registry/tests/`.
- [ ] `W03.P05.S32` - Verify binding selectors, resolver enrollment, calculation paths, and provenance for every filing-grade revision; `src/cadrumo/domain/calculations/registry/tests/`.
- [ ] `W03.P05.S33` - Verify official export layout selection, mapped semantic owners, and emitted-byte offsets for every filing-grade revision; `src/cadrumo/application/filing/tests/`.

### Phase `W03.P06` - predecessor campaign closure

Close the predicate-relevant work in temporal coverage, source-casilla integration, and export-fragment authority with records, summaries, reviews, and canonical plan state.

- [ ] `W03.P06.S34` - Close registry-temporal-coverage predicate-relevant rows, execution records, summaries, stale assumptions, and final review; `.vault/plan/2026-08-14-registry-temporal-coverage-plan.md`.
- [ ] `W03.P06.S35` - Close source-casilla-integration predicate-relevant rows, execution records, summaries, stale assumptions, and final review; `.vault/plan/2026-08-22-source-casilla-integration-plan.md`.
- [ ] `W03.P06.S36` - Close aeat-export-fragment-generator-authority predicate-relevant rows, execution records, summaries, stale assumptions, and final review; `.vault/plan/2026-08-10-aeat-export-fragment-generator-authority-plan.md`.

### Phase `W03.P07` - release honesty and delivery

Run the derived release gate and an independent fresh-context honesty review, action every finding, and publish the final supported-versus-refused registry boundary.

- [ ] `W03.P07.S37` - Run a fresh-context honesty review of the derived closure report and every predecessor close claim; `.vault/audit/`.
- [ ] `W03.P07.S38` - Resolve or formally defer every honesty-review finding through its owning predecessor plan; `.vault/plan/`.
- [ ] `W03.P07.S39` - Run the blocking release predicate, publish the supported-versus-refused boundary, and close this roll-up plan; `dev/registry/conformance/`.

## Parallelization

Waves are ordered. In W01, S01 through S05 are serialized because later reconciliation
depends on independent review, while S06 through S09 may proceed independently after
S05 and converge at S10; S11 follows the composed report. The fourteen W02 adjudication
Steps may run in parallel with one agent per revision, but each produces an independent
evidence record and none may edit a predecessor plan. S26 through S28 are serialized by
plan owner after all adjudications finish; S29 follows all three. The four W03 semantic
verification Steps may run in parallel against the landed corpus. Predecessor close
Steps S34 through S36 may run in parallel only when their file scopes do not overlap;
S37 through S39 are strictly serialized. Terra/xhigh is the default executor. Sol/low
or Sol/medium is reserved for steps whose live inspection demonstrates hard semantic,
generator, or cross-layer implementation work.

## Verification

Completion requires all 39 Steps closed with one execution record per Step and mandatory
independent code review after every implementation cycle. The derived report must carry
one row for every law-selectable registered revision and must fail closed for a missing,
stale, unreviewed, conflicting, or scope-inadequate limb. Every live filing gap must have
exactly one evidence-bearing refusal or one existing-plan owner. Localization, semantic
casilla continuity, binding and calculation provenance, official layout selection, and
emitted-byte tests must pass across the supported umbrella. The three predecessor plans
must have no predicate-relevant open row, missing record, stale checkbox, unresolved
high or medium review finding, or unrecorded supersession. A fresh-context honesty audit
must action every finding before the blocking release predicate can close this plan.
