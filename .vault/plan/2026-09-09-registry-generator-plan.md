---
tags:
  - '#plan'
  - '#registry-generator'
date: '2026-09-09'
tier: L3
related:
  - '[[2026-09-09-registry-generator-adr]]'
  - '[[2026-09-09-registry-generator-corpus-provenance-research]]'
  - '[[2026-09-09-registry-generator-divergence-evidence-research]]'
  - '[[2026-09-09-registry-generator-signal-coverage-research]]'
modified: '2026-09-09'
body_schema: body-v2
body_hash: 'sha256:43a2748f317656db062cbff8cb5d1905945bbbd1177215291927ddd2bce7202d'
---

# `registry-generator` plan

## Description

Deliver a registry whose shipped values can be shown to derive from the official documents they
cite, and the tooling that keeps that true as new official documents arrive.

The governing decision record is `2026-09-09-registry-generator-adr`, accepted, and this plan
executes it in full. Wave W01 settles the one premise the record marks as unverified and returns
the currently failing assertions to green. Wave W02 executes the refusal rulings D1a and D2. Wave
W03 executes the attestation ruling D3 and the cross-period diagnostic D6. Wave W04 executes the
independent rulings D7, D8, the static limb of D4, D9 and D10. Wave W05 opens the consumer lane the
record defers and then settles the two rulings held on its answer, D1b and D5.

The three grounding documents in `related:` supply the measurements this plan acts on: the corpus
shape and the stalled migration, the divergence census and its mechanism, and what the existing
gates can and cannot see. Two rulings are deliberately not executed before Wave W05, because the
consumer lane decides their primitive rather than refining it.

The work binds the producer and the attestation, not the produced files. Correcting a shipped
declaration by hand is futile while the generator that overwrites it is unchanged, which is why no
Step here repairs a value without a Step that changes what produces it.

## Steps

## Wave `W01` - ground truth and the red tree

Establishes the facts every later Wave depends on and returns the tree to green. The accepted decision record rests on one premise nobody has verified - that the annual IVA summary's official design carries a per-page legend placing the sign in the first position - and eight assertions are failing today because the shipped declarations contradict that reading. Nothing downstream may proceed on an unverified premise, so this Wave settles it first, resolves the failing assertions, and repairs the modelo that three independent instruments flagged. Blocks every other Wave.

### Phase `W01.P01` - verify the official premise

Establishes from the captured official document whether the annual IVA summary states the sign convention, and records the answer as evidence rather than as inference.

- [x] `W01.P01.S01` - Extract the per-page legend text from the captured official design and record whether it states a sign position; `src/cadrumo/_data/corpus/aeat_official/disenos_registro/modelo_390/`.
- [x] `W01.P01.S02` - Cross-check the same legend question against a modelo whose design spells the sign inline rather than by legend; `src/cadrumo/_data/corpus/aeat_official/disenos_registro/modelo_200/`.
- [ ] `W01.P01.S03` - Record the verified premise, or its refutation, as a digest-pinned reviewed adjudication; `dev/registry/pipeline/source_defects.py`.

### Phase `W01.P02` - resolve the failing sign assertions

Returns the eight failing registry assertions to green on whichever side the verified premise supports, with the outcome recorded as a reviewed adjudication.

- [ ] `W01.P02.S04` - Declare the width-17 signed membership rule for the annual IVA summary citing the per-page sign legend as official-source evidence; `dev/registry/render_profiles/modelo_390/`.
- [ ] `W01.P02.S05` - Enumerate the width-17 signed anchors for each affected revision of the annual IVA summary; `dev/registry/render_profiles/modelo_390/`.
- [ ] `W01.P02.S06` - Regenerate the affected export trees through the owning generator and review the diff; `src/cadrumo/_data/registry/aeat/modelos/390/revisions/`.
- [ ] `W01.P02.S66` - Correct the recorded justification that infers the sign from the content cell alone; `dev/registry/pipeline/source_defects.py`.
- [ ] `W01.P02.S07` - Run the annual IVA summary registry suite and record the exit status from the run metadata; `src/cadrumo/domain/calculations/registry/tests/`.

### Phase `W01.P03` - repair the thrice-flagged modelo

Repairs the informative-declaration modelo whose manifest disagrees with its shipped declarations, whose monetary fields diverge across a revision boundary, and whose revisions are the only ones where check mode is never invoked. Independent of the sign work: this modelo carries no signed or unsigned numeric field at all.

- [ ] `W01.P03.S08` - Reconcile the manifest against the shipped declarations for the earlier informative revision; `dev/registry/mappings/modelo_347/2011/`.
- [ ] `W01.P03.S09` - Reconcile the manifest against the shipped declarations for the later informative revision; `dev/registry/mappings/modelo_347/2025/`.
- [ ] `W01.P03.S10` - Reproduce the binding-rows repeat and per-row casilla identities the ledger names as the defect; `dev/registry/mappings/modelo_347/`.
- [ ] `W01.P03.S11` - Decide how the uncontrolled type vocabulary is read, given this modelo carries no canonical type token; `dev/registry/pipeline/render_profile_eligibility.py`.
- [ ] `W01.P03.S67` - Pin the informative modelo's check-mode refusal before its disposition rows are retired; `dev/registry/tests/test_generated_export_trees.py`.
- [ ] `W01.P03.S12` - Retire the two disposition rows once the shipped bytes reproduce from the current inputs; `dev/registry/pipeline/generated_tree_dispositions.toml`.

## Wave `W02` - the generator refuses

Makes the producer fail closed on the two axes the decision record settles: an undetermined sign, and a design whose own columns contradict each other. Refusals are measured at 2,017 fields across 22 of 32 generated revisions, so they land against the named disposition ledger rather than as red reproduction gates, one row per affected revision, each pinning its source and its retirement condition. Depends on Wave W01 having settled what the official columns actually say.

### Phase `W02.P16` - make the ledger able to absorb a refusal

Prerequisite for every refusal in this Wave. The reproduction gate renders unconditionally before it consults the ledger, and the ledger model forbids extra fields and carries only the record-drift class, so a refusal raises before any row can excuse it. This Phase gives the ledger a refusal class and moves the consultation ahead of the render.

- [ ] `W02.P16.S61` - Add a refusal disposition class to the ledger model under a new schema version; `dev/registry/pipeline/render_check.py`.
- [ ] `W02.P16.S62` - Consult the ledger before the fresh render rather than after it; `dev/registry/tests/test_generated_export_trees.py`.
- [ ] `W02.P16.S63` - Treat a ledgered refusal as an expected raise rather than an error; `dev/registry/tests/test_generated_export_trees.py`.
- [ ] `W02.P16.S64` - Confirm an unledgered refusal still fails the gate; `dev/registry/tests/`.
- [ ] `W02.P16.S65` - Confirm a refusal row whose cause is repaired fails as dormant; `dev/registry/tests/`.

### Phase `W02.P04` - refuse a self-contradicting design

Implements the primary remedy: an arithmetic, decidable check that a row's type column and its content cell describe the same slot width, refusing when they do not.

- [ ] `W02.P04.S13` - Implement the width arithmetic that reads a type column and a content cell as one slot; `dev/registry/pipeline/_export_tree.py`.
- [ ] `W02.P04.S14` - Raise on a contradiction naming modelo, revision, field and both readings; `dev/registry/pipeline/_export_tree.py`.
- [ ] `W02.P04.S15` - Decide and implement the disposition of the five hundred and seventy-nine rows whose type cell is a spelled-out word or a non-type; `dev/registry/pipeline/_export_tree.py`.
- [ ] `W02.P04.S16` - Prove the detector with a planted contradiction in an isolated temporary tree; `dev/registry/tests/`.
- [ ] `W02.P04.S17` - Prove a consistent unsigned design does not fire the detector; `dev/registry/tests/`.

### Phase `W02.P05` - determine the sign or refuse

Removes the unconditional literals and the predicate fold that make the official distinction unavailable downstream, so the generator either determines the sign from the official column or refuses.

- [ ] `W02.P05.S18` - Replace the unconditional signed literals with a value derived from the official type column; `dev/registry/pipeline/_export_tree.py`.
- [ ] `W02.P05.S19` - Unfold the numeric predicate that collapses the signed and unsigned type tokens into one class; `dev/registry/pipeline/render_profile_eligibility.py`.
- [ ] `W02.P05.S20` - Raise when the sign cannot be established from an authority rather than writing a constant; `dev/registry/pipeline/_export_tree.py`.
- [ ] `W02.P05.S21` - Narrow the generator parameter type so an undetermined sign is not expressible at the call site; `dev/registry/pipeline/_export_tree.py`.
- [ ] `W02.P05.S71` - Add the runtime validator at the registry boundary that the primary control depends on; `src/cadrumo/domain/calculations/registry/`.
- [ ] `W02.P05.S22` - Prove the refusal with a planted undetermined sign in an isolated temporary tree; `dev/registry/tests/`.

### Phase `W02.P06` - ledger the refusals

Records one disposition row per affected revision so the refusals land without turning the reproduction gates red, each row pinning its source and its retirement condition.

- [ ] `W02.P06.S23` - Add one disposition row per affected revision pinning its source and reconsideration condition; `dev/registry/pipeline/generated_tree_dispositions.toml`.
- [ ] `W02.P06.S24` - Confirm both reproduction gates stay green with the refusals ledgered; `dev/registry/tests/test_generated_export_trees.py`.
- [ ] `W02.P06.S25` - Confirm the ledger gate still fails when a pin goes dormant; `dev/registry/tests/`.

## Wave `W03` - attestation and cross-period diagnosis

Converts the comparison from a bespoke sweep into a fact the artefact carries, and adds the cross-period signal the operator asked for as a diagnostic that demands explanation rather than a gate that reads agreement as correctness. Depends on Wave W02, because a per-field verdict can only record agrees, adjudicated or refused once refusal exists.

### Phase `W03.P07` - attest the per-field verdict

Adds a per-field divergence verdict computed at generation time, so a disagreement between the official row and the shipped field becomes a diffable fact rather than something only a bespoke sweep can see.

- [ ] `W03.P07.S26` - Compute a per-field verdict of agrees, adjudicated or refused at generation time; `dev/registry/pipeline/export_fragment_provenance.py`.
- [ ] `W03.P07.S27` - Serialize the verdict into the generation manifest beside the existing derivation record; `dev/registry/pipeline/export_fragment_provenance.py`.
- [ ] `W03.P07.S28` - Regenerate the manifests and review the verdict distribution against the measured census; `src/cadrumo/_data/registry/aeat/modelos/`.
- [ ] `W03.P07.S72` - Re-pin any reproduction pin whose disposition class moved when the manifests changed; `dev/registry/tests/test_generated_export_trees.py`.
- [ ] `W03.P07.S29` - Prove a planted divergence produces a refused verdict rather than an agreeing one; `dev/registry/tests/`.

### Phase `W03.P08` - build the cross-period diagnostic

Reports a field whose typed wire shape changes between revisions without a corresponding change in the official designs as a suspect requiring explanation, without asserting correctness from stability.

- [ ] `W03.P08.S30` - Compare the typed wire shape of each field identity across the revisions of its modelo; `dev/registry/analysis/`.
- [ ] `W03.P08.S31` - Report a shape change unaccompanied by an official change as a suspect requiring explanation; `dev/registry/analysis/`.
- [ ] `W03.P08.S32` - Record that agreement is not treated as evidence of correctness, with the bound that travels with the signal; `dev/registry/analysis/`.
- [ ] `W03.P08.S33` - Prove the diagnostic detects a planted cross-revision shape change; `dev/registry/tests/`.
- [ ] `W03.P08.S68` - Enrol the new diagnostic in the screens register so the invariant gate sees it; `dev/registry/analysis/screens.py`.
- [ ] `W03.P08.S69` - Document the new diagnostic in the registry readme the invariant gate also checks; `dev/registry/README.md`.

## Wave `W04` - close the standing gaps

Addresses the rulings that are independent of the refusal mechanism: the authoring default that regrows the hand-authored surface, the staleness detector wired to nothing, the type-check scope that excludes the generator package, the reporting screens with no drain, and the absence of any check that does not originate in the generator. Every Phase here is independent of every other and of Wave W03.

### Phase `W04.P09` - make generation the scaffolded default

Changes the authoring default so a new revision scaffolds the generated path and hand-authoring becomes the declared exception, stating why.

- [ ] `W04.P09.S34` - Scaffold the generated export path for a new revision instead of the hand-authored layout; `dev/registry/newmodelo/manager.py`.
- [ ] `W04.P09.S35` - Rewrite the authoring checklist so hand-authoring is the declared exception stating why; `dev/registry/newmodelo/checklist.py`.
- [ ] `W04.P09.S36` - Add a declaration recording whether a revision's values are derived or transcribed; `src/cadrumo/domain/calculations/registry/`.
- [ ] `W04.P09.S37` - Prove a newly scaffolded revision arrives on the generated path; `dev/registry/tests/`.

### Phase `W04.P10` - wire the staleness detector

Puts the existing live-source detector on a schedule with defined acceptance: it reports a republish as a finding, does not block a change-triggered gate, and reports an unreachable network as a limitation rather than as pass or fail.

- [ ] `W04.P10.S38` - Invoke the detector's live-check flag from a scheduled workflow; `.github/workflows/`.
- [ ] `W04.P10.S39` - Report a detected republish as a finding against the corpus without blocking a change-triggered gate; `dev/corpus/sync_aeat_record_design_corpus.py`.
- [ ] `W04.P10.S40` - Report an unreachable network explicitly as a limitation rather than as pass or fail; `dev/corpus/sync_aeat_record_design_corpus.py`.

### Phase `W04.P11` - admit the generator package to the type gate

Burns the generator package's diagnostics to zero and admits it permanently, with no baseline, ratchet or per-tree exemption.

- [ ] `W04.P11.S41` - Burn the generator package's type diagnostics to zero without suppressions; `dev/registry/`.
- [ ] `W04.P11.S42` - Admit the generator package to the type-check target list; `dev/quality/types.py`.
- [ ] `W04.P11.S43` - Update the burn-down comment to remove the admitted entry; `dev/quality/types.py`.

### Phase `W04.P12` - give the findings screens a drain

Promotes or retires each reporting screen that returns findings and carries a non-zero population, leaving census screens untouched.

- [ ] `W04.P12.S44` - Enumerate each findings screen carrying a non-zero population; `dev/registry/analysis/screens.py`.
- [ ] `W04.P12.S45` - Promote or retire each enumerated findings screen, leaving census screens untouched; `dev/registry/analysis/`.
- [ ] `W04.P12.S46` - Record the promote-or-retire condition so a findings screen cannot sit indefinitely; `dev/registry/analysis/screens.py`.
- [ ] `W04.P12.S73` - Correct the readme prose stating a screen never gates, where a screen is promoted; `dev/registry/README.md`.
- [ ] `W04.P12.S74` - Account for the derived screen that re-reports its source's findings when counting populations; `dev/registry/analysis/screens.py`.

### Phase `W04.P13` - introduce an independent oracle

Decodes official worked examples through the shipped codec and compares field by field, so at least one check does not originate in the generator.

- [ ] `W04.P13.S47` - Extend the existing external-oracle corpus enum rather than creating a second oracle surface; `src/cadrumo/core/external_oracle_corpus.py`.
- [ ] `W04.P13.S48` - Extend the existing grounding fold and conformance-vector mechanism to carry the new comparison; `src/cadrumo/domain/calculations/registry/external_grounding.py`.
- [ ] `W04.P13.S70` - Confirm at least one bundled worked example carries a negative amount in an affected fixed-width slot; `src/cadrumo/_data/corpus/manual_oracles/`.
- [ ] `W04.P13.S49` - Compare the decoded values field by field against the published figures; `src/cadrumo/domain/calculations/registry/tests/`.
- [ ] `W04.P13.S50` - Confirm no expected value in the oracle originates in the generator; `src/cadrumo/domain/calculations/registry/tests/`.

## Wave `W05` - the consumer lane and the held rulings

Examines how the consuming application behaves when handed a registry that is internally inconsistent, temporally incoherent, or partially adjudicated - the question the decision record explicitly defers and on which two rulings are held. Its answer decides whether an undetermined state is representable end to end, which is the primitive for required-ness and for the absence validators. Runs last because it may amend the accepted record.

### Phase `W05.P14` - examine consumer behaviour

Determines whether the consuming application refuses, degrades or proceeds when the registry is incoherent, and whether a calculation can distinguish an undetermined value from an adjudicated one.

- [ ] `W05.P14.S51` - Determine whether the authority refuses, degrades or proceeds when a revision is internally inconsistent; `src/cadrumo/domain/calculations/registry/`.
- [ ] `W05.P14.S52` - Determine whether a calculation can distinguish an undetermined value from an adjudicated one; `src/cadrumo/domain/calculations/`.
- [ ] `W05.P14.S53` - Determine whether filing-grade paths distinguish a silent registry from one that states zero; `src/cadrumo/application/`.
- [ ] `W05.P14.S54` - Determine whether a temporally incoherent revision selection is rejected at the authority boundary; `src/cadrumo/domain/calculations/registry/`.
- [ ] `W05.P14.S55` - Record the consumer findings as a reference document for the held rulings; `.vault/reference/`.

### Phase `W05.P15` - settle the held rulings

Amends the accepted record with the refusal semantics the consumer lane establishes, then implements the two rulings held on its answer.

- [ ] `W05.P15.S56` - Amend the accepted decision record with the refusal semantics the consumer lane establishes; `.vault/adr/`.
- [ ] `W05.P15.S57` - Introduce an undetermined state for required-ness distinct from required and optional; `src/cadrumo/domain/calculations/registry/`.
- [ ] `W05.P15.S58` - Stop folding said-optional, said-nothing and unrecognised-token into one value; `dev/registry/pipeline/_export_tree.py`.
- [ ] `W05.P15.S59` - Tie each groundable wire axis to its official source column with a refusing validator; `src/cadrumo/domain/calculations/registry/`.
- [ ] `W05.P15.S60` - Prove the undetermined state survives from declaration through calculation to filing handoff; `src/cadrumo/domain/calculations/tests/`.

## Parallelization

Waves are sequenced. W01 blocks everything, because the refusal rulings act on what the official
columns say. W02 blocks W03, because a per-field verdict can only record refused once refusal
exists. W05 runs last because it may amend the accepted record.

Inside W02, Phase W02.P16 blocks W02.P04 and W02.P05 absolutely. The reproduction gate renders
unconditionally before it consults the ledger, and the ledger model forbids extra fields and
carries only the record-drift class, so until P16 lands a refusal raises before any row can excuse
it and no refusal in this Wave can be made to land green. Nothing in W02 may start with P16 open.

W04 is the parallel opportunity, with one hard exception. It depends on nothing in W02 or W03 and
may begin as soon as W01 closes. The exception is W04.P11: admitting the generator package to the
type gate puts the pipeline and analysis packages under an error-level checker while W02 and W03
are actively rewriting both. W04.P11 therefore runs either before W02 starts or after W03 closes,
never alongside them. Note also that W04.P10 edits a package that is already inside the type gate,
so its Steps must land type-clean immediately rather than at the end of W04.P11.

Within W01, Phase W01.P03 is independent of W01.P01 and W01.P02 and runs in parallel with them,
except for one Step: W01.P03.S11 and W02.P05.S19 touch the same predicate region, so S11 is
sequenced against W02.P05 rather than run concurrently with it. W01.P01 and W01.P02 are strictly
sequential.

Within W02, Phases W02.P04 and W02.P05 touch the same module and take one writer between them,
sequentially. W02.P06 follows both.

Within W03, Phases W03.P07 and W03.P08 are independent, with one shared-file caveat below.

Within W04, the Phases are independent of each other with two exceptions: W04.P11 as stated above,
and W04.P12, which owns the screens register and the registry readme.

Shared files take one writer. The generator module is touched by W02.P04, W02.P05 and W05.P15. The
screens register and the registry readme are touched by W03.P08 and W04.P12, so those two Phases
do not run concurrently despite sitting in different Waves. The reproduction gate module is touched
by W01.P03, W02.P16, W02.P06 and W03.P07.

This worktree has concurrent writers outside this plan. Before starting any Phase, re-read the
files it names and the current diff, because an inventory taken earlier may already be stale.

## Verification

The plan is complete when every Step is closed and each criterion below holds.

- The premise recorded as unverified in the governing decision record is either verified against
  the captured official document or refuted, and the outcome is a digest-pinned adjudication rather
  than an inference.
- The eight registry assertions that fail today pass, and the run exit status is read from the run
  metadata rather than from a pipeline whose trailing command masks it.
- The generator raises on a design whose type column and content cell describe different slot
  widths, and a planted contradiction in an isolated temporary tree proves it.
- The generator raises rather than writing a constant when the sign cannot be established, and a
  planted undetermined sign in an isolated temporary tree proves it.
- A consistent unsigned design does not fire either refusal, proving the detectors are not blanket.
- Both reproduction gates pass with the refusals ledgered, and the ledger gate still fails when a
  pin goes dormant.
- Every generated field carries a divergence verdict, and a planted divergence yields refused
  rather than agrees.
- The cross-period diagnostic detects a planted shape change and asserts nothing from agreement.
- A newly scaffolded revision arrives on the generated path.
- The staleness detector runs on a schedule, reports a republish as a finding, and reports an
  unreachable network as a limitation rather than as pass or fail.
- The generator package is inside the type-check target list with zero diagnostics and no
  suppression, baseline or exemption.
- Every findings screen carrying a non-zero population is promoted or retired; census screens are
  unchanged.
- At least one check compares shipped behaviour against an official worked example whose expected
  values do not originate in the generator.
- The consumer lane has reported, in a persisted reference, whether the authority refuses, degrades
  or proceeds on an incoherent registry, and whether an undetermined value is distinguishable from
  an adjudicated one.
- No Step introduced a new lint, type, test, schema or vault failure, and any pre-existing failure
  is reported separately with evidence.

Every new gate carries a planted defect. A gate that cannot demonstrate detection of a
representative defect does not close its Step.

Knowingly excluded, so that the exclusion is a decision rather than an oversight:

- The hand-authored export surface is not repaired by this plan. Its revisions largely cite an
  official source that is present in the corpus and has never been joined to the shipped field, and
  that remains true at the end of this work. The attestation ruling makes the surface auditable by
  the same means once it carries manifests; producing those manifests is not in scope here.
- The four duplicated statutory figures recorded during discovery are excluded by operator
  direction and are not re-raised.

One standing hazard, carried here because it is a completion condition rather than a Step: several
generated trees are pinned by class, and a change to the generator or to the manifest can move a
pin's class and trip its assertion. No Phase closes while a pin it moved is left dormant.
