---
tags:
  - '#plan'
  - '#code-duplication-sweep'
date: '2026-05-19'
tier: L3
related:
  - '[[2026-05-19-code-duplication-sweep-research]]'
  - '[[2026-05-19-code-duplication-sweep-adr]]'
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
- [ ] `W02.P02.S07` - Extract shared repository roundtrip testing utility to replace duplicate assertions; `src/aeat/adapters/persistence/storage/conftest.py`.

### Phase `W02.P03` - Consolidate External Integrations

Unify copy-pasted pdfplumber extraction logic, logging control suppression, and live oracle checker drivers.

- [ ] `W02.P03.S08` - Migrate all PDF text extraction calls to canonical pdfplumber utility and implement the shared `_suppress_pdfminer_debug_logging` control to eliminate PDF logging noise globally; `src/aeat/adapters/inbound/pdf/_pdfplumber.py`.
- [ ] `W02.P03.S09` - Refactor borrador parser to use shared PDF text extraction utility; `src/aeat/adapters/inbound/borrador/_parsers/_pdfplumber_backend.py`.
- [ ] `W02.P03.S10` - Refactor declaracion parser to use shared PDF text extraction utility; `src/aeat/adapters/inbound/declaracion/_parsers/_pdfplumber_backend.py`.
- [ ] `W02.P03.S11` - Extract BaseCheckerOracle and shared JSON-decoding replay driver under live parity backend; `src/aeat/domain/calculations/registry/_live_parity.py`.
- [ ] `W02.P03.S12` - Refactor AeatNifIvaCheckerOracle to inherit from BaseCheckerOracle; `src/aeat/domain/calculations/registry/_aeat_nif_iva_oracle.py`.
- [ ] `W02.P03.S13` - Refactor GroiCheckerOracle to inherit from BaseCheckerOracle; `src/aeat/domain/calculations/registry/_groi_oracle.py`.

## Wave `W03` - Acronym & Term Standardization

Standardize the dual-acronym structures (VAT vs IVA) and triple-terminology divides (Filing vs Modelo vs Declaración), deprecating redundant draft persistence blocks.

### Phase `W03.P04` - Consolidate Value-Added Tax (VAT vs IVA)

Establish a uniform terminology glossary and merge overlapping classification logic into a canonical VAT domain package.

- [ ] `W03.P04.S14` - Create canonical IVA invoice classification schema as the unified surface under domain/iva, absorbing VatClassification and IvaInvoiceClassification; `src/aeat/domain/iva/_classification.py`.
- [ ] `W03.P04.S15` - Migrate VatRegulation, VATRateKind, and VATCatalogue into IvaRegulation, IvaRateKind, and IvaCatalogue under domain/iva, reconciling with any existing IVA equivalents; `src/aeat/domain/iva/_schema.py`.
- [ ] `W03.P04.S18` - Migrate VatLedgerSelector callsites to the canonical _IvaLedgerSelector under domain/iva and remove the duplicate selector; `src/aeat/domain/iva/_flow.py`.
- [ ] `W03.P04.S19` - Collapse IssuerResidency and CustomerResidency into a single IvaResidency enum used in both issuer and customer field roles; `src/aeat/domain/iva/_classification.py`.
- [ ] `W03.P04.S20` - Collapse InvoiceDirection into the existing InvoiceKind enum and remove the InvoiceDirection symbol; `src/aeat/domain/iva/_classification.py`.
- [ ] `W03.P04.S21` - Rename the domain package from domain/vat to domain/iva and update every import site to the new path; `src/aeat/domain/iva/__init__.py`.
- [ ] `W03.P04.S22` - Delete the legacy domain/vat package directory after all consumers have migrated to domain/iva; `src/aeat/domain/vat/`.

### Phase `W03.P05` - Unify Draft Persistence and Deprecate Local file-based Snapshotting

Retire the insecure local file-based borrador.py snapshotting strategy and consolidate all Modelo 100 draft persistence under borrador_100.py.

- [ ] `W03.P05.S16` - Migrate all active commands from local file-based borrador storage to secure borrador_100 object repository; `src/aeat/application/live/_borrador_100.py`.
- [ ] `W03.P05.S17` - Delete deprecated local filesystem-based borrador parser file-caching implementation; `src/aeat/application/live/_borrador.py`.

## Wave `W04` - Spanish-Stem Terminology Renames

Execute the ADR-approved English-to-Spanish identifier renames across the Declaracion, Censo, and Modelo clusters, plus consolidate DraftStatus and FilingDraftStatus into a single ModeloDraftStatus enum. Each phase covers one cluster (or one subdomain of the Modelo cluster) so coders can execute in parallel without rename conflicts. No shims, no deprecation aliases; every callsite migrates in lockstep with its definition.

### Phase `W04.P06` - Declaration to Declaracion Rename

Rename the 20 Declaration-prefixed identifiers to Declaracion across the outbound Sede contract, application filing/review/workflow surface, registry live-parity, and domain reconciliation. Public-API rows in the outbound Sede contract are coordinated cuts: every callsite renames in the same commit.

- [ ] `W04.P06.S23` - Rename Declaration to Declaracion in the outbound Sede declarations surface; `src/aeat/adapters/outbound/aeat/sede/_declarations.py`.
- [ ] `W04.P06.S24` - Rename DeclarationsRegisterSession to DeclaracionesRegisterSession in the outbound Sede declarations surface; `src/aeat/adapters/outbound/aeat/sede/_declarations.py`.
- [ ] `W04.P06.S25` - Rename FiledDeclarationArtefact to FiledDeclaracionArtefact in the outbound Sede schema; `src/aeat/adapters/outbound/aeat/sede/_schema.py`.
- [ ] `W04.P06.S26` - Rename FiledDeclarationObservation to FiledDeclaracionObservation in the outbound Sede schema; `src/aeat/adapters/outbound/aeat/sede/_schema.py`.
- [ ] `W04.P06.S27` - Rename FiledDeclarationObservationStore to FiledDeclaracionObservationStore; `src/aeat/adapters/outbound/aeat/sede/_observation_store.py`.
- [ ] `W04.P06.S28` - Rename DeclarationCalculateNextAction to DeclaracionCalculateNextAction; `src/aeat/application/filing/_calculate.py`.
- [ ] `W04.P06.S29` - Rename DeclarationCalculateSummary to DeclaracionCalculateSummary; `src/aeat/application/filing/_calculate.py`.
- [ ] `W04.P06.S30` - Rename DeclarationExportFormat to DeclaracionExportFormat; `src/aeat/application/filing/_export.py`.
- [ ] `W04.P06.S31` - Rename DeclarationVerifyVerdict to DeclaracionVerifyVerdict; `src/aeat/application/filing/_export.py`.
- [ ] `W04.P06.S32` - Rename DeclarationExportResult to DeclaracionExportResult; `src/aeat/application/filing/_export.py`.
- [ ] `W04.P06.S33` - Rename DeclarationVerifyResult to DeclaracionVerifyResult; `src/aeat/application/filing/_export.py`.
- [ ] `W04.P06.S34` - Rename DeclarationEditSpec to DeclaracionEditSpec; `src/aeat/application/review/_edit.py`.
- [ ] `W04.P06.S35` - Rename DeclarationReviewFilterKey to DeclaracionReviewFilterKey; `src/aeat/application/review/_filter.py`.
- [ ] `W04.P06.S36` - Rename DeclarationReviewStatus to DeclaracionReviewStatus; `src/aeat/application/review/_filter.py`.
- [ ] `W04.P06.S37` - Rename DeclarationReviewFilterSpec to DeclaracionReviewFilterSpec; `src/aeat/application/review/_filter.py`.
- [ ] `W04.P06.S38` - Rename DeclarationPointer to DeclaracionPointer; `src/aeat/application/workflow/_models.py`.
- [ ] `W04.P06.S39` - Rename DeclarationParseError to DeclaracionParseError; `src/aeat/domain/filing/reconciliation/_errors.py`.
- [ ] `W04.P06.S40` - Rename ReconciliationDeclarationSourceUnsupportedError to ReconciliationDeclaracionSourceUnsupportedError; `src/aeat/application/modelo/_reconcile.py`.
- [ ] `W04.P06.S41` - Rename CrossReferenceApplicabilityDeclaration to CrossReferenceApplicabilityDeclaracion; `src/aeat/domain/calculations/registry/_live_parity.py`.
- [ ] `W04.P06.S42` - Rename RentaDeclarationType to RentaDeclaracionType in the renta codes module; `src/aeat/domain/profile/_renta_codes.py`.

### Phase `W04.P07` - Census to Censo Rename

Rename the 22 Census-prefixed identifiers to Censo across application profile sync, live snapshot, domain calculations registry, and outbound Sede surfaces. The module paths application/live/_census.py and adapters/outbound/aeat/sede/_census.py rename to _censo.py in lockstep with the contained symbols. The CensoSnapshot retains its Snapshot infra suffix per the ADR disambiguation rule.

- [ ] `W04.P07.S43` - Rename CensusSyncError to CensoSyncError; `src/aeat/application/profile/_census_errors.py`.
- [ ] `W04.P07.S44` - Rename CensusNotAvailableError to CensoNotAvailableError; `src/aeat/application/profile/_census_errors.py`.
- [ ] `W04.P07.S45` - Rename CensusFieldValidationError to CensoFieldValidationError; `src/aeat/application/profile/_census_errors.py`.
- [ ] `W04.P07.S46` - Rename CensusApplyConflictError to CensoApplyConflictError; `src/aeat/application/profile/_census_errors.py`.
- [ ] `W04.P07.S47` - Rename CensusComparisonStatus to CensoComparisonStatus; `src/aeat/application/profile/_census_sync.py`.
- [ ] `W04.P07.S48` - Rename CensusFieldComparison to CensoFieldComparison; `src/aeat/application/profile/_census_sync.py`.
- [ ] `W04.P07.S49` - Rename CensusProfileComparison to CensoProfileComparison; `src/aeat/application/profile/_census_sync.py`.
- [ ] `W04.P07.S50` - Rename CensusApplyResult to CensoApplyResult; `src/aeat/application/profile/_census_sync.py`.
- [ ] `W04.P07.S51` - Rename CensusSyncService to CensoSyncService; `src/aeat/application/profile/_census_sync.py`.
- [ ] `W04.P07.S52` - Rename CensusSnapshot to CensoSnapshot (retain Snapshot infra suffix per ADR disambiguation rule); `src/aeat/application/live/_censo.py`.
- [ ] `W04.P07.S53` - Rename module application/live/_census.py to _censo.py in lockstep with the Censo rename; `src/aeat/application/live/_censo.py`.
- [ ] `W04.P07.S54` - Rename CensusStaleRefusedError to CensoStaleRefusedError; `src/aeat/domain/modelos/_errors.py`.
- [ ] `W04.P07.S55` - Rename CensusRatioMismatchError to CensoRatioMismatchError; `src/aeat/domain/usage_ratios/_errors.py`.
- [ ] `W04.P07.S56` - Rename RatiosCensusOverrideWarning to RatiosCensoOverrideWarning; `src/aeat/application/ledger/_ratios.py`.
- [ ] `W04.P07.S57` - Rename CensusModeloRole to CensoModeloRole; `src/aeat/domain/calculations/registry/_census_modelos.py`.
- [ ] `W04.P07.S58` - Rename CensusModeloEventKind to CensoModeloEventKind; `src/aeat/domain/calculations/registry/_census_modelos.py`.
- [ ] `W04.P07.S59` - Rename CensusModeloFoundationLogFields to CensoModeloFoundationLogFields; `src/aeat/domain/calculations/registry/_census_modelos.py`.
- [ ] `W04.P07.S60` - Rename CensusModeloOwnership to CensoModeloOwnership; `src/aeat/domain/calculations/registry/_census_modelos.py`.
- [ ] `W04.P07.S61` - Rename CensusModeloFoundationContract to CensoModeloFoundationContract; `src/aeat/domain/calculations/registry/_census_modelos.py`.
- [ ] `W04.P07.S62` - Rename CensusModeloFoundationCommand to CensoModeloFoundationCommand; `src/aeat/domain/calculations/registry/_census_modelos.py`.
- [ ] `W04.P07.S63` - Rename CensusModeloFoundationResult to CensoModeloFoundationResult; `src/aeat/domain/calculations/registry/_census_modelos.py`.
- [ ] `W04.P07.S64` - Rename CensusFactSet to CensoFactSet and module _census.py to _censo.py under outbound Sede; `src/aeat/adapters/outbound/aeat/sede/_censo.py`.
- [ ] `W04.P07.S65` - Rename CensusParseError to CensoParseError under outbound Sede; `src/aeat/adapters/outbound/aeat/sede/_censo.py`.

### Phase `W04.P08` - Modelo Cluster: domain/filing Schema and Errors

Rename the Filing-prefixed identifiers under src/aeat/domain/filing/ to their Modelo equivalents: schema records, validators, amendment models, errors, protocols, and the FilingDraftRepository. Self-contained domain package; no cross-domain ripple within this phase.


### Phase `W04.P09` - Modelo Cluster: domain/modelos FilingRecord Consolidation

Rename FilingRecord, FilingRecordStatus, FilingRecordCatalogue and friends to their Modelo equivalents under src/aeat/domain/modelos/ while preserving the split between ModeloRecord (domain pydantic) and ModeloRow (SQL ORM) per project-lead adjudication of ADR footnote 1. Schema-impact rows; gated by the standard roundtrip-test pattern.


### Phase `W04.P10` - Modelo Cluster: domain/deadlines and domain/calculations

Rename FilingObligation, FilingEnrollment, FilingIVAProfile under domain/deadlines, and FilingScheduleDefinition, RegistryFilingObservation, OracleFilingObservation, RegistryFilingObservationRequirement, _PreviousFilingSelector under domain/calculations/registry. These are cross-domain registry symbols; rename in coordinated commits with their importers.


### Phase `W04.P11` - Modelo Cluster: application/filing, application/modelo, application/workflow

Rename Filing-prefixed identifiers across the application layer: filing errors, history, review, reconciliation, runtime, testing harnesses, workflow adapters and protocols, and modelo action errors. The CLI _modelo_payloads renames are public-API and coordinate with operator-facing locale refresh.


### Phase `W04.P12` - Modelo Cluster: domain/submission and domain/justificante

Rename FilingFindingSeverity, FilingFinding, FilingDraftLike, DraftLoader, SubmittedFiling under domain/submission, and PdfFilingImportError under domain/justificante. DraftStatus consolidation is the dedicated next phase; here only the prefix renames land.


### Phase `W04.P13` - DraftStatus Consolidation to Single ModeloDraftStatus

Per project-lead adjudication of ADR footnote 2, consolidate DraftStatus (domain/submission) and FilingDraftStatus (domain/filing) into a single canonical ModeloDraftStatus enum and remove the duplicate. Single coordinated step; every callsite migrates in the same commit.
