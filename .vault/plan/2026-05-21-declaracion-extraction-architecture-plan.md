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

- [ ] `W03.P05.S18` - Sweep the AEAT Diseno and instructions corpus and casilla registry data for modelos 303, 180, and 190 and append any surfaced schema-tweak Steps via the vault plan CLI; `src/aeat/_data/registry/aeat/modelos/`.

### Phase `W03.P06` - modelo 303 and 180 profile authoring

Author declaracion_pdf extraction profiles for modelos 303 and 180.

- [ ] `W03.P06.S19` - Author the declaracion_pdf extraction profile for Modelo 303 from the AEAT Diseno and instructions; `src/aeat/_data/registry/aeat/modelos/303/`.
- [ ] `W03.P06.S20` - Author the declaracion_pdf extraction profile for Modelo 180 from the AEAT Diseno and instructions; `src/aeat/_data/registry/aeat/modelos/180/`.

### Phase `W03.P07` - modelo 190 stub repair and modelo 130 cross-check

Replace modelo 190's decl.* stub targets and restore the modelo 130 cross-check stanza.

- [ ] `W03.P07.S21` - Replace Modelo 190's abstract decl.* stub target_casillas with the real numeric and labelled targets the form prints; `src/aeat/_data/registry/aeat/modelos/190/`.
- [ ] `W03.P07.S22` - Restore the Modelo 130 03 = 01 - 02 intra-filing cross-check as a verification_expectations stanza; `src/aeat/_data/registry/aeat/modelos/130/`.
- [ ] `W03.P07.S23` - Verify modelos 130, 111, 115, and 123 still parse and validate unchanged after the numeric-tier changes; `src/aeat/adapters/inbound/declaracion/test_parser_boundary.py`.

## Wave `W04` - named-field tier

Named-field tier Wave. Corrects or removes the dead modelo 720 and 840 stub profiles, registers modelo 037 which has no registry presence today, and authors named-field declaracion_pdf profiles for modelos 036, 037, 369, 720, and 840 on the W02 primitive. Deferred content of the ADR, in-scope as part of this umbrella plan. Hard-depends on W02; depends on W01. Authorised by the declaracion-extraction-architecture ADR and its research.

### Phase `W04.P08` - scoped named-field discovery

Scoped discovery sweep of the named-field modelo corpus and registry presence.

- [ ] `W04.P08.S24` - Sweep the named-field modelo corpus and registry presence for modelos 036, 037, 369, 720, and 840 and append any surfaced schema-tweak Steps via the vault plan CLI; `src/aeat/_data/registry/aeat/modelos/`.
- [ ] `W04.P08.S80` - Classify per dead-stub modelo 184 193 232 347 349 720 and 840 whether each non-matchable decl slug target resolves to a numeric casilla or a named-field target; `src/aeat/_data/registry/aeat/modelos/`.
- [ ] `W04.P08.S86` - Decide fetch-versus-defer for the source-blocked Modelo 037 which has no Diseno instructions or fixtures in the corpus and record the fetch-or-descope decision; `src/aeat/_data/registry/aeat/modelos/037/`.

### Phase `W04.P09` - dead-stub repair and modelo 037 registration

Correct or remove the dead 720/840 stubs and register modelo 037.

- [ ] `W04.P09.S25` - Correct or remove the dead Modelo 720 declaracion_pdf stub profile so it no longer loads green; `src/aeat/_data/registry/aeat/modelos/720/`.
- [ ] `W04.P09.S26` - Correct or remove the dead Modelo 840 declaracion_pdf stub profile so it no longer loads green; `src/aeat/_data/registry/aeat/modelos/840/`.
- [ ] `W04.P09.S27` - Register Modelo 037 in the registry which has no registry presence today; `src/aeat/_data/registry/aeat/modelos/037/`.

### Phase `W04.P14` - newly-surfaced dead-stub repair

Repair the five dead-stub declaracion_pdf profiles W01 discovery surfaced beyond the ADR-named set: modelos 184 193 232 347 and 349 each load green today but extract nothing; replace each non-matchable decl slug stub with the real numeric or named-field targets its classification determined.

- [ ] `W04.P14.S81` - Replace the Modelo 184 dead decl slug stub targets with the real numeric or named-field targets its classification determined; `src/aeat/_data/registry/aeat/modelos/184.toml`.
- [ ] `W04.P14.S82` - Replace the Modelo 193 dead decl slug stub targets with the real numeric or named-field targets its classification determined; `src/aeat/_data/registry/aeat/modelos/193.toml`.
- [ ] `W04.P14.S83` - Replace the Modelo 232 dead decl slug stub targets with the real numeric or named-field targets its classification determined; `src/aeat/_data/registry/aeat/modelos/232/`.
- [ ] `W04.P14.S84` - Replace the Modelo 347 dead decl slug stub targets with the real numeric or named-field targets its classification determined; `src/aeat/_data/registry/aeat/modelos/347.toml`.
- [ ] `W04.P14.S85` - Replace the Modelo 349 dead decl slug stub targets with the real numeric or named-field targets its classification determined; `src/aeat/_data/registry/aeat/modelos/349/`.

### Phase `W04.P10` - named-field profile authoring

Author named-field declaracion_pdf profiles for modelos 036, 037, 369, 720, and 840.

- [ ] `W04.P10.S28` - Author the named-field declaracion_pdf profile for Modelo 036 using the W02 named_label primitive; `src/aeat/_data/registry/aeat/modelos/036/`.
- [ ] `W04.P10.S29` - Author the named-field declaracion_pdf profile for Modelo 037 using the W02 named_label primitive; `src/aeat/_data/registry/aeat/modelos/037/`.
- [ ] `W04.P10.S30` - Author the named-field declaracion_pdf profile for Modelo 369 using the W02 named_label primitive; `src/aeat/_data/registry/aeat/modelos/369/`.
- [ ] `W04.P10.S31` - Author the named-field declaracion_pdf profile for Modelo 720 using the W02 named_label primitive; `src/aeat/_data/registry/aeat/modelos/720/`.
- [ ] `W04.P10.S32` - Author the named-field declaracion_pdf profile for Modelo 840 using the W02 named_label primitive; `src/aeat/_data/registry/aeat/modelos/840/`.

## Wave `W05` - verification and rollout

Verification Wave. Adds real per-modelo round-trip parse tests against PDF corpus fixtures, confirms the snapshot-build gate is green, and confirms all 26 modelos validate. Depends on every preceding Wave. Authorised by the declaracion-extraction-architecture ADR and its research.

### Phase `W05.P11` - round-trip parse tests and gate verification

Add per-modelo round-trip parse tests and confirm the snapshot-build gate is green.

- [ ] `W05.P11.S33` - Add a real round-trip parse test for Modelo 303 against a PDF corpus fixture; `src/aeat/adapters/inbound/declaracion/test_parser_boundary.py`.
- [ ] `W05.P11.S34` - Add a real round-trip parse test for Modelo 180 against a PDF corpus fixture; `src/aeat/adapters/inbound/declaracion/test_parser_boundary.py`.
- [ ] `W05.P11.S35` - Add a real round-trip parse test for Modelo 190 against a PDF corpus fixture; `src/aeat/adapters/inbound/declaracion/test_parser_boundary.py`.
- [ ] `W05.P11.S36` - Add a real round-trip parse test for Modelo 036 against a PDF corpus fixture; `src/aeat/adapters/inbound/declaracion/test_parser_boundary.py`.
- [ ] `W05.P11.S37` - Add a real round-trip parse test for Modelo 037 against a PDF corpus fixture; `src/aeat/adapters/inbound/declaracion/test_parser_boundary.py`.
- [ ] `W05.P11.S38` - Add a real round-trip parse test for Modelo 369 against a PDF corpus fixture; `src/aeat/adapters/inbound/declaracion/test_parser_boundary.py`.
- [ ] `W05.P11.S39` - Add a real round-trip parse test for Modelo 720 against a PDF corpus fixture; `src/aeat/adapters/inbound/declaracion/test_parser_boundary.py`.
- [ ] `W05.P11.S40` - Add a real round-trip parse test for Modelo 840 against a PDF corpus fixture; `src/aeat/adapters/inbound/declaracion/test_parser_boundary.py`.
- [ ] `W05.P11.S41` - Confirm the snapshot-build gate is green and all 26 modelos validate; `src/aeat/domain/calculations/registry/test_committed_registry.py`.

### Phase `W05.P15` - paper-trail cleanup

Correct the four stale documents that still describe the deleted per-modelo extractor classes as if implemented so no surviving document or comment contradicts the registry-profile-driven generic-parser architecture this plan executes.

- [ ] `W05.P15.S87` - Correct the modelo-115 calc-verify ADR prose that still describes the deleted per-modelo extractor classes as implemented; `.vault/adr/2026-04-27-modelo-115-calc-verify-adr.md`.
- [ ] `W05.P15.S88` - Correct the modelo-303 calc-verify ADR prose that still describes the deleted per-modelo extractor classes as implemented; `.vault/adr/2026-04-27-modelo-303-calc-verify-adr.md`.
- [ ] `W05.P15.S89` - Correct the modelo-111 rule-delta reference prose that still describes the deleted per-modelo extractor classes as implemented; `.vault/reference/2026-04-27-modelo-111-rule-delta-reference.md`.
- [ ] `W05.P15.S90` - Correct the stale declaracion detector module comment that still describes the deleted per-modelo extractor surface; `src/aeat/adapters/inbound/declaracion/_detect.py`.
