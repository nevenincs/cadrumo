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
modified: '2026-09-10'
body_schema: body-v2
body_hash: 'sha256:eaf80f9469e53c833a89c7302db9cad3cbd36bf54dcb995e975d54986de083c1'
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
- [x] `W01.P01.S03` - Record the verified premise, or its refutation, as a digest-pinned reviewed adjudication; `dev/registry/pipeline/source_defects.py`.

### Phase `W01.P02` - resolve the failing sign assertions

Returns the eight failing registry assertions to green on whichever side the verified premise supports, with the outcome recorded as a reviewed adjudication.

- [x] `W01.P02.S04` - RETIRED as mis-scoped: the render profile governs only fields whose content cell is BLANK, so the annual IVA summary's rows are ineligible by construction and a membership rule for them is refused as unknown anchors. The sign is derived at the generator from the official type column instead; `dev/registry/pipeline/_export_tree.py`.
- [x] `W01.P02.S05` - RETIRED with S04: enumerating anchors for a rule the profile cannot accept. Superseded by deriving the sign from the type column for every field, which needs no anchor list; `dev/registry/pipeline/_export_tree.py`.
- [x] `W01.P02.S06` - Regenerate modelo 390's export trees with the sign derived from the official type column. Landed: all four revisions republished, and 390/2022 now declares exactly the 294 signed fields the previewed diff predicted (243 unsigned remain); 2023 has 298, 2024 has 362, 2025 has 282; `src/cadrumo/_data/registry/aeat/modelos/390/revisions/`.
- [x] `W01.P02.S66` - Correct the recorded justification that infers the sign from the content cell alone; `dev/registry/pipeline/source_defects.py`.
- [x] `W01.P02.S07` - Re-run the shipped-declaration tests that assert modelo 390's sign. Landed: test_modelo_390_registry.py reports 56 passed exit 0, against the 8 failed and 48 passed recorded before S06 regenerated the trees; `src/cadrumo/domain/calculations/registry/tests/`.

### Phase `W01.P03` - repair the thrice-flagged modelo

Repairs the informative-declaration modelo whose manifest disagrees with its shipped declarations, whose monetary fields diverge across a revision boundary, and whose revisions are the only ones where check mode is never invoked. Independent of the sign work: this modelo carries no signed or unsigned numeric field at all.

- [x] `W01.P03.S08` - SUPERSEDED by S10: reconciling the manifest is not the work; authoring the record repeat is, and the ledger already states which side is right; `dev/registry/mappings/modelo_347/2011/`.
- [x] `W01.P03.S09` - SUPERSEDED by S10, as S08; `dev/registry/mappings/modelo_347/2025/`.
- [ ] `W01.P03.S10` - Author modelo 347's declarado repeat and row bindings, then give the generator a split-cell identity. PARTLY LANDED: both semantic maps now author repeat=binding_rows, the per-row casilla identities and the eight row-binding fields exactly as the shipped trees carry them, and the fresh render matches the shipped record everywhere except one cell. That cell is BLOCKED ON THE EXPORT-SCHEMA MIGRATION: the design's own text divides the four-byte cell at offset 77 into '77-78 CODIGO PROVINCIA' and '79-80 CODIGO PAIS', and giving each half an identity through the join needs a new key on RecordDesignIntermediateField or SemanticMapAnchor, both stored in every generation manifest, which the canonical round-trip refuses; encoding the part in the printed ordinal would fabricate a label AEAT never printed. Also found: the 2011 shipped tree binds a counterparty NIF casilla into offset 264 length 237, which the design declares BLANCOS - a copy from the 2025 design - so that field is wrong in the shipped bytes and the render is right; `dev/registry/mappings/modelo_347/`.
- [x] `W01.P03.S11` - Answered by the type census rather than by a decision here: the uncontrolled spellings are already normalised for eligibility on an accent-stripped stem, and the informative modelo's slots carry no numeric type at all, so no sign question arises for them. What remains is the 579 rows tracked in S15; `dev/registry/pipeline/render_profile_eligibility.py`.
- [x] `W01.P03.S67` - STALE until S12: the informative modelo carries disposition rows, so the gate returns before check mode runs and a pinned refusal could never be exercised. The pin belongs with the retirement, not before it; `dev/registry/tests/test_generated_export_trees.py`.
- [ ] `W01.P03.S12` - BLOCKED until S10 authors the repeat: retiring the rows before the map reproduces the counterparty records is exactly the action that ships a truncated informative return; `dev/registry/pipeline/generated_tree_dispositions.toml`.

## Wave `W02` - the generator refuses

Makes the producer fail closed on the two axes the decision record settles: an undetermined sign, and a design whose own columns contradict each other. Refusals are measured at 2,017 fields across 22 of 32 generated revisions, so they land against the named disposition ledger rather than as red reproduction gates, one row per affected revision, each pinning its source and its retirement condition. Depends on Wave W01 having settled what the official columns actually say.

### Phase `W02.P16` - make the ledger able to absorb a refusal

Prerequisite for every refusal in this Wave. The reproduction gate renders unconditionally before it consults the ledger, and the ledger model forbids extra fields and carries only the record-drift class, so a refusal raises before any row can excuse it. This Phase gives the ledger a refusal class and moves the consultation ahead of the render.

- [x] `W02.P16.S61` - Add a refusal disposition class to the ledger model under a new schema version; `dev/registry/pipeline/render_check.py`.
- [x] `W02.P16.S62` - Consult the ledger before the fresh render rather than after it; `dev/registry/tests/test_generated_export_trees.py`.
- [x] `W02.P16.S63` - Treat a ledgered refusal as an expected raise rather than an error; `dev/registry/tests/test_generated_export_trees.py`.
- [x] `W02.P16.S64` - STALE as written: no refusal row exists now that the sign derives instead of refusing, so an unledgered refusal cannot be staged without inventing a defect the generator no longer produces. The ledger's refusal class keeps its own six planted-defect proofs; `dev/registry/tests/test_render_check.py`.
- [x] `W02.P16.S65` - STALE with S64, and the property it wanted is covered: the gate asserts a standing disposition whose tree no longer drifts must be removed, which is dormancy detection for the class that actually has rows; `dev/registry/tests/test_generated_export_trees.py`.

### Phase `W02.P04` - refuse a self-contradicting design

Implements the primary remedy: an arithmetic, decidable check that a row's type column and its content cell describe the same slot width, refusing when they do not.

- [x] `W02.P04.S13` - Implement the width arithmetic that reads a type column and a content cell as one slot; `dev/registry/pipeline/_export_tree.py`.
- [x] `W02.P04.S14` - Raise on a contradiction naming modelo, revision, field and both readings; `dev/registry/pipeline/_export_tree.py`.
- [x] `W02.P04.S15` - Decide the sign disposition of the 579 uncontrolled AEAT type spellings from the designs' own text. Settled, and nothing emitted changes. 241 'Numerico' and 93 of 95 'No consta' fields are unsigned under an explicit design-wide rule, verified against the design each revision pins (aeat-dr-184-2023-2024, -184-2025, -296-2024, -347-2011, -347-2025): 'Todos los campos numericos se presentaran alineados a la derecha y rellenos a ceros por la izquierda sin signos y sin empaquetar'; modelo 296 carries direction in a separate alphabetic SIGNO subfield, never an N prefix. The last 2 'No consta' fields are in aeat-dr-185-2026, whose design states no convention: a TELEFONO header field and an APELLIDOS Y NOMBRE header field, a phone number and a name, which have no negative domain, so unsigned follows from the field and not from a design rule. 243 alphabetic and blank spellings are not numeric; `dev/registry/pipeline/_export_tree.py`.
- [x] `W02.P04.S16` - Prove the detector with a planted contradiction in an isolated temporary tree; `dev/registry/tests/`.
- [x] `W02.P04.S17` - Prove a consistent unsigned design does not fire the detector; `dev/registry/tests/`.

### Phase `W02.P05` - determine the sign or refuse

Removes the unconditional literals and the predicate fold that make the official distinction unavailable downstream, so the generator either determines the sign from the official column or refuses.

- [x] `W02.P05.S18` - Replace the unconditional signed literals with a value derived from the official type column; `dev/registry/pipeline/_export_tree.py`.
- [x] `W02.P05.S19` - STALE and would be a regression: the predicate answers ELIGIBILITY - is this field numeric and therefore owed a reviewed render rule - where folding the signed and unsigned tokens is correct, and the fold exists because PDF designs spell the word out. Unfolding it would make signed fields ineligible for review. The sign is read from the type column at the derivation site and no longer passes through here, which is why calling this predicate the defect was retracted; `dev/registry/pipeline/render_profile_eligibility.py`.
- [x] `W02.P05.S20` - Raise when the sign cannot be established from an authority rather than writing a constant; `dev/registry/pipeline/_export_tree.py`.
- [x] `W02.P05.S21` - Narrow the generator parameter type so an undetermined sign is not expressible at the call site; `dev/registry/pipeline/_export_tree.py`.
- [ ] `W02.P05.S71` - BLOCKED by the publication gap: it changes emitted output, and publish refuses a tree whose records differ from the shipped manifest, which is the difference being landed. It also needs the shipped declaration schema to carry the official source column it would validate against, which the schema does not have; `src/cadrumo/domain/calculations/registry/`.
- [x] `W02.P05.S22` - Prove the refusal with a planted undetermined sign in an isolated temporary tree; `dev/registry/tests/`.

### Phase `W02.P06` - ledger the refusals

Records one disposition row per affected revision so the refusals land without turning the reproduction gates red, each row pinning its source and its retirement condition.

- [x] `W02.P06.S23` - Add one disposition row per affected revision pinning its source and reconsideration condition; landed as record_drift rather than refusal once the sign became derivable; `dev/registry/pipeline/generated_tree_dispositions.toml`.
- [x] `W02.P06.S24` - Confirm both reproduction gates stay green with the refusals ledgered; `dev/registry/tests/test_generated_export_trees.py`.
- [x] `W02.P06.S25` - Confirm the ledger gate still fails when a pin goes dormant; `dev/registry/tests/`.

## Wave `W03` - attestation and cross-period diagnosis

Converts the comparison from a bespoke sweep into a fact the artefact carries, and adds the cross-period signal the operator asked for as a diagnostic that demands explanation rather than a gate that reads agreement as correctness. Depends on Wave W02, because a per-field verdict can only record agrees, adjudicated or refused once refusal exists.

### Phase `W03.P07` - attest the per-field verdict

Adds a per-field divergence verdict computed at generation time, so a disagreement between the official row and the shipped field becomes a diffable fact rather than something only a bespoke sweep can see.

- [ ] `W03.P07.S26` - BLOCKED with S27 and S28, not merely before them: the manifest loader compares canonical bytes, so adding even an optional verdict field invalidates all 32 shipped manifests, and regenerating them needs the publication path that refuses a changed tree; `dev/registry/pipeline/export_fragment_provenance.py`.
- [ ] `W03.P07.S27` - BLOCKED with S26: proven by attempting it. An optional field defaulting to None still moves the canonical serialization and every shipped manifest fails to load; `dev/registry/pipeline/export_fragment_provenance.py`.
- [ ] `W03.P07.S28` - BLOCKED on the publication gap: regenerating manifests requires publishing a corrected tree, and publish runs a no-drift check that refuses the very difference being landed. See the check-mode comparison of the shipped manifest against the fresh render; `dev/registry/pipeline/_tree_check.py`.
- [x] `W03.P07.S72` - Re-pin any reproduction pin whose disposition class moved when the manifests changed; `dev/registry/tests/test_generated_export_trees.py`.
- [ ] `W03.P07.S29` - BLOCKED by the publication gap: it changes emitted output, and publish refuses a tree whose records differ from the shipped manifest, which is the difference being landed. The planted-defect proof cannot exist before the verdict it proves, which S26 and S27 cannot land; `dev/registry/tests/`.

### Phase `W03.P08` - build the cross-period diagnostic

Reports a field whose typed wire shape changes between revisions without a corresponding change in the official designs as a suspect requiring explanation, without asserting correctness from stability.

- [x] `W03.P08.S30` - Compare the typed wire shape of each field identity across the revisions of its modelo; `dev/registry/analysis/`.
- [x] `W03.P08.S31` - Report a shape change unaccompanied by an official change as a suspect requiring explanation; `dev/registry/analysis/`.
- [x] `W03.P08.S32` - Record that agreement is not treated as evidence of correctness, with the bound that travels with the signal; `dev/registry/analysis/`.
- [x] `W03.P08.S33` - Prove the diagnostic detects a planted cross-revision shape change; `dev/registry/tests/`.
- [x] `W03.P08.S68` - Enrol the new diagnostic in the screens register so the invariant gate sees it; `dev/registry/analysis/screens.py`.
- [x] `W03.P08.S69` - Document the new diagnostic in the registry readme the invariant gate also checks; `dev/registry/README.md`.

## Wave `W04` - close the standing gaps

Addresses the rulings that are independent of the refusal mechanism: the authoring default that regrows the hand-authored surface, the staleness detector wired to nothing, the type-check scope that excludes the generator package, the reporting screens with no drain, and the absence of any check that does not originate in the generator. Every Phase here is independent of every other and of Wave W03.

### Phase `W04.P09` - make generation the scaffolded default

Changes the authoring default so a new revision scaffolds the generated path and hand-authoring becomes the declared exception, stating why.

- [x] `W04.P09.S34` - Scaffold the generated export path for a new revision instead of the hand-authored layout; `dev/registry/newmodelo/manager.py`.
- [x] `W04.P09.S35` - Rewrite the authoring checklist so hand-authoring is the declared exception stating why; `dev/registry/newmodelo/checklist.py`.
- [x] `W04.P09.S36` - Add a declaration recording whether a revision's values are derived or transcribed; `src/cadrumo/domain/calculations/registry/`.
- [x] `W04.P09.S37` - Prove a newly scaffolded revision arrives on the generated path; `dev/registry/tests/`.

### Phase `W04.P10` - wire the staleness detector

Puts the existing live-source detector on a schedule with defined acceptance: it reports a republish as a finding, does not block a change-triggered gate, and reports an unreachable network as a limitation rather than as pass or fail.

- [x] `W04.P10.S38` - Invoke the detector's live-check flag from a scheduled workflow; `.github/workflows/`.
- [x] `W04.P10.S39` - Report a detected republish as a finding against the corpus without blocking a change-triggered gate; `dev/corpus/sync_aeat_record_design_corpus.py`.
- [x] `W04.P10.S40` - Report an unreachable network explicitly as a limitation rather than as pass or fail; `dev/corpus/sync_aeat_record_design_corpus.py`.

### Phase `W04.P11` - admit the generator package to the type gate

Burns the generator package's diagnostics to zero and admits it permanently, with no baseline, ratchet or per-tree exemption.

- [x] `W04.P11.S41` - Burn the generator package's type diagnostics to zero without suppressions; `dev/registry/`.
- [x] `W04.P11.S42` - Admit the generator package to the type-check target list; `dev/quality/types.py`.
- [x] `W04.P11.S43` - Update the burn-down comment to remove the admitted entry; `dev/quality/types.py`.

### Phase `W04.P12` - give the findings screens a drain

Promotes or retires each reporting screen that returns findings and carries a non-zero population, leaving census screens untouched.

- [x] `W04.P12.S44` - Enumerated: 15 authority screens report zero, so the drain premise is false for them. The whole unexamined population is in the three corpus screens - note_label_scope 124, unnumbered_note_scope 40, note_text_drift 26 - and 85 of the 124 are labels resolving to more than one distinct text; `dev/registry/analysis/screens.py`.
- [x] `W04.P12.S45` - STALE premise: every enumerated findings screen reports ZERO, so there is nothing to promote or retire. The unexamined population is in the corpus screens, which the enumeration reached only after correcting a signature mis-call, and one of those - the ambiguous note pointers - is now its own enrolled screen; `dev/registry/analysis/screens.py`.
- [x] `W04.P12.S46` - STALE with S45: a promote-or-retire condition governs screens carrying a population, and every enumerated findings screen reports zero; `dev/registry/analysis/screens.py`.
- [x] `W04.P12.S73` - STALE with S45: the readme sentence only misleads where a screen has been promoted to gate, and none has been, because none carried a population to promote; `dev/registry/README.md`.
- [x] `W04.P12.S74` - Accounted for: the one derived screen re-reports the pointer screen's findings, and both report zero today, so no double count arises in the enumerated populations; `dev/registry/analysis/screens.py`.

### Phase `W04.P13` - introduce an independent oracle

Decodes official worked examples through the shipped codec and compares field by field, so at least one check does not originate in the generator.

- [x] `W04.P13.S47` - Extend the existing external-oracle corpus enum rather than creating a second oracle surface; `src/cadrumo/core/external_oracle_corpus.py`.
- [x] `W04.P13.S48` - Extend the existing grounding fold and conformance-vector mechanism to carry the new comparison; `src/cadrumo/domain/calculations/registry/external_grounding.py`.
- [ ] `W04.P13.S70` - BLOCKED on official evidence, and the note-scope axis it sat beside is now closed: the adrift pointer population is 2, both diagnosed benign, after correcting a screen that over-reported by ninety times; `src/cadrumo/_data/corpus/manual_oracles/`.
- [x] `W04.P13.S49` - Satisfied by the shipped worked-example oracles: the corporate-tax and instalment tests compare computed values field by field against AEAT's printed liquidacion tables, with page locators into the bundled official manuals; `src/cadrumo/application/modelo/tests/`.
- [x] `W04.P13.S50` - Confirm no expected value in the oracle originates in the generator; `src/cadrumo/domain/calculations/registry/tests/`.

## Wave `W05` - the consumer lane and the held rulings

Examines how the consuming application behaves when handed a registry that is internally inconsistent, temporally incoherent, or partially adjudicated - the question the decision record explicitly defers and on which two rulings are held. Its answer decides whether an undetermined state is representable end to end, which is the primitive for required-ness and for the absence validators. Runs last because it may amend the accepted record.

### Phase `W05.P14` - examine consumer behaviour

Determines whether the consuming application refuses, degrades or proceeds when the registry is incoherent, and whether a calculation can distinguish an undetermined value from an adjudicated one.

- [x] `W05.P14.S51` - Determine whether the authority refuses, degrades or proceeds when a revision is internally inconsistent; `src/cadrumo/domain/calculations/registry/`.
- [x] `W05.P14.S52` - ANSWERED: no, and structurally rather than for want of a feature. Every adjudication mechanism is generator-side, the source-defect surface appears in the shipped package zero times, so an adjudication is consumed at generation and leaves no trace a calculation could read. This is the case FOR the per-field verdict, not against it; `dev/registry/pipeline/source_defects.py`.
- [x] `W05.P14.S53` - Determine whether filing-grade paths distinguish a silent registry from one that states zero; `src/cadrumo/application/`.
- [x] `W05.P14.S54` - Determine whether a temporally incoherent revision selection is rejected at the authority boundary; `src/cadrumo/domain/calculations/registry/`.
- [x] `W05.P14.S55` - Record the consumer findings as a reference document for the held rulings; `.vault/reference/`.

### Phase `W05.P15` - settle the held rulings

Amends the accepted record with the refusal semantics the consumer lane establishes, then implements the two rulings held on its answer.

- [x] `W05.P15.S56` - Amend the accepted decision record with the refusal semantics the consumer lane establishes; `.vault/adr/`.
- [x] `W05.P15.S57` - Make isolated-target validation answer corpus-scope checks correctly. Landed in 5fef4b20cb: the continuity witness now carries every sibling revision of the target, not only its strict-continuity predecessors, so checks that reason across a modelo's revisions run with the siblings present while _require_isolated_target_context still holds the target alone. The rejected alternatives are recorded: staging siblings as full revisions dismantles the isolation contract; a check-skipping parameter on the production loader is a consumer-side downgrade; declaring intentional_singleton writes a falsehood. Result: modelo 202's three trees pass check mode through the real authority and were republished, with their drift rows and reproduction-pending pins retired (generated-tree, type-column and ledger gates 88 passed exit 0). The qualified-requirement half formerly carried here remains blocked on export-schema closure under S58-S60; `dev/registry/pipeline/candidate_staging.py`.
- [ ] `W05.P15.S58` - UNBLOCKED on publication, BLOCKED on schema closure, and the population is 10 fields not 14,675. Tracing which requirement cells reach export emission - rather than censusing parsed designs - finds 92 cells reaching it corpus-wide, of which 10 state a qualified requirement ('Obligatorio PI' x6 in 303, 'OBLIGATORIO (persona fisica)' x4 in 390) that a boolean cannot carry. The 12 'OBLIGATORIO.' and 9 'En blanco' cells never reach emission and are inert. Carrying the wording needs a new ExportFieldDefinition key, which both the normalization schema version and the canonical-JSON manifest round-trip refuse at authority load; it is a coordinated migration through the bootstrap transport; `src/cadrumo/domain/calculations/registry/`.
- [ ] `W05.P15.S59` - UNBLOCKED on publication, BLOCKED on schema closure, and the population is 10 fields not 14,675. Tracing which requirement cells reach export emission - rather than censusing parsed designs - finds 92 cells reaching it corpus-wide, of which 10 state a qualified requirement ('Obligatorio PI' x6 in 303, 'OBLIGATORIO (persona fisica)' x4 in 390) that a boolean cannot carry. The 12 'OBLIGATORIO.' and 9 'En blanco' cells never reach emission and are inert. Carrying the wording needs a new ExportFieldDefinition key, which both the normalization schema version and the canonical-JSON manifest round-trip refuse at authority load; it is a coordinated migration through the bootstrap transport; `src/cadrumo/domain/calculations/registry/`.
- [ ] `W05.P15.S60` - UNBLOCKED on publication, BLOCKED on schema closure, and the population is 10 fields not 14,675. Tracing which requirement cells reach export emission - rather than censusing parsed designs - finds 92 cells reaching it corpus-wide, of which 10 state a qualified requirement ('Obligatorio PI' x6 in 303, 'OBLIGATORIO (persona fisica)' x4 in 390) that a boolean cannot carry. The 12 'OBLIGATORIO.' and 9 'En blanco' cells never reach emission and are inert. Carrying the wording needs a new ExportFieldDefinition key, which both the normalization schema version and the canonical-JSON manifest round-trip refuse at authority load; it is a coordinated migration through the bootstrap transport; `src/cadrumo/domain/calculations/registry/`.
- [x] `W05.P15.S75` - Extend the type-column comparison to the 62 hand-authored revisions it could not see, and correct what it finds. Landed in df4ffab003: dev/registry/analysis/hand_authored_type_column.py joins each shipped record to the one sheet of its revision's own pinned design that carries all of its (offset, length) slots, within one revision only; 250 of 290 records align, reproducing the hand-verified modelo 490 count of 72. 1,484 money fields typed N now carry the sign (one line each; non-negative amounts keep identical bytes). The gate dev/registry/tests/test_hand_authored_layouts_agree_with_type_column.py declares the remainder per revision and checks each declaration in both directions: 60 modelo 714 integer fields the schema cannot sign, and 44 records plus two design-less revisions that cannot be aligned, reported as UNCHECKED rather than passed. Planted tests prove both detections. Open follow-ups: the 60 integer fields need a schema that signs integer amounts; the 44 unaligned records need a sheet assignment; five fields are over-declared signed where the design is not N; `dev/registry/tests/`.
- [x] `W05.P15.S76` - Bind every modelo 200 field to the casilla printed on its own sheet, and gate the class. Landed in e2e7b7232e: the 33 wrong-sheet bindings whose own-sheet casilla exists are rebound (target section matches the field's design text in all 33; each entry's legal_refs already a subset of the target's, so only casilla_id changes), own-sheet bindings go from 41 to 74, and the back-reference writer now replaces a declaration naming only the layout's own fields while still refusing one naming any other. The gate dev/registry/tests/test_casilla_bindings_name_their_own_sheet.py fails any field bound to another sheet while its own-sheet casilla exists, and declares the remaining 63 per revision as unrebindable because their own-sheet casilla was never declared; authoring those casillas is unowned corpus work, and the gate fails once any of them exists so the rebinding is not forgotten; `dev/registry/tests/`.
- [ ] `W05.P15.S77` - Open the export schema by a one-shot versioned migration, awaiting operator approval. Measured constraints: export_fragment_provenance_manifest_json_bytes dumps with model_dump(mode=json) and no exclude_none, so ANY new optional key serialises as null and every shipped manifest stops round-tripping; and republishing cannot migrate all 32 trees, because nine are drift-pinned and their check mode refuses publication for documented reasons. So: bump EXPORT_RENDER_NORMALIZATION_SCHEMA_VERSION, add the new keys, and convert every stored manifest by a format-only migration command that loads the old version and re-serialises it unchanged apart from the defaulted keys, proven by the reproduction, type-column and ledger gates before and after. The legacy reader lives only in the migration command's single run and is never committed, per no-legacy-compatibility; `dev/registry/pipeline/export_fragment_provenance.py`.
- [ ] `W05.P15.S78` - After the schema opens, land its blocked uses, each gated: requirement_statement carrying a qualified requirement wording (10 fields: 'Obligatorio PI' x6 in 303, 'OBLIGATORIO (persona fisica)' x4 in 390); a signed integer amount in schema and codec (modelo 714's 60 fields); a mandated value domain on a signed field (390/2025's 80 'rellenas a 0' amounts); a part identity for a design cell whose own text declares sub-offsets (modelo 347's provincia/pais cell, letting both 347 trees republish and correcting the 2011 blank-region NIF binding); and a SIGN-POSITION CONVENTION, a live filing-byte defect found by reading the designs: modelos 165 and 189 subdivide an amount into a leading alphabetic SIGNO position that carries 'N' when negative and 'En cualquier otro caso ... un espacio', and modelo 280's is 'siempre una N', but the codec's only signed form zero-fills the sign position for a non-negative amount, so every positive amount in modelo-165-t1-importe-fondos-propios (2016-2022, 2026-y-siguientes), modelo-189-t1-valoracion-total, modelo-189-t2-valoracion and modelo-280-t2-rendimientos-negativos-imputables writes '0' where the design requires a space or an 'N'. The dev render-profile policy name 'n-prefix-negative-blank-nonnegative' also misdescribes the zero-filling it maps to; `src/cadrumo/domain/calculations/registry/schema_exports.py`.

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
