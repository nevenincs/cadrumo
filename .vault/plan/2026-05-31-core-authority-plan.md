---
tags:
  - '#plan'
  - '#core-authority'
date: '2026-05-31'
modified: '2026-05-31'
tier: L4
related:
  - '[[2026-05-31-core-authority-adr]]'
  - '[[2026-05-31-core-authority-action-tracker-v2-reference]]'
  - '[[2026-05-30-identity-primitives-adr]]'
  - '[[2026-05-30-identity-primitives-plan]]'
  - '[[2026-05-31-core-authority-research]]'
---
# `core-authority` `core-authority campaign` plan

## Epic intent

Establish src/aeat/core/ as the single authoritative source for every cross-layer shared definition across 1,655 Python files: enums, constants, Protocols, TypeAliases, Literals, error hierarchies, and identity primitives. This Epic executes all 91 action rows from the core-authority-action-tracker-v2-reference, resolves 471 illegal import-direction edges across 9 direction pairs, eliminates 193 same-name multi-declarations, and extends the enforcement test from 4 to 10 structural clauses. External PM association: GitHub milestone 'core-as-authority' on project board chore/476-restructure-execution, tracking the full hexagonal-architecture compliance surface. Timeline horizon: 12 Waves over 6-8 weeks. Agent team: vaultspec-high-executor for Waves 01-03 and 06-10 (high-risk structural changes), vaultspec-standard-executor for Waves 04-05 and 11-12 (consolidation and enforcement). The identity-primitives plan (W01-W05 predecessor, 69 Steps, 100% closed) provides the structural precedent this Epic extends to all definition kinds.

## Wave `W01` - latent-bug fixes

Fix the two latent runtime bugs (FIX-001 ExportFormatError double-registration, FIX-002 _parse_decimal arg-order reversal) surfaced by the semantic audit before any structural migration touches those paths. Rule 3 governs FIX-001; aeat-calculation-grounding governs FIX-002. Both fixes carry mandatory regression tests; W02 may not begin until both Steps are closed and the adapter test suite passes sequentially.

### Phase `W01.P01` - ExportFormatError rename and parse-decimal fix

Rename the adapter ExportFormatError class to AeatExportFormatError to eliminate the double-registration collision in core/errors/_registry.py (FIX-001), update the four adapter call sites, then fix the reversed _parse_decimal argument at line 402 with a regression test proving correct decimal extraction (FIX-002). Both Steps must pass the adapter suite before W02 opens.

- [x] `W01.P01.S01` - rename ExportFormatError to AeatExportFormatError in the adapter export errors module, update the four call sites in the same package, and assert the error-registry contains exactly one ExportFormatError entry pointing at the application canonical class; `FIX-001, Rule 3; `src/aeat/adapters/outbound/aeat/export/_errors.py`.
- [x] `W01.P01.S02` - swap the _parse_decimal call arguments at line 402 to _parse_decimal(raw, field) and add a regression test asserting that a known fixture export string yields the correct Decimal value and not a validation error; `FIX-002, aeat-calculation-grounding; `src/aeat/domain/calculations/registry/_export_parse.py`.

## Wave `W02` - CoreError root and error-class consolidation

Introduce the CoreError base class in core/errors/_base.py and migrate all layer-specific error hierarchies to descend from it, satisfying Rule 3. This Wave also collapses the four RAG-surfaced error-class semantic duplicates (MERGE-011 ValidationError family, MERGE-012 NotFoundError family, FIX-001 AeatExportFormatError rename, PROMOTE-003 CoreError promotion). W03 depends on this Wave because constant-centralisation Steps that add entries to core/external_constants.py must not land before the error hierarchy is stable.

### Phase `W02.P02` - CoreError base and ValidationError family

Declare CoreError in core/errors/_base.py, export it through core/errors/__init__, then migrate all five ValidationError subclasses across layers to descend from CoreError, satisfying Rule 3 and MERGE-011.

- [x] `W02.P02.S03` - declare CoreError as the root exception class, export it through core/errors/__init__, and add a non-tautological test asserting that catching CoreError catches a concrete subclass instance; `PROMOTE-003, Rule 3; `src/aeat/core/errors/_base.py`.
- [x] `W02.P02.S04` - make the core/errors ValidationError subclass descend from CoreError and assert the catch order is well-defined; `MERGE-011, Rule 3; `src/aeat/core/errors/__init__.py`.
- [x] `W02.P02.S05` - make the domain/filing ValidationError subclass descend from CoreError and run the filing test suite sequentially to confirm catch-order is preserved; `MERGE-011, Rule 3; `src/aeat/domain/filing/_errors.py`.
- [x] `W02.P02.S06` - make the two application-layer ValidationError subclasses (application/export and application/filing) descend from CoreError and run the application test suite sequentially; `MERGE-011, Rule 3; `src/aeat/application/`.
- [x] `W02.P02.S07` - make the adapters ValidationError subclass descend from CoreError and run the adapters test suite sequentially; `MERGE-011, Rule 3; `src/aeat/adapters/_errors.py`.

### Phase `W02.P03` - NotFoundError family consolidation

Consolidate the three NotFoundError declarations under a single CoreNotFoundError base in core/errors/_not_found.py, making domain subclasses explicit descendants, satisfying MERGE-012 and Rule 3.

- [x] `W02.P03.S08` - rename the core/errors/_not_found.py NotFoundError to CoreNotFoundError, update its __all__ export, and assert it descends from CoreError; `MERGE-012, Rule 3; `src/aeat/core/errors/_not_found.py`.
- [x] `W02.P03.S09` - make the first domain NotFoundError subclass an explicit subclass of CoreNotFoundError and run the relevant domain test suite sequentially; `MERGE-012, Rule 3; `src/aeat/domain/`.
- [x] `W02.P03.S10` - make the second domain NotFoundError subclass an explicit subclass of CoreNotFoundError and run the sequential pytest suite confirming no caller regressions; `MERGE-012, Rule 3; `src/aeat/domain/`.

## Wave `W03` - constant centralisation to core

Relocate cross-layer constants to core/external_constants.py per Rules 4 and 6, and delete eight zero-consumer dead constants per the aeat-source-hygiene rule. Phases group by concern cluster: i18n constants (RELOC-001..003), URL-to-Settings migration (RELOC-004..008), regulatory threshold merge (RELOC-012, MERGE-001, RELOC-013), dead-constant deletes (DELETE-001..008), and low-risk renames for same-name constant collisions (RENAME-006..009). W04 depends on this Wave because enum-centralisation Steps may import constants that must already be in their canonical location.

### Phase `W03.P04` - i18n constants relocation

Move the three i18n constants OUTPUT_LANGUAGE_ENV_VAR, DEFAULT_OUTPUT_LANGUAGE, SUPPORTED_OUTPUT_LANGUAGES from core/i18n/_render.py to core/external_constants.py per Rule 4 and RELOC-001..003, then update the three consumer import paths.

- [x] `W03.P04.S11` - move OUTPUT_LANGUAGE_ENV_VAR from core/i18n/_render.py to core/external_constants.py and update the three consumer import paths to the canonical location; `RELOC-001, Rule 4; `src/aeat/core/external_constants.py`.
- [x] `W03.P04.S12` - move DEFAULT_OUTPUT_LANGUAGE from core/i18n/_render.py to core/external_constants.py and update the two consumer import paths; `RELOC-002, Rule 4; `src/aeat/core/external_constants.py`.
- [x] `W03.P04.S13` - move SUPPORTED_OUTPUT_LANGUAGES from core/i18n/_render.py to core/external_constants.py, update the twelve consumer import paths, and run the i18n test suite sequentially; `RELOC-003, Rule 4; `src/aeat/core/external_constants.py`.

### Phase `W03.P05` - URL constants to Settings migration

Replace the five module-scope AnyUrl constant declarations in domain oracle modules with Settings.external_constants() lazy call-site reads per Rule 6 and RELOC-004..008, eliminating domain-layer URL constants as Rule 6 violations.

- [x] `W03.P05.S14` - replace AEAT_GROI_URL module-scope constant with Settings.external_constants() lazy read at all five call sites and confirm oracle test passes sequentially; `RELOC-004, Rule 6; `src/aeat/domain/calculations/registry/_groi_oracle.py`.
- [x] `W03.P05.S15` - replace AEAT_NIF_IVA_VERIFICATION_URL module-scope constant with Settings.external_constants() lazy read at the three call sites; `RELOC-005, Rule 6; `src/aeat/domain/calculations/registry/_aeat_nif_iva_oracle.py`.
- [x] `W03.P05.S16` - replace AEAT_NIF_IVA_ENTRY_URL module-scope constant with Settings.external_constants() lazy read at the three call sites; `RELOC-006, Rule 6; `src/aeat/domain/calculations/registry/_aeat_nif_iva_oracle.py`.
- [x] `W03.P05.S17` - replace RENTA_WEB_OPEN_LANDING_URL module-scope constant with Settings.external_constants() lazy read at the two call sites; `RELOC-007, Rule 6; `src/aeat/domain/calculations/registry/_renta_web_open_oracle.py`.
- [x] `W03.P05.S18` - replace RENTA_WEB_OPEN_APP_URL module-scope constant with Settings.external_constants() lazy read at the three call sites and run the oracle test suite sequentially; `RELOC-008, Rule 6; `src/aeat/domain/calculations/registry/_renta_web_open_oracle.py`.

### Phase `W03.P06` - regulatory threshold consolidation

Consolidate the two M347 threshold declarations to core/external_constants.py as M347_THRESHOLD_EUR and migrate four callers (RELOC-012, MERGE-001), then move THRESHOLD_720_EUR_PER_CLASS to core/external_constants.py as MODELO_720_REPORTING_THRESHOLD_EUR (RELOC-013).

- [x] `W03.P06.S19` - add M347_THRESHOLD_EUR = Decimal('3005.06') to core/external_constants.py, delete the domain/modelos copy and the application/aggregation copy, and update the four caller import paths; `MERGE-001, RELOC-012, Rule 6; `src/aeat/core/external_constants.py`.
- [x] `W03.P06.S20` - move THRESHOLD_720_EUR_PER_CLASS to core/external_constants.py as MODELO_720_REPORTING_THRESHOLD_EUR and update the one caller import path; `RELOC-013, Rule 6; `src/aeat/core/external_constants.py`.

### Phase `W03.P07` - dead-constant deletion

Delete all eight zero-consumer constants (DELETE-001..008) after ripgrep confirms zero callers in each case, satisfying the aeat-source-hygiene rule.

- [x] `W03.P07.S21` - delete SYSTEM_BUCKET_ID and WORKFLOW_STATE_OBJECT_ID from application/workflow/_events.py after ripgrep confirms zero callers; `DELETE-001, DELETE-002, aeat-source-hygiene; `src/aeat/application/workflow/_events.py`.
- [x] `W03.P07.S22` - delete DAYS_PER_YEAR from domain/fincas/_amortization_ledger.py after ripgrep confirms zero callers; `DELETE-003, aeat-source-hygiene; `src/aeat/domain/fincas/_amortization_ledger.py`.
- [x] `W03.P07.S23` - delete LATIN_1_ENCODING, PROVENANCE_SOURCE_MANUAL_CLI, and PDF_MIME_TYPE from core/external_constants.py after ripgrep confirms zero callers for each; `DELETE-004, DELETE-005, DELETE-006, aeat-source-hygiene; `src/aeat/core/external_constants.py`.
- [x] `W03.P07.S24` - delete ASSETS_AMORTIZATION_LEDGER_FILENAME, ASSETS_LEDGER_FILENAME, and INVENTORY_LEDGER_FILENAME from the storage profile assets modules after ripgrep confirms zero callers; `DELETE-007, DELETE-008, aeat-source-hygiene; `src/aeat/adapters/persistence/storage/profile/`.

### Phase `W03.P08` - constant name-collision renames

Eliminate constant name collisions: verify and delete the five zero-consumer constants in application/aggregation/_shared_issue_reasons.py (RENAME-006), disambiguate SCHEMA_VERSION to ASSETS_SCHEMA_VERSION and INVENTORY_SCHEMA_VERSION in the two domain/profile subpackages (RENAME-007), rename the two ERROR_CODES constants to domain-specific names (RENAME-009).

- [x] `W03.P08.S25` - verify zero callers via ripgrep then delete UNSUPPORTED_DIRECTION, UNSUPPORTED_CURRENCY, UNCLASSIFIED_BUSINESS_STATE, PERSONAL_TRANSACTION, and OUTSIDE_PERIOD from application/aggregation/_shared_issue_reasons.py; `RENAME-006, aeat-source-hygiene; `src/aeat/application/aggregation/_shared_issue_reasons.py`.
- [x] `W03.P08.S26` - rename SCHEMA_VERSION to ASSETS_SCHEMA_VERSION in domain/profile/assets/__init__.py and update the two call sites; `RENAME-007, Rule 4; `src/aeat/domain/profile/assets/__init__.py`.
- [x] `W03.P08.S27` - rename SCHEMA_VERSION to INVENTORY_SCHEMA_VERSION in domain/profile/inventory/__init__.py and update its call sites; `RENAME-007, Rule 4; `src/aeat/domain/profile/inventory/__init__.py`.
- [x] `W03.P08.S28` - rename application/aggregation/_service.py ERROR_CODES to AggregationErrorCodes and update the four caller references; `RENAME-009, Rule 4; `src/aeat/application/aggregation/_service.py`.
- [x] `W03.P08.S29` - rename application/operator_surface/_contract.py ERROR_CODES to OperatorSurfaceErrorCodes and update caller references; `RENAME-009, Rule 4; `src/aeat/application/operator_surface/_contract.py`.

## Wave `W04` - enum centralisation

Consolidate duplicate and mis-placed enum declarations per Rule 7. Phases cover: CalendarCCAA elimination and CCAA migration (MERGE-002, RELOC-021, RELOC-022), ProfileFactValue canonical-site collapse (MERGE-003, RELOC-023, RELOC-024), IVA rate mapping consolidation after BOE cross-reference (MERGE-013), STRICT_FROZEN pre-condition audit and merge (MERGE-014), and ActorLabel disambiguation (MERGE-015). The CCAA evaluate-for-promotion step (RELOC-021) is a bounded audit that produces a documented decision, not an open-ended investigation. W05 depends on this Wave because type-alias centralisation Steps import the enum canonical sites settled here.

### Phase `W04.P09` - CalendarCCAA elimination and CCAA migration

Delete CalendarCCAA from domain/deadlines/_festivos.py (MERGE-002, RELOC-022) because it is a 100% geographic duplicate of CCAA in domain/profile/_ccaa.py, and migrate the six callers in domain/deadlines/ to use CCAA directly. Conduct the bounded CCAA-promotion audit (RELOC-021) and document the placement decision.

- [x] `W04.P09.S30` - audit whether CCAA is consumed outside domain/ to determine if Rule 1 clause (a) triggers promotion to core/geography.py; `produce a one-sentence placement decision persisted in the commit message; RELOC-021, Rule 1; `src/aeat/domain/profile/_ccaa.py`.
- [x] `W04.P09.S31` - delete CalendarCCAA from domain/deadlines/_festivos.py and migrate the first two domain/deadlines/ callers to import CCAA from domain/profile/_ccaa.py; `MERGE-002, RELOC-022, Rule 7; `src/aeat/domain/deadlines/_festivos.py`.
- [x] `W04.P09.S32` - migrate the remaining four domain/deadlines/ callers of CalendarCCAA to CCAA and run the deadlines test suite sequentially to confirm zero regressions; `MERGE-002, Rule 7; `src/aeat/domain/deadlines/`.

### Phase `W04.P10` - ProfileFactValue canonical collapse

Establish domain/calculations/registry/_schema.py ProfileFactValue as the single canonical declaration, delete domain/user_profile/_values.py copy (MERGE-003, RELOC-024), and alias the application/overview/_explain.py variant to the canonical (RELOC-023).

- [x] `W04.P10.S33` - delete the ProfileFactValue TypeAlias from domain/user_profile/_values.py, switch its three consumers to import from domain/calculations/registry/_schema.py, and run the user_profile suite sequentially; `MERGE-003, RELOC-024, Rule 7; `src/aeat/domain/user_profile/_values.py`.
- [x] `W04.P10.S34` - alias _ProfileFactValue in application/overview/_explain.py to the canonical domain/calculations/registry/_schema.py ProfileFactValue and run the overview test suite; `RELOC-023, Rule 1; `src/aeat/application/overview/_explain.py`.

### Phase `W04.P11` - IVA rate mapping BOE cross-reference and consolidation

Cross-reference the two missing IVA rate entries against BOE to confirm oversight or intentional exclusion, then consolidate to the single canonical mapping in domain/iva/_classification.py with a coverage test (MERGE-013, Rule 7).

- [x] `W04.P11.S35` - cross-reference the two missing entries in domain/iva/_classification.py _IVA_RATE_TO_VAT_KIND against the BOE IVA rate schedule and document the finding as intentional exclusion or oversight in the commit message; `MERGE-013, Rule 7; `src/aeat/domain/iva/_classification.py`.
- [x] `W04.P11.S36` - consolidate the IVA rate mapping to domain/iva/_classification.py, delete the application/calculations/ copy, update the four callers, and add a coverage test asserting every BOE-confirmed IVA rate has a mapping entry; `MERGE-013, Rule 7; `src/aeat/domain/iva/_classification.py`.

### Phase `W04.P12` - STRICT_FROZEN pre-condition audit and canonical merge

Audit all 10 _STRICT_FROZEN declarations to confirm identical ConfigDict values, then consolidate to STRICT_FROZEN_CONFIG in core/_models.py exported via core/__init__.py, migrating every production module (MERGE-014, Rule 10).

- [x] `W04.P12.S37` - audit all 10 _STRICT_FROZEN declarations across the codebase via ripgrep, compare ConfigDict values, and document any intentional divergence with module-specific names in the commit message before the merge executes; `MERGE-014, Rule 10; `src/aeat/`.
- [x] `W04.P12.S38` - declare STRICT_FROZEN_CONFIG in core/_models.py, export via core/__init__.py, and migrate the first five production modules from _STRICT_FROZEN to the canonical import; `MERGE-014, Rule 10; `src/aeat/core/_models.py`.
- [x] `W04.P12.S39` - migrate the remaining five production modules from _STRICT_FROZEN to STRICT_FROZEN_CONFIG imported from core and run the full suite sequentially to confirm zero config-drift regressions; `MERGE-014, Rule 10; `src/aeat/`.

### Phase `W04.P13` - ActorLabel disambiguation

Rename the five _ActorLabel declarations across domain/buckets and domain/modelos to domain-specific names (BucketActorLabel, ModeloActorLabel, etc.) to eliminate the five-way name collision (MERGE-015, Rule 4).

- [x] `W04.P13.S40` - rename the domain/buckets _ActorLabel declaration to BucketActorLabel and update its callers in the same package; `MERGE-015, Rule 4; `src/aeat/domain/buckets/`.
- [x] `W04.P13.S41` - rename the four domain/modelos _ActorLabel declarations to ModeloActorLabel (and three variant names) and update all callers; `run the modelos test suite sequentially; MERGE-015, Rule 4; `src/aeat/domain/modelos/`.

## Wave `W05` - type-alias and Literal centralisation

Centralise cross-layer TypeAlias, Literal, and Annotated alias declarations per Rules 1 and 4. Phases cover: ModeloCapability Literal rename (RENAME-002), ParityStatus collapse (RENAME-003), EvidenceTier collapse (RENAME-004), VerifyVerdict entrypoint duplicate removal (RENAME-005), ApplicabilityVerdict promotion audit (RENAME-011), SCHEMA_VERSION disambiguation (RENAME-007), CLAVE_MOVIL_DIAGNOSTIC_NAMESPACE review (RENAME-014), CENSUS_MODELO_SERVICE_OWNER move (RENAME-013), and SECURE_OBJECT namespace key review (RENAME-012). W06 depends on this Wave because Protocol declarations reference TypeAlias types that must be in their canonical module before conformance tests run.

### Phase `W05.P14` - registry Literal renames and parity-alias collapses

Rename ModeloCapability Literal to ModeloFilingCapability in domain/calculations/registry/_schema.py (RENAME-002), collapse ParityStatus to single definition in _parity_tapes.py (RENAME-003), collapse EvidenceTier to single definition in _schema.py (RENAME-004), and update all callers.

- [x] `W05.P14.S42` - rename ModeloCapability Literal alias to ModeloFilingCapability in domain/calculations/registry/_schema.py and update the three caller sites; `RENAME-002, Rule 4; `src/aeat/domain/calculations/registry/_schema.py`.
- [x] `W05.P14.S43` - consolidate ParityStatus to the single definition in domain/calculations/registry/_parity_tapes.py, delete the _workbook_parity.py copy, and update the two callers; `RENAME-003, Rule 4; `src/aeat/domain/calculations/registry/_parity_tapes.py`.
- [x] `W05.P14.S44` - consolidate EvidenceTier Literal to the single definition in domain/calculations/registry/_schema.py, delete the _workbook_parity.py copy, and import in _workbook_parity.py; `RENAME-004, Rule 4; `src/aeat/domain/calculations/registry/_schema.py`.

### Phase `W05.P15` - entrypoints Literal duplicate and multi-layer type reviews

Remove the entrypoints _VerifyVerdict private duplicate (RENAME-005), conduct the bounded ApplicabilityVerdict promotion audit (RENAME-011), and execute the three low-risk constant-identifier placement reviews (RENAME-012, RENAME-013, RENAME-014).

- [x] `W05.P15.S45` - remove the _VerifyVerdict private Literal from entrypoints/cli/_app_live.py and import VerifyVerdict directly from application/live/_verify.py; `RENAME-005, Rule 4; `src/aeat/entrypoints/cli/_app_live.py`.
- [x] `W05.P15.S46` - audit ApplicabilityVerdict consumers across layers; `if consumed outside domain/calculations/registry/ promote to core/, otherwise document the placement decision as same-package-only in the commit message; RENAME-011, Rule 1; `src/aeat/domain/calculations/registry/_applicability.py`.
- [x] `W05.P15.S47` - review SECURE_OBJECT_CATALOGUE_KEY, SECURE_OBJECT_DEFAULT_KEY, SECURE_OBJECT_WORKFLOW_STATE_KEY ownership and move to domain/buckets/ or application/workflow/ per the ownership decision, updating the two callers per key; `RENAME-012, Rule 4; `src/aeat/adapters/persistence/storage/_namespace_registry.py`.
- [x] `W05.P15.S48` - move CENSUS_MODELO_SERVICE_OWNER to core/external_constants.py and update the two callers; `RENAME-013, Rule 6; `src/aeat/domain/calculations/registry/_censo_modelos.py`.
- [x] `W05.P15.S49` - move CLAVE_MOVIL_DIAGNOSTIC_NAMESPACE to core/external_constants.py or document the adapter-placement rationale, then update the four callers; `RENAME-014, Rule 6; `src/aeat/adapters/outbound/aeat/auth/_clave_movil.py`.

## Wave `W06` - Protocol centralisation and SnapshotRepository conformance

Extract domain-layer repository Protocol declarations to domain/<agg>/_protocols.py files per Rule 8, break the 89 domain-to-adapters import edges (MIGRATE-003), add SnapshotRepository @runtime_checkable isinstance gate (RELOC-040, Rule 9-A), annotate SubjectTaxId on domain Protocol method signatures (PROMOTE-002), and expose AggregationSourceKind via core/__init__ (PROMOTE-004). W07 depends on this Wave because shim-delete Steps assume Protocol ports are in place before the adapter import edges they replace are removed.

### Phase `W06.P16` - domain repository Protocol extraction to _protocols.py

For every domain/_repository.py file that imports from adapters/persistence/, extract the repository interface as a Protocol to domain/<agg>/_protocols.py, have the persistence adapter implement the Protocol, and remove the inbound import edge (MIGRATE-003, Rule 8). This Phase has the highest file-count in the plan: 89 domain files across all domain aggregates.

- [x] `W06.P16.S50` - extract the StorageRecord protocol shape for domain/transactions/_repository.py to domain/transactions/_protocols.py, update the repository to import from _protocols.py, remove the adapters/persistence import edge, and run the transactions test suite; `MIGRATE-003, Rule 8; `src/aeat/domain/transactions/_protocols.py`.
- [x] `W06.P16.S51` - extract repository protocol for domain/invoices/_repository.py to domain/invoices/_protocols.py, remove the adapters import edge, and run the invoices test suite; `MIGRATE-003, Rule 8; `src/aeat/domain/invoices/_protocols.py`.
- [x] `W06.P16.S52` - extract repository protocol for domain/attachments/_repository.py to domain/attachments/_protocols.py, remove the adapters import edge, and run the attachments test suite; `MIGRATE-003, Rule 8; `src/aeat/domain/attachments/_protocols.py`.
- [x] `W06.P16.S53` - extract repository protocol for domain/modelos/_repository.py to domain/modelos/_protocols.py, remove the adapters import edge, and run the modelos test suite; `MIGRATE-003, Rule 8; `src/aeat/domain/modelos/_protocols.py`.
- [x] `W06.P16.S54` - extract repository protocol for domain/buckets/_repository.py to domain/buckets/_protocols.py, remove the adapters import edge, and run the buckets test suite; `MIGRATE-003, Rule 8; `src/aeat/domain/buckets/_protocols.py`.
- [x] `W06.P16.S55` - extract repository protocols for all remaining domain aggregate _repository.py files (domain/filing, domain/renta, domain/fincas, domain/deadlines, domain/iva, domain/profile, domain/submission, domain/calculations) to their respective _protocols.py modules, remove all adapters import edges, and run the sequential domain suite; `MIGRATE-003, Rule 8; `src/aeat/domain/`.

### Phase `W06.P17` - SnapshotRepository conformance gate and SubjectTaxId annotation

Make SnapshotRepository @runtime_checkable and add a non-tautological CI-gate test asserting isinstance for all three concrete live repositories (RELOC-040, Rule 9-A), then annotate SubjectTaxId on the three domain Protocol method signatures (PROMOTE-002) and expose AggregationSourceKind via core/__init__ (PROMOTE-004).

- [x] `W06.P17.S56` - mark SnapshotRepository with @runtime_checkable in application/live/_snapshot_base.py and add a non-tautological test asserting isinstance(repo, SnapshotRepository) for each of LiveBorradorRepository, LiveCensusRepository, and LiveExpedientesRepository; `RELOC-040, Rule 9-A; `src/aeat/application/live/_snapshot_base.py`.
- [x] `W06.P17.S57` - annotate SubjectTaxId on the method signatures of the three domain repository Protocols that declare bare-str subject_tax_id parameters; `PROMOTE-002, Rule 5; `src/aeat/domain/`.
- [x] `W06.P17.S58` - expose AggregationSourceKind via core/__init__.py or core/aggregation/__init__.py and update callers to the canonical import path; `PROMOTE-004, Rule 1; `src/aeat/core/__init__.py`.

## Wave `W07` - indirection and shim deletes

Remove the actionable shims and indirection aliases: LedgerTransactionDirection alias in three production modules and one test module (RELOC-033..036), domain.calculations passthrough init migration for five callers (RELOC-039, Rule 9-B), and the entrypoints _VerifyVerdict private duplicate (RENAME-005, already settled in W05). Phases also cover the SECURE_OBJECT catalogue-key placement decision (RENAME-012) and test constant deduplication (RENAME-008). W08 depends on this Wave because same-name duplicate collapse Steps must not import from alias sites that are being deleted here.

### Phase `W07.P18` - LedgerTransactionDirection alias removal

Remove the LedgerTransactionDirection alias from three production modules and one test module (RELOC-033..036), replacing each use with TransactionDirection imported directly, per the aeat-architecture-boundaries no-alias rule.

- [x] `W07.P18.S59` - remove LedgerTransactionDirection alias and replace with TransactionDirection direct import in application/aggregation/_renta_ledger.py; `RELOC-033, architecture-boundaries; `src/aeat/application/aggregation/_renta_ledger.py`.
- [x] `W07.P18.S60` - remove LedgerTransactionDirection alias and replace with TransactionDirection direct import in application/aggregation/_renta_income_ledger.py; `RELOC-034, architecture-boundaries; `src/aeat/application/aggregation/_renta_income_ledger.py`.
- [x] `W07.P18.S61` - remove LedgerTransactionDirection alias and replace with TransactionDirection direct import in application/aggregation/_iva_ledger.py; `RELOC-035, architecture-boundaries; `src/aeat/application/aggregation/_iva_ledger.py`.
- [x] `W07.P18.S62` - remove LedgerTransactionDirection alias from the test module application/aggregation/test_renta_ledger_helpers.py and replace with TransactionDirection direct import; `RELOC-036, architecture-boundaries; `src/aeat/application/aggregation/test_renta_ledger_helpers.py`.

### Phase `W07.P19` - domain.calculations passthrough migration and test deduplication

Migrate the five callers that use the domain.calculations short-path passthrough to direct domain.calculations.registry.* imports, then remove the passthrough symbols from __init__.py per Rule 9-B (RELOC-039). Also deduplicate SECRET_PASSPHRASE test constant via conftest (RENAME-008).

- [x] `W07.P19.S63` - migrate the first domain.calculations passthrough caller to a direct domain.calculations.registry.* import and verify the registry test suite passes; `RELOC-039, Rule 9-B; `src/aeat/domain/calculations/`.
- [x] `W07.P19.S64` - migrate the second domain.calculations passthrough caller to a direct domain.calculations.registry.* import; `RELOC-039, Rule 9-B; `src/aeat/domain/calculations/`.
- [x] `W07.P19.S65` - migrate the third domain.calculations passthrough caller to a direct domain.calculations.registry.* import; `RELOC-039, Rule 9-B; `src/aeat/domain/calculations/`.
- [x] `W07.P19.S66` - migrate the fourth domain.calculations passthrough caller to a direct domain.calculations.registry.* import; `RELOC-039, Rule 9-B; `src/aeat/domain/calculations/`.
- [x] `W07.P19.S67` - migrate the fifth domain.calculations passthrough caller to a direct domain.calculations.registry.* import, remove the six passthrough symbols from domain/calculations/registry/__init__.py, and run the registry suite sequentially; `RELOC-039, Rule 9-B; `src/aeat/domain/calculations/registry/__init__.py`.
- [x] `W07.P19.S68` - deduplicate SECRET_PASSPHRASE test constant by extracting to a shared conftest fixture referenced by both test files; `RENAME-008, aeat-source-hygiene; `src/aeat/adapters/outbound/aeat/auth/`.

## Wave `W08` - import-direction violation purge - application to adapters cluster

Sever the 143 application-to-adapters illegal import edges per Rule 2. Phases cover: AuthSessionProtocol extraction to application/auth/_protocols.py (MIGRATE-001, 17 bi-directional auth edges), IvaCompensationRepositoryProtocol extraction to application/calculations/_ports.py and Google-adapter cycle break (MIGRATE-002, 17 bi-directional Google edges), application/filing and application/ledger port protocol extraction (RELOC-015, RELOC-019, RELOC-020), application/live error-base move to core/errors (RELOC-018), and the 52 adapter-to-application inbound-edge corrections (RELOC-032). Each Phase closes with a pytest run scoped to the packages it touches; the full adapter+application suite runs at Wave close.

### Phase `W08.P20` - auth session protocol extraction and cycle break

Extract AuthSessionProtocol to application/auth/_protocols.py, migrate the 17 bi-directional auth adapter edges to depend inward on the Protocol, and run the auth test suite (MIGRATE-001, RELOC-016, Rule 2 and Rule 8).

- [x] `W08.P20.S69` - declare AuthSessionProtocol in application/auth/_protocols.py capturing the interface currently satisfied by the adapter auth session shapes; `MIGRATE-001, Rule 8; `src/aeat/application/auth/_protocols.py`.
- [x] `W08.P20.S70` - update application/auth/_sessions.py to depend on AuthSessionProtocol rather than the adapters session shape and remove the adapters import; `MIGRATE-001, RELOC-016, Rule 2; `src/aeat/application/auth/_sessions.py`.
- [x] `W08.P20.S71` - migrate the 15 remaining bi-directional auth adapter import edges to depend inward on AuthSessionProtocol and run the auth test suite sequentially; `MIGRATE-001, Rule 2; `src/aeat/adapters/outbound/aeat/auth/`.

### Phase `W08.P21` - IvaCompensation port extraction and Google adapter cycle break

Extract IvaCompensationRepositoryProtocol to application/calculations/_ports.py, migrate the Google adapter to implement it, break the 17 bi-directional Google-adapter cycle edges (MIGRATE-002, RELOC-017, Rule 2 and Rule 8).

- [x] `W08.P21.S72` - declare IvaCompensationRepositoryProtocol in application/calculations/_ports.py capturing the interface used by application/calculations/_iva_compensation_history.py; `MIGRATE-002, Rule 8; `src/aeat/application/calculations/_ports.py`.
- [x] `W08.P21.S73` - update application/calculations/_iva_compensation_history.py to depend on IvaCompensationRepositoryProtocol and remove the adapters import; `MIGRATE-002, RELOC-017, Rule 2; `src/aeat/application/calculations/_iva_compensation_history.py`.
- [x] `W08.P21.S74` - migrate the 15 remaining Google adapter bi-directional cycle edges to depend inward on the Protocol and run the calculations test suite sequentially; `MIGRATE-002, Rule 2; `src/aeat/adapters/outbound/google/`.

### Phase `W08.P22` - application filing, ledger, and live error port extractions

Extract port protocols for application/filing/_runtime_repository.py (RELOC-015), application/filing/_export.py (RELOC-019), application/ledger/_actions.py (RELOC-020), and move the shared error base for application/live/_errors.py to core/errors/ (RELOC-018). Each removes one application-to-adapters import edge.

- [x] `W08.P22.S75` - introduce domain-layer repository protocol for application/filing/_runtime_repository.py and remove the adapters import; `RELOC-015, Rule 2, Rule 8; `src/aeat/application/filing/_runtime_repository.py`.
- [x] `W08.P22.S76` - extract shared export contract to application/export/_contracts.py and update application/filing/_export.py to use the contract instead of the adapters import; `RELOC-019, Rule 2; `src/aeat/application/export/_contracts.py`.
- [x] `W08.P22.S77` - extract repository protocol to application/ledger/_protocols.py and update application/ledger/_actions.py to depend on the Protocol instead of the adapters import; `RELOC-020, Rule 2, Rule 8; `src/aeat/application/ledger/_protocols.py`.
- [x] `W08.P22.S78` - move the shared error base referenced by application/live/_errors.py to core/errors/ and update the two import sites; `RELOC-018, Rule 2; `src/aeat/application/live/_errors.py`.

### Phase `W08.P23` - adapter-to-application inbound edge corrections

Break the 52 adapter-to-application inbound import edges (RELOC-032) by ensuring each adapter depends on the Protocol ports declared in W08.P20..P22, not on application concrete types. Wave close gate: sequential pytest across adapters/ and application/.

- [x] `W08.P23.S79` - correct the 52 adapter-to-application inbound import edges by switching each adapter to depend on the Protocol ports introduced in P20..P22 rather than application concrete types, and run sequential pytest across adapters/ and application/; `RELOC-032, Rule 2; `src/aeat/adapters/`.

## Wave `W09` - import-direction violation purge - domain and core outbound clusters

Sever the remaining illegal import-direction edges: 89 domain-to-adapters repository edges not covered by W06 Phase P01 (split across MIGRATE-003 sub-files), 7 domain-to-application edges (MIGRATE-005, RELOC-029), 5 domain-to-entrypoint edges (MIGRATE-004, RELOC-030), 36 core-to-domain edges (MIGRATE-006, RELOC-025), 13 core-to-application edges (MIGRATE-007, RELOC-026), and 4 core-to-adapters edges (MIGRATE-008, RELOC-027). Rule 2 exceptions A, B, C are pre-verified before each edge is severed. Wave close gate: sequential pytest across domain/ and core/.

### Phase `W09.P24` - domain-to-application and domain-to-entrypoints edge removal

Sever the 7 domain-to-application illegal import edges (MIGRATE-005, RELOC-029) by moving each shared type to domain/ or core/, and eliminate the 5 domain-to-entrypoints edges (MIGRATE-004, RELOC-030) by removing any domain module reference to entrypoints. Rule 2.

- [x] `W09.P24.S80` - identify all 7 domain-to-application import sites and move each shared type to domain/ or core/, removing the upward import edge; `MIGRATE-005, RELOC-029, Rule 2; `src/aeat/domain/`.
- [x] `W09.P24.S81` - identify all 5 domain-to-entrypoints import sites, extract any referenced symbol to domain/ or core/, and remove the entrypoints import from every domain module; `MIGRATE-004, RELOC-030, Rule 2; `src/aeat/domain/`.

### Phase `W09.P25` - core outbound edges elimination

Eliminate the 36 core-to-domain edges (MIGRATE-006, RELOC-025), 13 core-to-application edges (MIGRATE-007, RELOC-026), and 4 core-to-adapters edges (MIGRATE-008, RELOC-027) by moving each referenced symbol into core/ or removing the dependency. Rule 1. Wave close gate: sequential pytest across domain/ and core/.

- [x] `W09.P25.S82` - enumerate the 36 core-to-domain import edges, verify Rule 2 exceptions A B C do not apply, and for each edge move the referenced symbol into core/ or remove the core/ dependency; `MIGRATE-006, RELOC-025, Rule 1; `src/aeat/core/`.
- [x] `W09.P25.S83` - enumerate the 13 core-to-application import edges and for each move the referenced symbol into core/ or remove the dependency; `MIGRATE-007, RELOC-026, Rule 1; `src/aeat/core/`.
- [x] `W09.P25.S84` - enumerate the 4 core-to-adapters import edges, move referenced symbols into core/, and run sequential pytest across domain/ and core/ as Wave W09 close gate; `MIGRATE-008, RELOC-027, Rule 1; `src/aeat/core/`.

## Wave `W10` - semantic-equivalence consolidations

Execute the twelve GPU-semantic-search-only findings: collapse three _hash_file copies to core/hashing.sha256_file (MERGE-006), migrate five SHA-256 one-liner call sites (MERGE-007), consolidate _normalise_period duplicates (MERGE-008), harden validate_identity NIF rejection and add regression test (MERGE-009, classified FIX), unify reconciliation status enum triple (MERGE-005), consolidate ValidatedRegistryAuthority.load boilerplate (MERGE-010). Phases also cover the ReconciliationStatus vs SubmissionStatus 50pct-overlap audit and documented divergence (MERGE-004). Wave close gate: sequential pytest across domain/, application/, and core/.

### Phase `W10.P26` - hashing and utility function consolidations

Collapse the three _hash_file copies to core/hashing.sha256_file (MERGE-006), migrate five SHA-256 one-liner call sites (MERGE-007), consolidate the two _normalise_period copies to application/filing/_period_utils.py (MERGE-008), and harden validate_identity NIF rejection (MERGE-009, classified FIX).

- [x] `W10.P26.S85` - declare sha256_file in core/hashing.py, delete the two non-canonical _hash_file copies from domain/calculations/registry/_workbook_parity.py and application/ledger/_actions.py, and migrate their callers to core.hashing.sha256_file; `MERGE-006, Rule 1; `src/aeat/core/hashing.py`.
- [x] `W10.P26.S86` - migrate each of the five independent SHA-256 one-liner hashlib call sites across domain/ and application/ to use core.hashing.sha256_file; `MERGE-007, Rule 1; `src/aeat/`.
- [x] `W10.P26.S87` - extract _normalise_period to application/filing/_period_utils.py, delete the two copies from application/filing/_normalise_period.py and application/filing/reconciliation/_normalise_period.py, and update the four callers; `MERGE-008, Rule 1; `src/aeat/application/filing/_period_utils.py`.
- [x] `W10.P26.S88` - harden core/identity/validate_identity to reject malformed NIFs that _normalise_tax_identity would reject, add a regression test asserting rejection of a known malformed NIF, and update the domain function to call core/identity/validate_identity; `MERGE-009, Rule 1; `src/aeat/core/identity/`.

### Phase `W10.P27` - reconciliation status consolidation and registry load boilerplate

Audit and document the ReconciliationStatus vs SubmissionStatus divergence (MERGE-004), unify the three reconciliation status enum variants under a single core type (MERGE-005), and eliminate the three ValidatedRegistryAuthority.load boilerplate duplications via a factory helper (MERGE-010). Wave close gate: sequential pytest across domain/, application/, and core/.

- [x] `W10.P27.S89` - audit whether ReconciliationStatus states are a subset of SubmissionStatus and document explicit divergence or consolidation rationale in the commit message; `MERGE-004, Rule 7; `src/aeat/application/filing/reconciliation/_schema.py`.
- [x] `W10.P27.S90` - unify RentaReconciliationStatus, ReconciliationStatus, and ModeloReconciliationVerdict under a single core reconciliation status type and update the five callers; `MERGE-005, Rule 7; `src/aeat/core/`.
- [x] `W10.P27.S91` - introduce a factory helper in domain/calculations/registry/_authority.py eliminating the two duplicate ValidatedRegistryAuthority.load boilerplate call sites and run sequential pytest across domain/, application/, and core/ as Wave W10 close gate; `MERGE-010, aeat-registry-authority-flow; `src/aeat/domain/calculations/registry/_authority.py`.

## Wave `W11` - enforcement-test extension to 10 clauses

Extend src/aeat/diagnostics/test_identity_primitive_placement.py from 4 inherited clauses to 10 cumulative clauses per Rule 11. Each of the 6 new clauses is one Step: Clause 5 sibling-domain enum import, Clause 6 sibling-domain constant import, Clause 7 sibling-domain protocol import, Clause 8 private-name cross-package escape, Clause 9 same-name UPPER_SNAKE_CASE multi-declaration, Clause 10 bare-str _kind/_status/_state at persisted boundaries. Wave close gate: the full 10-clause test passes sequentially against the post-W10 tree with zero violations. Absence or reduction below 10 clauses is a Rule 11 violation.

### Phase `W11.P28` - six new enforcement clauses

Extend the diagnostics test from 4 to 10 cumulative clauses per Rule 11. One Step per new clause, each with its own anti-tautology proof (introduce a deliberate violation under a scratch path, observe the clause fires, revert). The 10-clause test must pass against the post-W10 codebase tree.

- [x] `W11.P28.S92` - implement Clause 5 asserting no domain.<a> module imports from domain.<b>._enums for a != b, with anti-tautology proof; `Rule 11; `src/aeat/diagnostics/test_identity_primitive_placement.py`.
- [x] `W11.P28.S93` - implement Clause 6 asserting no domain.<a> module imports from domain.<b>._constants for a != b, with anti-tautology proof; `Rule 11; `src/aeat/diagnostics/test_identity_primitive_placement.py`.
- [x] `W11.P28.S94` - implement Clause 7 asserting no domain.<a> module imports from domain.<b>._protocols for a != b, with anti-tautology proof; `Rule 11; `src/aeat/diagnostics/test_identity_primitive_placement.py`.
- [x] `W11.P28.S95` - implement Clause 8 asserting no production module imports a _-prefixed name from a cross-package module other than _ids.py, with anti-tautology proof; `Rule 11; `src/aeat/diagnostics/test_identity_primitive_placement.py`.
- [x] `W11.P28.S96` - implement Clause 9 asserting no two production modules outside the protect list declare an UPPER_SNAKE_CASE constant with the same name and same literal value, with anti-tautology proof; `Rule 11; `src/aeat/diagnostics/test_identity_primitive_placement.py`.
- [x] `W11.P28.S97` - implement Clause 10 asserting no pydantic field at a persisted or wire boundary ending in _kind, _status, or _state uses bare str with only a length/pattern constraint when a typed alias exists, with anti-tautology proof; `verify all 10 clauses pass as Wave W11 close gate; Rule 11; `src/aeat/diagnostics/test_identity_primitive_placement.py`.

## Wave `W12` - identity-primitive promotion and bare-str enrollment

Promote BundleId and EvidenceId from application/evidence/_ids.py to core/identity/ per Rule 1 clause (a) (RELOC-037, RELOC-038, resolving the W05.S68 identity-primitives follow-up), enroll the 54 bare-str identity-primitive sites onto typed aliases (PROMOTE-001, Rule 5), annotate SubjectTaxId on the three domain Protocol method signatures (PROMOTE-002). Wave close gate: sequential pytest across all packages; Clause 10 of the W11 enforcement test must remain green against the post-W12 tree with zero _kind/_status/_state bare-str violations at persisted boundaries.

### Phase `W12.P29` - BundleId EvidenceId promotion and bare-str enrollment

Promote BundleId and EvidenceId to core/identity/ (RELOC-037, RELOC-038), enroll the 54 bare-str _id/_kind/_status/_state sites onto typed aliases (PROMOTE-001, Rule 5), and annotate SubjectTaxId on the remaining domain Protocol method signatures (PROMOTE-002). Wave close gate: sequential pytest across all packages; W11 Clause 10 enforcement must remain zero-violation.

- [x] `W12.P29.S98` - declare BundleId alias in core/identity/_bundle.py, re-export through core/identity/__init__, delete the application/evidence/_ids.py declaration, and update all callers; `RELOC-037, Rule 1; `src/aeat/core/identity/_bundle.py`.
- [x] `W12.P29.S99` - declare EvidenceId alias in core/identity/_evidence.py, re-export through core/identity/__init__, delete the application/evidence/_ids.py declaration, and update all callers; `RELOC-038, Rule 1; `src/aeat/core/identity/_evidence.py`.
- [x] `W12.P29.S100` - enroll the first 18 bare-str _id/_kind/_status/_state field sites onto their typed aliases, asserting pydantic shape enforcement at construction for each site; `PROMOTE-001, Rule 5; `src/aeat/domain/`.
- [x] `W12.P29.S101` - enroll the next 18 bare-str _id/_kind/_status/_state field sites onto typed aliases across the application layer; `PROMOTE-001, Rule 5; `src/aeat/application/`.
- [x] `W12.P29.S102` - enroll the remaining 18 bare-str _id/_kind/_status/_state field sites onto typed aliases across adapters and entrypoints, run sequential pytest across all packages, and confirm W11 Clause 10 reports zero violations; `PROMOTE-001, Rule 5; `src/aeat/`.

## Wave `W13` - Honest follow-up: close audit findings

Execute the 10 corrective actions prescribed by the post-campaign honesty review (2026-05-31-core-authority-audit). Covers the CTIMEX-003 import resolution, STRICT_FROZEN 87-site migration, PROMOTE-001 protect-list formalisation, W11 gate re-assertion, two ADR amendments, ProfileFactValue rename, audit-pipeline brief update, vault stubs for deferred tasks, and a final structural verification pass.

### Phase `W13.P30` - CTIMEX-003 and STRICT_FROZEN migration

Fix the broken core._time import (CTIMEX-003) and execute the 87-site STRICT_FROZEN_CONFIG migration (MERGE014-001).

- [x] `W13.P30.S103` - verify CTIMEX-003 is resolved: confirm application/filing/__init__.py imports from core.time._clock not the deleted core._time, run collection on application/filing/ to assert zero ImportErrors, and document root-cause and resolution; `src/aeat/application/filing/__init__.py`.
- [x] `W13.P30.S104` - migrate all 87 production files declaring _STRICT_FROZEN = ConfigDict(...) locally to import STRICT_FROZEN_CONFIG from aeat.core._models, grouped by package (domain, application, adapters, entrypoints); `skip the 3 bespoke-variant modules documented in W04; verify rg returns only the 3 bespoke modules; `src/aeat/`.

### Phase `W13.P31` - PROMOTE-001 protect-list and W11 gate re-assertion

Formalise the 52 blocked PROMOTE-001 sites into a typed protect-list constant and re-run the full W11 10-clause gate to confirm zero violations.

- [x] `W13.P31.S105` - land the PROMOTE-001 protect-list as a typed constant in src/aeat/diagnostics/_identity_placement.py, documenting the constraint-shape mismatch rationale for each of the 52 blocked sites, and update the W11 Clause 10 detector to skip protect-list entries; `src/aeat/diagnostics/_identity_placement.py`.
- [x] `W13.P31.S106` - re-run all 10 diagnostics clauses against the full tree as an honest W11 gate re-assertion, confirm zero violations, and document actual counts in Step Record; `src/aeat/diagnostics/test_identity_primitive_placement.py`.

### Phase `W13.P32` - ADR amendments, ProfileFactValue rename, audit-pipeline update

Amend the core-authority ADR Rule 7 for CalendarCCAA wontfix, execute the ProfileFactValue rename, mark MERGE-013 IVA wontfix, and update the audit dispatch brief template with the constraint-shape pre-filter.

- [x] `W13.P32.S107` - amend the core-authority ADR Rule 7 to acknowledge CalendarCCAA is NOT a geographic duplicate of CCAA (different value formats, different member sets) and add a wontfix Consequences entry for MERGE-002; `.vault/adr/2026-05-31-core-authority-adr.md`.
- [x] `W13.P32.S108` - rename application/user_profile/_values::ProfileFactValue to UserProfileFactValue to eliminate the name collision with domain/calculations/registry/_schema::ProfileFactValue, migrate all callers, and add ADR Consequences entry marking MERGE-003 as RENAME not MERGE; `src/aeat/application/user_profile/_values.py`.
- [x] `W13.P32.S109` - amend the core-authority ADR Consequences to mark MERGE-013 (IVA mapping) as wontfix with rationale: 3-entry percentage-lookup and 5-entry VAT-classification mappings are intentionally different in structure and domain semantics; `.vault/adr/2026-05-31-core-authority-adr.md`.
- [x] `W13.P32.S110` - update the audit dispatch brief template in .claude/rules/ to mandate a substitutability pre-filter: any audit brief targeting X where Y exists must require the auditor to verify Y constraint shape is a superset of X constraint shape before flagging X as actionable; `.claude/rules/`.

### Phase `W13.P33` - Vault stubs and final structural verification

Create vault research stubs for deferred tasks 583-587 and run final structural-boundary check documenting actual import counts.

- [x] `W13.P33.S111` - create .vault/research/ stubs for deferred tasks 583-587 (STRICT_FROZEN migration, CalendarCCAA wontfix, ProfileFactValue rename, PROMOTE-001 protect-list, audit-pipeline pre-filter) each referencing the honesty-audit and status; `.vault/research/`.
- [x] `W13.P33.S112` - run final structural verification: pytest diagnostics suite, rg for cross-layer import violations (adapters importing application, application importing adapters, domain importing core as outbound), document actual counts in Step Record; `src/aeat/`.
