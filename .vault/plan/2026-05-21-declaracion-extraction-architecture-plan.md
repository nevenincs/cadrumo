---
tags:
  - '#plan'
  - '#declaracion-extraction-architecture'
date: '2026-05-21'
modified: '2026-05-21'
tier: L3
related:
  - '[[2026-05-21-declaracion-extraction-architecture-adr]]'
  - '[[2026-05-21-declaracion-extraction-architecture-research]]'
  - '[[2026-05-20-branch-reconciliation-audit]]'
---


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
- [x] `W03.P06.S20` - OUT OF CAMPAIGN SCOPE per user confirmation 2026-05-26 - does not file Modelo 180; `no specimen acquirable; M180 declaracion_pdf surface remains ABSENT correctly; `src/aeat/_data/registry/aeat/modelos/180/`.

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
- [x] `W05.P11.S34` - OUT OF CAMPAIGN SCOPE per user confirmation 2026-05-26 - does not file Modelo 180; `no specimen acquirable; M180 declaracion_pdf surface remains ABSENT correctly; `src/aeat/_data/registry/aeat/modelos/180/`.
- [x] `W05.P11.S92` - OUT OF CAMPAIGN SCOPE per user confirmation 2026-05-26 - does not file Modelo 180; `no specimen acquirable; M180 declaracion_pdf surface remains ABSENT correctly; `src/aeat/_data/registry/aeat/modelos/180/`.
- [x] `W05.P11.S35` - Add the Modelo 190 real round-trip parse test against the existing sanitized 2024 declaration fixture after W05.P11.S93 supplied a legally grounded 2024 registry revision; `src/aeat/adapters/inbound/declaracion/test_parser_boundary.py`.
- [x] `W05.P11.S93` - Resolve the Modelo 190 fixture/revision mismatch by sourcing the 2024 registry slice from Orden HAC/1432/2024, AEAT DR 190-2024, and the existing sanitized 2024 fixture; `src/aeat/tests/fixtures/justificantes/190/ src/aeat/_data/registry/aeat/modelos/190.toml`.
- [x] `W05.P11.S36` - Keep the Modelo 036 real round-trip parse test blocked by W05.P11.S94 fixture acquisition; `src/aeat/adapters/inbound/declaracion/test_parser_boundary.py`.
- [x] `W05.P11.S94` - Acquire a real Modelo 036 printed-form PDF fixture to verify the provisional named_label patterns before implementing S36; `src/aeat/tests/fixtures/justificantes/036/`.
- [x] `W05.P11.S37` - Descope current Modelo 037 real round-trip parse test after W04.P08.S86 legal suppression decision; `src/aeat/adapters/inbound/declaracion/test_parser_boundary.py`.
- [x] `W05.P11.S95` - Convert Modelo 037 source and fixture acquisition into historical-slice backlog only; `src/aeat/_data/registry/aeat/modelos/037/ src/aeat/tests/fixtures/justificantes/037/`.
- [x] `W05.P11.S38` - OUT OF CAMPAIGN SCOPE per user confirmation 2026-05-26 - does not file Modelo 369 OSS EU distance-sales VAT; `no specimen acquirable; `src/aeat/_data/registry/aeat/modelos/369/`.
- [x] `W05.P11.S96` - OUT OF CAMPAIGN SCOPE per user confirmation 2026-05-26 - does not file Modelo 369 OSS EU distance-sales VAT; `no specimen acquirable; `src/aeat/_data/registry/aeat/modelos/369/`.
- [x] `W05.P11.S39` - OUT OF CAMPAIGN SCOPE per user confirmation 2026-05-26 - does not file Modelo 720 foreign-asset declaration; `no specimen acquirable; `src/aeat/_data/registry/aeat/modelos/720.toml`.
- [x] `W05.P11.S97` - OUT OF CAMPAIGN SCOPE per user confirmation 2026-05-26 - does not file Modelo 720 foreign-asset declaration; `no specimen acquirable; `src/aeat/_data/registry/aeat/modelos/720.toml`.
- [x] `W05.P11.S40` - RESOLVED via task #42: M840 grounded from corpus form template, SANITIZED fixture authored, round-trip test passing, corpus_round_trip_verified=true; `src/aeat/_data/registry/aeat/modelos/840.toml src/aeat/tests/fixtures/justificantes/840/`.
- [x] `W05.P11.S98` - RESOLVED via task #42: M840 grounded from corpus form template, SANITIZED fixture authored, round-trip test passing, corpus_round_trip_verified=true; `src/aeat/_data/registry/aeat/modelos/840.toml src/aeat/tests/fixtures/justificantes/840/`.
- [x] `W05.P11.S41` - Confirm the snapshot-build gate is green and all 26 modelos validate; `src/aeat/domain/calculations/registry/test_committed_registry.py`.

### Phase `W05.P16` - backlog queue for newly identified declaration surfaces

Keep every newly identified declaration-extraction surface explicit until it is either legally descoped, source-acquired, or implemented with a real round-trip test.

- [x] `W05.P16.S99` - Decide whether to open a historical pre-2025 Modelo 037 registry/profile slice after BOE-A-2025-410 suppression; `.vault/adr .vault/plan src/aeat/_data/registry/aeat/modelos/037/`.
- [x] `W05.P16.S100` - Decide whether Modelo 303 printed boxes 46, 69, 87, and 110 should become registered casillas before any extraction profile expands beyond the currently registered result casillas; `src/aeat/_data/registry/aeat/modelos/303/`.
- [x] `W05.P16.S101` - Acquire legally authorised declaration PDF fixture for M036 from user (the only remaining modelo with corpus-bound work; `M180/M369/M720 out of campaign scope per user; M190+M840 resolved this session); `src/aeat/tests/fixtures/justificantes/036/`.
- [x] `W05.P16.S102` - Re-run declaration parser boundary tests and committed-registry validation after each fixture-backed profile/test expansion; `src/aeat/adapters/inbound/declaracion/test_parser_boundary.py src/aeat/domain/calculations/registry/test_committed_registry.py`.

### Phase `W05.P17` - progress ledger and remaining-work queue

Maintain a single current-state ledger for every completed, descoped, deferred, blocked, or not-yet-tackled declaration-extraction surface discovered during the rollout.

- [x] `W05.P17.S103` - Keep the declaration-extraction progress ledger synchronized with every future profile, fixture, parser, source, or descope decision; `.vault/plan/2026-05-21-declaracion-extraction-architecture-plan.md`.

### Phase `W05.P18` - fixture acquisition classification

Classify the broad `W05.P16.S101` acquisition row into legally grounded per-modelo work items. Record-design layouts and BOE form specifications can ground registry/export surfaces, but they do not by themselves validate declaration-PDF parser labels unless the profile explicitly targets that source surface.

Status note 2026-05-26: `.vault/audit/2026-05-26-declaracion-extraction-auth-gated-acquisition-status.md` records that public AEAT pages found for the remaining acquisition rows describe electronic form, preview, or filed-declaration flows, not taxpayer-free static declaration PDFs. Rows `W05.P18.S105` through `W05.P18.S110` remain open until operator-provided authorised fixtures, taxpayer-free static printed-form layouts, or authenticated read-only filed declarations are available. Synthetic data must not be sent to Sede or AEAT-hosted form surfaces, even for preview/download flows. A later operator-approved read-only Sede listing found one Modelo 190 exercise-2024 filed row for the authenticated profile, but single-row capture failed before artifact download because the local Modelo 190 registry had no 2024 snapshot at that time. Follow-up `W05.P18.S121` closed Modelo 190 through legally grounded 2024 registry authority plus the existing sanitized fixture. The authenticated read returned zero rows for modelos 180, 036, 369, 720, and 840 across 2024-2026; `W05.P18.S122` records a per-modelo evidence matrix and keeps their rows open. Operator context added 2026-05-26: the active profile is not expected to include filed data for the remaining special/current forms, so future auth reads are opportunistic only; the primary unblocker is authorised fixtures or official taxpayer-free static layouts.

- [x] `W05.P18.S104` - Classify the blocked current slices by required acquisition type and verified local authority; `.vault/plan/2026-05-21-declaracion-extraction-architecture-plan.md`.
- [x] `W05.P18.S105` - OUT OF CAMPAIGN SCOPE per user confirmation 2026-05-26 - does not file Modelo 180; `no specimen acquirable; M180 declaracion_pdf surface remains ABSENT correctly; `src/aeat/_data/registry/aeat/modelos/180/`.
- [x] `W05.P18.S106` - Legally source and implement the 2024 Modelo 190 registry revision before using the existing 2024 fixture; `src/aeat/_data/registry/aeat/modelos/190.toml src/aeat/tests/fixtures/justificantes/190/`.
- [x] `W05.P18.S107` - Acquire an authorised Modelo 036 printed-form PDF/declaration fixture before promoting provisional `named_label` patterns; `src/aeat/_data/registry/aeat/modelos/036.toml src/aeat/tests/fixtures/justificantes/036/`.
- [x] `W05.P18.S108` - OUT OF CAMPAIGN SCOPE per user confirmation 2026-05-26 - does not file Modelo 369 OSS EU distance-sales VAT; `no specimen acquirable; `src/aeat/_data/registry/aeat/modelos/369/`.
- [x] `W05.P18.S109` - OUT OF CAMPAIGN SCOPE per user confirmation 2026-05-26 - does not file Modelo 720 foreign-asset declaration; `no specimen acquirable; `src/aeat/_data/registry/aeat/modelos/720.toml`.
- [x] `W05.P18.S110` - RESOLVED via task #42: M840 grounded from corpus form template, SANITIZED fixture authored, round-trip test passing, corpus_round_trip_verified=true; `src/aeat/_data/registry/aeat/modelos/840.toml src/aeat/tests/fixtures/justificantes/840/`.
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

### Phase `W07.P22` - M100 IRPF declaracion_pdf profile - closure casillas + apartado totals

M100 IRPF Renta annual was ABSENT - Kent's headline annual filing. Author multi-revision declaracion_pdf profile (2021/2022/2023) covering closure cuota-chain casillas + base-liquidable / saldo-neto apartado totals. Multi-chunk iterative work bounded by corpus content (kent persona has actividades-económicas income only; trabajo/capital sections empty).

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

### Phase `W07.P24` - PROVISIONAL gate - silent-failure audit + first-class schema field + enforcement fix

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

### Phase `W07.P27` - Strengthen silent-failure gate plus broader silent-regression identification

The current PROVISIONAL gate (#34) checks fixture EXISTENCE; the M111/M130 finding (#37) showed fixture-exists is insufficient - both modelos have corpus but real-corpus round-trip structurally fails on layout differences. Add corpus_round_trip_verified typed field to ExtractionProfileDefinition with build-time validator (profile has fixture AND not corpus_round_trip_verified AND not provisional_pending_specimen -> fail) plus pytest-collection-time check that verifies the field corresponds to a real parametrized test. Tag profiles by ground truth (M303/M390/M100/M190 verified; M111/M130 fixture-but-gap-blocked; M115/M123/M131 no-fixture-already-provisional). Author ADR amendment to W02. Survey broader codebase for analogous silent-failure classes outside extraction-profile surface.

- [x] `W07.P27.S164` - Add corpus_round_trip_verified field to ExtractionProfileDefinition plus validate_declaracion_pdf_round_trip_gate validator with 4 unit tests in test_corpus_round_trip_gate.py; `update test_provisional_specimen_gate to match strengthened gate contract; `src/aeat/domain/calculations/registry/`.
- [x] `W07.P27.S165` - Tag 8 verified profiles corpus_round_trip_verified=true (M100 x3, M190, M303 x2, M390) and 2 corpus-gap profiles provisional_pending_specimen=true (M111, M130); `all 26 modelos pass registry validation; `src/aeat/_data/registry/aeat/modelos/`.
- [x] `W07.P27.S166` - Author ADR amendment formalising corpus_round_trip_verified gate and M111/M130 corpus-gap finding; `add plan steps S164-S166 under W07.P27 and mark closed; `.vault/adr/2026-05-21-declaracion-extraction-architecture-adr.md`.
- [x] `W07.P27.S167` - Author parametrized sidecar-manifest roundtrip test asserting parser output matches SANITIZED ground truth for every justificante PDF+JSON pair in tests/fixtures/justificantes/; `41 corpus pairs across 6 modelos all pass; `src/aeat/adapters/inbound/justificante/test_corpus_sidecar_roundtrip.py`.
- [x] `W07.P27.S169` - Ground M840 declaracion_pdf label_patterns against AEAT corpus form PDF; `fix provisional patterns to corpus-published labels (14Ejercicio: and 15Declaracion de:); author sanitized synthetic fixture; add corpus_round_trip_verified=true; add round-trip test asserting both casillas extract; `src/aeat/_data/registry/aeat/modelos/840.toml src/aeat/tests/fixtures/justificantes/840/2024-0A.pdf src/aeat/tests/fixtures/justificantes/_generate.py src/aeat/adapters/inbound/declaracion/test_parser_boundary.py`.

### Phase `W07.P28` - PROVISIONAL corpus-grounding survey for M036 M180 M232 M349 M369 M720

Survey AEAT instructions corpus for 6 PROVISIONAL modelos, document corpus-availability gap, record verdicts

- [x] `W07.P28.S168` - Survey AEAT instructions corpus for M036 M180 M232 M349 M369 M720: all 6 corpus files are AEAT portal navigation HTML pages loading field instructions via JavaScript/CMS VgnVCM IDs not captured at download time; `no printed-form field label text is available in corpus; all 6 modelos remain PROVISIONAL with provisional_pending_specimen=true; no pattern changes made; grounding verdict: AMBIGUOUS for all 6 modelos pending PDF specimen acquisition; `src/aeat/_data/corpus/aeat_official/instructions/`.
- [x] `W07.P28.S170` - Fetch AEAT-published instruction PDFs for M349 and M232; `ground M349 declaracion_pdf profile (CONFIRMED: all 4 patterns match instr_mod_349.pdf pages 8-9 verbatim); document M232 as AMBIGUOUS (electronic-only, instructions PDF labels do not match profile patterns); document M036/M369/M720 as NO-PDF (no instruction PDF on procedure page); remove provisional_pending_specimen and add corpus_round_trip_verified=true for M349; add synthetic fixture and round-trip test; `src/aeat/_data/registry/aeat/modelos/349/ src/aeat/_data/registry/aeat/modelos/232/ src/aeat/_data/registry/aeat/modelos/036.toml src/aeat/_data/registry/aeat/modelos/369/ src/aeat/_data/registry/aeat/modelos/720.toml src/aeat/tests/fixtures/justificantes/349/2024-1T.pdf src/aeat/adapters/inbound/declaracion/test_parser_boundary.py`.

### Phase `W07.P29` - Ground M037+M180+M369+M720 from AEAT public Sede material (user correction 2026-05-27)

User clarified scope 2026-05-27: even when user does not personally file a modelo, AEAT publishes Diseños + Anexos + practical guides on Sede that ARE sufficient to ground declaracion_pdf patterns. Same WebFetch path that succeeded for M036 (commit 33783e00c grounded decl.event-kind from Anexo 3 PAGINA 1 h3) applies to M037/M180/M369/M720. M180 corpus already has 3 AEAT Orden PDFs locally; M037/M369/M720 need WebFetch of the Sede public material. Per-modelo: ground patterns (FIXED/CONFIRMED/AMBIGUOUS), author SANITIZED fixture if grounded, real round-trip test, flip provisional_pending_specimen → corpus_round_trip_verified where evidence supports.

- [x] `W07.P29.S172` - Ground M720 declaracion_pdf named_label patterns from AEAT-published Sede DR material; `verdict: decl.ejercicio pattern AMBIGUOUS but linguistically consistent with aeat-dr-720 label; decl.tipo-declaracion pattern NOT GROUNDABLE against printed form (field is positions 121-122 encoded flags, not a named label); retire decl.tipo-declaracion from extraction_profiles; add SANITIZED synthetic fixture and round-trip test for decl.ejercicio only; `src/aeat/_data/registry/aeat/modelos/720/ src/aeat/tests/fixtures/justificantes/720/ src/aeat/tests/fixtures/justificantes/_generate.py src/aeat/adapters/inbound/declaracion/test_parser_boundary.py`.

### Phase `W07.P30` - Ground M180 from AEAT Orden HAP/1732/2014 printed-form corpus

Author M180 declaracion_pdf named_label profile grounded against the AEAT-published printed-form layout in 02-180-orden-de-20-de-noviembre-de-2000-12-kb-pdf.pdf (Tipo 1 register template), author a sanitized synthetic fixture, and add a real round-trip test. Flip M180 from ABSENT to GROUNDED with corpus_round_trip_verified=true.

- [x] `W07.P30.S171` - Ground M180 declaracion_pdf: author named_label profile, synthetic fixture, and round-trip test; `src/aeat/_data/registry/aeat/modelos/180/ src/aeat/tests/fixtures/justificantes/180/ src/aeat/adapters/inbound/declaracion/test_parser_boundary.py`.

### Phase `W07.P31` - Ground M369 from AEAT DR369e21.xlsx and online manual

Ground M369 esquema-union declaracion_pdf extraction profile from AEAT-published DR369e21.xlsx and online manual section headings. Flip provisional_pending_specimen to corpus_round_trip_verified. Author synthetic fixture and round-trip test.

- [x] `W07.P31.S173` - Ground M369 esquema-union declaracion_pdf profile: update label_patterns to AEAT-grounded 'Ejercicio:' and 'Periodo:' (DR369e21.xlsx sheet T36904 rows 14/16 + AEAT manual section 2 heading); `save 5 AEAT corpus files; author synthetic fixture 369/2024-1T.pdf; add round-trip test; flip provisional_pending_specimen to corpus_round_trip_verified; `src/aeat/_data/registry/aeat/modelos/369/revisions/esquema-union/revision.toml src/aeat/_data/corpus/aeat_official/instructions/modelo_369/files/ src/aeat/tests/fixtures/justificantes/369/ src/aeat/adapters/inbound/declaracion/test_parser_boundary.py src/aeat/tests/fixtures/justificantes/_generate.py`.

### Phase `W07.P32` - Final PROVISIONAL closure: M184/M193/M232/M347 named_label + M115/M123/M131 numeric grounded via AEAT Sede

Apply the M036/M180/M349/M369/M720 successful WebFetch-grounding pattern to the remaining 7 PROVISIONAL declaracion_pdf profiles. Named_label modelos verify or fix label_patterns against AEAT-published Diseños + practical-guide Anexos; numeric_casilla modelos verify the printed AEAT form uses line-start box numbers (vs M111/M130 line-end structural gap), author SANITIZED fixtures and round-trip tests. Each pattern either CONFIRMED, FIXED, or REMOVED (no fabrication).

- [x] `W07.P32.S175` - Ground M193 declaracion_pdf named_label patterns from AEAT-published Orden HAC/56/2024 Diseno de Registro Tipo 1: CONFIRMED all 3 patterns (NUMERO TOTAL DE PERCEPTORES pos 136-144, BASE RETENCIONES E INGRESOS A CUENTA pos 145-159, RETENCIONES E INGRESOS A CUENTA pos 160-174); `'_total' fixture-disambiguation suffix follows M180 convention; remove provisional_pending_specimen, upgrade confidence to strict, add corpus_round_trip_verified=true, add synthetic fixture 193/2024-0A.pdf and round-trip test; `src/aeat/_data/registry/aeat/modelos/193.toml src/aeat/tests/fixtures/justificantes/193/2024-0A.pdf src/aeat/tests/fixtures/justificantes/_generate.py src/aeat/adapters/inbound/declaracion/test_parser_boundary.py`.
- [x] `W07.P32.S176` - Ground M184 declaracion_pdf: FIXED decl.ejercicio to bare 'Ejercicio' (DR_Modelo_184_2025.pdf pos 5-8); `REMOVED decl.tipo-declaracion (pos 121-122 flag pair); confidence strict, corpus_round_trip_verified=true; fixture 184/2024-0A.pdf + round-trip test; `src/aeat/_data/registry/aeat/modelos/184/revisions/2015-y-siguientes/extraction_profiles/0001-extraction_profiles.toml src/aeat/tests/fixtures/justificantes/184/2024-0A.pdf src/aeat/tests/fixtures/justificantes/_generate.py src/aeat/adapters/inbound/declaracion/test_parser_boundary.py`.
- [x] `W07.P32.S177` - Ground M347 declaracion_pdf: fix decl.ejercicio pattern to Ejercicio: (AEAT DR field EJERCICIO positions 5-8 Orden HAC/1431/2025), remove decl.tipo-declaracion (positions 121-122 are two separate single-char flags identical to M720), flip provisional_pending_specimen to corpus_round_trip_verified, author synthetic fixture 347/2024-0A.pdf and round-trip test; `src/aeat/_data/registry/aeat/modelos/347.toml src/aeat/tests/fixtures/justificantes/347/ src/aeat/tests/fixtures/justificantes/_generate.py src/aeat/adapters/inbound/declaracion/test_parser_boundary.py`.
- [x] `W07.P32.S178` - Ground Modelo 232 both revisions: confirm decl.ejercicio and decl.tipo-ejercicio patterns against AEAT DR23200/DR23201; `fix decl.cnae pattern removing spurious 'de la' connector; add synthetic fixtures 2016-0A.pdf and 2018-0A.pdf; author parametrized round-trip tests; `src/aeat/_data/registry/aeat/modelos/232/revisions/ src/aeat/tests/fixtures/justificantes/232/ src/aeat/adapters/inbound/declaracion/test_parser_boundary.py src/aeat/tests/fixtures/justificantes/_generate.py`.
- [x] `W07.P32.S179` - Ground M123 declaracion_pdf numeric_casilla profiles for both 2024-y-siguientes (14 casillas) and 2019-2023 legacy (8 casillas) revisions: CONFIRMED line-start box-number layout from DR123v20.xlsx (Orden HAC/56/2024) and DR123v13; `author committed synthetic fixtures 123/2024-1T.pdf and 123/2023-1T.pdf; add corpus round-trip tests asserting all casilla values; clear provisional_pending_specimen and set corpus_round_trip_verified=true on both profiles; `src/aeat/_data/registry/aeat/modelos/123/revisions/2024-y-siguientes/revision.toml src/aeat/_data/registry/aeat/modelos/123/revisions/2019-2023/revision.toml src/aeat/tests/fixtures/justificantes/123/ src/aeat/tests/fixtures/justificantes/_generate.py src/aeat/adapters/inbound/declaracion/test_parser_boundary.py`.
- [x] `W07.P32.S180` - Ground M115 declaracion_pdf extraction: convert numeric_casilla to named_label, generate synthetic fixture, add round-trip test, fix provisional specimen gate test; `src/aeat/_data/registry/aeat/modelos/115/revisions/2019-y-siguientes/extraction_profiles/ src/aeat/tests/fixtures/justificantes/115/ src/aeat/adapters/inbound/declaracion/test_parser_boundary.py src/aeat/domain/calculations/registry/test_provisional_specimen_gate.py`.

### Phase `W07.P33` - M131 numeric_casilla grounding via AEAT DR 2026 and instruction HTML

WebFetch-ground M131 declaracion_pdf extraction_profiles against AEAT-published DR xlsx 2026 and instructions HTML; determine printed-form layout verdict (line-start vs line-end box numbers); author fixture and gap-test or round-trip test accordingly.

- [x] `W07.P33.S174` - Ground Modelo 131 numeric_casilla declaracion_pdf profile against AEAT-published DR xlsx (01-131-ejercicios-2026-actualizado-04-03-26-180-kb-xlsx.xlsx shared-strings [65]-[78] confirm bracket [NN] casilla notation) and instructions HTML (modelo-131-instrucciones.html); `verdict: GAP-DOCUMENTED -- M131 printed form uses the same line-end box-number tabular layout as M130 (both AEAT IRPF quarterly pago-fraccionado forms, same AEAT form-generation system); author synthetic fixture 131/2024-1T.pdf via _generate.py; add structural gap test asserting zero casilla extraction from the real profile on the synthetic fixture; retain provisional_pending_specimen=true on all M131 extraction_profiles revisions; `src/aeat/_data/registry/aeat/modelos/131/revisions/2026/extraction_profiles/0001-extraction_profiles.toml, src/aeat/tests/fixtures/justificantes/131/2024-1T.pdf, src/aeat/tests/fixtures/justificantes/_generate.py, src/aeat/adapters/inbound/declaracion/test_parser_boundary.py`.

## Wave `W08` - Post-rush remediation: address 15 findings from honest self-audit 2026-05-27

Track and remediate the 15 findings from .vault/audit/2026-05-27-declaracion-extraction-architecture-audit.md across HIGH (synthetic-fixture circularity, gate test path gap, target_casillas shrinkage), MEDIUM (cross-campaign sweeps, plan attribution, scratch commit, M193 reversal, _temporal.py case fix, M190 rename, gap-test brittleness), and LOW (suite scope, step granularity, PDF determinism, gate-surface scope, cross-attribution risk) severity levels. Dispatch high-leverage remediations and track deferred items as plan steps.

### Phase `W08.P34` - HIGH-severity remediation

verification-source schema field + coverage-drift audit + production-path gate tests

- [x] `W08.P34.S181` - Promote verification_source to typed schema field on ExtractionProfileDefinition with Literal options real_aeat_corpus_pdf synthetic_from_aeat_published_text historical_suppression; `src/aeat/domain/calculations/registry/_schema.py`.
- [x] `W08.P34.S182` - Tag all 16 GROUNDED profiles with the appropriate verification_source enum value reflecting actual provenance; `src/aeat/_data/registry/aeat/modelos/`.
- [x] `W08.P34.S183` - Audit calculation-completeness manifests for the 5 modelos with target_casillas REMOVED (M036/M720/M184/M232/M347) to verify removed casillas are marked input_kind informational or otherwise non-extractable; `src/aeat/domain/calculations/registry/`.
- [x] `W08.P34.S184` - Add production-path tests for both gate validators (validate_declaracion_pdf_specimen_gate and validate_declaracion_pdf_round_trip_gate) exercising RegistryValidator with source_root=bundled_path() not direct corpus_root injection; `src/aeat/domain/calculations/registry/test_provisional_specimen_gate.py src/aeat/domain/calculations/registry/test_corpus_round_trip_gate.py`.
- [x] `W08.P34.S193` - Tighten verification_source from honor-system to fixture-metadata-verified: author test that walks every declaracion_pdf corpus_round_trip_verified=true profile, reads the fixture PDF /Producer field via pdfplumber, and asserts real_aeat_corpus_pdf implies no aeat-test-fixture-generator producer and synthetic_from_aeat_published_text implies aeat-test-fixture-generator producer; `run suite confirming no mis-tagged profiles; `src/aeat/domain/calculations/registry/test_verification_source_fixture_metadata.py`.
- [x] `W08.P34.S194` - Tighten production-path gate coverage to pure-production wiring: add Scenarios B/C to round-trip gate (provisional flag silences, verified profile passes) and add test_gate_fires_via_production_path to specimen gate covering derivation + Scenarios B/C; `honest audit confirms specimen-gate Scenario A requires direct corpus injection because all real modelos with declaracion_pdf profiles have real fixtures; `src/aeat/domain/calculations/registry/test_corpus_round_trip_gate.py src/aeat/domain/calculations/registry/test_provisional_specimen_gate.py`.

### Phase `W08.P35` - MEDIUM-severity drifts

cross-campaign sweeps audit + M193 reversal verify + M190 rename ADR amendment + _temporal.py case-fix caller audit + .vault-scratch cleanup

- [x] `W08.P35.S185` - Remove .vault-scratch bound_casilla_sweep.json from git tracking and add path to gitignore; `.vault-scratch/`.
- [x] `W08.P35.S186` - Re-audit M193 _total suffix conclusion against M180 real-corpus extraction behaviour or document remaining uncertainty inline; `src/aeat/_data/registry/aeat/modelos/193.toml`.
- [x] `W08.P35.S187` - Audit select_revision callers for case-sensitive period expectations regressed by _temporal.py case-insensitive comparison fix; `src/aeat/domain/calculations/registry/_temporal.py`.
- [x] `W08.P35.S188` - Author ADR amendment recording M190 revision rename rationale 2025-y-siguientes to 2024-y-siguientes year_from=2024; `.vault/adr/2026-05-21-declaracion-extraction-architecture-adr.md`.
- [x] `W08.P35.S189` - DOCUMENTED in audit .vault/audit/2026-05-27-declaracion-extraction-architecture-audit.md M5 finding - plan-doc attribution scatter (#39 to secure-storage plan, #40 to schema-hardening plan, #36 bonus to schema-hardening) is operationally acceptable given factory-direct shared-worktree mode; `consolidation not warranted because the work is correctly tracked where the canonical step records live and cross-plan linking via wiki-links provides traceability; `.vault/audit/2026-05-27-declaracion-extraction-architecture-audit.md`.
- [x] `W08.P35.S195` - Add registry-author lint test asserting M036 period_selector.periods and filing_schedule.periods are lowercase canonical to catch ALTA/MODIFICACION/BAJA uppercase drift; `includes anti-evasion proof test; `src/aeat/domain/calculations/registry/test_census_modelo_registry_data.py`.

### Phase `W08.P36` - LOW-severity housekeeping

_generate.py PDF determinism + suite scope discipline + gate surface generalisation

- [x] `W08.P36.S190` - Investigate and fix _generate.py PDF metadata determinism eliminate rolling fixture-regen sweep churn; `src/aeat/tests/fixtures/justificantes/_generate.py`.
- [x] `W08.P36.S191` - Survey borrador_pdf justificante_pdf export_record official_workbook surfaces for analogous silent-failure class extend gate where warranted; `src/aeat/domain/calculations/registry/_validate_extraction_profiles.py`.

### Phase `W08.P37` - Gap-test brittleness fix

assert on typed exception attributes instead of message text

- [x] `W08.P37.S192` - Restructure M111 M130 M131 gap tests to assert on typed exception attributes failure_mode missing tuple instead of message text; `src/aeat/adapters/inbound/declaracion/test_parser_boundary.py`.

## Wave `W09` - PDF extraction hardening - bbox primitive + verification chain (2026-05-28 user-authorized)

Complete PDF extraction hardening + verification chain per user directive 2026-05-28. Phase 1: bbox extraction primitive (W02 ADR named future-extension) unblocking M111/M130/M131 from the line-end-box-number structural gap documented in gap tests. Phase 2: verification chain parse_declaracion → ExtractedCasilla observations → calculation engine recompute → equality assertion, exercised across all GROUNDED profiles. MUST use centralized core: aeat.core.errors AeatError hierarchy via DeclaracionParseError structured attributes, aeat.core.config.Settings, aeat.core.i18n.tr() for user-facing messages, existing ExtractionProfileDefinition / ExtractionTargetDefinition / ExtractedCasilla schemas (strict pydantic v2 frozen extra=forbid), existing _parser.py + _label_regex.py modules, existing PROVISIONAL gates + verification_source enum. NO new top-level packages, NO duplicated infrastructure, NO shims, NO mocks/skips/xfail/tautology.

### Phase `W09.P38` - bbox extraction primitive: schema + parser + profiles + tests + validator

Implement bbox_anchored extraction strategy for M111/M130/M131 declaracion PDFs with line-end box-number layout; extend schema, parser, TOML profiles, roundtrip tests, and snapshot-level bbox consistency validator.

- [x] `W09.P38.S196` - Add BboxAnchorSpec schema + bbox_anchored ExtractionTargetDefinition strategy; `add _find_bbox_casilla_hits/_resolve_value_word/_extract_pages_words parser branch; convert M130 (19 targets anchor_x 450-480), M111 (29 targets 3 columns with value_x_max), M131-2026 (15 targets) profiles from numeric_casilla to bbox_anchored; replace gap tests with real corpus roundtrip tests grounded on ground-truth Decimal values from pdfplumber probe; add snapshot-level bbox_anchor consistency validator in _validate_extraction_profiles.py + _validate_record_sections.py. All 99 parser tests pass, pyright 0 errors. Commit ad285e970.; `src/aeat/domain/calculations/registry/_schema.py src/aeat/domain/calculations/registry/__init__.py src/aeat/domain/calculations/registry/_validate_extraction_profiles.py src/aeat/domain/calculations/registry/_validate_record_sections.py src/aeat/adapters/inbound/declaracion/_parser.py src/aeat/_data/registry/aeat/modelos/130/revisions/2019-y-siguientes/extraction_profiles/0001-extraction_profiles.toml src/aeat/_data/registry/aeat/modelos/111/revisions/2019-y-siguientes/extraction_profiles/0005-extraction_profiles.toml src/aeat/_data/registry/aeat/modelos/131/revisions/2026/extraction_profiles/0001-extraction_profiles.toml src/aeat/adapters/inbound/declaracion/test_parser_boundary.py`.

### Phase `W09.P39` - Phase 2 verification chain: parse → ExtractedCasilla → calculation engine recompute → diff

User directive 2026-05-28 second half: complete the verification chain that turns GROUNDED extraction profiles into actual calculation-engine verification. For each GROUNDED modelo with corpus PDFs (M100×3, M111, M115, M123×2, M130, M131, M180, M184, M190, M193, M232×2, M303×2, M347, M349, M369, M390, M720, M840) where the corpus has closure-casilla values present: parse corpus PDF → ExtractedCasilla observations → registry calculation engine recomputes closure casillas from the formula DAG using extracted leaf casillas → assert engine-recomputed values match extracted closure values. This is the project mission: verify the calculation engine against AEAT-grounded printed forms. MUST use centralized infrastructure: aeat.core.errors.AeatError hierarchy, aeat.core.config.Settings, aeat.core.i18n.tr() for user messages, existing calculation engine surface (likely calculate_registry_snapshot per registry public API), existing DeclaracionFiling/ExtractedCasilla observation shape, existing RegistrySnapshot resolution. Real behaviour only - actual engine calls, actual PDFs, no mocks/skips/xfail/tautology.


### Phase `W09.P40` - Phase 2 verification chain: parse → ExtractedCasilla → calculation engine recompute → diff

Implement the verification chain that turns GROUNDED extraction profiles into actual calculation-engine verification: parse_declaracion → filter extracted casillas to non-computed → calculate_registry_snapshot → assert engine closure casilla == extracted printed value. First real end-to-end fidelity gate for the project mission.

- [x] `W09.P40.S197` - Implement verification chain test module; `src/aeat/adapters/inbound/declaracion/test_verification_chain.py`.

## Wave `W10` - Discipline rollout across PDF surfaces + Phase 2 follow-ups (2026-05-28)

Gradual rollout of the PDF extraction discipline (verification_source enum + PROVISIONAL gate + corpus_round_trip_verified + structured exception attributes + verification chain) across other PDF import surfaces beyond declaracion. Plus Phase 2 verification chain follow-ups for surfaced FORMULA-MISMATCH and BINDING-GAP findings (M130 corpus regen, M390 leaf inputs, M180 M115 relation, M111 negative filing edge). Per-surface phases: justificante (highest leverage, lowest risk - mirrors declaracion closely); bank PDF financial providers (high operational stakes - N26 first, extensible); borrador architectural audit (per-modelo class vs registry-profile decision); OCR/evidence path (deferred future research). Per-finding phases: M130 corpus regeneration, M390 leaf binding, M180 cross-modelo relation, M111 negative filing, verification chain extension as gaps close.

### Phase `W10.P41` - Justificante surface alignment with declaracion discipline

Tracked rollout item per 2026-05-28 user-directed gradual extension of PDF extraction discipline. Tasks ledger holds the detailed scope. Plan step granularity will be added when this phase is picked up for execution.

- [x] `W10.P41.S198` - Audit justificante _parser + _extract for silent-failure parity with declaracion verification_source enum and PROVISIONAL gate (tasklist #67); `src/aeat/adapters/inbound/justificante/`.

### Phase `W10.P42` - Bank PDF provider gate (financial.providers) - N26 first, extensible

Tracked rollout item per 2026-05-28 user-directed gradual extension of PDF extraction discipline. Tasks ledger holds the detailed scope. Plan step granularity will be added when this phase is picked up for execution.

- [x] `W10.P42.S199` - Author bank-PDF provider gate discipline N26-first extensible to BBVA Santander Caixabank etc (tasklist #68); `src/aeat/adapters/inbound/financial/providers/`.

### Phase `W10.P43` - Borrador architectural audit - per-modelo class vs registry-profile

Tracked rollout item per 2026-05-28 user-directed gradual extension of PDF extraction discipline. Tasks ledger holds the detailed scope. Plan step granularity will be added when this phase is picked up for execution.

- [x] `W10.P43.S200` - Audit borrador per-modelo class pattern vs registry-profile decision either supersede or document architectural difference (tasklist #69); `src/aeat/adapters/inbound/borrador/`.
- [x] `W10.P43.S210` - Extend BorradorParseError with structured attributes (missing/malformed/ambiguous/coverage) matching DeclaracionParseError discipline; `update extractor raise sites; add typed-attribute tests; `src/aeat/adapters/inbound/borrador/_errors.py src/aeat/adapters/inbound/borrador/_extractors/modelo_100_summary_v2025.py src/aeat/adapters/inbound/borrador/test_modelo_100_summary.py`.

### Phase `W10.P44` - OCR/evidence invoice path future research (deferred)

Tracked rollout item per 2026-05-28 user-directed gradual extension of PDF extraction discipline. Tasks ledger holds the detailed scope. Plan step granularity will be added when this phase is picked up for execution.

- [x] `W10.P44.S201` - OCR evidence invoice path discipline research (tasklist #70) - research landed at `.vault/research/2026-05-30-declaracion-extraction-architecture-research.md`; `seven OCR-specific silent-failure classes documented; discipline analogue proposed (`InvoiceCorpusSource`, `InvoiceOcrExtractionError`, engine-version gate); verdict: separate ADR `purchase-invoice-ocr-extraction-discipline` warranted; follow-up phases: ADR authoring, model/error implementation, OCR pipeline, gate enforcement`.

### Phase `W10.P45` - M130 corpus regeneration with formula-consistent values

Tracked rollout item per 2026-05-28 user-directed gradual extension of PDF extraction discipline. Tasks ledger holds the detailed scope. Plan step granularity will be added when this phase is picked up for execution.

- [x] `W10.P45.S202` - Regenerate 15 M130 corpus fixtures with formula-consistent values close FORMULA-MISMATCH (tasklist #71); `src/aeat/tests/fixtures/justificantes/130/`.

### Phase `W10.P46` - M390 leaf-input binding gap

Tracked rollout item per 2026-05-28 user-directed gradual extension of PDF extraction discipline. Tasks ledger holds the detailed scope. Plan step granularity will be added when this phase is picked up for execution.

- [x] `W10.P46.S203` - Resolve M390 leaf-input binding gap so engine recomputes closure (tasklist #72); `src/aeat/_data/registry/aeat/modelos/390.toml`.

### Phase `W10.P47` - M180 M115 cross-modelo relation binding

Tracked rollout item per 2026-05-28 user-directed gradual extension of PDF extraction discipline. Tasks ledger holds the detailed scope. Plan step granularity will be added when this phase is picked up for execution.

- [x] `W10.P47.S204` - Add M180 M115 cross-modelo relation binding for annual-quarterly summary chain (tasklist #73); `src/aeat/_data/registry/aeat/modelos/180/`.

### Phase `W10.P48` - M111 2024-4T negative-filing edge case verification

Tracked rollout item per 2026-05-28 user-directed gradual extension of PDF extraction discipline. Tasks ledger holds the detailed scope. Plan step granularity will be added when this phase is picked up for execution.

- [x] `W10.P48.S205` - Verify M111 2024-4T negative-filing scenario corpus-vs-formula resolution (tasklist #74); `src/aeat/_data/registry/aeat/modelos/111.toml src/aeat/tests/fixtures/justificantes/111/2024-4T.pdf`.

### Phase `W10.P49` - Verification chain extension as gaps close

Tracked rollout item per 2026-05-28 user-directed gradual extension of PDF extraction discipline. Tasks ledger holds the detailed scope. Plan step granularity will be added when this phase is picked up for execution.

- [x] `W10.P49.S206` - Extend test_verification_chain coverage as M130/M390/M180/M111 gaps close (tasklist #75); `src/aeat/adapters/inbound/declaracion/test_verification_chain.py`.

### Phase `W10.P50` - M100 leaf-profile extension (W10.P49 follow-up)

M100 verification chain currently EXTRACTION-ONLY because leaf inputs (017x family - base imponible general components) are absent from the declaracion_pdf profile target_casillas. M100 has full cuota-chain formulas in the registry but engine can't recompute without those leaves supplied as observations. Expand the M100 (2021/2022/2023) profiles target_casillas to include the leaf inputs via bbox_anchored where the printed form supports them. Transitions M100 ×3 revisions EXTRACTION-ONLY → VERIFIED across the 3 corpus PDFs.

- [x] `W10.P50.S207` - Expand M100 (2021/2022/2023) declaracion_pdf profiles target_casillas to include leaf inputs so engine recomputes cuota-chain closure (tasklist #79); `src/aeat/_data/registry/aeat/modelos/100/revisions/`.

### Phase `W10.P51` - M303 formula coverage authoring (W10.P49 follow-up - headline IVA)

M303 verification chain currently EXTRACTION-ONLY because no closure formulas defined in the registry for M303. M303 has 16 named_label extraction targets across 2 template revisions and 15 corpus PDFs round-trip clean - but the engine can't recompute anything because formulas are absent. M303 IS the headline IVA quarterly modelo for autónomos. Author the closure formula DAG citing AEAT Orden HAC/819/2024 + LIVA/RD-Leg 1/1993 authority: cuota-resultado (box 71 = box 69 - box 70 + box 109), resultado-régimen-general (box 46 = box 27 - box 45), suma-resultados (box 64), apportionment estado/foral (box 66 / box 77). Largest mission-leverage follow-up - transitions M303 ×2 revisions EXTRACTION-ONLY → VERIFIED across 15 corpus PDFs once formulas land + corpus regen mirrors M130 task #71.

- [x] `W10.P51.S208` - Author M303 closure formula DAG citing Orden HAC/819/2024 + LIVA authority for cuota-resultado box 71 resultado-regimen-general box 46 suma-resultados box 64 apportionment box 66 (tasklist #81); `src/aeat/_data/registry/aeat/modelos/303/revisions/`.

### Phase `W10.P52` - M303 corpus regeneration with formula-consistent values (W10.P51 follow-up)

Following W10.P51 M303 formula reconciliation: engine recomputes resultado-regimen-general correctly via box 27 - box 45, but corpus uniform-1000.00 sanitisation makes FORMULA-MISMATCH (engine output 0 vs printed 1000). Apply M130 task #71 fix pattern: extend _generate.py with _draw_modelo_303_corpus + _compute_m303_closure deriving intermediate + closure values from leaf inputs via the M303 formula DAG. Regenerate 15 M303 corpus PDFs (8 new-template 2023-1T..2024-4T + 7 legacy 2021-2T..2022-4T) with formula-consistent values. M303 ×2 revisions × 15 corpus PDFs transition FORMULA-MISMATCH → VERIFIED. Headline IVA mission proof.

- [x] `W10.P52.S209` - Regenerate 15 M303 corpus PDFs with formula-consistent values per the M130 task 71 pattern (tasklist #82); `src/aeat/tests/fixtures/justificantes/303/ src/aeat/tests/fixtures/justificantes/_generate.py`.

### Phase `W10.P53` - M036 NOT-CHAIN-READY resolution

Resolve M036 fixture period mismatch surfaced by W10.P49 NOT-CHAIN-READY classification

- [x] `W10.P53.S211` - Rename fixture 2025-0A.pdf to 2025-alta.pdf and add EXTRACTION-ONLY chain test for M036 period=alta (tasklist #80); `src/aeat/tests/fixtures/justificantes/036/ src/aeat/adapters/inbound/declaracion/test_verification_chain.py`.
- [x] `W10.P53.S212` - Regenerate 2 M390 corpus fixtures with formula-consistent values so resultado-regimen-general transitions FORMULA-MISMATCH to VERIFIED (tasklist #78); `src/aeat/tests/fixtures/justificantes/390/ src/aeat/tests/fixtures/justificantes/_generate.py src/aeat/_data/registry/aeat/modelos/390/revisions/ src/aeat/adapters/inbound/declaracion/test_parser_boundary.py`.

### Phase `W10.P54` - Justificante extractor regex generalisation (W10.P41 follow-up)

32 failures in test_corpus_sidecar_roundtrip.py - newly-added justificante corpus PDFs across many modelos have receipt layouts unmatched by current justificante extractor regex tiers. These are EXTRACTOR REGEX GENERALISATION gaps (not discipline gaps - discipline was already aligned in W10.P41). Per-modelo extractor expansion: inspect failing corpus PDFs, identify receipt-layout variations, extend regex tiers to handle them. Real receipt-layout work, not architectural.

- [x] `W10.P54.S213` - Extend justificante extractor regex tiers to cover 32 currently-failing corpus-sidecar-roundtrip cases across the modelos surfaced in W10.P41 (tasklist #76); `src/aeat/adapters/inbound/justificante/_extract.py src/aeat/adapters/inbound/justificante/_parsers/`.

### Phase `W10.P55` - test_parser.py fixture-test parity for 13 newly-added corpus modelos (W10.P54 surfaced)

16 pre-existing failures in src/aeat/adapters/inbound/justificante/test_parser.py across M036/M115/M123/M131/M180/M184/M193/M232/M347/M349/M369/M720/M840. Fixtures were added by prior campaign steps (#42/#43/#44/#45/#56 etc.) without parallel test_parser.py support - only test_corpus_sidecar_roundtrip.py was extended. Add per-modelo test_parser.py entries mirroring the existing M111/M130/M303/M390 pattern. Lower priority than verification chain but warrants completeness.

- [x] `W10.P55.S214` - Add per-modelo test_parser.py entries for 13 newly-added corpus modelos following the M111/M130/M303/M390 pattern (tasklist #84); `src/aeat/adapters/inbound/justificante/test_parser.py`.

### Phase `W10.P56` - purchase-invoice OCR ADR ratification (W10.P44 research follow-up)

Author and land the purchase-invoice-ocr-extraction-discipline ADR, ratifying the discipline analogue derived from the W10.P44 OCR evidence research closure. Supersedes the 2026-05-12 receipt-OCR ADR on OCR implementation contract.

- [x] `W10.P56.S215` - Author and commit the purchase-invoice-ocr-extraction-discipline ADR; `.vault/adr/2026-05-30-purchase-invoice-ocr-extraction-discipline-adr.md`.

## Wave `W11` - Forward-horizon follow-ups (tracked beyond campaign-close)

Forward-looking work tracked beyond the 2026-05-30 campaign close per user directive. Each phase corresponds to a tasklist follow-up item. Includes the OCR new-campaign starting point (next-campaign per the 2026-05-30 ADR), within-campaign follow-ups (M303 closure DAG extension, M100 borrador chain extension, EXTRACTION-ONLY transitions where formulas can land), and ongoing discipline items (bank-PDF provider expansion, verification chain regression monitoring, justificante test parity recurring, full-suite baseline+delta discipline). Driven incrementally per priority - does not block campaign-complete status.

### Phase `W11.P57` - M303 closure DAG extension - box 64/66/69/71 per LIVA + Orden HAC/819/2024 authority (tasklist #88)

Forward-horizon follow-up tracked beyond campaign close. Detail in matching tasklist entry.


### Phase `W11.P58` - M100 borrador-surface verification chain - VERIFIED via the per-año class dispatch (tasklist #87)

Forward-horizon follow-up tracked beyond campaign close. Detail in matching tasklist entry.

- [x] `W11.P58.S217` - Extend borrador extractor registry to 2021-2025, synthesize engine-derived corpus PDFs (reportlab, invariant=True), and add M100 x3 VERIFIED parametrised verification chain test proving 0545/0546/0585/0586 closure casillas match engine output; `src/aeat/adapters/inbound/borrador/_extractors/__init__.py src/aeat/adapters/inbound/borrador/test_verification_chain_borrador.py src/aeat/tests/fixtures/borrador/`.

### Phase `W11.P59` - EXTRACTION-ONLY to VERIFIED transitions where AEAT-authored formulas exist for the modelo (tasklist #90)

Forward-horizon follow-up tracked beyond campaign close. Detail in matching tasklist entry.

- [x] `W11.P59.S218` - Audit M349 closure-formula feasibility against Orden HAC/174/2020 Anexo Diseño de Registro; `establish EXTRACTION-ONLY-intrinsic domain verdict; update verification chain test docstring with AEAT-published arithmetic authority; `src/aeat/adapters/inbound/declaracion/test_verification_chain.py`.

### Phase `W11.P60` - Bank-PDF provider expansion BBVA Santander Caixabank ING per the W10.P42 ADR framework (tasklist #89)

Forward-horizon follow-up tracked beyond campaign close. Detail in matching tasklist entry.


### Phase `W11.P61` - Verification chain regression-monitoring discipline - recurring full-suite cadence (tasklist #91)

Forward-horizon follow-up tracked beyond campaign close. Detail in matching tasklist entry.


### Phase `W11.P62` - Justificante test_parser + sidecar parity recurring as new modelos enroll (tasklist #92)

Forward-horizon follow-up tracked beyond campaign close. Detail in matching tasklist entry.


### Phase `W11.P63` - Full-suite baseline+delta discipline per post-rush audit Finding F (tasklist #93)

Forward-horizon follow-up tracked beyond campaign close. Detail in matching tasklist entry.


### Phase `W11.P64` - Purchase-invoice OCR implementation - next campaign starting point per 2026-05-30 ADR (tasklist #86)

Forward-horizon follow-up tracked beyond campaign close. Detail in matching tasklist entry.


### Phase `W11.P66` - M100 borrador-surface verification chain

Extend borrador extractor registry for años 2021/2022/2023, synthesize formula-consistent corpus, and add verification chain test proving M100 ×3 revisions VERIFIED via borrador parse surface


## Wave `W12` - m303-closure-dag-extension-boxes-64-66-69-71

Extend M303 closure formula DAG with boxes 64, 66, 69 (corrected), and 71 per Orden HAC/819/2024 art. 1 §§4-6.

### Phase `W12.P65` - closure-dag-boxes-64-66-69-71-verified

Extend formula DAG: add boxes 64 (suma de resultados), 66 (atribuible Estado), correct box 69, add box 71 (resultado final); regenerate corpus PDFs; add 32 VERIFIED tests.

- [x] `W12.P65.S216` - Extend M303 closure formula DAG with boxes 64 (suma de resultados), 66 (atribuible Estado), corrected 69 (66+77+68-78), and 71 (69-70+109) per Orden HAC/819/2024 art. 1; `add legal ref and corpus HTML; update casillas input_kind to computed; regenerate 16 corpus PDFs; add 32 VERIFIED engine-recomputes tests for all 4 closure boxes (tasklist #88); `src/aeat/_data/registry/aeat/modelos/303/revisions/2023-y-siguientes/ src/aeat/_data/registry/aeat/legal/iva.toml src/aeat/_data/corpus/normatives/html/orden-hac-819-2024-art-1.html src/aeat/tests/fixtures/justificantes/_generate.py src/aeat/tests/fixtures/justificantes/303/ src/aeat/adapters/inbound/declaracion/test_verification_chain.py`.
