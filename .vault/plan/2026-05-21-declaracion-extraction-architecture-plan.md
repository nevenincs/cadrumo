---
tags:
  - '#plan'
  - '#declaracion-extraction-architecture'
date: '2026-05-21'
tier: L3
related:
  - '[[2026-05-21-declaracion-extraction-architecture-adr]]'
  - '[[2026-05-21-declaracion-extraction-architecture-research]]'
  - '[[2026-05-20-branch-reconciliation-audit]]'
---

<!-- LINK RULES:
     - [[wiki-links]] are ONLY for .vault/ documents in the
       related: field above.
     - The related: field carries the AUTHORISING documents
       (ADR, research, reference, prior plan) for every Step in
       this plan. Steps inherit this chain; per-row reference
       footers do not exist.
     - NEVER use [[wiki-links]] or markdown links in the
       document body. -->

# `declaracion-extraction-architecture` umbrella plan

## Wave `W01` - discovery sweep

Discovery Wave. Haiku and sonnet sub-agents sweep the large, nebulous-edged codebase to produce a migration inventory: every consumer of declaracion extraction and any residue of the deleted DeclaracionExtractor surface, the state of every registry declaracion_pdf extraction profile, registry schemas needing tweaks for the named-field primitive, and the per-modelo AEAT Diseno corpus available to source profiles from. This Wave hard-precedes W02, W03, W04, and W05 because its inventory scopes them; its findings are EXPECTED to surface additional migration and schema-tweak Steps appended to later Waves via the vault plan CLI. Authorised by the declaracion-extraction-architecture ADR, its research, and the branch-reconciliation audit.

### Phase `W01.P01` - consumer and registry-profile inventory sweep

Sub-agent discovery Steps producing the migration inventory that scopes every later Wave.

- [x] `W01.P01.S01` - Sweep every consumer of declaracion extraction and any residue of the deleted DeclaracionExtractor surface and record callers, exports, and dead references; `src/aeat/adapters/inbound/declaracion/`.
- [x] `W01.P01.S02` - Inventory every registry declaracion_pdf extraction profile and classify its state as functional numeric, absent, or dead decl.* slug stub; `src/aeat/_data/registry/aeat/modelos/`.
- [x] `W01.P01.S03` - Identify registry schema fields and constraints needing tweaks for the named-field primitive; `src/aeat/domain/calculations/registry/_schema.py`.
- [x] `W01.P01.S04` - Catalogue the per-modelo AEAT Diseno and instructions corpus available for modelos 303, 180, 190 and the named-field modelos; `src/aeat/_data/registry/aeat/modelos/`.
- [x] `W01.P01.S05` - Consolidate the four discovery sweeps into a migration inventory and append the surfaced migration and schema-tweak Steps to W02 through W05 via the vault plan CLI; `.vault/plan/2026-05-21-declaracion-extraction-architecture-plan.md`.

## Wave `W02` - named-field primitive

Umbrella-infrastructure Wave. Extends ExtractionProfileDefinition with the typed named-field primitive (match_strategy and value_kind Literal enums plus an optional label pattern), branches the parser matching core on match_strategy, and adds the snapshot-build validator rule that a declaracion_pdf profile targeting a text-typed casilla must use named_label. The primitive is purely additive: numeric-casilla profiles already working stay unchanged. This Wave depends on W01 and hard-precedes W04, whose named-field profile content cannot be authored until the primitive exists. Authorised by the declaracion-extraction-architecture ADR and its research.

### Phase `W02.P02` - schema extension

Extend ExtractionProfileDefinition with the typed named-field primitive fields.

- [x] `W02.P02.S06` - Run a git diff collision check on the contended registry schema file before editing in the shared worktree; `src/aeat/domain/calculations/registry/_schema.py`.
- [x] `W02.P02.S07` - Add the typed match_strategy Literal numeric_casilla or named_label field to ExtractionProfileDefinition holding the strict frozen extra-forbid discipline; `src/aeat/domain/calculations/registry/_schema.py`.
- [x] `W02.P02.S08` - Add the typed value_kind Literal amount text or enum field to the extraction-profile target descriptor; `src/aeat/domain/calculations/registry/_schema.py`.
- [x] `W02.P02.S42` - Add the new strict frozen extra-forbid ExtractionTargetDefinition RegistryModel record carrying per-target casilla_id match_strategy and value_kind; `src/aeat/domain/calculations/registry/_schema.py`.
- [x] `W02.P02.S43` - Restructure ExtractionProfileDefinition target_casillas from a flat tuple of CasillaId to a tuple of ExtractionTargetDefinition records; `src/aeat/domain/calculations/registry/_schema.py`.
- [x] `W02.P02.S44` - Update the target_casillas uniqueness field_validator to deduplicate on the per-target casilla_id of the ExtractionTargetDefinition records; `src/aeat/domain/calculations/registry/_schema.py`.
- [x] `W02.P02.S09` - Add the optional named_label pattern field to the extraction-profile target descriptor; `src/aeat/domain/calculations/registry/_schema.py`.
- [x] `W02.P02.S10` - Add strict roundtrip and anti-tautology tests for the extended ExtractionProfileDefinition named-field fields; `src/aeat/domain/calculations/registry/test_registry_schema.py`.

### Phase `W02.P03` - parser match-strategy branch

Branch the parser matching core on match_strategy without changing the numeric path.

- [x] `W02.P03.S11` - Run a git diff collision check on the contended parser file before editing in the shared worktree; `src/aeat/adapters/inbound/declaracion/_parser.py`.
- [x] `W02.P03.S12` - Branch _find_casilla_hits on match_strategy leaving the numeric_casilla path byte-for-byte unchanged; `src/aeat/adapters/inbound/declaracion/_parser.py`.
- [x] `W02.P03.S13` - Implement the named_label matching path anchoring on the printed label and capturing via the existing TEXT_VALUE_GROUP; `src/aeat/adapters/inbound/declaracion/_parser.py`.
- [x] `W02.P03.S46` - Update _extract_profile_values and _find_casilla_hits to read per-target match_strategy and value_kind from the ExtractionTargetDefinition records; `src/aeat/adapters/inbound/declaracion/_parser.py`.
- [x] `W02.P03.S45` - Decide and apply the ExtractedCasilla printed_value text-storage path so a named_label capture stores its text value alongside the typed Decimal numeric path; `src/aeat/adapters/inbound/declaracion/_parser.py`.
- [x] `W02.P03.S14` - Add parser-boundary tests proving the numeric path is unchanged and the named_label path captures text values; `src/aeat/adapters/inbound/declaracion/test_parser_boundary.py`.

### Phase `W02.P04` - validator text-casilla gate

Add the snapshot-build validator rule rejecting text-typed casilla targets without named_label.

- [x] `W02.P04.S15` - Run a git diff collision check on the contended registry referential validator before editing in the shared worktree; `src/aeat/domain/calculations/registry/_validate_references.py`.
- [x] `W02.P04.S16` - Add the snapshot-build validator rule that a declaracion_pdf profile targeting a data_type text casilla must use named_label; `src/aeat/domain/calculations/registry/_validate_references.py`.
- [x] `W02.P04.S48` - Update the second extraction-profile referential validator site to resolve per-target casilla_id from the ExtractionTargetDefinition records; `src/aeat/domain/calculations/registry/_validate_references.py`.
- [x] `W02.P04.S47` - Change the _validate_extraction_profile_section signature to receive casilla_by_id and validate each ExtractionTargetDefinition value_kind against the target casilla data_type; `src/aeat/domain/calculations/registry/_validate.py`.
- [x] `W02.P04.S17` - Add a regression test proving the validator gate fails loud on a text-casilla decl.* slug stub; `src/aeat/domain/calculations/registry/test_referential_integrity.py`.

### Phase `W02.P12` - target_casillas TOML stanza migration

Migrate every registry declaracion_pdf target_casillas TOML stanza from the flat casilla-id list to the tuple-of-records form the ExtractionTargetDefinition primitive requires, one Step per registry file.

- [x] `W02.P12.S49` - Migrate the Modelo 131 2019-2023 revision target_casillas stanza to the ExtractionTargetDefinition tuple-of-records form; `src/aeat/_data/registry/aeat/modelos/131/revisions/2019-2023.toml`.
- [x] `W02.P12.S50` - Migrate the Modelo 131 2024 revision target_casillas stanza to the ExtractionTargetDefinition tuple-of-records form; `src/aeat/_data/registry/aeat/modelos/131/revisions/2024.toml`.
- [x] `W02.P12.S51` - Migrate the Modelo 131 2025 revision target_casillas stanza to the ExtractionTargetDefinition tuple-of-records form; `src/aeat/_data/registry/aeat/modelos/131/revisions/2025.toml`.
- [x] `W02.P12.S52` - Migrate the Modelo 131 2026 revision target_casillas stanza to the ExtractionTargetDefinition tuple-of-records form; `src/aeat/_data/registry/aeat/modelos/131/revisions/2026.toml`.
- [x] `W02.P12.S53` - Migrate the Modelo 720 target_casillas stanza to the ExtractionTargetDefinition tuple-of-records form; `src/aeat/_data/registry/aeat/modelos/720.toml`.
- [x] `W02.P12.S54` - Migrate the Modelo 840 target_casillas stanza to the ExtractionTargetDefinition tuple-of-records form; `src/aeat/_data/registry/aeat/modelos/840.toml`.
- [x] `W02.P12.S55` - Migrate the Modelo 347 target_casillas stanza to the ExtractionTargetDefinition tuple-of-records form; `src/aeat/_data/registry/aeat/modelos/347.toml`.
- [x] `W02.P12.S56` - Migrate the Modelo 184 target_casillas stanza to the ExtractionTargetDefinition tuple-of-records form; `src/aeat/_data/registry/aeat/modelos/184.toml`.
- [x] `W02.P12.S57` - Migrate the Modelo 190 target_casillas stanza to the ExtractionTargetDefinition tuple-of-records form; `src/aeat/_data/registry/aeat/modelos/190.toml`.
- [x] `W02.P12.S58` - Migrate the Modelo 193 target_casillas stanza to the ExtractionTargetDefinition tuple-of-records form; `src/aeat/_data/registry/aeat/modelos/193.toml`.
- [x] `W02.P12.S59` - Migrate the Modelo 115 target_casillas stanza to the ExtractionTargetDefinition tuple-of-records form; `src/aeat/_data/registry/aeat/modelos/115.toml`.
- [x] `W02.P12.S60` - Migrate the Modelo 130 target_casillas stanza to the ExtractionTargetDefinition tuple-of-records form; `src/aeat/_data/registry/aeat/modelos/130.toml`.
- [x] `W02.P12.S61` - Migrate the Modelo 349 2020-y-siguientes extraction-profiles target_casillas stanza to the ExtractionTargetDefinition tuple-of-records form; `src/aeat/_data/registry/aeat/modelos/349/revisions/2020-y-siguientes/extraction_profiles/0005-extraction_profiles.toml`.
- [x] `W02.P12.S62` - Migrate the Modelo 111 2019-y-siguientes extraction-profiles target_casillas stanza to the ExtractionTargetDefinition tuple-of-records form; `src/aeat/_data/registry/aeat/modelos/111/revisions/2019-y-siguientes/extraction_profiles/0005-extraction_profiles.toml`.
- [x] `W02.P12.S63` - Migrate the Modelo 123 2019-2023 revision target_casillas stanza to the ExtractionTargetDefinition tuple-of-records form; `src/aeat/_data/registry/aeat/modelos/123/revisions/2019-2023/revision.toml`.
- [x] `W02.P12.S64` - Migrate the Modelo 123 2024-y-siguientes revision target_casillas stanza to the ExtractionTargetDefinition tuple-of-records form; `src/aeat/_data/registry/aeat/modelos/123/revisions/2024-y-siguientes/revision.toml`.
- [x] `W02.P12.S65` - Migrate the Modelo 180 2023-y-siguientes export-record target_casillas stanza to the ExtractionTargetDefinition tuple-of-records form; `src/aeat/_data/registry/aeat/modelos/180/revisions/2023-y-siguientes/extraction_profiles/0001-modelo-180-export-record.toml`.
- [x] `W02.P12.S66` - Migrate the Modelo 180 2019-2022 export-record target_casillas stanza to the ExtractionTargetDefinition tuple-of-records form; `src/aeat/_data/registry/aeat/modelos/180/revisions/2019-2022/extraction_profiles/0001-modelo-180-export-record.toml`.
- [x] `W02.P12.S67` - Migrate the Modelo 232 2016-2017 declaracion-pdf target_casillas stanza to the ExtractionTargetDefinition tuple-of-records form; `src/aeat/_data/registry/aeat/modelos/232/revisions/2016-2017/extraction_profiles/0001-modelo-232-2016-declaracion-pdf.toml`.
- [x] `W02.P12.S68` - Migrate the Modelo 232 2018-y-siguientes declaracion-pdf target_casillas stanza to the ExtractionTargetDefinition tuple-of-records form; `src/aeat/_data/registry/aeat/modelos/232/revisions/2018-y-siguientes/extraction_profiles/0001-modelo-232-2018-declaracion-pdf.toml`.

### Phase `W02.P13` - target_casillas test-reader migration

Update every test that reads ExtractionProfileDefinition target_casillas as a bare casilla-id string to read the per-target casilla_id from the ExtractionTargetDefinition records, one Step per test file.

- [x] `W02.P13.S69` - Update the sede declarations test to read per-target casilla_id from the ExtractionTargetDefinition records; `src/aeat/adapters/outbound/aeat/sede/test_declarations.py`.
- [x] `W02.P13.S70` - Update the registry-schema test to read per-target casilla_id from the ExtractionTargetDefinition records; `src/aeat/domain/calculations/registry/test_registry_schema.py`.
- [x] `W02.P13.S71` - Update the Modelo 349 registry test to read per-target casilla_id from the ExtractionTargetDefinition records; `src/aeat/domain/calculations/registry/test_modelo_349_registry.py`.
- [x] `W02.P13.S72` - Update the record-design test to read per-target casilla_id from the ExtractionTargetDefinition records; `src/aeat/domain/calculations/registry/test_record_design.py`.
- [x] `W02.P13.S73` - Update the Modelo 720 registry test to read per-target casilla_id from the ExtractionTargetDefinition records; `src/aeat/domain/calculations/registry/test_modelo_720_registry.py`.
- [x] `W02.P13.S74` - Update the Modelo 232 registry test to read per-target casilla_id from the ExtractionTargetDefinition records; `src/aeat/domain/calculations/registry/test_modelo_232_registry.py`.
- [x] `W02.P13.S75` - Update the referential-integrity test to read per-target casilla_id from the ExtractionTargetDefinition records; `src/aeat/domain/calculations/registry/test_referential_integrity.py`.
- [x] `W02.P13.S76` - Update the renta first-slice routing test to read per-target casilla_id from the ExtractionTargetDefinition records; `src/aeat/domain/renta/test_first_slice_routing.py`.
- [x] `W02.P13.S77` - Update the parser-boundary test to read per-target casilla_id from the ExtractionTargetDefinition records; `src/aeat/adapters/inbound/declaracion/test_parser_boundary.py`.
- [x] `W02.P13.S78` - Update the renta cuota chain contract test to read per-target casilla_id from the ExtractionTargetDefinition records; `src/aeat/domain/calculations/registry/test_renta_cuota_chain_contract.py`.
- [x] `W02.P13.S79` - Update the Modelo 100 borrador summary test to read per-target casilla_id from the ExtractionTargetDefinition records; `src/aeat/adapters/inbound/borrador/test_modelo_100_summary.py`.

## Wave `W03` - numeric-casilla tier

Numeric-casilla tier Wave. Authors declaracion_pdf extraction profiles for modelos 303 and 180 from the AEAT Diseno and instructions, replaces modelo 190's abstract decl.* stub targets with the real numeric and labelled targets the form prints, and restores the modelo 130 03 = 01 - 02 cross-check as a verification_expectations stanza. Depends on W01; independent of W02 and W04. Authorised by the declaracion-extraction-architecture ADR, its research, and branch-reconciliation audit row 6.

### Phase `W03.P05` - scoped numeric-tier discovery

Scoped discovery sweep of the AEAT Diseno corpus and casilla data for the numeric-tier modelos.

- [x] `W03.P05.S18` - Sweep the AEAT Diseno and instructions corpus and casilla registry data for modelos 303, 180, and 190 and append any surfaced schema-tweak Steps via the vault plan CLI; `src/aeat/_data/registry/aeat/modelos/`.

### Phase `W03.P06` - modelo 303 and 180 profile authoring

Author declaracion_pdf extraction profiles for modelos 303 and 180.

- [x] `W03.P06.S19` - Author the declaracion_pdf extraction profile for Modelo 303 from the AEAT Diseno and instructions; `src/aeat/_data/registry/aeat/modelos/303/`.
- [ ] `W03.P06.S20` - Keep Modelo 180 declaracion_pdf profile authoring blocked until W05.P11.S92 supplies authorised PDF/layout evidence; `src/aeat/_data/registry/aeat/modelos/180/`.

### Phase `W03.P07` - modelo 190 stub repair and modelo 130 cross-check

Replace modelo 190's decl.* stub targets and restore the modelo 130 cross-check stanza.

- [x] `W03.P07.S21` - Replace Modelo 190's abstract decl.* stub target_casillas with the real numeric and labelled targets the form prints; `src/aeat/_data/registry/aeat/modelos/190/`.
- [x] `W03.P07.S22` - Restore the Modelo 130 03 = 01 - 02 intra-filing cross-check as a verification_expectations stanza; `src/aeat/_data/registry/aeat/modelos/130/`.
- [x] `W03.P07.S23` - Verify modelos 130, 111, 115, and 123 still parse and validate unchanged after the numeric-tier changes; `src/aeat/adapters/inbound/declaracion/test_parser_boundary.py`.

## Wave `W04` - named-field tier

Named-field tier Wave. Corrects or removes the dead modelo 720 and 840 stub profiles, registers modelo 037 which has no registry presence today, and authors named-field declaracion_pdf profiles for modelos 036, 037, 369, 720, and 840 on the W02 primitive. Deferred content of the ADR, in-scope as part of this umbrella plan. Hard-depends on W02; depends on W01. Authorised by the declaracion-extraction-architecture ADR and its research.

### Phase `W04.P08` - scoped named-field discovery

Scoped discovery sweep of the named-field modelo corpus and registry presence.

- [x] `W04.P08.S24` - Sweep the named-field modelo corpus and registry presence for modelos 036, 037, 369, 720, and 840 and append any surfaced schema-tweak Steps via the vault plan CLI; `src/aeat/_data/registry/aeat/modelos/`.
- [x] `W04.P08.S80` - Classify per dead-stub modelo 184 193 232 347 349 720 and 840 whether each non-matchable decl slug target resolves to a numeric casilla or a named-field target; `src/aeat/_data/registry/aeat/modelos/`.
- [x] `W04.P08.S86` - Decide fetch-versus-defer for the source-blocked Modelo 037 which has no Diseno instructions or fixtures in the corpus and record the fetch-or-descope decision; `src/aeat/_data/registry/aeat/modelos/037/`.
- [x] `W04.P08.S91` - Record that W02 code-review fix removed the dead declaracion_pdf profiles for Modelo 347 (revision 2008-y-siguientes) and Modelo 840 (revision 2003-y-siguientes) because both carried decl.tipo-declaracion (data_type=text) with match_strategy=numeric_casilla; `W04 P09 and P10 must author real named-field profiles for these two modelos; `src/aeat/_data/registry/aeat/modelos/347.toml src/aeat/_data/registry/aeat/modelos/840.toml`.

### Phase `W04.P09` - dead-stub repair and modelo 037 registration

Correct or remove the dead 720/840 stubs and register modelo 037.

- [x] `W04.P09.S25` - Correct or remove the dead Modelo 720 declaracion_pdf stub profile so it no longer loads green; `src/aeat/_data/registry/aeat/modelos/720/`.
- [x] `W04.P09.S26` - Correct or remove the dead Modelo 840 declaracion_pdf stub profile so it no longer loads green; `src/aeat/_data/registry/aeat/modelos/840/`.
- [x] `W04.P09.S27` - Descope current Modelo 037 registry registration after W04.P08.S86 legal suppression decision; `src/aeat/_data/registry/aeat/modelos/037/`.

### Phase `W04.P14` - newly-surfaced dead-stub repair

Repair the five dead-stub declaracion_pdf profiles W01 discovery surfaced beyond the ADR-named set: modelos 184 193 232 347 and 349 each load green today but extract nothing; replace each non-matchable decl slug stub with the real numeric or named-field targets its classification determined.

- [x] `W04.P14.S81` - Replace the Modelo 184 dead decl slug stub targets with the real numeric or named-field targets its classification determined; `src/aeat/_data/registry/aeat/modelos/184.toml`.
- [x] `W04.P14.S82` - Replace the Modelo 193 dead decl slug stub targets with the real numeric or named-field targets its classification determined; `src/aeat/_data/registry/aeat/modelos/193.toml`.
- [x] `W04.P14.S83` - Replace the Modelo 232 dead decl slug stub targets with the real numeric or named-field targets its classification determined; `src/aeat/_data/registry/aeat/modelos/232/`.
- [x] `W04.P14.S84` - Replace the Modelo 347 dead decl slug stub targets with the real numeric or named-field targets its classification determined; `src/aeat/_data/registry/aeat/modelos/347.toml`.
- [x] `W04.P14.S85` - Replace the Modelo 349 dead decl slug stub targets with the real numeric or named-field targets its classification determined; `src/aeat/_data/registry/aeat/modelos/349/`.

### Phase `W04.P10` - named-field profile authoring

Author named-field declaracion_pdf profiles for modelos 036, 037, 369, 720, and 840.

- [x] `W04.P10.S28` - Author the named-field declaracion_pdf profile for Modelo 036 using the W02 named_label primitive; `src/aeat/_data/registry/aeat/modelos/036/`.
- [x] `W04.P10.S29` - Descope current Modelo 037 named-field declaracion_pdf profile after W04.P08.S86 legal suppression decision; `src/aeat/_data/registry/aeat/modelos/037/`.
- [x] `W04.P10.S30` - Author the named-field declaracion_pdf profile for Modelo 369 using the W02 named_label primitive; `src/aeat/_data/registry/aeat/modelos/369/`.
- [x] `W04.P10.S31` - Author the named-field declaracion_pdf profile for Modelo 720 using the W02 named_label primitive; `src/aeat/_data/registry/aeat/modelos/720/`.
- [x] `W04.P10.S32` - Author the named-field declaracion_pdf profile for Modelo 840 using the W02 named_label primitive; `src/aeat/_data/registry/aeat/modelos/840/`.

## Wave `W05` - verification and rollout

Verification Wave. Adds real per-modelo round-trip parse tests against PDF corpus fixtures, confirms the snapshot-build gate is green, and confirms all 26 modelos validate. Depends on every preceding Wave. Authorised by the declaracion-extraction-architecture ADR and its research.

### Phase `W05.P11` - round-trip parse tests and gate verification

Add per-modelo round-trip parse tests and confirm the snapshot-build gate is green.

- [x] `W05.P11.S33` - Add a real round-trip parse test for Modelo 303 against a PDF corpus fixture; `src/aeat/adapters/inbound/declaracion/test_parser_boundary.py`.
- [ ] `W05.P11.S34` - Keep the Modelo 180 real round-trip parse test blocked by W05.P11.S92 fixture acquisition; `src/aeat/adapters/inbound/declaracion/test_parser_boundary.py`.
- [ ] `W05.P11.S92` - Acquire or generate from an authorised source a real Modelo 180 declaration PDF fixture before authoring the Modelo 180 declaracion_pdf profile or round-trip test; `src/aeat/tests/fixtures/justificantes/180/`.
- [x] `W05.P11.S35` - Add the Modelo 190 real round-trip parse test against the existing sanitized 2024 declaration fixture after W05.P11.S93 supplied a legally grounded 2024 registry revision; `src/aeat/adapters/inbound/declaracion/test_parser_boundary.py`.
- [x] `W05.P11.S93` - Resolve the Modelo 190 fixture/revision mismatch by sourcing the 2024 registry slice from Orden HAC/1432/2024, AEAT DR 190-2024, and the existing sanitized 2024 fixture; `src/aeat/tests/fixtures/justificantes/190/ src/aeat/_data/registry/aeat/modelos/190.toml`.
- [ ] `W05.P11.S36` - Keep the Modelo 036 real round-trip parse test blocked by W05.P11.S94 fixture acquisition; `src/aeat/adapters/inbound/declaracion/test_parser_boundary.py`.
- [ ] `W05.P11.S94` - Acquire a real Modelo 036 printed-form PDF fixture to verify the provisional named_label patterns before implementing S36; `src/aeat/tests/fixtures/justificantes/036/`.
- [x] `W05.P11.S37` - Descope current Modelo 037 real round-trip parse test after W04.P08.S86 legal suppression decision; `src/aeat/adapters/inbound/declaracion/test_parser_boundary.py`.
- [x] `W05.P11.S95` - Convert Modelo 037 source and fixture acquisition into historical-slice backlog only; `src/aeat/_data/registry/aeat/modelos/037/ src/aeat/tests/fixtures/justificantes/037/`.
- [ ] `W05.P11.S38` - Keep the Modelo 369 real round-trip parse test blocked by W05.P11.S96 fixture acquisition; `src/aeat/adapters/inbound/declaracion/test_parser_boundary.py`.
- [ ] `W05.P11.S96` - Acquire a real Modelo 369 printed-form PDF fixture to verify the provisional Esquema Union named_label patterns before implementing S38; `src/aeat/tests/fixtures/justificantes/369/`.
- [ ] `W05.P11.S39` - Keep the Modelo 720 real round-trip parse test blocked by W05.P11.S97 fixture acquisition; `src/aeat/adapters/inbound/declaracion/test_parser_boundary.py`.
- [ ] `W05.P11.S97` - Acquire a real Modelo 720 printed-form PDF fixture before implementing S39; `src/aeat/tests/fixtures/justificantes/720/`.
- [ ] `W05.P11.S40` - Keep the Modelo 840 real round-trip parse test blocked by W05.P11.S98 fixture acquisition; `src/aeat/adapters/inbound/declaracion/test_parser_boundary.py`.
- [ ] `W05.P11.S98` - Acquire a real Modelo 840 printed-form PDF fixture to verify the provisional named_label patterns before implementing S40; `src/aeat/tests/fixtures/justificantes/840/`.
- [x] `W05.P11.S41` - Confirm the snapshot-build gate is green and all 26 modelos validate; `src/aeat/domain/calculations/registry/test_committed_registry.py`.

### Phase `W05.P16` - backlog queue for newly identified declaration surfaces

Keep every newly identified declaration-extraction surface explicit until it is either legally descoped, source-acquired, or implemented with a real round-trip test.

- [x] `W05.P16.S99` - Decide whether to open a historical pre-2025 Modelo 037 registry/profile slice after BOE-A-2025-410 suppression; `.vault/adr .vault/plan src/aeat/_data/registry/aeat/modelos/037/`.
- [x] `W05.P16.S100` - Decide whether Modelo 303 printed boxes 46, 69, 87, and 110 should become registered casillas before any extraction profile expands beyond the currently registered result casillas; `src/aeat/_data/registry/aeat/modelos/303/`.
- [ ] `W05.P16.S101` - Acquire legally authorised declaration PDF fixtures or official printed-form layouts for the blocked current slices 180, 036, 369, 720, and 840 (M190 resolved via session 2026-05-26 corpus + grounded profile); `src/aeat/tests/fixtures/justificantes/`.
- [x] `W05.P16.S102` - Re-run declaration parser boundary tests and committed-registry validation after each fixture-backed profile/test expansion; `src/aeat/adapters/inbound/declaracion/test_parser_boundary.py src/aeat/domain/calculations/registry/test_committed_registry.py`.

### Phase `W05.P17` - progress ledger and remaining-work queue

Maintain a single current-state ledger for every completed, descoped, deferred, blocked, or not-yet-tackled declaration-extraction surface discovered during the rollout.

- [x] `W05.P17.S103` - Keep the declaration-extraction progress ledger synchronized with every future profile, fixture, parser, source, or descope decision; `.vault/plan/2026-05-21-declaracion-extraction-architecture-plan.md`.

### Phase `W05.P18` - fixture acquisition classification

Classify the broad `W05.P16.S101` acquisition row into legally grounded per-modelo work items. Record-design layouts and BOE form specifications can ground registry/export surfaces, but they do not by themselves validate declaration-PDF parser labels unless the profile explicitly targets that source surface.

Status note 2026-05-26: `.vault/audit/2026-05-26-declaracion-extraction-auth-gated-acquisition-status.md` records that public AEAT pages found for the remaining acquisition rows describe electronic form, preview, or filed-declaration flows, not taxpayer-free static declaration PDFs. Rows `W05.P18.S105` through `W05.P18.S110` remain open until operator-provided authorised fixtures, taxpayer-free static printed-form layouts, or authenticated read-only filed declarations are available. Synthetic data must not be sent to Sede or AEAT-hosted form surfaces, even for preview/download flows. A later operator-approved read-only Sede listing found one Modelo 190 exercise-2024 filed row for the authenticated profile, but single-row capture failed before artifact download because the local Modelo 190 registry had no 2024 snapshot at that time. Follow-up `W05.P18.S121` closed Modelo 190 through legally grounded 2024 registry authority plus the existing sanitized fixture. The authenticated read returned zero rows for modelos 180, 036, 369, 720, and 840 across 2024-2026; `W05.P18.S122` records a per-modelo evidence matrix and keeps their rows open. Operator context added 2026-05-26: the active profile is not expected to include filed data for the remaining special/current forms, so future auth reads are opportunistic only; the primary unblocker is authorised fixtures or official taxpayer-free static layouts.

- [x] `W05.P18.S104` - Classify the blocked current slices by required acquisition type and verified local authority; `.vault/plan/2026-05-21-declaracion-extraction-architecture-plan.md`.
- [ ] `W05.P18.S105` - Acquire an authorised Modelo 180 declaration PDF or official printed-form layout before authoring a declaration-PDF extraction profile; `src/aeat/_data/registry/aeat/modelos/180/ src/aeat/tests/fixtures/justificantes/180/`.
- [x] `W05.P18.S106` - Legally source and implement the 2024 Modelo 190 registry revision before using the existing 2024 fixture; `src/aeat/_data/registry/aeat/modelos/190.toml src/aeat/tests/fixtures/justificantes/190/`.
- [ ] `W05.P18.S107` - Acquire an authorised Modelo 036 printed-form PDF/declaration fixture before promoting provisional `named_label` patterns; `src/aeat/_data/registry/aeat/modelos/036.toml src/aeat/tests/fixtures/justificantes/036/`.
- [ ] `W05.P18.S108` - Acquire an authorised Modelo 369 Esquema Union printed-form PDF/declaration fixture before promoting provisional `named_label` patterns; `src/aeat/_data/registry/aeat/modelos/369/ src/aeat/tests/fixtures/justificantes/369/`.
- [ ] `W05.P18.S109` - Acquire an authorised Modelo 720 declaration PDF fixture before asserting profile round-trip coverage; `src/aeat/_data/registry/aeat/modelos/720.toml src/aeat/tests/fixtures/justificantes/720/`.
- [ ] `W05.P18.S110` - Complete Modelo 840 value-bearing parser round-trip coverage after obtaining a generated/submitted declaration PDF or an approved filled-form fixture; `src/aeat/tests/fixtures/justificantes/840/ src/aeat/adapters/inbound/declaracion/test_parser_boundary.py`.
- [x] `W05.P18.S111` - Import the verified AEAT Modelo 840 static printed-form PDF into the official corpus/source registry and re-ground declaration-PDF label patterns against printed labels (`14 Ejercicio`, `15 Declaración de`); `src/aeat/_data/registry/aeat/modelos/840.toml src/aeat/_data/registry/aeat/legal/iae.toml`.
- [x] `W05.P18.S121` - Register reviewed 2024 legal/source authority for Modelo 190 from Orden HAC/1432/2024 and AEAT `DISENOS_LOGICOS_190-2024.pdf`, then implement the 2024 registry revision and sanitized-fixture round-trip parser verification; `src/aeat/_data/registry/aeat/legal/irpf.toml src/aeat/_data/registry/aeat/modelos/190.toml src/aeat/tests/fixtures/justificantes/190/`.
- [x] `W05.P18.S122` - Record the post-authenticated-read acquisition matrix for modelos 180, 036, 369, 720, and 840, including local official-source coverage, fixture gaps, live-read result, and remaining legal gates; `.vault/audit/2026-05-26-declaracion-extraction-auth-gated-acquisition-status.md`.
- [x] `W05.P18.S123` - Convert the acquisition policy from "operator-approved synthetic preview/download possible" to "no synthetic data to Sede or AEAT-hosted form surfaces"; `.vault/plan/2026-05-21-declaracion-extraction-architecture-plan.md .vault/audit/2026-05-26-declaracion-extraction-auth-gated-acquisition-status.md`.
- [x] `W05.P18.S124` - Open and execute the follow-up no-synthetic-Sede ADR/plan slice for AEAT-hosted synthetic live-surface policy conflicts discovered outside this declaration-acquisition slice; `Modelo 100 Renta WEB Open, Modelo 349 GROI/IXVI, and direct GROI/NIF-IVA Sede guard policies now disallow AEAT-hosted synthetic input; `.vault/adr/2026-05-26-no-synthetic-sede-live-surfaces-adr.md .vault/plan/2026-05-26-no-synthetic-sede-live-surfaces-plan.md src/aeat/_data/registry/aeat/modelos/100/ src/aeat/_data/registry/aeat/modelos/349/ src/aeat/domain/calculations/registry/ src/aeat/adapters/outbound/aeat/sede/`.
- [x] `W05.P18.S125` - Research the no-synthetic-Sede blast radius for accepted live-parity surfaces and persist findings for the S124 ADR; `.vault/research/2026-05-26-no-synthetic-sede-live-surfaces-research.md`.
- [x] `W05.P18.S126` - Accept the no-synthetic-Sede ADR that supersedes the prior AEAT-hosted synthetic live-surface allowance and preserves replay/static evidence paths; `.vault/adr/2026-05-26-no-synthetic-sede-live-surfaces-adr.md`.
- [x] `W05.P18.S127` - Backlog the Modelo 303 submitted-file export-layout regression on modelo-303-envelope-marker before treating the broader Sede declarations batch as green; `src/aeat/_data/registry/aeat/modelos/303/ src/aeat/adapters/outbound/aeat/sede/test_declarations.py`.
- [x] `W05.P18.S128` - Author the Modelo 390 declaracion_pdf extraction profile for the 5 named_label closure casillas (47 64 65 97 662) confirmed in the hybrid corpus PDFs and add parametrised round-trip tests for the 2022 and 2023 Spanish-language fixtures; `src/aeat/_data/registry/aeat/modelos/390.toml src/aeat/adapters/inbound/declaracion/test_parser_boundary.py`.

## Wave `W06` - codebase convention hardening

Re-ground the declaration-extraction implementation and adjacent shared surfaces against codebase conventions before expanding more parser coverage. This wave is source/static only unless a row explicitly asks for authenticated AEAT evidence; authenticated rows must stop for operator login before touching live taxpayer data.

### Phase `W06.P15` - paper-trail cleanup

Correct the four stale documents that still describe the deleted per-modelo extractor classes as if implemented so no surviving document or comment contradicts the registry-profile-driven generic-parser architecture this plan executes.

- [x] `W06.P15.S87` - Correct the modelo-115 calc-verify ADR prose that still describes the deleted per-modelo extractor classes as implemented; `.vault/adr/2026-04-27-modelo-115-calc-verify-adr.md`.
- [x] `W06.P15.S88` - Correct the modelo-303 calc-verify ADR prose that still describes the deleted per-modelo extractor classes as implemented; `.vault/adr/2026-04-27-modelo-303-calc-verify-adr.md`.
- [x] `W06.P15.S89` - Correct the modelo-111 rule-delta reference prose that still describes the deleted per-modelo extractor classes as implemented; `.vault/reference/2026-04-27-modelo-111-rule-delta-reference.md`.
- [x] `W06.P15.S90` - Correct the stale declaracion detector module comment that still describes the deleted per-modelo extractor surface; `src/aeat/adapters/inbound/declaracion/_detect.py`.

### Phase `W06.P19` - convention audit and guardrail backlog

Audit and harden the declaration-extraction slice against repo-wide conventions
before adding further parser coverage. Rows in this phase must preserve localized
operator messages, the core exception hierarchy, observable exception handling,
centralized settings, shared model boundaries, and source-grounded tests.

- [x] `W06.P19.S112` - Audit declaration extraction, inbound PDF, registry, core error, core i18n, and core settings surfaces for `tr()` user-facing messages, `AeatError` inheritance, exception swallowing/logging, non-tautological tests, settings centralisation, shared enums/models, pydantic boundaries, and duplication; `.vault/audit/ src/aeat/adapters/inbound/declaracion/ src/aeat/adapters/inbound/pdf/ src/aeat/domain/calculations/registry/ src/aeat/core/`.
- [x] `W06.P19.S113` - Convert any newly introduced declaration-extraction user-facing error strings to `tr()` keys while preserving structured exception context; `src/aeat/adapters/inbound/declaracion/ src/aeat/locales/`.
- [x] `W06.P19.S114` - Enforce or extend tests proving declaration/PDF/registry exception classes derive from `aeat.core.errors.AeatError`; `src/aeat/adapters/inbound/declaracion/ src/aeat/adapters/inbound/pdf/ src/aeat/domain/calculations/registry/`.
- [x] `W06.P19.S115` - Harden exception-swallowing checks so broad handlers either re-raise, convert, or log at least at debug level on the audited surfaces; `src/aeat/adapters/inbound/declaracion/ src/aeat/adapters/inbound/pdf/ src/aeat/domain/calculations/registry/`.
- [x] `W06.P19.S116` - Re-audit the declaration-extraction tests for tautology and replace any mirror-logic assertions with independent fixture, source, or behavior assertions; `src/aeat/adapters/inbound/declaracion/test_parser_boundary.py src/aeat/domain/calculations/registry/test_modelo_840_registry.py`.
- [x] `W06.P19.S117` - Verify environment handling remains routed through central `Settings` and core access-gate/settings helpers, with no new direct environment wrangling in declaration extraction; `src/aeat/core/config.py src/aeat/adapters/inbound/declaracion/ src/aeat/adapters/inbound/pdf/`.
- [x] `W06.P19.S118` - Verify declaration extraction uses existing shared enums/models/pydantic records and document or eliminate any duplicated local shape definitions; `src/aeat/adapters/inbound/declaracion/_schema.py src/aeat/adapters/inbound/pdf/_shared.py src/aeat/domain/calculations/registry/_schema.py`.
- [x] `W06.P19.S119` - Harden the Modelo 840 printed-form label grounding test so it pins the official labels and cannot pass solely through an over-broad registry regex; `src/aeat/domain/calculations/registry/test_modelo_840_registry.py`.
- [x] `W06.P19.S120` - Resolve the remaining direct `JustificanteRepository` storage crypto/sql import cycle exposed while localizing PDF error imports; `src/aeat/domain/justificante/__init__.py src/aeat/domain/justificante/_repository.py src/aeat/adapters/persistence/storage/`.

## Wave `W07` - session-2026-05-26: out-of-W02-scope authoring, PROVISIONAL gate, regression healing

Track work delivered in the 2026-05-26 session that extends the W02 named_label primitive beyond its original 6-modelo scope (M390, M100, M303 older template) and converts the silent-failure audit findings into a structural validator gate. Also captures the cross-cutting regression triage that landed during the session (parser tax-id multi-line NIF, ExtractedCasilla canonical CasillaId alignment, M190 revision-range + label-pattern, 50-test broad-suite cluster fix).

### Phase `W07.P20` - M303 named_label profile + 2021-2022 template variant

Unblock W03 BLOCKED finding: M303 corpus PDFs are hybrid documents (receipt header + full printed declaracion form below). Author named_label profile for 2023+ template; later add 2021-2022 template-revision variant with its own profile. End-state: 15/15 M303 corpus PDFs round-trip via 2 template revisions.

- [x] `W07.P20.S129` - Author Modelo 303 declaracion_pdf named_label profile with 10 closure-casilla targets for 2023+ template; `src/aeat/_data/registry/aeat/modelos/303.toml`.
- [x] `W07.P20.S130` - Author parametrized round-trip test for 8 corpus PDFs 2023-2024 asserting Decimal value for stable closure targets; `src/aeat/adapters/inbound/declaracion/test_parser_boundary.py`.
- [x] `W07.P20.S131` - Expand Modelo 303 profile to 12 named_label targets adding boxes 29 IVA soportado interiores and 37 intracomunitarias; `src/aeat/_data/registry/aeat/modelos/303.toml`.
- [x] `W07.P20.S132` - Author Modelo 303 older-template revision 2009-y-siguientes with 4-casilla closure profile for 2021-2022 printed-form layout; `src/aeat/_data/registry/aeat/modelos/303/revisions/2009-y-siguientes/extraction_profiles/0001-modelo-303-declaracion-pdf.toml`.
- [x] `W07.P20.S133` - Author parametrized round-trip test for 7 older-template corpus PDFs 2021-2022; `src/aeat/adapters/inbound/declaracion/test_parser_boundary.py`.

### Phase `W07.P21` - M390 declaracion_pdf profile authoring + closure-casilla coverage

M390 IVA annual was ABSENT in W01 classification. Corpus PDFs exist at tests/fixtures/justificantes/390/. Apply same hybrid-PDF named_label pattern as M303. Honest partial coverage of closure casillas; the remaining 7/13 are structurally not coverable via named_label (multi-column tables need bbox extraction, or are application-internal reconciliation values).

- [x] `W07.P21.S134` - Author Modelo 390 declaracion_pdf named_label profile with 5 closure-casilla targets; `src/aeat/_data/registry/aeat/modelos/390.toml`.
- [x] `W07.P21.S135` - Author parametrized round-trip test for 2 Spanish-language corpus PDFs excluding the English 2021 specimen; `src/aeat/adapters/inbound/declaracion/test_parser_boundary.py`.
- [x] `W07.P21.S136` - Expand Modelo 390 profile to 6 named_label targets adding box 49 IVA soportado total interiores corrientes; `src/aeat/_data/registry/aeat/modelos/390.toml`.

### Phase `W07.P22` - M100 IRPF declaracion_pdf profile — closure casillas + apartado totals

M100 IRPF Renta annual was ABSENT — Kent's headline annual filing. Author multi-revision declaracion_pdf profile (2021/2022/2023) covering closure cuota-chain casillas + base-liquidable / saldo-neto apartado totals. Multi-chunk iterative work bounded by corpus content (kent persona has actividades-económicas income only; trabajo/capital sections empty).

- [x] `W07.P22.S137` - Author Modelo 100 declaracion_pdf profile first chunk 9 closure casillas across 3 revisions 2021 2022 2023; `src/aeat/_data/registry/aeat/modelos/100/revisions/`.
- [x] `W07.P22.S138` - Wire Modelo 100 application_links to parse_declaracion consumer across all 3 revisions; `src/aeat/_data/registry/aeat/modelos/100/revisions/`.
- [x] `W07.P22.S139` - Export TemplateNotDetectedError from declaracion init module pre-existing broken import; `src/aeat/adapters/inbound/declaracion/__init__.py`.
- [x] `W07.P22.S140` - Author Modelo 100 round-trip test parametrized over 2021 2022 2023 corpus PDFs; `src/aeat/adapters/inbound/declaracion/test_parser_boundary.py`.
- [x] `W07.P22.S141` - Expand Modelo 100 profile second chunk 4 apartado-summary casillas across all 3 revisions; `src/aeat/_data/registry/aeat/modelos/100/revisions/`.
- [x] `W07.P22.S160` - Expand Modelo 100 profile third chunk 6 actividades-economicas ED detail casillas 0180 0218 0223 0224 0226 0231 across all 3 revisions; `src/aeat/_data/registry/aeat/modelos/100/revisions/, src/aeat/adapters/inbound/declaracion/test_parser_boundary.py`.

### Phase `W07.P23` - Parser fixes + canonical type alignment

Fix parser-level bugs surfaced during corpus-driven extraction. Fixes: _TAX_ID_RE multi-line NIF regex (8/15 -> 15/15 M303 tax-id); ExtractedCasilla.casilla_id max_length 32 -> 64 aligned to canonical CasillaId (semantic slugs longer than 32 chars); M190 revision range + retenciones label_pattern (silent-failure: pattern missing 'las ' token, profile loaded green but never matched).

- [x] `W07.P23.S142` - Fix _TAX_ID_RE multi-line NIF pattern add _TAX_ID_BEFORE_LABEL_RE fallback 15-of-15 M303 tax-id extraction; `src/aeat/adapters/inbound/declaracion/_parser.py`.
- [x] `W07.P23.S143` - Align ExtractedCasilla casilla_id field to canonical CasillaId type alias max_length 32 to 64; `src/aeat/adapters/inbound/pdf/_shared.py`.
- [x] `W07.P23.S144` - Fix Modelo 190 revision range year_from 2024 plus retenciones-total label_pattern missing las token; `src/aeat/_data/registry/aeat/modelos/190.toml`.

### Phase `W07.P24` - PROVISIONAL gate — silent-failure audit + first-class schema field + enforcement fix

Audit 9 unverified named_label profiles for silent-failure risk (label_patterns derived circularly from registry self-reference, never validated against printed-form). Annotate silently-PROVISIONAL profiles. Promote PROVISIONAL to first-class typed field provisional_pending_specimen with validator gate: declaracion_pdf profiles without a corpus fixture MUST explicitly opt-in. Fix the production-path corpus-root derivation bug that silently disabled the gate.

- [x] `W07.P24.S145` - Run silent-failure audit on 9 unverified named_label profiles produce per-profile GROUNDED PROVISIONAL UNKNOWN report; `.vault/audit/`.
- [x] `W07.P24.S146` - Annotate M184 M193 M720 with explicit PROVISIONAL warning comment downgrade confidence to review_required; `src/aeat/_data/registry/aeat/modelos/`.
- [x] `W07.P24.S147` - Add provisional_pending_specimen typed field to ExtractionProfileDefinition with 5 unit tests; `src/aeat/domain/calculations/registry/`.
- [x] `W07.P24.S148` - Author validate_declaracion_pdf_specimen_gate validator thread justificante_corpus_root through cache keys; `src/aeat/domain/calculations/registry/`.
- [x] `W07.P24.S149` - Tag the 9 PROVISIONAL profiles with provisional_pending_specimen true; `src/aeat/_data/registry/aeat/modelos/`.
- [x] `W07.P24.S150` - Author ADR amendment formalising provisional_pending_specimen as canonical silent-failure-prevention mechanism; `.vault/adr/2026-05-21-declaracion-extraction-architecture-adr.md`.
- [x] `W07.P24.S151` - Fix corpus-root derivation bug parents 2 to parents 0 that silently disabled the production gate add production-path test; `src/aeat/domain/calculations/registry/`.

### Phase `W07.P25` - Broad-suite regression triage + 6-cluster healing

Triage 50 broad-suite registry failures surfaced after the session's profile-authoring and revision-rename work. Cluster by root cause (BIND-4 ledger source removed, M190 rename ripple, RegistryValidator refactor callsite, M720 confidence assertion, registry private-import gate, M100 synthetic-data assertion). Surgical 6-cluster fix + bonus M200 cross-dependency. 1923/1923 final pass.

- [x] `W07.P25.S152` - Triage 50 broad-suite registry failures into 6 surgical clusters with concrete file line root-cause attribution; `.vault/audit/`.
- [x] `W07.P25.S153` - Cluster B rename M190 revision to 2024-y-siguientes year_from 2024 update test refs drop M303 cross-revision reviewed_singletons; `src/aeat/_data/registry/aeat/modelos/190.toml`.
- [x] `W07.P25.S154` - Cluster A change _binding helper source ledger to invoice remove vacuous test_free_form_source; `src/aeat/domain/calculations/registry/test_export.py`.
- [x] `W07.P25.S155` - Cluster C reroute static-method callsite to module-level validate_informative_class_invariant; `src/aeat/domain/calculations/registry/test_referential_integrity.py`.
- [x] `W07.P25.S156` - Cluster D update M720 confidence assertion strict to review_required; `src/aeat/domain/calculations/registry/test_modelo_720_registry.py`.
- [x] `W07.P25.S157` - Cluster E reroute 3 private registry imports through public init API stage 2 untracked test files; `src/aeat/adapters/ src/aeat/domain/calculations/registry/`.
- [x] `W07.P25.S158` - Cluster F flip M100 renta-web-open synthetic_data_allowed assertion True to False; `src/aeat/domain/calculations/registry/test_modelo_100_registry.py`.
- [x] `W07.P25.S159` - Bonus M200 cross-dependency fix new-entity-flag and incn-prior-12-months binding values; `src/aeat/domain/calculations/registry/test_modelo_200_cuota_integra_lanes.py`.

### Phase `W07.P26` - Real-corpus round-trip conversion for M111 + M130

Both modelos have substantial corpus collections (M111 4 PDFs 2024-1T..4T; M130 15 PDFs 2021-2T..2024-4T) but their primary round-trip tests use SYNTHETIC PDFs via _write_declaration_pdf. The corpus PDFs are exercised only for tax-id extraction. Add parametrized real-corpus round-trip tests asserting each target casilla extracts to the printed value (Decimal type-check; specific value if independently verifiable). Keep synthetic tests for full-target-coverage scaffold. Strengthens calculation-grounding verification mission.

- [x] `W07.P26.S161` - Survey M111 and M130 corpus PDF text layouts via pdfplumber; `confirm numeric_casilla profile cannot match real AEAT PDF form layout; identify named_label candidates for M111 closure casillas 28 and 30; `src/aeat/tests/fixtures/justificantes/111/, src/aeat/tests/fixtures/justificantes/130/`.
- [x] `W07.P26.S162` - Author parametrized corpus round-trip tests for M111: tax-id extraction (4 PDFs) plus named_label extraction using in-test ExtractionProfileDefinition for closure casillas 28 and 30; `assert Decimal values from printed PDF text; `src/aeat/adapters/inbound/declaracion/test_parser_boundary.py`.
- [x] `W07.P26.S163` - Author parametrized corpus round-trip tests for M130: tax-id extraction (15 PDFs) plus coverage-gap documentation asserting numeric_casilla profile fails with coverage=0 for all corpus PDFs; `src/aeat/adapters/inbound/declaracion/test_parser_boundary.py`.
