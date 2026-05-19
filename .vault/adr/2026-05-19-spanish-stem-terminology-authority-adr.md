---
tags:
  - '#adr'
  - '#code-duplication-sweep'
date: '2026-05-19'
related:
  - "[[2026-05-19-code-duplication-sweep-research]]"
  - "[[2026-05-19-spanish-tax-glossary-reference]]"
  - "[[2026-05-19-code-duplication-sweep-adr]]"
---

<!-- LINK RULES: wiki-links only in related field above. -->

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
- justificante per AEAT Sede Electronica (CSV / justificante de presentacion workflow); regulatory framework Ley 40/2015 Articulo 27. Supersedes receipt, proof, confirmation when the artifact is the AEAT submission attestation. Does not absorb factura (commercial invoice, RD 1619/2012) or recibo (commercial receipt).
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

### 8. Items explicitly retained (no rename)

The following identifiers, although flagged in the raw inventory, remain unchanged under this ADR:

- Snapshot family used as generic state-capture (ProfileSnapshot, RegistrySnapshot, AeatGateEnvSnapshot, RegistrySnapshotRef, RegistrySnapshotError, ProfileSnapshotPolicy, ProfileSnapshotHashMismatchError, ProfileSnapshotNotFoundError, UserProfileSnapshot). Snapshot is generic infra.
- All *Repository, *Row, *Record, *Service, *Factory, *Validator, *Observation, *Protocol, *Error, *Selector, *Catalogue, *Store, *Adapter, *Driver, *Oracle, *Result, *Payload, *Ref suffixes. Generic infra.
- NIF, CIF, NIE, IBAN, SWIFT, BIC. International identifiers.
- Decimal, datetime, primitive types. Python primitives.
- Justificante* family (already Spanish-stem; only the surrounding suffixes are English-infra).
- Borrador* family except the duplicate BorradorPrefillEntry and Borrador100Snapshot collision in _borrador.py (those are handled by the original ADR W03.P05 phase as deletion of the legacy module, not as renames).

## Implementation

### 1. Decision

Spanish stems are authoritative for tax-domain identifiers. The canonical stems, each grounded in the cited primary source, are:

- iva per Ley 37/1992 IVA (BOE-A-1992-28740). Supersedes vat, value_added_tax.
- irpf per Ley 35/2006 IRPF (BOE-A-2006-20764). Supersedes income_tax, personal_income_tax, pit.
- modelo per AEAT Sede Electronica nomenclature and the per-modelo Ordenes Ministeriales (e.g. Orden HFP/227/2017 for Modelo 303). Supersedes form, tax_form, return_form. Always followed by the three-digit modelo number.
- declaracion per Ley 58/2003 LGT Articulo 119 (BOE-A-2003-23186). Supersedes declaration, return when used in the LGT-119 sense.
- autoliquidacion per Ley 58/2003 LGT Articulo 120. Supersedes self_assessment, self_liquidation.
- justificante per AEAT Sede Electronica (CSV / justificante de presentacion workflow); regulatory framework Ley 40/2015 Articulo 27. Supersedes receipt, proof, confirmation when the artifact is the AEAT submission attestation. Does not absorb factura (commercial invoice, RD 1619/2012) or recibo (commercial receipt).
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

