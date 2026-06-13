---
tags:
  - '#plan'
  - '#code-duplication-sweep'
date: '2026-05-19'
modified: '2026-05-19'
tier: L3
related:
  - '[[2026-05-19-code-duplication-sweep-research]]'
  - '[[2026-05-19-code-duplication-sweep-adr]]'
---


# `code-duplication-sweep` `Code Duplication Sweep Remediation Plan` plan

## Wave `W01` - Minor Symbol Segregations

Unify minor colliding and shadowed identifiers under unique canonical names, ensuring no shadowed imports or catching bugs exist.

### Phase `W01.P01` - Consolidate Shadowed Exception Hierarchies and Identifier Naming Collisions

Resolve import shadows and exception-catching bugs across WorkUnitNotFoundError, CCAA, and ModeloRepository.

- [x] `W01.P01.S01` - Consolidate WorkUnitNotFoundError to actions.py and raise it in reconcile.py; `src/aeat/application/modelo/_reconcile.py`.
- [x] `W01.P01.S02` - Rename calendar-specific CCAA enum to CalendarCCAA to prevent collision with profile CCAA; `src/aeat/domain/deadlines/_festivos.py`.
- [x] `W01.P01.S03` - Rename read-only static ModeloRepository facade to StaticModeloRepository; `src/aeat/core/resources/_repos/modelos.py`.

## Wave `W02` - Boilerplate Consolidation

Consolidate repeated repository structures and drivers into generic base classes, and unify third-party dependencies under common modules.

### Phase `W02.P02` - Consolidate SecureObjectRepository Boilerplate

Create a reusable generic persistence repository baseline to replace repeated pathing, locking, and serialization logic.

- [x] `W02.P02.S04` - Implement generic SecureBoundRepository baseline class; `src/aeat/adapters/persistence/storage/envelope/_secure_repository.py`.
- [x] `W02.P02.S05` - Refactor FilingDraftRepository to inherit from SecureBoundRepository; `src/aeat/domain/filing/_repository.py`.
- [x] `W02.P02.S06` - Refactor SubmissionRepository to inherit from SecureBoundRepository; `src/aeat/domain/submission/_repository.py`.
- [x] `W02.P02.S07` - Extract shared repository roundtrip testing utility to replace duplicate assertions; `src/aeat/adapters/persistence/storage/conftest.py`.

### Phase `W02.P03` - Consolidate External Integrations

Unify copy-pasted pdfplumber extraction logic, logging control suppression, and live oracle checker drivers.

- [x] `W02.P03.S08` - Migrate all PDF text extraction calls to canonical pdfplumber utility and implement the shared `_suppress_pdfminer_debug_logging` control to eliminate PDF logging noise globally; `src/aeat/adapters/inbound/pdf/_pdfplumber.py`.
- [x] `W02.P03.S09` - Refactor borrador parser to use shared PDF text extraction utility; `src/aeat/adapters/inbound/borrador/_parsers/_pdfplumber_backend.py`.
- [x] `W02.P03.S10` - Refactor declaracion parser to use shared PDF text extraction utility; `src/aeat/adapters/inbound/declaracion/_parsers/_pdfplumber_backend.py`.
- [x] `W02.P03.S11` - Extract BaseCheckerOracle and shared JSON-decoding replay driver under live parity backend; `src/aeat/domain/calculations/registry/_live_parity.py`.
- [x] `W02.P03.S12` - Refactor AeatNifIvaCheckerOracle to inherit from BaseCheckerOracle; `src/aeat/domain/calculations/registry/_aeat_nif_iva_oracle.py`.
- [x] `W02.P03.S13` - Refactor GroiCheckerOracle to inherit from BaseCheckerOracle; `src/aeat/domain/calculations/registry/_groi_oracle.py`.

## Wave `W03` - Acronym & Term Standardization

Standardize the dual-acronym structures (VAT vs IVA) and triple-terminology divides (Filing vs Modelo vs Declaración), deprecating redundant draft persistence blocks.

### Phase `W03.P04` - Consolidate Value-Added Tax (VAT vs IVA)

Establish a uniform terminology glossary and merge overlapping classification logic into a canonical VAT domain package.

- [x] `W03.P04.S14` - Create canonical IVA invoice classification schema as the unified surface under domain/iva, absorbing VatClassification and IvaInvoiceClassification; `src/aeat/domain/iva/_classification.py`.
- [x] `W03.P04.S15` - Migrate VatRegulation, VATRateKind, and VATCatalogue into IvaRegulation, IvaRateKind, and IvaCatalogue under domain/iva, reconciling with any existing IVA equivalents; `src/aeat/domain/iva/_schema.py`.
- [x] `W03.P04.S18` - Migrate VatLedgerSelector callsites to the canonical _IvaLedgerSelector under domain/iva and remove the duplicate selector; `src/aeat/domain/iva/_flow.py`.
- [x] `W03.P04.S19` - Collapse IssuerResidency and CustomerResidency into a single IvaResidency enum used in both issuer and customer field roles; `src/aeat/domain/iva/_classification.py`.
- [x] `W03.P04.S20` - Collapse InvoiceDirection into the existing InvoiceKind enum and remove the InvoiceDirection symbol; `src/aeat/domain/iva/_classification.py`.
- [x] `W03.P04.S21` - Rename the domain package from domain/vat to domain/iva and update every import site to the new path; `src/aeat/domain/iva/__init__.py`.
- [x] `W03.P04.S22` - Delete the legacy domain/vat package directory after all consumers have migrated to domain/iva; `src/aeat/domain/vat/`.

### Phase `W03.P05` - Unify Draft Persistence and Deprecate Local file-based Snapshotting

Retire the insecure local file-based borrador.py snapshotting strategy and consolidate all Modelo 100 draft persistence under borrador_100.py.

- [x] `W03.P05.S16` - Migrate all active commands from local file-based borrador storage to secure borrador_100 object repository; `src/aeat/application/live/_borrador_100.py`.
- [x] `W03.P05.S17` - Delete deprecated local filesystem-based borrador parser file-caching implementation; `src/aeat/application/live/_borrador.py`.

## Wave `W04` - Spanish-Stem Terminology Renames

Execute the ADR-approved English-to-Spanish identifier renames across the Declaracion, Censo, and Modelo clusters, plus consolidate DraftStatus and FilingDraftStatus into a single ModeloDraftStatus enum. Each phase covers one cluster (or one subdomain of the Modelo cluster) so coders can execute in parallel without rename conflicts. No shims, no deprecation aliases; every callsite migrates in lockstep with its definition.

### Phase `W04.P06` - Declaration to Declaracion Rename

Rename the 20 Declaration-prefixed identifiers to Declaracion across the outbound Sede contract, application filing/review/workflow surface, registry live-parity, and domain reconciliation. Public-API rows in the outbound Sede contract are coordinated cuts: every callsite renames in the same commit.

- [x] `W04.P06.S23` - Rename Declaration to Declaracion in the outbound Sede declarations surface; `src/aeat/adapters/outbound/aeat/sede/_declarations.py`.
- [x] `W04.P06.S24` - Rename DeclarationsRegisterSession to DeclaracionesRegisterSession in the outbound Sede declarations surface; `src/aeat/adapters/outbound/aeat/sede/_declarations.py`.
- [x] `W04.P06.S25` - Rename FiledDeclarationArtefact to FiledDeclaracionArtefact in the outbound Sede schema; `src/aeat/adapters/outbound/aeat/sede/_schema.py`.
- [x] `W04.P06.S26` - Rename FiledDeclarationObservation to FiledDeclaracionObservation in the outbound Sede schema; `src/aeat/adapters/outbound/aeat/sede/_schema.py`.
- [x] `W04.P06.S27` - Rename FiledDeclarationObservationStore to FiledDeclaracionObservationStore; `src/aeat/adapters/outbound/aeat/sede/_observation_store.py`.
- [x] `W04.P06.S28` - Rename DeclarationCalculateNextAction to DeclaracionCalculateNextAction; `src/aeat/application/filing/_calculate.py`.
- [x] `W04.P06.S29` - Rename DeclarationCalculateSummary to DeclaracionCalculateSummary; `src/aeat/application/filing/_calculate.py`.
- [x] `W04.P06.S30` - Rename DeclarationExportFormat to DeclaracionExportFormat; `src/aeat/application/filing/_export.py`.
- [x] `W04.P06.S31` - Rename DeclarationVerifyVerdict to DeclaracionVerifyVerdict; `src/aeat/application/filing/_export.py`.
- [x] `W04.P06.S32` - Rename DeclarationExportResult to DeclaracionExportResult; `src/aeat/application/filing/_export.py`.
- [x] `W04.P06.S33` - Rename DeclarationVerifyResult to DeclaracionVerifyResult; `src/aeat/application/filing/_export.py`.
- [x] `W04.P06.S34` - Rename DeclarationEditSpec to DeclaracionEditSpec; `src/aeat/application/review/_edit.py`.
- [x] `W04.P06.S35` - Rename DeclarationReviewFilterKey to DeclaracionReviewFilterKey; `src/aeat/application/review/_filter.py`.
- [x] `W04.P06.S36` - Rename DeclarationReviewStatus to DeclaracionReviewStatus; `src/aeat/application/review/_filter.py`.
- [x] `W04.P06.S37` - Rename DeclarationReviewFilterSpec to DeclaracionReviewFilterSpec; `src/aeat/application/review/_filter.py`.
- [x] `W04.P06.S38` - Rename DeclarationPointer to DeclaracionPointer; `src/aeat/application/workflow/_models.py`.
- [x] `W04.P06.S39` - Rename DeclarationParseError to DeclaracionParseError; `src/aeat/domain/filing/reconciliation/_errors.py`.
- [x] `W04.P06.S40` - Rename ReconciliationDeclarationSourceUnsupportedError to ReconciliationDeclaracionSourceUnsupportedError; `src/aeat/application/modelo/_reconcile.py`.
- [x] `W04.P06.S41` - Rename CrossReferenceApplicabilityDeclaration to CrossReferenceApplicabilityDeclaracion; `src/aeat/domain/calculations/registry/_live_parity.py`.
- [x] `W04.P06.S42` - Rename RentaDeclarationType to RentaDeclaracionType in the renta codes module; `src/aeat/domain/profile/_renta_codes.py`.

### Phase `W04.P07` - Census to Censo Rename

Rename the 22 Census-prefixed identifiers to Censo across application profile sync, live snapshot, domain calculations registry, and outbound Sede surfaces. The module paths application/live/_census.py and adapters/outbound/aeat/sede/_census.py rename to _censo.py in lockstep with the contained symbols. The CensoSnapshot retains its Snapshot infra suffix per the ADR disambiguation rule.

- [x] `W04.P07.S43` - Rename CensusSyncError to CensoSyncError; `src/aeat/application/profile/_census_errors.py`.
- [x] `W04.P07.S44` - Rename CensusNotAvailableError to CensoNotAvailableError; `src/aeat/application/profile/_census_errors.py`.
- [x] `W04.P07.S45` - Rename CensusFieldValidationError to CensoFieldValidationError; `src/aeat/application/profile/_census_errors.py`.
- [x] `W04.P07.S46` - Rename CensusApplyConflictError to CensoApplyConflictError; `src/aeat/application/profile/_census_errors.py`.
- [x] `W04.P07.S47` - Rename CensusComparisonStatus to CensoComparisonStatus; `src/aeat/application/profile/_census_sync.py`.
- [x] `W04.P07.S48` - Rename CensusFieldComparison to CensoFieldComparison; `src/aeat/application/profile/_census_sync.py`.
- [x] `W04.P07.S49` - Rename CensusProfileComparison to CensoProfileComparison; `src/aeat/application/profile/_census_sync.py`.
- [x] `W04.P07.S50` - Rename CensusApplyResult to CensoApplyResult; `src/aeat/application/profile/_census_sync.py`.
- [x] `W04.P07.S51` - Rename CensusSyncService to CensoSyncService; `src/aeat/application/profile/_census_sync.py`.
- [x] `W04.P07.S52` - Rename CensusSnapshot to CensoSnapshot (retain Snapshot infra suffix per ADR disambiguation rule); `src/aeat/application/live/_censo.py`.
- [x] `W04.P07.S53` - Rename module application/live/_census.py to _censo.py in lockstep with the Censo rename; `src/aeat/application/live/_censo.py`.
- [x] `W04.P07.S54` - Rename CensusStaleRefusedError to CensoStaleRefusedError; `src/aeat/domain/modelos/_errors.py`.
- [x] `W04.P07.S55` - Rename CensusRatioMismatchError to CensoRatioMismatchError; `src/aeat/domain/usage_ratios/_errors.py`.
- [x] `W04.P07.S56` - Rename RatiosCensusOverrideWarning to RatiosCensoOverrideWarning; `src/aeat/application/ledger/_ratios.py`.
- [x] `W04.P07.S57` - Rename CensusModeloRole to CensoModeloRole; `src/aeat/domain/calculations/registry/_census_modelos.py`.
- [x] `W04.P07.S58` - Rename CensusModeloEventKind to CensoModeloEventKind; `src/aeat/domain/calculations/registry/_census_modelos.py`.
- [x] `W04.P07.S59` - Rename CensusModeloFoundationLogFields to CensoModeloFoundationLogFields; `src/aeat/domain/calculations/registry/_census_modelos.py`.
- [x] `W04.P07.S60` - Rename CensusModeloOwnership to CensoModeloOwnership; `src/aeat/domain/calculations/registry/_census_modelos.py`.
- [x] `W04.P07.S61` - Rename CensusModeloFoundationContract to CensoModeloFoundationContract; `src/aeat/domain/calculations/registry/_census_modelos.py`.
- [x] `W04.P07.S62` - Rename CensusModeloFoundationCommand to CensoModeloFoundationCommand; `src/aeat/domain/calculations/registry/_census_modelos.py`.
- [x] `W04.P07.S63` - Rename CensusModeloFoundationResult to CensoModeloFoundationResult; `src/aeat/domain/calculations/registry/_census_modelos.py`.
- [x] `W04.P07.S64` - Rename CensusFactSet to CensoFactSet and module _census.py to _censo.py under outbound Sede; `src/aeat/adapters/outbound/aeat/sede/_censo.py`.
- [x] `W04.P07.S65` - Rename CensusParseError to CensoParseError under outbound Sede; `src/aeat/adapters/outbound/aeat/sede/_censo.py`.

### Phase `W04.P08` - Modelo Cluster: domain/filing Schema and Errors

Rename the Filing-prefixed identifiers under src/aeat/domain/filing/ to their Modelo equivalents: schema records, validators, amendment models, errors, protocols, and the FilingDraftRepository. Self-contained domain package; no cross-domain ripple within this phase.

- [x] `W04.P08.S66` - Rename FilingDraft to ModeloDraft in the filing schema; `src/aeat/domain/filing/_schema.py`.
- [x] `W04.P08.S67` - Rename FilingValue to ModeloValue in the filing schema; `src/aeat/domain/filing/_schema.py`.
- [x] `W04.P08.S68` - Rename FilingValueKind to ModeloValueKind in the filing schema; `src/aeat/domain/filing/_schema.py`.
- [x] `W04.P08.S69` - Rename FilingBindingValue to ModeloBindingValue in the filing schema; `src/aeat/domain/filing/_schema.py`.
- [x] `W04.P08.S70` - Rename FilingValidationFinding to ModeloValidationFinding in the filing schema; `src/aeat/domain/filing/_schema.py`.
- [x] `W04.P08.S71` - Rename FilingApprovalBasis to ModeloApprovalBasis in the filing schema; `src/aeat/domain/filing/_schema.py`.
- [x] `W04.P08.S72` - Rename FilingValidator to ModeloValidator; `src/aeat/domain/filing/_validator.py`.
- [x] `W04.P08.S73` - Rename FilingAmendment to ModeloAmendment; `src/aeat/domain/filing/_amendment.py`.
- [x] `W04.P08.S74` - Rename FilingAmendmentError to ModeloAmendmentError; `src/aeat/domain/filing/_errors.py`.
- [x] `W04.P08.S75` - Rename FilingDraftError to ModeloDraftError; `src/aeat/domain/filing/_errors.py`.
- [x] `W04.P08.S76` - Rename FilingBuilderError to ModeloBuilderError; `src/aeat/domain/filing/_errors.py`.
- [x] `W04.P08.S77` - Rename FilingValidationError to ModeloValidationError; `src/aeat/domain/filing/_errors.py`.
- [x] `W04.P08.S78` - Rename FilingComputationError to ModeloComputationError; `src/aeat/domain/filing/_errors.py`.
- [x] `W04.P08.S79` - Rename FilingImportError to ModeloImportError; `src/aeat/domain/filing/_errors.py`.
- [x] `W04.P08.S80` - Rename FilingExportError to ModeloExportError; `src/aeat/domain/filing/_errors.py`.
- [x] `W04.P08.S81` - Rename FilingExportValidationError to ModeloExportValidationError; `src/aeat/domain/filing/_errors.py`.
- [x] `W04.P08.S82` - Rename FilingProfile protocol to ModeloProfile; `src/aeat/domain/filing/_protocols.py`.
- [x] `W04.P08.S83` - Rename FilingDraftRepository to ModeloDraftRepository; `src/aeat/domain/filing/_repository.py`.

### Phase `W04.P09` - Modelo Cluster: domain/modelos FilingRecord Consolidation

Rename FilingRecord, FilingRecordStatus, FilingRecordCatalogue and friends to their Modelo equivalents under src/aeat/domain/modelos/ while preserving the split between ModeloRecord (domain pydantic) and ModeloRow (SQL ORM) per project-lead adjudication of ADR footnote 1. Schema-impact rows; gated by the standard roundtrip-test pattern.

- [x] `W04.P09.S84` - Rename FilingRecord to ModeloRecord as the canonical domain pydantic record; `keep the SQL ModeloRow separate per project-lead adjudication; `src/aeat/domain/modelos/_filing_record.py`.
- [x] `W04.P09.S85` - Rename FilingRecordStatus to ModeloRecordStatus; `src/aeat/domain/modelos/_filing_record.py`.
- [x] `W04.P09.S86` - Rename FilingRecordCatalogue to ModeloRecordCatalogue; `src/aeat/domain/modelos/_filing_record.py`.
- [x] `W04.P09.S87` - Rename FilingRecordPersistenceError to ModeloRecordPersistenceError; `src/aeat/domain/modelos/_filing_record.py`.
- [x] `W04.P09.S88` - Rename FilingRecordCatalogueRepository to ModeloRecordCatalogueRepository; `src/aeat/domain/modelos/_filing_repository.py`.
- [x] `W04.P09.S89` - Run the strict roundtrip-test gate over the ModeloRecord domain pydantic and ModeloRow SQL boundary after the rename, populating every defaultable field with a non-default value; `src/aeat/domain/modelos/test_modelo_record_roundtrip.py`.

### Phase `W04.P10` - Modelo Cluster: domain/deadlines and domain/calculations

Rename FilingObligation, FilingEnrollment, FilingIVAProfile under domain/deadlines, and FilingScheduleDefinition, RegistryFilingObservation, OracleFilingObservation, RegistryFilingObservationRequirement, _PreviousFilingSelector under domain/calculations/registry. These are cross-domain registry symbols; rename in coordinated commits with their importers.

- [x] `W04.P10.S90` - Rename FilingObligation to ModeloObligation; `src/aeat/domain/deadlines/_models.py`.
- [x] `W04.P10.S91` - Rename FilingEnrollment to ModeloEnrollment; `src/aeat/domain/deadlines/_models.py`.
- [x] `W04.P10.S92` - Rename FilingIVAProfile to ModeloIvaProfile; `src/aeat/domain/deadlines/_models.py`.
- [x] `W04.P10.S93` - Rename FilingScheduleDefinition to ModeloScheduleDefinition; `src/aeat/domain/calculations/registry/_schema.py`.
- [x] `W04.P10.S94` - Rename RegistryFilingObservation to RegistryModeloObservation; `src/aeat/domain/calculations/registry/_bindings.py`.
- [x] `W04.P10.S95` - Rename OracleFilingObservation to OracleModeloObservation; `src/aeat/domain/calculations/registry/_bindings.py`.
- [x] `W04.P10.S96` - Rename RegistryFilingObservationRequirement to RegistryModeloObservationRequirement; `src/aeat/domain/calculations/registry/_bindings.py`.
- [x] `W04.P10.S97` - Rename _PreviousFilingSelector to _PreviousModeloSelector; `src/aeat/domain/calculations/registry/_bindings.py`.

### Phase `W04.P11` - Modelo Cluster: application/filing, application/modelo, application/workflow

Rename Filing-prefixed identifiers across the application layer: filing errors, history, review, reconciliation, runtime, testing harnesses, workflow adapters and protocols, and modelo action errors. The CLI _modelo_payloads renames are public-API and coordinate with operator-facing locale refresh.

- [x] `W04.P11.S98` - Rename FilingApplicationError to ModeloApplicationError; `src/aeat/application/filing/errors.py`.
- [x] `W04.P11.S99` - Rename FilingCalculateError to ModeloCalculateError; `src/aeat/application/filing/errors.py`.
- [x] `W04.P11.S100` - Rename FilingHistory to ModeloHistory; `src/aeat/application/filing/_history_models.py`.
- [x] `W04.P11.S101` - Rename FilingHistoryEntry to ModeloHistoryEntry; `src/aeat/application/filing/_history_models.py`.
- [x] `W04.P11.S102` - Rename FilingHistoryRepository to ModeloHistoryRepository; `src/aeat/application/filing/_history_repository.py`.
- [x] `W04.P11.S103` - Rename FilingApprovalStaleReason to ModeloApprovalStaleReason; `src/aeat/application/filing/_review.py`.
- [x] `W04.P11.S104` - Rename FilingDivergenceKind to ModeloDivergenceKind in the reconciliation surface; `src/aeat/application/filing/reconciliation/_models.py`.
- [x] `W04.P11.S105` - Rename FilingDraftRef to ModeloDraftRef in the reconciliation surface; `src/aeat/application/filing/reconciliation/_models.py`.
- [x] `W04.P11.S106` - Rename FilingOperatorProfile to ModeloOperatorProfile; `src/aeat/application/filing/runtime.py`.
- [x] `W04.P11.S107` - Rename RegistryFilingSubview to RegistryModeloSubview; `src/aeat/application/filing/runtime.py`.
- [x] `W04.P11.S108` - Rename FilingTestProfile to ModeloTestProfile; `src/aeat/application/filing/testing.py`.
- [x] `W04.P11.S109` - Rename FilingTestDeadlineStatus to ModeloTestDeadlineStatus; `src/aeat/application/filing/testing.py`.
- [x] `W04.P11.S110` - Rename FilingTestDeadlineChecker to ModeloTestDeadlineChecker; `src/aeat/application/filing/testing.py`.
- [x] `W04.P11.S111` - Rename FilingDraftBuilderAdapter to ModeloDraftBuilderAdapter; `src/aeat/application/workflow/_adapters.py`.
- [x] `W04.P11.S112` - Rename RegistryFilingDraftProtocol to RegistryModeloDraftProtocol; `src/aeat/application/workflow/_protocols.py`.
- [x] `W04.P11.S113` - Rename FilingDraftBuilderProtocol to ModeloDraftBuilderProtocol; `src/aeat/application/workflow/_protocols.py`.
- [x] `W04.P11.S114` - Rename FilingInputsProviderProtocol to ModeloInputsProviderProtocol; `src/aeat/application/workflow/_protocols.py`.
- [x] `W04.P11.S115` - Rename FilingRecordNotFoundError to ModeloRecordNotFoundError; `src/aeat/application/modelo/_actions.py`.
- [x] `W04.P11.S116` - Rename ExternalFilingImportError to ExternalModeloImportError; `src/aeat/application/modelo/_actions.py`.
- [x] `W04.P11.S117` - Rename FilingFixtureError to ModeloFixtureError; `src/aeat/core/errors/__init__.py`.
- [x] `W04.P11.S118` - Rename FilingRecordPayload to ModeloRecordPayload (public-API; `refresh operator locales); `src/aeat/entrypoints/cli/_modelo_payloads.py`.
- [x] `W04.P11.S119` - Rename FilingRecordListResult to ModeloRecordListResult (public-API); `src/aeat/entrypoints/cli/_modelo_payloads.py`.
- [x] `W04.P11.S120` - Rename FilingRecordShowResult to ModeloRecordShowResult (public-API); `src/aeat/entrypoints/cli/_modelo_payloads.py`.

### Phase `W04.P12` - Modelo Cluster: domain/submission and domain/justificante

Rename FilingFindingSeverity, FilingFinding, FilingDraftLike, DraftLoader, SubmittedFiling under domain/submission, and PdfFilingImportError under domain/justificante. DraftStatus consolidation is the dedicated next phase; here only the prefix renames land.

- [x] `W04.P12.S121` - Rename FilingFindingSeverity to ModeloFindingSeverity under domain/submission; `src/aeat/domain/submission/_schema.py`.
- [x] `W04.P12.S122` - Rename FilingFinding to ModeloFinding under domain/submission; `src/aeat/domain/submission/_schema.py`.
- [x] `W04.P12.S123` - Rename FilingDraftLike to ModeloDraftLike under domain/submission; `src/aeat/domain/submission/_protocols.py`.
- [x] `W04.P12.S124` - Rename DraftLoader to ModeloDraftLoader under domain/submission; `src/aeat/domain/submission/_protocols.py`.
- [x] `W04.P12.S125` - Rename SubmittedFiling to SubmittedModelo under domain/submission; `src/aeat/domain/submission/_schema.py`.
- [x] `W04.P12.S126` - Rename PdfFilingImportError to PdfModeloImportError; `src/aeat/domain/justificante/_errors.py`.

### Phase `W04.P13` - DraftStatus Consolidation to Single ModeloDraftStatus

Per project-lead adjudication of ADR footnote 2, consolidate DraftStatus (domain/submission) and FilingDraftStatus (domain/filing) into a single canonical ModeloDraftStatus enum and remove the duplicate. Single coordinated step; every callsite migrates in the same commit.

- [x] `W04.P13.S127` - Consolidate DraftStatus (domain/submission) and FilingDraftStatus (domain/filing) into a single canonical ModeloDraftStatus enum, migrating every callsite in the same commit and deleting both legacy enums; `src/aeat/domain/filing/_schema.py`.

## Wave `W05` - Snapshot Service Consolidation and Fincas Rename

Consolidate the five near-clone snapshot services (Borrador legacy retired, Borrador100 base done, Censo, Expedientes, Notifications) under shared SnapshotService/StatelessSnapshotService base classes, and execute the schema-impact Rental-to-Fincas package and SQL rename. The Fincas cluster is a single coordinated SQL migration gated by strict roundtrip-tests with non-default fixture populations.

### Phase `W05.P14` - Snapshot Service Base-Class Consolidation

Introduce a shared SnapshotService[TPayload] base class and a StatelessSnapshotService variant under src/aeat/application/live/_snapshot_base.py, then refactor Censo, Expedientes, and Notifications snapshot services to inherit it. The Borrador100 base class work (Phase 1 of the snapshot proposal) and the legacy _borrador.py retirement are already complete; this phase covers Phases 2, 3, 4 (shared exception hierarchy via SnapshotNotFoundError) and Phase 5 (final retire-legacy validation pass).

- [x] `W05.P14.S128` - Create the SnapshotService[TPayload] generic base class, StatelessSnapshotService variant, SnapshotLifecycleState, and SnapshotNotFoundError shared exception base in a new _snapshot_base module; `src/aeat/application/live/_snapshot_base.py`.
- [x] `W05.P14.S129` - Refactor CensoSnapshotService to inherit SnapshotService[CensoSnapshot] and drop the duplicate validator and supersession code; `src/aeat/application/live/_censo.py`.
- [x] `W05.P14.S130` - Refactor ExpedientesSnapshotService to inherit StatelessSnapshotService; `src/aeat/application/live/_expedientes.py`.
- [x] `W05.P14.S131` - Refactor NotificationsSnapshotService to inherit StatelessSnapshotService; `src/aeat/application/live/_notifications.py`.
- [x] `W05.P14.S132` - Align BorradorSnapshotNotFoundError and analogous per-service not-found errors under the shared SnapshotNotFoundError base, preserving per-service identity; `src/aeat/application/live/_borrador_100.py`.
- [x] `W05.P14.S133` - Verify the retirement of legacy _borrador.py is complete by confirming no production callsite imports it and remove any residual references in tests and fixtures; `src/aeat/application/live/_borrador.py`.

### Phase `W05.P15` - Rental to Fincas Package and SQL Rename

Rename domain/rental to domain/fincas and execute the coordinated SQL migration for the 11 schema-impact rows: RentalFinca to Finca, RentalContract to Arrendamiento, RentalIncomeRecord to FincaIncomeRecord, RentalExpense to FincaExpense, RentalAmortizationLedger to FincaAmortizationLedger, and each *Row equivalent under adapters/persistence/storage/sql/_orm.py. Income/Expense/Amortization stay English per project-lead adjudication. Strict roundtrip-test gate applies before and after the rename.

- [x] `W05.P15.S134` - Rename the domain package from domain/rental to domain/fincas and migrate every import site to the new path; `src/aeat/domain/fincas/__init__.py`.
- [x] `W05.P15.S135` - Rename RentalFinca to Finca in the domain models; `src/aeat/domain/fincas/_models.py`.
- [x] `W05.P15.S136` - Rename RentalFincaRow to FincaRow in the SQL ORM with coordinated SQL column-name migration; `src/aeat/adapters/persistence/storage/sql/_orm.py`.
- [x] `W05.P15.S137` - Rename RentalContract to Arrendamiento in the domain models; `src/aeat/domain/fincas/_models.py`.
- [x] `W05.P15.S138` - Rename RentalContractRow to ArrendamientoRow in the SQL ORM with coordinated SQL column-name migration; `src/aeat/adapters/persistence/storage/sql/_orm.py`.
- [x] `W05.P15.S139` - Rename RentalIncomeRecord to FincaIncomeRecord (Income kept English per project-lead adjudication); `src/aeat/domain/fincas/_models.py`.
- [x] `W05.P15.S140` - Rename RentalIncomeRecordRow to FincaIncomeRecordRow in the SQL ORM with coordinated SQL column-name migration; `src/aeat/adapters/persistence/storage/sql/_orm.py`.
- [x] `W05.P15.S141` - Rename RentalExpense to FincaExpense (Expense kept English per project-lead adjudication); `src/aeat/domain/fincas/_models.py`.
- [x] `W05.P15.S142` - Rename RentalExpenseRow to FincaExpenseRow in the SQL ORM with coordinated SQL column-name migration; `src/aeat/adapters/persistence/storage/sql/_orm.py`.
- [x] `W05.P15.S143` - Rename RentalAmortizationLedger to FincaAmortizationLedger (Amortization kept English per project-lead adjudication); `src/aeat/domain/fincas/_amortization_ledger.py`.
- [x] `W05.P15.S144` - Rename RentalAmortizationLedgerRow to FincaAmortizationLedgerRow in the SQL ORM with coordinated SQL column-name migration; `src/aeat/adapters/persistence/storage/sql/_orm.py`.
- [x] `W05.P15.S145` - Execute the strict roundtrip-test gate over the renamed Fincas SQL boundary with non-default optional fields populated and the anti-tautology mutation proof in place; `src/aeat/domain/fincas/test_fincas_roundtrip.py`.
- [x] `W05.P15.S146` - Migrate the FilingRepository and any rental-keyed repositories to the new Fincas table and column names with coordinated SecureObjectRepository roundtrip coverage; `src/aeat/adapters/persistence/storage/sql/_repositories.py`.
