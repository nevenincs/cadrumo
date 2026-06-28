---
tags:
  - '#adr'
  - '#code-duplication-sweep'
date: '2026-05-19'
modified: '2026-05-19'
related:
  - "[[2026-05-19-code-duplication-sweep-research]]"
  - "[[2026-05-19-spanish-tax-glossary-reference]]"
  - "[[2026-05-19-code-duplication-sweep-adr]]"
---


# spanish-stem-terminology-authority adr: Spanish Stem Terminology Authority for Tax-Domain Identifiers | (**status:** accepted)

## Problem Statement

The code-duplication-sweep campaign audit catalogued large-scale English/Spanish terminology drift across the codebase:

- 189 identifier candidates flagged across src/aeat/** for stem drift (filing/modelo, declaration/declaracion, census/censo, borrador/draft/snapshot, vat/iva, renta/rental, etc.).
- 251 exception class definitions audited; 3 class-name collisions (StorageError, StorageValidationError, WorkUnitNotFoundError, plus the NoActiveBucketError family), one parent-class divergence on WorkUnitNotFoundError, and 2 dead exceptions.
- 23 numbered duplication findings in the deeper structural sweep, plus 13 adapter-layer ENG/ESP drift candidates concentrated in the outbound Sede artefacts (Declaration*, FiledDeclaration*) and the SQL ORM Rental*Row cluster.
- Public-API and persistence-layer surfaces are split between Spanish stems in some packages (domain/renta, domain/justificante, domain/modelos) and pure English in others (domain/vat, domain/rental, outbound Declaration*).

The prior code-duplication-sweep ADR proposed consolidating Value-Added Tax under English in domain/vat, with VatClassification absorbing IvaInvoiceClassification. The project lead has since declared Spanish stems authoritative for tax-system terms, reversing that direction and requiring a fresh decision document.

## Considerations

- The accepted Spanish-tax-glossary reference document cites the primary BOE or AEAT source for every canonical stem.
- Hexagonal boundaries must hold. Adapter renames ripple to wire formats; persistence renames carry schema-migration cost; domain renames stay in-process.
- The 189-row raw inventory contains known stem-stuttering proposals that must not be executed verbatim (e.g. BorradorBorrador, RentaRenta, FincasFinca).
- Zero-mock and roundtrip-discipline gates require that every rename flows through to real-adapter persistence tests; no rename is cosmetic.
- The campaign master tracker remains the code-duplication-sweep feature; this ADR is filed under that feature tag.

## Constraints

- Adapter-layer renames touching the outbound Sede contract must preserve wire-format compatibility with AEAT responses; identifier renames affect Python symbols only, never serialised payloads controlled by AEAT.
- Persistence renames where the identifier is encoded in column names, table names, or envelope schema headers require a strict roundtrip-test gate before and after the rename.
- Public CLI JSON contract field names are not in scope for this ADR.
- The Spanish-stem rule applies only to tax-domain identifiers as catalogued in the glossary reference. Infrastructure suffixes and international identifiers remain English.


## Implementation

### 1. Decision

Spanish stems are authoritative for tax-domain identifiers. The canonical stems, each grounded in the cited primary source, are:

- iva per Ley 37/1992 IVA (BOE-A-1992-28740). Supersedes vat, value_added_tax.
- irpf per Ley 35/2006 IRPF (BOE-A-2006-20764). Supersedes income_tax, personal_income_tax, pit.
- modelo per AEAT Sede Electronica nomenclature and the per-modelo Ordenes Ministeriales (e.g. Orden HFP/227/2017 for Modelo 303). Supersedes form, tax_form, return_form. Always followed by the three-digit modelo number.
- declaracion per Ley 58/2003 LGT Articulo 119 (BOE-A-2003-23186). Supersedes declaration, return when used in the LGT-119 sense.
- autoliquidacion per Ley 58/2003 LGT Articulo 120. Supersedes self_assessment, self_liquidation.
- justificante per AEAT Sede Electronica (CSV / justificante de presentacion workflow); regulatory framework Ley 39/2015 LPAC Articulo 27 (BOE-A-2015-10565), with direct CSV regime grounded in Articulo 27.3 and Real Decreto 203/2021. Supersedes receipt, proof, confirmation when the artifact is the AEAT submission attestation. Does not absorb factura (commercial invoice, RD 1619/2012) or recibo (commercial receipt).
- borrador per Ley 35/2006 IRPF Articulo 98 (AEAT Renta Web draft). Supersedes draft, prefill when the entity is the AEAT-prepared Modelo 100 draft.
- renta per Ley 35/2006 IRPF (Titulo I, Capitulo I). Supersedes income in the IRPF base sense. Never collapses with English rental.
- fincas (singular finca) per Ley Hipotecaria (Decreto 1946, BOE-A-1946-2453) and RDLeg 1/2004 del Catastro Inmobiliario. Supersedes real_estate, properties when the unit is a registrable real-estate parcel.
- expediente per Ley 39/2015 LPAC Articulo 70 (BOE-A-2015-10565). Supersedes case_file, case when the artifact is the AEAT administrative expediente.
- censo per RD 1065/2007 RGAGI Titulo II Capitulo I (BOE-A-2007-15984). Supersedes census, taxpayer_registry. declaracion_censal for Modelos 036 / 037.
- ccaa / comunidad_autonoma per Constitucion Espanola Titulo VIII; financial framework LOFCA (Ley Organica 8/1980). Already standardised.

### 2. English exceptions (retained)

The following remain in English regardless of the Spanish-stem default and are explicitly composable with Spanish stems as suffixes:

- International identifiers fixed in BOE or ISO standards: NIF, CIF, NIE, IBAN (ISO 13616), SWIFT / BIC (ISO 9362).
- Python standard-library primitives: Decimal, datetime, bool, str, int. Never translated.
- Generic infrastructure suffixes used in adapter and persistence layers. These compose with Spanish stems; they do not replace them: Snapshot, Repository, Record, Row, Service, Factory, Validator, Observation, Protocol, Error, Selector, Catalogue, Store, Adapter, Driver, Oracle, Result, Payload, Ref, Spec, Kind, Status.
- Examples of valid composition: ModeloRepository, DeclaracionObservation, Borrador100Snapshot, JustificanteFetchError, FincaRow, CensoSyncService.

These suffixes remain English because they encode generic infrastructure roles, not tax semantics, and translating them would produce stem-stuttering or over-translation (FilaModelo, RegistroModelo, OracleVerificador).

### 3. Stem-stuttering rule

No rename may produce stem-stuttering. If the canonical stem already appears in the identifier, do not re-add it during the rename. The following raw-inventory proposals are explicitly invalid and must be filtered out by any executing agent:

- BorradorSnapshotNotFoundError to BorradorBorradorNotFoundError.
- Borrador100Snapshot to Borrador100Borrador.
- RentaIncomeType to RentaRentaType.
- RentalFinca to FincasFinca (also blocked on Renta vs Rental adjudication; Fincas is plural and incorrect as a singular class prefix in any case).
- Any Snapshot to Borrador rename where the entity is a generic state-capture (ProfileSnapshot, RegistrySnapshot, AeatGateEnvSnapshot, etc.).

The rule generalises: a single canonical stem appears at most once per identifier, and the surrounding tokens are infrastructure suffixes from the English-exceptions list.


### 4. Snapshot disambiguation

Snapshot is a generic infrastructure suffix and stays English in every case EXCEPT where the entity is itself the AEAT-prepared Modelo draft. The semantic test is what entity is captured, not what suffix is used:

- Snapshot stays as a generic state-capture suffix when the underlying entity is a Sede scrape, an AEAT remote-state cache, or a point-in-time snapshot of a domain record. Examples: CensusSnapshot (becomes CensoSnapshot for stem reasons, but retains Snapshot), ProfileSnapshot, RegistrySnapshot, AeatGateEnvSnapshot, ExpedienteSnapshot, NotificationSnapshot.
- Borrador100Snapshot keeps the Borrador stem because the entity itself is the AEAT borrador (Ley 35/2006 Art. 98); Snapshot here is the generic cache-state suffix on top of the borrador entity. The composition Borrador100Snapshot is therefore correct and is NOT a stem stutter.

The rule is therefore: rename the stem token within the identifier to its Spanish form (Census to Censo, Expediente already correct), but leave the Snapshot suffix in place.

### 5. Renta vs Rental adjudication

The Renta (IRPF base) vs Rental (English rental-property terminology) collision is the single largest blocked rename surface, covering the entire domain/rental package, the Rental*Row cluster in adapters/persistence/storage/sql/_orm.py, and the RentalAmortizationLedger family.

Decision: rename domain/rental to domain/fincas.

Justification:

- The domain primary tax surface is rendimientos del capital inmobiliario, which AEAT settles per finca (registrable parcel) for Modelo 100 and Modelo 210. The unit of account is the finca, not the lease contract.
- fincas is the BOE term per Ley Hipotecaria and the Catastro Inmobiliario (RDLeg 1/2004) and is also used for Modelo 347 arrendamientos and IBI municipal references. It is the broadest authoritative covering term.
- alquiler (rental contract) is one possible status of a finca, not the canonical unit; restricting the domain to alquiler would exclude vacant fincas, owner-occupied fincas declared for imputed-renta purposes, and non-leased parcels feeding Modelo 100.
- Operational status (is_rented, lease_active) becomes a field on the finca model, not a package name.

Consequences of this adjudication:

- The package path becomes src/aeat/domain/fincas/.
- Identifiers rename per the canonical ledger below: RentalFinca to Finca, RentalContract to Arrendamiento, RentalIncome* to Finca* with the income/expense role expressed as a separate suffix, RentalAmortizationLedger to FincaAmortizationLedger.
- Existing Renta* identifiers under domain/renta are unaffected; the IRPF income-base package stays domain/renta.
- The SQL ORM Rental*Row cluster renames in lockstep with the domain package and is gated by a roundtrip-test pass.

### 6. Supersession of the prior W03.P04 direction

The prior code-duplication-sweep ADR proposed creating a VatClassification schema under domain/vat and absorbing IvaInvoiceClassification into it. That direction is reversed:

- IvaInvoiceClassification is canonical.
- VatClassification, VatRegulation, VATRateKind, the entire domain/vat package surface, the IssuerResidency / CustomerResidency pair, and InvoiceDirection migrate into domain/iva (or the existing IVA-bearing package, to be selected during plan retargeting).
- _iva_ledger.py and _IvaLedgerSelector are the canonical ledger-aggregation surface.
- The W03.P04 phase in the existing plan must be retargeted by the plan-authoring agent to consolidate VAT into IVA, not the reverse.


### 7. Canonical rename ledger

The tables below are the QC-filtered, ADR-Specialist-approved subset of the 189-row raw inventory. Rows where the raw inventory proposed stem-stuttering, generic-infra translation, or international-identifier translation have been removed. Rows blocked on the Renta-vs-Rental adjudication are included now that the adjudication is settled. Stem authority cites the canonical glossary entry; phase references map to the existing plan wave/phase structure where known and to TBD where plan retargeting is required.

#### Modelo cluster (Filing to Modelo)

Stem authority: modelo per AEAT nomenclature and per-modelo Ordenes Ministeriales.

| Current | Location | Approved Rename | Phase |
| --- | --- | --- | --- |
| FilingDraft | src/aeat/domain/filing/_schema.py | ModeloDraft | TBD |
| FilingDraftStatus | src/aeat/domain/filing/_schema.py | ModeloDraftStatus | TBD |
| FilingValue | src/aeat/domain/filing/_schema.py | ModeloValue | TBD |
| FilingValueKind | src/aeat/domain/filing/_schema.py | ModeloValueKind | TBD |
| FilingBindingValue | src/aeat/domain/filing/_schema.py | ModeloBindingValue | TBD |
| FilingValidationFinding | src/aeat/domain/filing/_schema.py | ModeloValidationFinding | TBD |
| FilingApprovalBasis | src/aeat/domain/filing/_schema.py | ModeloApprovalBasis | TBD |
| FilingValidator | src/aeat/domain/filing/_validator.py | ModeloValidator | TBD |
| FilingAmendment | src/aeat/domain/filing/_amendment.py | ModeloAmendment | TBD |
| FilingAmendmentError | src/aeat/domain/filing/_errors.py | ModeloAmendmentError | TBD |
| FilingDraftError | src/aeat/domain/filing/_errors.py | ModeloDraftError | TBD |
| FilingBuilderError | src/aeat/domain/filing/_errors.py | ModeloBuilderError | TBD |
| FilingValidationError | src/aeat/domain/filing/_errors.py | ModeloValidationError | TBD |
| FilingComputationError | src/aeat/domain/filing/_errors.py | ModeloComputationError | TBD |
| FilingImportError | src/aeat/domain/filing/_errors.py | ModeloImportError | TBD |
| FilingExportError | src/aeat/domain/filing/_errors.py | ModeloExportError | TBD |
| FilingExportValidationError | src/aeat/domain/filing/_errors.py | ModeloExportValidationError | TBD |
| FilingProfile | src/aeat/domain/filing/_protocols.py | ModeloProfile | TBD |
| FilingDraftRepository | src/aeat/domain/filing/_repository.py | ModeloDraftRepository | TBD |
| FilingRecord | src/aeat/domain/modelos/_filing_record.py | ModeloRecord (consolidates with persistence-side; see footnote 1) | schema-impact |
| FilingRecordStatus | src/aeat/domain/modelos/_filing_record.py | ModeloRecordStatus | schema-impact |
| FilingRecordCatalogue | src/aeat/domain/modelos/_filing_record.py | ModeloRecordCatalogue | schema-impact |
| FilingRecordPersistenceError | src/aeat/domain/modelos/_filing_record.py | ModeloRecordPersistenceError | schema-impact |
| FilingRecordCatalogueRepository | src/aeat/domain/modelos/_filing_repository.py | ModeloRecordCatalogueRepository | schema-impact |
| FilingObligation | src/aeat/domain/deadlines/_models.py | ModeloObligation | TBD |
| FilingEnrollment | src/aeat/domain/deadlines/_models.py | ModeloEnrollment | TBD |
| FilingIVAProfile | src/aeat/domain/deadlines/_models.py | ModeloIvaProfile | TBD |
| FilingScheduleDefinition | src/aeat/domain/calculations/registry/_schema.py | ModeloScheduleDefinition | TBD |
| RegistryFilingObservation | src/aeat/domain/calculations/registry/_bindings.py | RegistryModeloObservation | TBD |
| OracleFilingObservation | src/aeat/domain/calculations/registry/_bindings.py | OracleModeloObservation | TBD |
| RegistryFilingObservationRequirement | src/aeat/domain/calculations/registry/_bindings.py | RegistryModeloObservationRequirement | TBD |
| _PreviousFilingSelector | src/aeat/domain/calculations/registry/_bindings.py | _PreviousModeloSelector | TBD |
| FilingApplicationError | src/aeat/application/filing/errors.py | ModeloApplicationError | TBD |
| FilingCalculateError | src/aeat/application/filing/errors.py | ModeloCalculateError | TBD |
| FilingHistory | src/aeat/application/filing/_history_models.py | ModeloHistory | TBD |
| FilingHistoryEntry | src/aeat/application/filing/_history_models.py | ModeloHistoryEntry | TBD |
| FilingHistoryRepository | src/aeat/application/filing/_history_repository.py | ModeloHistoryRepository | TBD |
| FilingApprovalStaleReason | src/aeat/application/filing/_review.py | ModeloApprovalStaleReason | TBD |
| FilingDivergenceKind | src/aeat/application/filing/reconciliation/ | ModeloDivergenceKind | TBD |
| FilingDraftRef | src/aeat/application/filing/reconciliation/ | ModeloDraftRef | TBD |
| FilingOperatorProfile | src/aeat/application/filing/runtime.py | ModeloOperatorProfile | TBD |
| RegistryFilingSubview | src/aeat/application/filing/runtime.py | RegistryModeloSubview | TBD |
| FilingTestProfile | src/aeat/application/filing/testing.py | ModeloTestProfile | TBD |
| FilingTestDeadlineStatus | src/aeat/application/filing/testing.py | ModeloTestDeadlineStatus | TBD |
| FilingTestDeadlineChecker | src/aeat/application/filing/testing.py | ModeloTestDeadlineChecker | TBD |
| FilingDraftBuilderAdapter | src/aeat/application/workflow/_adapters.py | ModeloDraftBuilderAdapter | TBD |
| RegistryFilingDraftProtocol | src/aeat/application/workflow/_protocols.py | RegistryModeloDraftProtocol | TBD |
| FilingDraftBuilderProtocol | src/aeat/application/workflow/_protocols.py | ModeloDraftBuilderProtocol | TBD |
| FilingInputsProviderProtocol | src/aeat/application/workflow/_protocols.py | ModeloInputsProviderProtocol | TBD |
| FilingRecordNotFoundError | src/aeat/application/modelo/_actions.py | ModeloRecordNotFoundError | TBD |
| ExternalFilingImportError | src/aeat/application/modelo/_actions.py | ExternalModeloImportError | TBD |
| FilingFixtureError | src/aeat/core/errors/__init__.py | ModeloFixtureError | TBD |
| FilingRecordPayload | src/aeat/entrypoints/cli/_modelo_payloads.py | ModeloRecordPayload | public-API |
| FilingRecordListResult | src/aeat/entrypoints/cli/_modelo_payloads.py | ModeloRecordListResult | public-API |
| FilingRecordShowResult | src/aeat/entrypoints/cli/_modelo_payloads.py | ModeloRecordShowResult | public-API |
| FilingFindingSeverity | src/aeat/domain/submission/ | ModeloFindingSeverity | TBD |
| FilingFinding | src/aeat/domain/submission/ | ModeloFinding | TBD |
| FilingDraftLike | src/aeat/domain/submission/ | ModeloDraftLike | TBD |
| DraftLoader | src/aeat/domain/submission/ | ModeloDraftLoader | TBD |
| DraftStatus | src/aeat/domain/submission/_protocols.py | consolidate with ModeloDraftStatus (see footnote 2) | TBD |
| SubmittedFiling | src/aeat/domain/submission/ | SubmittedModelo | TBD |
| PdfFilingImportError | src/aeat/domain/justificante/_errors.py | PdfModeloImportError | TBD |

Footnote 1: ModeloRecord already exists in src/aeat/adapters/persistence/storage/sql/records.py. The consolidation must reconcile the domain FilingRecord (pydantic write-active boundary record) with the persistence ModeloRecord (SQL row). Project lead to confirm whether they collapse into one type or whether the SQL row becomes ModeloRow (already present in _orm.py) with ModeloRecord as the domain pydantic record.

Footnote 2: DraftStatus and FilingDraftStatus carry identical 10-value sets. Consolidate to a single ModeloDraftStatus enum and remove the duplicate.


#### Declaracion cluster (Declaration to Declaracion)

Stem authority: declaracion per Ley 58/2003 LGT Articulo 119.

| Current | Location | Approved Rename | Phase |
| --- | --- | --- | --- |
| Declaration | src/aeat/adapters/outbound/aeat/sede/_declarations.py | Declaracion | public-API |
| DeclarationsRegisterSession | src/aeat/adapters/outbound/aeat/sede/_declarations.py | DeclaracionesRegisterSession | public-API |
| FiledDeclarationArtefact | src/aeat/adapters/outbound/aeat/sede/_schema.py | FiledDeclaracionArtefact | public-API |
| FiledDeclarationObservation | src/aeat/adapters/outbound/aeat/sede/_schema.py | FiledDeclaracionObservation | public-API |
| FiledDeclarationObservationStore | src/aeat/adapters/outbound/aeat/sede/_observation_store.py | FiledDeclaracionObservationStore | public-API |
| DeclarationCalculateNextAction | src/aeat/application/filing/_calculate.py | DeclaracionCalculateNextAction | TBD |
| DeclarationCalculateSummary | src/aeat/application/filing/_calculate.py | DeclaracionCalculateSummary | TBD |
| DeclarationExportFormat | src/aeat/application/filing/_export.py | DeclaracionExportFormat | TBD |
| DeclarationVerifyVerdict | src/aeat/application/filing/_export.py | DeclaracionVerifyVerdict | TBD |
| DeclarationExportResult | src/aeat/application/filing/_export.py | DeclaracionExportResult | TBD |
| DeclarationVerifyResult | src/aeat/application/filing/_export.py | DeclaracionVerifyResult | TBD |
| DeclarationEditSpec | src/aeat/application/review/_edit.py | DeclaracionEditSpec | TBD |
| DeclarationReviewFilterKey | src/aeat/application/review/_filter.py | DeclaracionReviewFilterKey | TBD |
| DeclarationReviewStatus | src/aeat/application/review/_filter.py | DeclaracionReviewStatus | TBD |
| DeclarationReviewFilterSpec | src/aeat/application/review/_filter.py | DeclaracionReviewFilterSpec | TBD |
| DeclarationPointer | src/aeat/application/workflow/_models.py | DeclaracionPointer | TBD |
| DeclarationParseError | src/aeat/domain/filing/reconciliation/_errors.py | DeclaracionParseError | TBD |
| ReconciliationDeclarationSourceUnsupportedError | src/aeat/application/modelo/_reconcile.py | ReconciliationDeclaracionSourceUnsupportedError | TBD |
| CrossReferenceApplicabilityDeclaration | src/aeat/domain/calculations/registry/_live_parity.py | CrossReferenceApplicabilityDeclaracion | TBD |
| RentaDeclarationType | src/aeat/domain/profile/_renta_codes.py | RentaDeclaracionType | TBD |

#### Censo cluster (Census to Censo)

Stem authority: censo per RD 1065/2007 RGAGI.

| Current | Location | Approved Rename | Phase |
| --- | --- | --- | --- |
| CensusSyncError | src/aeat/application/profile/_census_errors.py | CensoSyncError | TBD |
| CensusNotAvailableError | src/aeat/application/profile/_census_errors.py | CensoNotAvailableError | TBD |
| CensusFieldValidationError | src/aeat/application/profile/_census_errors.py | CensoFieldValidationError | TBD |
| CensusApplyConflictError | src/aeat/application/profile/_census_errors.py | CensoApplyConflictError | TBD |
| CensusComparisonStatus | src/aeat/application/profile/_census_sync.py | CensoComparisonStatus | TBD |
| CensusFieldComparison | src/aeat/application/profile/_census_sync.py | CensoFieldComparison | TBD |
| CensusProfileComparison | src/aeat/application/profile/_census_sync.py | CensoProfileComparison | TBD |
| CensusApplyResult | src/aeat/application/profile/_census_sync.py | CensoApplyResult | TBD |
| CensusSyncService | src/aeat/application/profile/_census_sync.py | CensoSyncService | TBD |
| CensusSnapshot | src/aeat/application/live/_census.py | CensoSnapshot (Snapshot suffix retained per disambiguation rule) | TBD |
| CensusStaleRefusedError | src/aeat/domain/modelos/_errors.py | CensoStaleRefusedError | TBD |
| CensusRatioMismatchError | src/aeat/domain/usage_ratios/_errors.py | CensoRatioMismatchError | TBD |
| RatiosCensusOverrideWarning | src/aeat/application/ledger/_ratios.py | RatiosCensoOverrideWarning | TBD |
| CensusModeloRole | src/aeat/domain/calculations/registry/_census_modelos.py | CensoModeloRole | TBD |
| CensusModeloEventKind | src/aeat/domain/calculations/registry/_census_modelos.py | CensoModeloEventKind | TBD |
| CensusModeloFoundationLogFields | src/aeat/domain/calculations/registry/_census_modelos.py | CensoModeloFoundationLogFields | TBD |
| CensusModeloOwnership | src/aeat/domain/calculations/registry/_census_modelos.py | CensoModeloOwnership | TBD |
| CensusModeloFoundationContract | src/aeat/domain/calculations/registry/_census_modelos.py | CensoModeloFoundationContract | TBD |
| CensusModeloFoundationCommand | src/aeat/domain/calculations/registry/_census_modelos.py | CensoModeloFoundationCommand | TBD |
| CensusModeloFoundationResult | src/aeat/domain/calculations/registry/_census_modelos.py | CensoModeloFoundationResult | TBD |
| CensusFactSet | src/aeat/adapters/outbound/aeat/sede/_census.py | CensoFactSet | public-API |
| CensusParseError | src/aeat/adapters/outbound/aeat/sede/_census.py | CensoParseError | public-API |

The module path src/aeat/application/live/_census.py and the outbound module src/aeat/adapters/outbound/aeat/sede/_census.py also rename to _censo.py in lockstep with the contained symbols.


#### IVA cluster (VAT to IVA, reversing prior ADR)

Stem authority: iva per Ley 37/1992 IVA.

| Current | Location | Approved Rename | Phase |
| --- | --- | --- | --- |
| VatClassification | src/aeat/domain/vat/_classification.py | merge into IvaInvoiceClassification; VatClassification deleted | W03.P04 (retargeted) |
| VatRegulation | src/aeat/domain/vat/_classification.py | IvaRegulation (consolidate with existing IvaRegulation if present) | W03.P04 |
| VATRateKind | src/aeat/domain/vat/_schema.py | IvaRateKind (consolidate with existing) | W03.P04 |
| VATCatalogue | src/aeat/domain/vat/_schema.py | IvaCatalogue | W03.P04 |
| VatLedgerSelector | src/aeat/domain/vat/_flow.py | _IvaLedgerSelector (already exists; reconcile) | W03.P04 |
| IssuerResidency | src/aeat/domain/vat/_classification.py | IvaIssuerResidency (or consolidate into single IvaResidency enum; see footnote 3) | W03.P04 |
| CustomerResidency | src/aeat/domain/vat/_classification.py | IvaCustomerResidency | W03.P04 |
| InvoiceDirection | src/aeat/domain/vat/_classification.py | consolidate with InvoiceKind into a single InvoiceKind enum; remove InvoiceDirection | W03.P04 |
| IvaFlowDirection | src/aeat/domain/vat/_flow.py | retain as-is (REPERCUTIDO/SOPORTADO/AUTOREPERCUTIDO is IVA-specific; not the same axis as InvoiceKind) | n/a |
| Package path src/aeat/domain/vat/ | n/a | rename to src/aeat/domain/iva/ | W03.P04 (retargeted) |

Footnote 3: IssuerResidency and CustomerResidency carry identical 5-value sets (ES_MAINLAND, ES_CANARIAS, ES_CEUTA_MELILLA, EU_MEMBER, THIRD_COUNTRY). Project lead to confirm whether they collapse into a single IvaResidency enum used in two field roles, or stay as two parallel enums under Spanish names.

#### Fincas cluster (Renta/Rental adjudicated above)

Stem authority: finca per Ley Hipotecaria + RDLeg 1/2004 Catastro.

| Current | Location | Approved Rename | Phase |
| --- | --- | --- | --- |
| Package path src/aeat/domain/rental/ | n/a | rename to src/aeat/domain/fincas/ | schema-impact |
| RentalFinca | src/aeat/domain/rental/_models.py | Finca | schema-impact |
| RentalFincaRow | src/aeat/adapters/persistence/storage/sql/_orm.py | FincaRow | schema-impact |
| RentalContract | src/aeat/domain/rental/_models.py | Arrendamiento | schema-impact |
| RentalContractRow | src/aeat/adapters/persistence/storage/sql/_orm.py | ArrendamientoRow | schema-impact |
| RentalIncomeRecord | src/aeat/domain/rental/_models.py | FincaIncomeRecord (or FincaRendimientoRecord; see open question) | schema-impact |
| RentalIncomeRecordRow | src/aeat/adapters/persistence/storage/sql/_orm.py | FincaIncomeRecordRow | schema-impact |
| RentalExpense | src/aeat/domain/rental/_models.py | FincaExpense (or FincaGasto; see open question) | schema-impact |
| RentalExpenseRow | src/aeat/adapters/persistence/storage/sql/_orm.py | FincaExpenseRow | schema-impact |
| RentalAmortizationLedger | src/aeat/domain/rental/_amortization_ledger.py | FincaAmortizationLedger (verify Amortization vs Amortizacion; see open question) | schema-impact |
| RentalAmortizationLedgerRow | src/aeat/adapters/persistence/storage/sql/_orm.py | FincaAmortizationLedgerRow | schema-impact |

#### Borrador / Draft consolidation cluster

Stem authority: borrador per Ley 35/2006 Articulo 98 (AEAT Renta Web). Snapshot suffix retained per Section 4. Snapshot Service base-class consolidation in W04-new (see next cluster).

| Current | Location | Approved Rename | Phase |
| --- | --- | --- | --- |
| DraftStatus | src/aeat/domain/submission/_protocols.py | merge into ModeloDraftStatus (single canonical enum) | W03-extension |
| DraftLoader | src/aeat/domain/submission/ | ModeloDraftLoader | W03-extension |
| FilingDraftLike | src/aeat/domain/submission/ | ModeloDraftLike | W03-extension |
| Legacy Borrador service module | src/aeat/application/live/_borrador.py | retire; consumers migrate to Borrador100SnapshotService | W04-new |
| Borrador100Snapshot | src/aeat/application/live/_borrador_100.py | KEEP (Borrador entity + Snapshot infra suffix; not stuttering) | n/a |
| Borrador100SnapshotState | src/aeat/application/live/_borrador_100.py | KEEP; promote to shared SnapshotLifecycleState in W04 | W04-new |
| BorradorSnapshotNotFoundError | src/aeat/application/live/ | KEEP name; align parent via shared SnapshotNotFoundError base | W04-new |

#### Snapshot Service consolidation cluster (W04-new)

Per the research doc Snapshot Service Consolidation Proposal: 5 near-clones (Borrador legacy, Borrador100, Census, Expedientes, Notifications) share 70%+ method-signature and validator overlap. Consolidation introduces shared base classes and dedupes ~200-250 lines of validator and supersession code.

| Current | Location | Approved Rename | Phase |
| --- | --- | --- | --- |
| Borrador100SnapshotService | src/aeat/application/live/_borrador_100.py | KEEP; refactor to inherit SnapshotService[Borrador100Snapshot] | W04-new |
| CensusSnapshotService | src/aeat/application/live/_census.py | CensoSnapshotService; inherit SnapshotService[CensoSnapshot] | W04-new |
| ExpedientesSnapshotService | src/aeat/application/live/_expedientes.py | KEEP; inherit StatelessSnapshotService | W04-new |
| NotificationsSnapshotService | src/aeat/application/live/_notifications.py | KEEP; inherit StatelessSnapshotService | W04-new |
| (new) SnapshotService base module | src/aeat/application/live/_snapshot_base.py | NEW MODULE exposing SnapshotService[TPayload], StatelessSnapshotService, SnapshotLifecycleState, SnapshotNotFoundError | W04-new |
| Legacy Borrador snapshot service | src/aeat/application/live/_borrador.py | RETIRE; not consolidated (incompatible discard semantics) | W04-new |

#### Exception hierarchy cluster (W02-extension boilerplate)

Not stem renames; name-collision and dead-code remediations bundled into the boilerplate phase. Critical because the catch-shadow on StorageError will silently swallow outbound errors under a persistence catch (or vice versa).

| Current | Location | Approved Rename | Phase |
| --- | --- | --- | --- |
| StorageError (outbound) | src/aeat/adapters/outbound/storage/_errors.py | OutboundStorageError | W02-extension |
| StorageValidationError (outbound) | src/aeat/adapters/outbound/storage/_errors.py | OutboundStorageValidationError | W02-extension |
| BucketAlreadyPresentError | src/aeat/adapters/persistence/storage/bucket/_errors.py | DELETE (never raised in production) | W02-extension |
| NoActiveBucketError family | bucket/_errors.py, domain/transactions/_errors.py | consolidate under LedgerNoActiveBucketError; collapse parallel definitions | W02-extension |
| WorkUnitNotFoundError (divergent parent) | per research finding #7 | unify parent class; single canonical definition | W02-extension |

### 8. Items explicitly retained (no rename)

The following identifiers, although flagged in the raw inventory, remain unchanged under this ADR:

- Snapshot family used as generic state-capture (ProfileSnapshot, RegistrySnapshot, AeatGateEnvSnapshot, RegistrySnapshotRef, RegistrySnapshotError, ProfileSnapshotPolicy, ProfileSnapshotHashMismatchError, ProfileSnapshotNotFoundError, UserProfileSnapshot). Snapshot is generic infra.
- All *Repository, *Row, *Record, *Service, *Factory, *Validator, *Observation, *Protocol, *Error, *Selector, *Catalogue, *Store, *Adapter, *Driver, *Oracle, *Result, *Payload, *Ref suffixes. Generic infra.
- NIF, CIF, NIE, IBAN, SWIFT, BIC. International identifiers.
- Decimal, datetime, primitive types. Python primitives.
- Justificante* family (already Spanish-stem; only the surrounding suffixes are English-infra).
- Borrador* family except the duplicate BorradorPrefillEntry and Borrador100Snapshot collision in _borrador.py (those are handled by the original ADR W03.P05 phase as deletion of the legacy module, not as renames).

## Rationale

The Spanish-stems-win mandate has a single dominant rationale: every canonical stem carries a precise statutory definition (LGT article, modelo OM, RD, Ley) whose English back-translation either loses scope, collides with international tax-system terminology, or conflates artifacts that AEAT keeps separate. The glossary reference documents each loss in detail. Codifying the stems in identifiers preserves the statutory contract at every layer of the codebase.

The English-exceptions list is grounded in the same principle from the opposite direction. International identifiers (NIF, IBAN, SWIFT) are language-neutral by treaty. Python primitives are not domain terms. Infrastructure suffixes (Snapshot, Repository, Row) name generic roles that compose with the Spanish stem without translating the role itself. Translating those suffixes produces stem-stuttering or loses the role portability across packages.

The snapshot disambiguation rule resolves the most-confused single case in the inventory: Borrador100Snapshot is not a stem stutter because Borrador is the entity (the AEAT-prepared draft per Ley 35/2006 Art. 98) and Snapshot is the generic cache-state suffix. This composition is the canonical pattern: Spanish-stem entity plus English infra suffix.

The Renta-vs-Rental adjudication chooses fincas because the unit of account in the AEAT tax surfaces this domain feeds (Modelo 100 rendimientos del capital inmobiliario, Modelo 210 IRNR rentas inmobiliarias, Modelo 347 arrendamientos, IBI) is the finca, not the lease contract. Lease state becomes a field on the finca, not a package.

The reversal of the prior W03.P04 direction (VAT to IVA, not IVA to VAT) closes the only remaining contradiction between the prior ADR and the project-lead mandate.

## Consequences

### Schema-impact migrations

Approximately 51 rows in the canonical ledger touch persisted schemas:

- The Modelo* cluster includes FilingRecord to ModeloRecord consolidation across pydantic and SQL surfaces. Coordinated rename and SQL migration required, gated by the standard roundtrip-test pattern.
- The Censo* cluster renames affect CensoSnapshot and the _census_* module paths; storage-bucket scoping must be preserved.
- The entire Fincas* cluster (former Rental*Row) is a single coordinated SQL migration. The standard anti-tautology proof applies: build a populated Finca record with non-default optional fields, roundtrip through real SecureObjectRepository and SQL adapters, assert strict equality.

### Public-API renames

Approximately 54 rows are public-API renames (CLI payloads, outbound Sede contract symbols, registry entrypoints). Because the project mandate is factory-direct with no shims, these renames are coordinated cuts: every callsite renames in the same commit, no deprecation aliases. Coding agents must use the no-shim refactoring pattern.

### Parent-ADR-supersession ripple

The prior code-duplication-sweep ADR is superseded by this ADR specifically on the W03.P04 IVA/VAT direction and on the broader terminology question. Other ADRs in the vault that reference the original direction (VAT-wins, English-form-canonical) may need amendment. The ADR Specialist has not traced those references in this pass; the project manager should commission a follow-up vault-curate sweep to identify and either supersede or annotate each downstream ADR.

### Plan retargeting

The existing code-duplication-sweep plan W03.P04 phase (Consolidate Value-Added Tax (VAT vs IVA)) reads: Create canonical Value-Added Tax classification schema under domain/vat package -- this direction is reversed. Plan-authoring agent must rewrite W03.P04 to:

- Create canonical IVA classification schema under domain/iva (or place under the existing IVA-bearing package).
- Consolidate VatClassification and domain/vat symbols into IvaInvoiceClassification and domain/iva.
- Delete domain/vat after migration.

The remaining waves (W01 minor symbol segregations, W02 boilerplate consolidation, W03.P05 borrador deduplication) are unaffected and can proceed.

### Tooling and gate impact

- Linters and type-checkers will surface every rename automatically.
- The roundtrip-discipline gate (real adapters, strict pydantic equality, anti-tautology proof) is the single most important enforcement surface for the schema-impact rows.
- The locale CLI must be rerun after public-API renames to refresh any operator-facing strings that reference English stems.

### Open questions deferred to project manager

- FilingRecord to ModeloRecord collision footnote 1: confirm whether domain pydantic and SQL row collapse into one type or split as ModeloRecord (domain) + ModeloRow (SQL).
- DraftStatus and FilingDraftStatus consolidation footnote 2: confirm single ModeloDraftStatus enum across filing and submission domains.
- IssuerResidency and CustomerResidency footnote 3: collapse to a single IvaResidency enum used in two field roles, or keep two parallel enums under Spanish names.
- Within the Fincas cluster, whether Income, Expense, Amortization retain English (generic accounting infra) or take Spanish forms (Rendimiento, Gasto, Amortizacion). The current ledger defaults to English retention pending project lead confirmation.
- BorradorObservation and DeclaracionObservation already follow the canonical pattern (Spanish stem + English Observation suffix) and are not renamed; confirm this is intentional and not subject to a future consistency follow-up.
- Whether downstream ADRs that referenced the original VAT-wins direction need supersession or annotation; commission a vault-curate sweep.

## Amendment 2026-05-19: Legal-authority statutory refinements

Legal-authority's Modelo-cluster sanity check identified four statutory refinements and two IVA refinements. PM has adjudicated and accepted all six. This amendment records those decisions and supersedes the affected rows in Section 7 of the ADR body above.

### Statutory refinement A1: IvaResidency → IvaTerritorialScope

Affects: footnote 3 in the Section 7 IVA cluster (currently "IssuerResidency / CustomerResidency collapse to a single IvaResidency enum, deferred to project manager").

Adjudication: collapse to a single canonical enum, but name it `IvaTerritorialScope`, not `IvaResidency`. The IVA statute speaks of "territorio de aplicación del impuesto" (Ley 37/1992 Art. 3.Dos) and "lugar de realización del hecho imponible" (Arts. 68-72), not of residency. "Residency" was statutorily imprecise; the canonical concept is the territorial scope where the taxable event is realised.

Result: replace every Section 7 reference to `IvaResidency` with `IvaTerritorialScope`. `IssuerResidency` becomes `IvaIssuerTerritorialScope` (or is collapsed into the single `IvaTerritorialScope` enum used in two field roles). `CustomerResidency` likewise.

### Statutory refinement A2: IvaFlowDirection.AUTOREPERCUTIDO → INVERSION_SUJETO_PASIVO

Affects: the Section 7 row "IvaFlowDirection | retain as-is (REPERCUTIDO/SOPORTADO/AUTOREPERCUTIDO is IVA-specific)".

Adjudication: the enum is retained but the `AUTOREPERCUTIDO` member is renamed to `INVERSION_SUJETO_PASIVO` verbatim per Ley 37/1992 Art. 84.Uno.2º. `AUTOREPERCUTIDO` is colloquial; `inversión del sujeto pasivo` is the AEAT-canonical statutory term for reverse-charge.

Result: `IvaFlowDirection` keeps `REPERCUTIDO`, `SOPORTADO`, and renames `AUTOREPERCUTIDO` to `INVERSION_SUJETO_PASIVO`. Locale entries follow.

### Statutory refinement A3: FilingDraft → ModeloDraft carve-out for Borrador*

Affects: the Section 7 Modelo cluster rows for `FilingDraft`, `FilingDraftStatus`, `FilingDraftError`, `FilingDraftRepository`, `FilingDraftRef`, `FilingDraftBuilderAdapter`, `RegistryFilingDraftProtocol`, `FilingDraftBuilderProtocol`, `FilingDraftLike`, `_PreviousFilingSelector`-adjacent draft entities, and the Borrador entity disambiguation in Section 4.

Adjudication: distinguish `ModeloDraft` (taxpayer-side local draft) from the `Borrador*` family (AEAT-prepared draft, Ley 35/2006 IRPF Art. 98). The semantic test is who supplies contents:

- Taxpayer-side contents (local draft, not yet AEAT-prepared) ⇒ `ModeloDraft*`.
- AEAT-side contents (Renta Web borrador, AEAT-prefilled snapshot) ⇒ `Borrador*`.

Carve-out rule: any Modelo-100-borrador entity currently inside a `FilingDraft*` symbol migrates to the `Borrador100*` family, not to `ModeloDraft*`. Coders executing the Modelo rename cluster must inspect each `FilingDraft*` site for AEAT-prepared content before applying the default `FilingDraft* → ModeloDraft*` substitution.

### Statutory refinement A4: FilingObligation → ModeloDeadline (NOT ModeloObligation)

Affects: Section 7 Modelo cluster row "FilingObligation | src/aeat/domain/deadlines/_models.py | ModeloObligation".

Adjudication: rename to `ModeloDeadline`, not `ModeloObligation`. Anchor:

- File path `domain/deadlines/_models.py` is the canonical naming hint: the package is named for the deadline concept, not the obligation concept.
- LGT Art. 17 names the obligation, not the form. The "obligation" is the statutory duty to file; the "deadline" is the concrete date the obligation crystallises on. The on-disk entity at `_models.py` is the deadline, not the abstract obligation.

Adjacent rows in the same `_models.py` file (`FilingEnrollment`, `FilingIVAProfile`) keep the broader `Modelo` prefix per the Section 7 ledger: `ModeloEnrollment` and `ModeloIvaProfile`. Only `FilingObligation` retargets to `ModeloDeadline`.

Coder-gamma is dispatched to implement.

### Statutory refinement A5: FilingAmendment → split to ModeloComplementaria / ModeloSustitutiva

Affects: Section 7 Modelo cluster rows `FilingAmendment` and `FilingAmendmentError`.

Adjudication: do NOT use a single umbrella `ModeloAmendment` symbol. Per LGT Art. 122 verbatim, an amendment is either a `complementaria` (correcting a prior filing in the taxpayer's favour or against) or a `sustitutiva` (replacing a prior filing wholesale). The two are statutorily distinct and must surface as a discriminated union in the type system.

Concrete shape:

- `BaseAmendment` (or `ModeloAmendmentBase`) carries the common fields.
- `ModeloComplementaria(BaseAmendment)` and `ModeloSustitutiva(BaseAmendment)` are the two concrete classes.
- Consumers branch on the concrete type (or on a `kind: Literal["complementaria", "sustitutiva"]` discriminator field whose values are the Spanish strings verbatim).
- No umbrella `ModeloAmendment` alias class. Operating on an amendment requires choosing the concrete variant; the type system enforces the LGT-Art-122 distinction at every boundary.

`FilingAmendmentError` becomes `ModeloAmendmentError` (the error surface is shared across both variants; the discrimination happens on the entity, not on its error).

### Statutory refinement A6: SubmittedFiling → ModeloPresentado (NOT SubmittedModelo)

Affects: Section 7 Modelo cluster row "SubmittedFiling | src/aeat/domain/submission/ | SubmittedModelo".

Adjudication: rename to `ModeloPresentado` per AEAT Sede verbatim labeling. The AEAT lifecycle label is `Presentada` (feminine, agreeing with `declaración` or `autoliquidación` in the AEAT UI). Code-side the canonical entity prefix is `Modelo*`, yielding `ModeloPresentado`.

The full AEAT-Sede-verbatim lifecycle is:

`Borrador → Pendiente de presentar → Presentada → Aceptada / Rechazada`

English `Submitted/Acknowledged/Accepted/Rejected/Pending` status names elsewhere in the codebase need a coordinated future state-machine rename pass — see Future scope section below.

## Future scope (recorded for follow-up campaigns)

### Future scope F1: state-machine lifecycle rename

Per AEAT Sede verbatim, the canonical filing lifecycle is `Borrador → Pendiente de presentar → Presentada → Aceptada / Rechazada`. Status enums, state-machine transition methods, persisted lifecycle columns, and CLI emit values across the codebase currently use English labels (`Submitted`, `Acknowledged`, `Accepted`, `Rejected`, `Pending`, and adjacent). A coordinated rename pass is required to align every state-machine label with the AEAT Sede vocabulary. Scope is out of this ADR; capture as a follow-up campaign feature once the Modelo cluster lands.

### Future scope F2: SII / libro registro adapter naming

When the SII (Suministro Inmediato de Información) and `libro registro` adapter is built, the boundary identifiers must use the Spanish stems verbatim:

- `factura expedida` / `factura recibida` per RD 1619/2012 (BOE-A-2012-14696).
- `Libro registro de facturas expedidas` / `Libro registro de facturas recibidas` per RD 596/2016 (BOE-A-2016-11575).

Adapter-side Python identifiers compose these stems with the English infrastructure-suffix list (Repository, Record, etc.) per Section 2: e.g. `FacturaExpedidaRecord`, `LibroRegistroFacturasRecibidasRepository`. Wire-format strings carry the verbatim Spanish phrases at the boundary.

## Open Questions resolved (2026-05-19)

This subsection updates the Section "Open questions deferred to project manager" in the ADR body above.

- **Footnote 1 (FilingRecord vs ModeloRecord collision)**: resolved via the W04.P09 FilingRecord cluster execution. Domain pydantic and SQL row are kept as separate types; `ModeloRecord` (domain) lives alongside `ModeloRow` (SQL). No type collapse.
- **Footnote 2 (DraftStatus / FilingDraftStatus consolidation)**: resolved to a single `ModeloDraftStatus` enum, pre-staged as task #20.
- **Footnote 3 (IssuerResidency / CustomerResidency)**: resolved by Amendment A1 above. Collapse to a single `IvaTerritorialScope` enum used in two field roles (issuer and customer).
- **VATClassification merge into IvaInvoiceClassification**: deferred. Initial pass renamed `VATClassification` to `IvaClassificationResult` due to field-set incompatibility with `IvaInvoiceClassification`; proper merge is tracked as a follow-up (task #10). Recording the deferral here so the open-question rationale is durable.
- **AUTOREPERCUTIDO retention**: resolved by Amendment A2 above. Member renamed to `INVERSION_SUJETO_PASIVO`.
- **Modelo-cluster vs Borrador-cluster boundary for FilingDraft\***: resolved by Amendment A3 above. Carve-out rule applies; per-site inspection required during the Modelo rename cluster.
- **FilingObligation target name**: resolved by Amendment A4 above. Target is `ModeloDeadline`, not `ModeloObligation`. Coder-gamma dispatched.
- **FilingAmendment shape**: resolved by Amendment A5 above. Discriminated union via `ModeloComplementaria` + `ModeloSustitutiva`; no umbrella class.
- **SubmittedFiling target name**: resolved by Amendment A6 above. Target is `ModeloPresentado`. Full state-machine lifecycle rename is Future Scope F1.
- **BorradorObservation and DeclaracionObservation**: confirmed canonical pattern (Spanish stem + English Observation suffix). No rename. Marked resolved.
- **Fincas cluster Income/Expense/Amortization Spanishness**: still open. Defer to the F-cluster execution agent. Current default per Section 7 remains English (Generic accounting infra).
- **Downstream ADR supersession sweep**: still open. Capture as a separate vault-curate task.

## Verification addendum (2026-05-19)

The spanish-tax-glossary reference document carries the canonical BOE / AEAT citation list. As of the verification pass that accompanied this amendment, the glossary holds 16 verified citations (14 original + 2 additions):

- Addition: RD 1619/2012 (BOE-A-2012-14696) — reglamento de facturación. Required by Future Scope F2.
- Addition: RD 596/2016 (BOE-A-2016-11575) — modernización del IVA (libros registro). Required by Future Scope F2.

The glossary section "## Verification addendum (2026-05-19)" carries the verified-citation table. This amendment does not duplicate the table; it cross-references the glossary as the single source of truth for the citation set.

## Amendment A7 (2026-05-19): Future Scope F1 promoted to in-scope — canonical lifecycle vocabulary table

### Context

Task #39 promotes the state-machine rename from Future Scope F1 to an active in-scope campaign step. The full English→Spanish vocabulary table is required before coder agents can execute the rename sweep. This amendment provides that table with BOE/AEAT citations, adjudicates the contested `ACKNOWLEDGED` mapping, verifies the DraftStatus/ModeloDraftStatus singleton, and issues the enum-value encoding recommendation.

### A7.1 Enum inventory

The following enum classes carry filing/draft/submission/modelo-record lifecycle values across the three audit surfaces (`src/aeat/domain/`, `src/aeat/application/`, `src/aeat/adapters/persistence/`):

| Enum class | File | Values |
| --- | --- | --- |
| `SubmissionStatus` | `src/aeat/domain/submission/_models.py` | `PENDING`, `IN_PROGRESS`, `SUBMITTED`, `ACKNOWLEDGED`, `REJECTED`, `FAILED` |
| `ModeloDraftStatus` | `src/aeat/domain/submission/_protocols.py` | `DRAFT`, `VALIDATED`, `READY_TO_SUBMIT`, `APPROVED`, `APPROVAL_STALE`, `SUBMITTED`, `ACKNOWLEDGED`, `REJECTED`, `AMENDED`, `CANCELLED` |
| `ModeloRecordStatus` | `src/aeat/domain/modelos/_filing_record.py` | `CURRENT`, `SUPERSEDED` |
| `CalculationRevisionState` | `src/aeat/domain/modelos/_calculation_revision.py` | `DRAFT`, `VERIFIED_COMPLETE`, `FILED`, `FILED_SUPERSEDED`, `DISCARDED` |
| `WorkUnitState` | `src/aeat/domain/modelos/_work_unit.py` | `DRAFT`, `DISCARDED` |
| `ReconciliationStatus` | `src/aeat/application/filing/reconciliation/_schema.py` | `MATCH`, `DIVERGENT` |

**DraftStatus singleton verification:** grep confirms a single `ModeloDraftStatus` enum at `_protocols.py:123`. No second `DraftStatus` or `FilingDraftStatus` class exists at this point. Task #20 consolidation landed successfully. No collapse work remains.

### A7.2 Canonical English-to-Spanish vocabulary table

Scope: `SubmissionStatus` and `ModeloDraftStatus` — the two enums whose values represent the AEAT Sede Electrónica submission lifecycle. The other enums (`ModeloRecordStatus`, `CalculationRevisionState`, `WorkUnitState`, `ReconciliationStatus`) represent internal-tool lifecycle concepts, not AEAT Sede lifecycle stages; see A7.4 for those.

| Current English value | Canonical Spanish value | BOE / AEAT citation | Notes |
| --- | --- | --- | --- |
| `PENDING` | `PENDIENTE` | Ley 39/2015 LPAC Art. 27.1 (BOE-A-2015-10565): "los documentos administrativos se considerarán emitidos … cuando … estén pendientes de resolución". AEAT Sede Electrónica renders `Pendiente de presentar` in the declaración list view before first attempt. | See A7.3 for the full AEAT phrase (`PENDIENTE_DE_PRESENTAR`) vs. the abbreviated code token (`PENDIENTE`). |
| `IN_PROGRESS` | `EN_TRAMITACION` | Ley 39/2015 LPAC Art. 70.4 uses "en tramitación" for the open-expediente state. AEAT Sede uses "En trámite" in the expediente list for procedures under active processing. | `IN_PROGRESS` is tool-internal (browser attempt running); no direct AEAT Sede label. Closest statutory concept is "en tramitación" — the filing is in motion but not yet concluded. |
| `SUBMITTED` | `PRESENTADA` | AEAT Sede Electrónica renders `Presentada` on the declaración line immediately after the CSV justificante is issued, per the Sede submission flow documented under Ley 39/2015 LPAC Art. 27.3 (BOE-A-2015-10565) and Real Decreto 203/2021 Art. 41 (BOE-A-2021-4628). Ley 58/2003 LGT Art. 66.1 uses "presentación" as the operative moment for prescription purposes. | `SUBMITTED` covers the transition "attempt completed; awaiting AEAT response". Corresponds to the moment the declaración is logged as `Presentada` on Sede before AEAT validation completes. |
| `ACKNOWLEDGED` | `ACEPTADA` | AEAT Sede renders `Aceptada` as the single terminal-success label after validation, CSV generation, and PDF justificante issuance. Ley 39/2015 LPAC Art. 27.3 grounds the justificante as the legal act of acceptance. Real Decreto 203/2021 Art. 41 makes the justificante de presentación the statutory attestation of the accepted filing. | **ACKNOWLEDGED maps to ACEPTADA, not to a preliminary receipt state.** Code evidence: `SubmissionStatus.ACKNOWLEDGED` requires `justificante_csv` AND `justificante_pdf_path` to both be present (model_validator at `_models.py:117-124`). The justificante is only generated after AEAT validation succeeds — this is the same event AEAT Sede labels `Aceptada`. There is no distinct "acuse de recibo" state in the Sede UI; AEAT goes directly from `Presentada` to `Aceptada` or `Rechazada`. An intermediate `ACUSE_RECIBO` or `EN_TRAMITACION` state would require a distinct code path not present in the codebase. |
| `REJECTED` | `RECHAZADA` | AEAT Sede renders `Rechazada` when the declaración fails validation. Ley 39/2015 LPAC Art. 68.5 grounds rejection as a formal administrative act. | Both `SubmissionStatus.REJECTED` and `ModeloDraftStatus.REJECTED` map here. |
| `FAILED` | `FALLIDA` | No direct AEAT Sede label. `FAILED` is a tool-internal state (transport failure, browser crash before AEAT confirmed receipt). The closest Spanish administrative concept is "fallida" (failed attempt) — not a statutory AEAT term but a safe, unambiguous label. | Remains tool-internal; no AEAT Sede mapping. |
| `DRAFT` | `BORRADOR` | Ley 35/2006 IRPF Art. 98 (BOE-A-2006-20764) establishes the `borrador` as the AEAT-prepared draft. AEAT Sede renders `Borrador` in the Renta Web flow. | In `ModeloDraftStatus`, `DRAFT` denotes a taxpayer-side local draft not yet validated — distinct from the AEAT-prepared Borrador100. The Spanish token `BORRADOR` covers both: taxpayer local draft before submission is also in borrador state per colloquial AEAT usage. See Amendment A3 boundary rule. |
| `VALIDATED` | `VALIDADO` | Tool-internal state (local validation rules passed). No direct AEAT Sede label. `Validado` follows established Spanish past-participle convention (cf. `Presentada`, `Aceptada`) and is unambiguous in context. | `ModeloDraftStatus` only. |
| `READY_TO_SUBMIT` | `LISTO_PARA_PRESENTAR` | Tool-internal state (draft fully prepared, awaiting operator approval). No direct AEAT Sede label. `Listo para presentar` mirrors the AEAT Sede phrase "Pendiente de presentar" but from the tool's perspective (preparation complete); distinguished from `PENDIENTE` (filing recorded but attempt not yet run). | `ModeloDraftStatus` only. |
| `APPROVED` | `APROBADO` | Tool-internal state (operator approved the draft for submission). No statutory AEAT term. `Aprobado` is the standard Spanish past-participle for an operator-approval act. | `ModeloDraftStatus` only. |
| `APPROVAL_STALE` | `APROBACION_CADUCADA` | Tool-internal state (approval timestamp exceeded the staleness window per the draft-approval-staleness ADR). No AEAT Sede equivalent. `Aprobación caducada` follows the AEAT conventions for expired acts (cf. `caducidad` in LPAC Art. 95). | `ModeloDraftStatus` only. |
| `AMENDED` | `ENMENDADO` | Tool-internal state (draft superseded by a complementaria or sustitutiva per LGT Art. 122). `Enmendado` is the past-participle form; `enmienda` is the generic Spanish legal term for amendment. Note: per Amendment A5, the concrete amendment entities are `ModeloComplementaria` / `ModeloSustitutiva`. `ENMENDADO` is the status label on the superseded draft. | `ModeloDraftStatus` only. |
| `CANCELLED` | `ANULADO` | Ley 39/2015 LPAC Art. 89 (resolución de terminación) covers administrative cancellation. AEAT Sede uses `Anulada` for a cancelled declaración session. `ANULADO` is the correct past-participle for masculine `modelo` in context. | `ModeloDraftStatus` only. |

### A7.3 PENDIENTE vs PENDIENTE_DE_PRESENTAR adjudication

The AEAT Sede UI renders the full phrase `Pendiente de presentar` on the declaración list. The question is whether the enum member `.value` should be the full phrase token or a single-word abbreviation.

**Decision: `PENDIENTE_DE_PRESENTAR`** is the canonical `.value` string. Rationale:

- The AEAT Sede phrase is the statutory label; encoding the full phrase as an underscore-joined token removes ambiguity with any generic "pending" concept in adjacent code.
- `PENDIENTE` alone already appears in `src/aeat/application/review/_enums.py` and `_filter.py` with completely different semantics (operator review queue state). Using `PENDIENTE_DE_PRESENTAR` avoids collision.
- Enum member name: `PENDIENTE_DE_PRESENTAR` (matches `.value`; all-caps per StrEnum convention).

### A7.4 Non-AEAT-Sede lifecycle enums — recommendation

The following enums encode internal-tool or persistence lifecycle states, not AEAT Sede stages. They are **in scope for the rename convention** (Spanish stems authoritative) but do not map directly to Sede labels:

| Enum class | Current values | Recommended Spanish values | Rationale |
| --- | --- | --- | --- |
| `ModeloRecordStatus` | `CURRENT`, `SUPERSEDED` | `VIGENTE`, `SUPERSEDIDO` | `VIGENTE` is the AEAT-adjacent term for a currently active registration/declaration (e.g., AEAT uses `vigente` for active census registrations in RD 1065/2007 RGAGI). `SUPERSEDIDO` is a direct Spanish past-participle for the supersession concept; no closer AEAT term exists for this persistence-internal state. |
| `CalculationRevisionState` | `DRAFT`, `VERIFIED_COMPLETE`, `FILED`, `FILED_SUPERSEDED`, `DISCARDED` | `BORRADOR`, `VERIFICADO_COMPLETO`, `PRESENTADO`, `PRESENTADO_SUPERSEDIDO`, `DESCARTADO` | `PRESENTADO` mirrors `PRESENTADA` (the submission act); `DESCARTADO` is the operator-discard concept, cf. LGT Art. 73 settlement discretion. `BORRADOR` per Ley 35/2006 Art. 98. `VERIFICADO_COMPLETO` is the post-verification, pre-presentation gate — the revision has passed every required-input + blocking-finding check and is locked for filing. Past-participle agreement (`verificado y completo`) matches Spanish adjective convention for compound state labels. Amendment: this 5th member was added to the enum in commit `a4cd19901` (2026-05-13, between this ADR's initial draft and the W04.P10 rename pass) and was missed by the original A7.4 table; recovered + renamed under task #51. |
| `WorkUnitState` | `DRAFT`, `DISCARDED` | `BORRADOR`, `DESCARTADO` | Same rationale as `CalculationRevisionState`. |
| `ReconciliationStatus` | `MATCH`, `DIVERGENT` | `COINCIDE`, `DIVERGENTE` | Tool-internal reconciliation labels. `COINCIDE` and `DIVERGENTE` are unambiguous Spanish equivalents with no statutory loading. |

### A7.5 Enum encoding recommendation

**Decision: both MEMBER NAME and `.value` string go Spanish simultaneously.** Justification:

- The codebase mandate is "no shims, no legacy, no deprecation paths" (architecture-boundaries rule, aeat-source-hygiene rule). Keeping English member names with Spanish `.value` strings creates a two-tier cognitive model and is itself a form of compatibility shim.
- The persisted `.value` strings are stored in local SQLite under the dev branch (factory-direct, no production DB). No migration cost beyond re-seeding, which is standard for this campaign.
- The roundtrip-test gate (real adapters, strict pydantic equality, anti-tautology proof per aeat-roundtrip-discipline rule) enforces the rename through the persistence boundary automatically — a renamed `.value` that fails to roundtrip will fail the gate.
- Examples of the fully-Spanish encoding: `PRESENTADA = "PRESENTADA"`, `ACEPTADA = "ACEPTADA"`, `BORRADOR = "BORRADOR"`.

The coders executing this rename must: (1) rename both the member and the `.value` string in lockstep, (2) run the roundtrip gate for `SubmissionStatus` and `ModeloDraftStatus` before commit, (3) update every string-literal comparison and `Literal[...]` annotation that references the old English `.value` strings.

### A7.6 Canonical lifecycle phases not yet represented

Inspection found no enum value for the AEAT Sede intermediate state `En trámite` (between `Presentada` and `Aceptada/Rechazada`). AEAT validation is synchronous at the Sede submission boundary; the tool never observes this intermediate state because the Playwright adapter waits for the terminal CSV/rejection response before returning. No new enum member is required.

### A7.7 Supersession note

The "Future scope F1" paragraph in the "Future scope" section above is superseded by this amendment. The scope is now in-scope. The vocabulary table in A7.2 is the single authoritative source for all executing agents on this rename pass.

## Amendment A8 (2026-05-20): Surviving Filing* class-name adjudication — rename ledger

### Context

Task #44 PM-grep found approximately 20 `Filing*` class names surviving after the W04.P08–P13 rename cluster. This amendment adjudicates each surviving name against the entity-vs-workflow heuristic (is `Filing` denoting the modelo *entity* or the filing *act/service-layer*?), verifies code-side presence, and produces the rename ledger for coder execution.

Key heuristic applied: if the name pairs with an already-renamed `Modelo*` sibling, or if the Section 7 ledger already assigned a `Modelo*` replacement, it is RESIDUE. If it names a service-layer error, workflow act, or generic infrastructure concept where English "filing" is the correct generic term, it is LEGITIMATE.

### A8.1 Adjudication of names already present in Section 7 ledger

All of the following were listed in the Section 7 Modelo cluster table with an approved `Modelo*` replacement. Their surviving presence in the codebase confirms the W04 execution passes missed them. Verdict: **RESIDUE** — execute per Section 7 ledger (with A3 carve-out rule applied site-by-site for `FilingDraft*` items).

| Current name | File | Verdict | Replacement | Rationale |
| --- | --- | --- | --- | --- |
| `RegistryFilingDraftProtocol` | `application/workflow/_protocols.py` | RESIDUE | `RegistryModeloDraftProtocol` | Section 7 row; pairs with `ModeloDraftLike` base. A3 carve-out: inspect each site — if entity is AEAT-prepared, migrate to `Borrador*`; otherwise `ModeloDraft*`. |
| `FilingDraftBuilderProtocol` | `application/workflow/_protocols.py` | RESIDUE | `ModeloDraftBuilderProtocol` | Section 7 row; builds taxpayer-side local draft. A3 applies. |
| `FilingInputsProviderProtocol` | `application/workflow/_protocols.py` | RESIDUE | `ModeloInputsProviderProtocol` | Section 7 row; provides inputs for local draft construction. A3 applies. |
| `FilingDraftBuilderAdapter` | `application/workflow/_adapters.py` | RESIDUE | `ModeloDraftBuilderAdapter` | Section 7 row; concrete adapter implementing the builder protocol. A3 applies. |
| `FilingHistoryRepository` | `application/filing/_history_repository.py` | RESIDUE | `ModeloHistoryRepository` | Section 7 row; repository holding submitted-modelo history. |
| `FilingHistoryEntry` | `application/filing/_history_models.py` | RESIDUE | `ModeloHistoryEntry` | Section 7 row; one entry in the submitted-modelo history. |
| `FilingHistory` | `application/filing/_history_models.py` | RESIDUE | `ModeloHistory` | Section 7 row; full submitted-modelo history aggregate. |
| `FilingTestProfile` | `application/filing/testing.py` | RESIDUE | `ModeloTestProfile` | Section 7 row; test fixture for the modelo-filing application layer. |
| `FilingTestDeadlineStatus` | `application/filing/testing.py` | RESIDUE | `ModeloTestDeadlineStatus` | Section 7 row; pairs with production `DeadlineStatus` in the modelo deadline domain. |
| `FilingTestDeadlineChecker` | `application/filing/testing.py` | RESIDUE | `ModeloTestDeadlineChecker` | Section 7 row; test stub implementing `DeadlineChecker` for modelo deadline tests. |
| `FilingOperatorProfile` | `application/filing/runtime.py` | RESIDUE | `ModeloOperatorProfile` | Section 7 row; operator profile projected for a modelo filing session. |
| `RegistryFilingSubview` | `application/filing/runtime.py` | RESIDUE | `RegistryModeloSubview` | Section 7 row; schema projection of a single modelo registry definition. |
| `FilingApplicationError` | `application/filing/errors.py` | RESIDUE | `ModeloApplicationError` | Section 7 row; base error for the modelo application layer. Already inherits `ModeloDraftError`. |
| `FilingCalculateError` | `application/filing/errors.py` | RESIDUE | `ModeloCalculateError` | Section 7 row; calculation error in the modelo application layer. |
| `FilingApprovalStaleReason` | `application/filing/_review.py` | RESIDUE | `ModeloApprovalStaleReason` | Section 7 row; enum values describe why a modelo draft approval went stale. |
| `FilingDraftRef` | `application/filing/reconciliation/_schema.py` | RESIDUE | `ModeloDraftRef` | Section 7 row; reference to a local modelo draft in the reconciliation schema. A3 applies. |
| `FilingDivergenceKind` | `application/filing/reconciliation/_kind.py` | RESIDUE | `ModeloDivergenceKind` | Section 7 row; enum of divergence kinds when reconciling a submitted modelo against local draft. |
| `ExternalFilingImportError` | `application/modelo/_actions.py` | RESIDUE | `ExternalModeloImportError` | Section 7 row; raised when an externally-imported payload fails modelo import. The `External` prefix is a legitimate infra qualifier; `Filing` here means the modelo entity, not the filing act. |

### A8.2 Adjudication of names NOT in the Section 7 ledger

Two surviving names were not present in the Section 7 ledger and require fresh adjudication.

#### `FilingYear` — `domain/calculations/registry/_schema.py`

`FilingYear` is a pydantic `Annotated[int, ...]` type alias used as the canonical fiscal-year integer at the registry boundary. Its docstring reads: "Mirrors the `RegistrySnapshotRef.filing_year` bound so a casilla declaring `data_type = 'year'` and the snapshot coordinate agree on the supported window."

The `filing_year` concept is the tax year a modelo belongs to — directly in the modelo entity domain, not the generic filing-act layer. The registry is the modelo-schema registry; `FilingYear` quantifies which year a casilla definition applies to. This is an entity-domain type alias, not a service-layer concept.

**Verdict: RESIDUE. Replacement: `ModeloYear`.**

The internal helper `_coerce_filing_year` renames to `_coerce_modelo_year` in lockstep. The `RegistrySnapshotRef.filing_year` field name is a separate callsite; coders must grep for `filing_year` as a field name and rename those too (they are persistence-boundary fields — roundtrip-test gate applies).

#### `TestFilingYearAccepts` / `TestFilingYearRejects` — `domain/calculations/registry/test_year_data_type.py`

Test class names that derive directly from the subject under test (`FilingYear`). Once `FilingYear` → `ModeloYear` is executed, these test class names rename to `TestModeloYearAccepts` / `TestModeloYearRejects` in lockstep.

**Verdict: RESIDUE (derived from `FilingYear`). Replacement: `TestModeloYearAccepts` / `TestModeloYearRejects`.**

### A8.3 Complete rename ledger (all surviving Filing* class names)

| Current name | File | Verdict | Replacement | Rationale |
| --- | --- | --- | --- | --- |
| `RegistryFilingDraftProtocol` | `src/aeat/application/workflow/_protocols.py` | RESIDUE | `RegistryModeloDraftProtocol` | Section 7 ADR; A3 carve-out applies |
| `FilingDraftBuilderProtocol` | `src/aeat/application/workflow/_protocols.py` | RESIDUE | `ModeloDraftBuilderProtocol` | Section 7 ADR; A3 carve-out applies |
| `FilingInputsProviderProtocol` | `src/aeat/application/workflow/_protocols.py` | RESIDUE | `ModeloInputsProviderProtocol` | Section 7 ADR; A3 carve-out applies |
| `FilingDraftBuilderAdapter` | `src/aeat/application/workflow/_adapters.py` | RESIDUE | `ModeloDraftBuilderAdapter` | Section 7 ADR; A3 carve-out applies |
| `FilingHistoryRepository` | `src/aeat/application/filing/_history_repository.py` | RESIDUE | `ModeloHistoryRepository` | Section 7 ADR |
| `FilingHistoryEntry` | `src/aeat/application/filing/_history_models.py` | RESIDUE | `ModeloHistoryEntry` | Section 7 ADR |
| `FilingHistory` | `src/aeat/application/filing/_history_models.py` | RESIDUE | `ModeloHistory` | Section 7 ADR |
| `FilingTestProfile` | `src/aeat/application/filing/testing.py` | RESIDUE | `ModeloTestProfile` | Section 7 ADR |
| `FilingTestDeadlineStatus` | `src/aeat/application/filing/testing.py` | RESIDUE | `ModeloTestDeadlineStatus` | Section 7 ADR |
| `FilingTestDeadlineChecker` | `src/aeat/application/filing/testing.py` | RESIDUE | `ModeloTestDeadlineChecker` | Section 7 ADR |
| `FilingOperatorProfile` | `src/aeat/application/filing/runtime.py` | RESIDUE | `ModeloOperatorProfile` | Section 7 ADR |
| `RegistryFilingSubview` | `src/aeat/application/filing/runtime.py` | RESIDUE | `RegistryModeloSubview` | Section 7 ADR |
| `FilingApplicationError` | `src/aeat/application/filing/errors.py` | RESIDUE | `ModeloApplicationError` | Section 7 ADR; already inherits `ModeloDraftError` |
| `FilingCalculateError` | `src/aeat/application/filing/errors.py` | RESIDUE | `ModeloCalculateError` | Section 7 ADR |
| `FilingApprovalStaleReason` | `src/aeat/application/filing/_review.py` | RESIDUE | `ModeloApprovalStaleReason` | Section 7 ADR |
| `FilingDraftRef` | `src/aeat/application/filing/reconciliation/_schema.py` | RESIDUE | `ModeloDraftRef` | Section 7 ADR; A3 carve-out applies |
| `FilingDivergenceKind` | `src/aeat/application/filing/reconciliation/_kind.py` | RESIDUE | `ModeloDivergenceKind` | Section 7 ADR |
| `ExternalFilingImportError` | `src/aeat/application/modelo/_actions.py` | RESIDUE | `ExternalModeloImportError` | Section 7 ADR; `Filing` here denotes the modelo entity |
| `FilingYear` | `src/aeat/domain/calculations/registry/_schema.py` | RESIDUE | `ModeloYear` | Not in Section 7 — adjudicated A8.2; fiscal year of a modelo entity |
| `_coerce_filing_year` | `src/aeat/domain/calculations/registry/_schema.py` | RESIDUE | `_coerce_modelo_year` | Private helper renamed in lockstep with `FilingYear` |
| `TestFilingYearAccepts` | `src/aeat/domain/calculations/registry/test_year_data_type.py` | RESIDUE | `TestModeloYearAccepts` | Test class derived from `FilingYear`; renames in lockstep |
| `TestFilingYearRejects` | `src/aeat/domain/calculations/registry/test_year_data_type.py` | RESIDUE | `TestModeloYearRejects` | Test class derived from `FilingYear`; renames in lockstep |

**LEGITIMATE count: 0.** No surviving `Filing*` class name encodes the generic filing-act or service-layer concept independently of the modelo entity. The `application/filing/` package path itself is a workflow/act container and stays; only the class names inside it that denote modelo entities are RESIDUE.

### A8.4 Coder execution notes

- Apply Amendment A3 carve-out at every `FilingDraft*` site: inspect whether the entity is AEAT-prepared content (→ `Borrador*`) or taxpayer-side local draft content (→ `ModeloDraft*`) before substituting.
- `FilingYear` rename also requires grepping `filing_year` as a field name across `RegistrySnapshotRef` and any persistence column that encodes the string `"filing_year"`. Those field renames are persistence-boundary changes; roundtrip-test gate required.
- `__all__` exports in each file must be updated in lockstep with class renames.
- No shims, no deprecation aliases, no compatibility layers per architecture-boundaries rule.
