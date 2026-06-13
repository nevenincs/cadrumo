---
tags:
  - "#reference"
  - "#core-authority-types-v2"
date: "2026-05-31"
modified: '2026-05-31'
related: []
---

# core-authority-types-v2 reference: module-scope type definitions

Mechanical AST-based audit of all .py files under src/aeat/. 1,655 files, 0 parse failures.



## Per-category totals

| Category | Count |
|---|---|
| Enum | 226 |
| TypeAlias | 106 |
| TypedDict | 10 |
| NewType | 0 |
| Literal alias | 65 |
| Protocol | 84 |
| ABC | 7 |
| RootModel | 1 |
| Annotated alias | 97 |
| Parse failures | 0 |

Layer distribution (domain/application/adapter/core/entrypoint/test/unknown):

- **Enum** 102 / 81 / 23 / 18 / 2 / 0 / 0
- **TypeAlias** 53 / 17 / 12 / 2 / 0 / 21 / 1
- **TypedDict** 0 / 0 / 3 / 0 / 0 / 7 / 0
- **Literal** 47 / 9 / 5 / 2 / 1 / 1 / 0
- **Protocol** 26 / 22 / 26 / 6 / 3 / 1 / 0
- **ABC** 1 / 2 / 4 / 0 / 0 / 0 / 0
- **RootModel** 0 / 0 / 0 / 1 / 0 / 0 / 0
- **Annotated alias** 84 / 8 / 1 / 4 / 0 / 0 / 0

## 1. Enum declarations (226)

### Domain layer (102)

| file:line | name | domain |
|---|---|---|
| `domain/attachments/_enums.py:13` | AttachmentKind | attachments |
| `domain/attachments/_enums.py:40` | AttachmentSource | attachments |
| `domain/buckets/_event.py:51` | BucketEventType | buckets |
| `domain/buckets/_event.py:164` | BucketEventObjectType | buckets |
| `domain/calculations/registry/_applicability.py:118` | ApplicabilityVerdict | calculations |
| `domain/calculations/registry/_applicability.py:147` | PayerFact | calculations |
| `domain/calculations/registry/_applicability.py:1178` | TaxRoute | calculations |
| `domain/calculations/registry/_applicability.py:1339` | Modelo202Modality | calculations |
| `domain/calculations/registry/_censo_modelos.py:24` | CensoModeloRole | calculations |
| `domain/calculations/registry/_censo_modelos.py:31` | CensoModeloEventKind | calculations |
| `domain/calculations/registry/_live_parity.py:83` | OracleEnvironment | calculations |
| `domain/calculations/registry/_schema.py:88` | InputKind | calculations |
| `domain/calculations/registry/_schema.py:133` | CasillaFieldKind | calculations |
| `domain/calculations/registry/_workbook_parity.py:47` | WorkbookScanStatus | calculations |
| `domain/categories/_profile.py:20` | IvaDeductibilityHint | categories |
| `domain/categories/_proportionality.py:29` | CategoryCitationSource | categories |
| `domain/categories/_proportionality.py:88` | ProportionalityKind | categories |
| `domain/categories/_proportionality.py:113` | StatutoryCapPeriod | categories |
| `domain/categories/_spending_category.py:15` | SpendingCategory | categories |
| `domain/categories/_spending_category.py:66` | SpendingCategoryFamily | categories |
| `domain/currency/_models.py:10` | CurrencyNormalizationStatus | currency |
| `domain/deadlines/_festivos.py:59` | CalendarCCAA | deadlines |
| `domain/deadlines/_festivos.py:94` | HolidayJurisdiction | deadlines |
| `domain/deadlines/_models.py:24` | IVARegime | deadlines |
| `domain/deadlines/_models.py:46` | EntityType | deadlines |
| `domain/deadlines/_models.py:71` | LegalEntityForm | deadlines |
| `domain/deadlines/_models.py:106` | IrpfIncomeCategory | deadlines |
| `domain/deadlines/_models.py:139` | IrpfEstimationRegime | deadlines |
| `domain/deadlines/_models.py:161` | IrpfSpecialRegime | deadlines |
| `domain/deadlines/_models.py:187` | ObligationStatus | deadlines |
| `domain/filing/_amendment.py:48` | AmendmentKind | filing |
| `domain/filing/_schema.py:28` | ModeloValueKind | filing |
| `domain/fincas/_enums.py:14` | UseType | fincas |
| `domain/fincas/_enums.py:53` | ExpenseCategory | fincas |
| `domain/fincas/_enums.py:69` | ReduccionTier | fincas |
| `domain/invoices/_enums.py:25` | IvaRate | invoices |
| `domain/invoices/_enums.py:58` | PaymentStatus | invoices |
| `domain/iva/_classification.py:70` | IvaTerritorialScope | iva |
| `domain/iva/_classification.py:101` | InvoiceKind | iva |
| `domain/iva/_classification.py:121` | CustomerTaxStatus | iva |
| `domain/iva/_classification.py:144` | TransactionKind | iva |
| `domain/iva/_flow.py:95` | IvaFlowDirection | iva |
| `domain/iva/_flow.py:170` | IvaSettlementSide | iva |
| `domain/iva/_oss.py:40` | OssIossRegime | iva |
| `domain/iva/_oss.py:68` | IossFilerRole | iva |
| `domain/iva/_oss.py:93` | DeductionScope | iva |
| `domain/iva/_oss.py:121` | RegimePeriodicity | iva |
| `domain/iva/_prorrata.py:95` | ProrrataRegime | iva |
| `domain/iva/_prorrata.py:110` | ProrrataKind | iva |
| `domain/iva/_prorrata.py:124` | InputClassification | iva |
| `domain/iva/_schema.py:37` | IvaCategory | iva |
| `domain/iva/_schema.py:65` | EUMemberState | iva |
| `domain/iva/_schema.py:102` | IvaRateKind | iva |
| `domain/iva/_schema.py:112` | IvaCitationSource | iva |
| `domain/justificante/_schema.py:20` | JustificanteParserBackend | justificante |
| `domain/manuals/_ids.py:12` | ManualId | manuals |
| `domain/manuals/_ids.py:20` | ManualPart | manuals |
| `domain/modelos/_calculation_revision.py:55` | CalculationRevisionState | modelos |
| `domain/modelos/_calculation_revision.py:65` | CalculationRevisionAmendmentKind | modelos |
| `domain/modelos/_filing_record.py:55` | ModeloRecordStatus | modelos |
| `domain/modelos/_filing_record.py:69` | ExternalEvidenceKind | modelos |
| `domain/modelos/_verification_report.py:52` | VerificationCompletenessStatus | modelos |
| `domain/modelos/_verification_report.py:71` | ModeloVerificationFindingKind | modelos |
| `domain/modelos/_verification_report.py:87` | ModeloVerificationFindingSeverity | modelos |
| `domain/modelos/_work_unit.py:35` | WorkUnitState | modelos |
| `domain/normatives/_schema.py:33` | NormativeKind | normatives |
| `domain/portals/_categories.py:16` | PortalCategory | portals |
| `domain/portals/_categories.py:37` | AuthMethod | portals |
| `domain/portals/_categories.py:55` | UrlStability | portals |
| `domain/portals/_categories.py:72` | Subdomain | portals |
| `domain/portals/_codes.py:26` | Portal | portals |
| `domain/profile/_ccaa.py:56` | CCAA | profile |
| `domain/profile/_keys.py:33` | ProfileKeyRequirement | profile |
| `domain/profile/_renta_codes.py:14` | RentaDeclaracionType | profile |
| `domain/profile/_renta_codes.py:21` | RentaSexCode | profile |
| `domain/profile/_renta_codes.py:28` | RentaMaritalStatus | profile |
| `domain/profile/_renta_codes.py:37` | RentaDisabilityGrade | profile |
| `domain/profile/_renta_codes.py:61` | FiscalResidency | profile |
| `domain/profile/_renta_codes.py:82` | SituacionFamiliar | profile |
| `domain/profile/assets/__init__.py:28` | AssetClass | profile |
| `domain/profile/inventory/__init__.py:43` | MovementKind | profile |
| `domain/profile/inventory/__init__.py:60` | ValuationMethod | profile |
| `domain/renta/_ledger_expenses.py:39` | RentaExpenseDirection | renta |
| `domain/renta/_ledger_expenses.py:47` | RentaDeductibilityStatus | renta |
| `domain/renta/_ledger_expenses.py:54` | RentaInvoiceEvidenceStatus | renta |
| `domain/renta/_ledger_expenses.py:61` | RentaReconciliationStatus | renta |
| `domain/renta/_substrate.py:20` | RentaIncomeType | renta |
| `domain/renta/_substrate.py:49` | EstimacionDirectaModalidad | renta |
| `domain/submission/_models.py:22` | SubmissionStatus | submission |
| `domain/submission/_protocols.py:123` | ModeloDraftStatus | submission |
| `domain/transactions/_enums.py:12` | TransactionDirection | transactions |
| `domain/transactions/_enums.py:27` | BusinessClassification | transactions |
| `domain/transactions/_enums.py:58` | TransactionLifecycleState | transactions |
| `domain/transactions/_enums.py:84` | SplitRole | transactions |
| `domain/transactions/_model_tier.py:34` | ModelTier | transactions |
| `domain/transactions/_model_tier.py:50` | ModelCapability | transactions |
| `domain/transactions/_raw_transaction.py:30` | SourceFormat | transactions |
| `domain/user_profile/_registry_contract.py:21` | UserProfileRegistryContractSeverity | user_profile |
| `domain/user_profile/_schema.py:51` | ProfileFieldType | user_profile |
| `domain/user_profile/_schema.py:66` | ProfileSnapshotPolicy | user_profile |
| `domain/user_profile/_schema.py:72` | ProfileRemovePolicy | user_profile |
| `domain/user_profile/_values.py:100` | UserProfileStatus | user_profile |

### Application layer (81)

| file:line | name | domain |
|---|---|---|
| `application/aggregation/_counterpart.py:53` | OperationKind347 | non-domain |
| `application/aggregation/_counterpart.py:66` | OperationKind349 | non-domain |
| `application/aggregation/_foreign_assets.py:47` | ForeignAssetClass | non-domain |
| `application/aggregation/_iva_ledger.py:60` | IvaLedgerAggregationIssueReason | non-domain |
| `application/aggregation/_iva_ledger.py:108` | IvaLedgerInputKind | non-domain |
| `application/aggregation/_models.py:58` | PeriodKind | non-domain |
| `application/aggregation/_models.py:66` | Quarter | non-domain |
| `application/aggregation/_models.py:75` | PeriodType | non-domain |
| `application/aggregation/_prorrata.py:56` | IvaOperationKind | non-domain |
| `application/aggregation/_renta_income_ledger.py:48` | RentaIncomeLedgerAggregationIssueReason | non-domain |
| `application/aggregation/_renta_ledger.py:44` | RentaLedgerAggregationIssueReason | non-domain |
| `application/aggregation/_retenciones.py:28` | RetencionScheme | non-domain |
| `application/aggregation/_service.py:41` | PerModeloAggregationProvider | non-domain |
| `application/auth/__init__.py:32` | AuthProviderKind | non-domain |
| `application/auth/_acquisition_lock.py:30` | AuthAcquisitionLockState | non-domain |
| `application/auth/_operator.py:743` | ProviderProbeResult | non-domain |
| `application/calculations/_iva_compensation_history.py:27` | IvaCompensationExpiryReviewState | non-domain |
| `application/config_reset.py:34` | ConfigResetScope | non-domain |
| `application/evidence/_models.py:30` | BundleVerificationState | non-domain |
| `application/evidence/_models.py:39` | VerificationCheck | non-domain |
| `application/export/_tabular.py:18` | ExportSerializationFormat | non-domain |
| `application/filing/_calculate.py:37` | DeclaracionCalculateNextAction | non-domain |
| `application/filing/_export.py:65` | DeclaracionExportFormat | non-domain |
| `application/filing/_export.py:77` | DeclaracionVerifyVerdict | non-domain |
| `application/filing/_review.py:52` | ModeloApprovalStaleReason | non-domain |
| `application/filing/reconciliation/_kind.py:19` | ModeloDivergenceKind | non-domain |
| `application/filing/reconciliation/_schema.py:34` | ReconciliationStatus | non-domain |
| `application/ledger/_actions.py:129` | LedgerProviderID | non-domain |
| `application/ledger/_business_operation_invoice.py:48` | BusinessOperationInvoiceSourceKind | non-domain |
| `application/ledger/_business_operation_invoice.py:55` | IntracomOperationType | non-domain |
| `application/ledger/_preflight.py:33` | LedgerPreflightIssueReason | non-domain |
| `application/live/__init__.py:326` | LiveIvaReadSurface | non-domain |
| `application/live/__init__.py:333` | LiveIvaReadStatus | non-domain |
| `application/live/_errors.py:17` | LiveIvaAcquisitionFailureMode | non-domain |
| `application/live/_snapshot_base.py:70` | SnapshotLifecycleState | non-domain |
| `application/live/_verify.py:45` | VerifySurface | non-domain |
| `application/modelo/_reconcile.py:34` | ModeloReconciliationSourceKind | non-domain |
| `application/modelo/_reconcile.py:41` | ModeloReconciliationVerdict | non-domain |
| `application/modelo/_taxation_comparison.py:44` | TaxationRecommendation | non-domain |
| `application/operator_surface/_crud_contract.py:27` | CrudVerb | non-domain |
| `application/operator_surface/_crud_contract.py:40` | BucketEventSuffix | non-domain |
| `application/operator_surface/_crud_contract.py:67` | OrthogonalAxis | non-domain |
| `application/operator_surface/_crud_contract.py:84` | LifecycleStateVerb | non-domain |
| `application/operator_surface/_crud_contract.py:99` | KeyValueVerb | non-domain |
| `application/operator_surface/_crud_contract.py:115` | NounGroupExceptionKind | non-domain |
| `application/operator_surface/_models.py:11` | RootSurfaceName | non-domain |
| `application/operator_surface/_models.py:18` | ModeloLifecycleStep | non-domain |
| `application/operator_surface/_models.py:26` | SourceKind | non-domain |
| `application/operator_surface/_models.py:35` | OperatorMutability | non-domain |
| `application/operator_surface/_models.py:43` | HelpSurface | non-domain |
| `application/operator_surface/_models.py:51` | MountedCommandDomain | non-domain |
| `application/overview/__init__.py:114` | OverviewPeriodState | non-domain |
| `application/overview/_status.py:15` | FilingStatus | non-domain |
| `application/registry/_corpus.py:53` | RegistryManualId | non-domain |
| `application/review/_edit.py:248` | LedgerEditKey | non-domain |
| `application/review/_edit.py:269` | InvoiceEditKey | non-domain |
| `application/review/_enums.py:16` | ReviewItemKind | non-domain |
| `application/review/_enums.py:30` | ReviewSeverity | non-domain |
| `application/review/_enums.py:59` | ReviewState | non-domain |
| `application/review/_enums.py:71` | ReviewFormat | non-domain |
| `application/review/_filter.py:124` | LedgerReviewFilterKey | non-domain |
| `application/review/_filter.py:143` | LedgerReviewStatus | non-domain |
| `application/review/_filter.py:151` | LedgerReviewIssue | non-domain |
| `application/review/_filter.py:165` | InvoiceReviewFilterKey | non-domain |
| `application/review/_filter.py:179` | InvoiceReviewStatus | non-domain |
| `application/review/_filter.py:188` | DeclaracionReviewFilterKey | non-domain |
| `application/review/_filter.py:200` | DeclaracionReviewStatus | non-domain |
| `application/storage/calc_sheets/_records.py:59` | TabName | non-domain |
| `application/storage_write_policy.py:15` | StorageWritePolicyCode | non-domain |
| `application/transactions/_diagnostics.py:35` | LedgerImportDiagnosticKind | non-domain |
| `application/user_profile/_censo_sync.py:56` | CensoComparisonStatus | non-domain |
| `application/verification/_schema.py:26` | DiscrepancyCause | non-domain |
| `application/verification/_schema.py:47` | VerificationStatus | non-domain |
| `application/wizard/_models.py:24` | WizardWidget | non-domain |
| `application/wizard/_verifier.py:25` | WizardCheckSeverity | non-domain |
| `application/workflow/_engine.py:64` | DeadlineRole | non-domain |
| `application/workflow/_engine.py:71` | FilingWindowState | non-domain |
| `application/workflow/_models.py:69` | WorkflowStage | non-domain |
| `application/workflow/_models.py:82` | WorkflowPurpose | non-domain |
| `application/workflow/_models.py:108` | WorkflowAbortReason | non-domain |
| `application/workflow/_persistence.py:42` | WorkflowEnvelopeReasonClass | non-domain |

### Adapter layer (23)

| file:line | name | domain |
|---|---|---|
| `adapters/inbound/borrador/_schema.py:25` | ArtefactKind | non-domain |
| `adapters/inbound/borrador/_schema.py:41` | BorradorParseMode | non-domain |
| `adapters/outbound/aeat/auth/_clave_movil.py:150` | ClaveMovilFailureMode | non-domain |
| `adapters/outbound/aeat/auth/certificate.py:110` | CertificateHealthSeverity | non-domain |
| `adapters/outbound/aeat/browser/_errors.py:57` | BrowserFailureMode | non-domain |
| `adapters/outbound/aeat/browser/_site_health.py:32` | SiteHealthState | non-domain |
| `adapters/outbound/aeat/export/_formats/_record_spec.py:51` | FieldKind | non-domain |
| `adapters/outbound/aeat/export/_formats/_record_spec.py:78` | Justification | non-domain |
| `adapters/outbound/aeat/export/_formats/_record_spec.py:90` | DateFmt | non-domain |
| `adapters/outbound/aeat/export/_formats/_record_spec.py:104` | SignedMode | non-domain |
| `adapters/outbound/aeat/sede/_errors.py:51` | SedeFailureMode | non-domain |
| `adapters/outbound/google/_calc_sheets_pull.py:206` | MetadataMatchState | non-domain |
| `adapters/outbound/llm/_models.py:17` | LLMProvider | non-domain |
| `adapters/outbound/storage/_records.py:23` | ProviderKind | non-domain |
| `adapters/outbound/storage/_records.py:30` | RemoteMirrorIssueKind | non-domain |
| `adapters/persistence/storage/_namespace_registry.py:31` | StorageNamespaceScope | non-domain |
| `adapters/persistence/storage/_namespace_registry.py:39` | StorageRemoteMirrorPolicy | non-domain |
| `adapters/persistence/storage/_namespace_registry.py:47` | StoragePathKind | non-domain |
| `adapters/persistence/storage/bucket/_manifest.py:76` | BucketLifecycleStatus | non-domain |
| `adapters/persistence/storage/bucket/_manifest.py:95` | BucketKeySchedule | non-domain |
| `adapters/persistence/storage/envelope/_envelope.py:55` | AeadAlgorithm | non-domain |
| `adapters/persistence/storage/runtime.py:37` | StorageRuntimeReadinessCode | non-domain |
| `adapters/persistence/storage/sql/records.py:25` | PortalAuthMethod | non-domain |

### Core layer (18)

| file:line | name | domain |
|---|---|---|
| `core/aggregation.py:12` | AggregationSourceKind | non-domain |
| `core/classification/__init__.py:32` | SensitivityClass | non-domain |
| `core/classification/__init__.py:81` | OutputSensitivityClass | non-domain |
| `core/classification/__init__.py:100` | AtRestTreatment | non-domain |
| `core/classification/__init__.py:143` | RedactionStrategy | non-domain |
| `core/config.py:34` | SecretStoreBackend | non-domain |
| `core/config.py:81` | LLMProviderSetting | non-domain |
| `core/config.py:90` | CertificateBackend | non-domain |
| `core/config.py:104` | AuthProviderKindSetting | non-domain |
| `core/config.py:111` | StorageRouteKind | non-domain |
| `core/config.py:164` | JustificanteParserBackendSetting | non-domain |
| `core/errors/_registry.py:60` | ErrorCategory | non-domain |
| `core/errors/_severity.py:20` | BaseSeverity | non-domain |
| `core/identity/_documents.py:62` | IdentityDocument | non-domain |
| `core/observability/_models.py:52` | ArgumentSource | non-domain |
| `core/observability/_models.py:75` | RunEventKind | non-domain |
| `core/observability/_models.py:101` | RunOutcome | non-domain |
| `core/output_rendering.py:26` | OutputFormat | non-domain |
## 2. Type aliases (106)

Kind breakdown: pep695=42, generic_subscript=48, union_alias=16.

| file:line | name | layer | domain | kind |
|---|---|---|---|---|
| `adapters/inbound/declaracion/_parser.py:32` | _PdfWord | adapter | non-domain | generic_subscript |
| `adapters/outbound/aeat/auth/_providers.py:125` | AuthSessionDetail | adapter | non-domain | union_alias |
| `adapters/outbound/aeat/auth/_providers.py:127` | AuthLoginAssertionDetail | adapter | non-domain | union_alias |
| `adapters/outbound/aeat/export/_formats/_serialise.py:43` | HeaderValue | adapter | non-domain | union_alias |
| `adapters/outbound/aeat/sede/_censo_live.py:42` | BrowserSessionFactory | adapter | non-domain | generic_subscript |
| `adapters/outbound/aeat/sede/_declarations.py:143` | FiledDeclaracionArtefactSink | adapter | non-domain | pep695 |
| `adapters/outbound/aeat/verify/__init__.py:108` | VerifyBrowserSessionFactory | adapter | non-domain | generic_subscript |
| `adapters/outbound/google/_api.py:38` | GoogleApiResponseBody | adapter | non-domain | generic_subscript |
| `adapters/outbound/google/_calc_sheets_pull.py:48` | _ValueRange | adapter | non-domain | generic_subscript |
| `adapters/persistence/storage/envelope/_repository_test_suite.py:304` | _ParamCheck | adapter | non-domain | generic_subscript |
| `adapters/persistence/storage/master_key/_master_key.py:316` | PassphraseCallback | adapter | non-domain | generic_subscript |
| `adapters/persistence/storage/sql/secure_objects.py:126` | SecureObjectListItem | adapter | non-domain | union_alias |
| `application/aggregation/_service.py:179` | PerModeloAggregationPayload | application | non-domain | union_alias |
| `application/calculations/_iva_wallet_reconciliation.py:41` | IvaCompensationAuthority | application | non-domain | pep695 |
| `application/calculations/_iva_wallet_reconciliation.py:48` | IvaCompensationAuthoritySourceKind | application | non-domain | pep695 |
| `application/calculations/_iva_wallet_reconciliation.py:54` | IvaCompensationDivergence | application | non-domain | pep695 |
| `application/calculations/_row_set_assembly.py:76` | AssembledObservations | application | non-domain | union_alias |
| `application/inventory/_service.py:95` | InventoryRepositoryFactory | application | non-domain | generic_subscript |
| `application/ledger/_actions.py:145` | DirectionResolver | application | non-domain | generic_subscript |
| `application/ledger/_actions.py:146` | _EventSpec | application | non-domain | generic_subscript |
| `application/live/_borrador_100.py:45` | _BorradorValue | application | non-domain | pep695 |
| `application/live/_censo.py:70` | _CensoFactValue | application | non-domain | pep695 |
| `application/live/_snapshot_base.py:107` | _CanonicalScalar | application | non-domain | union_alias |
| `application/live/_snapshot_base.py:108` | _CanonicalValue | application | non-domain | union_alias |
| `application/overview/_explain.py:35` | _ProfileFactValue | application | non-domain | union_alias |
| `application/storage/calc_sheets/_engine.py:682` | RelationResolver | application | non-domain | generic_subscript |
| `application/user_profile/_censo_sync.py:119` | CensoFactSource | application | non-domain | generic_subscript |
| `application/workflow/_protocols.py:157` | ExpedientesSource | application | non-domain | generic_subscript |
| `application/workflow/_protocols.py:158` | NotificationsSource | application | non-domain | generic_subscript |
| `core/identity/__init__.py:60` | SubjectTaxId | core | non-domain | pep695 |
| `core/json_contract.py:99` | RegisteredSchema | core | non-domain | pep695 |
| `domain/calculations/registry/_authority.py:16` | _SnapshotKey | domain | calculations | generic_subscript |
| `domain/calculations/registry/_authority.py:17` | _DeadlineWindow | domain | calculations | generic_subscript |
| `domain/calculations/registry/_constructs.py:32` | _RevisionIndex | domain | calculations | pep695 |
| `domain/calculations/registry/_ids.py:14` | ModeloId | domain | calculations | pep695 |
| `domain/calculations/registry/_ids.py:15` | RevisionId | domain | calculations | pep695 |
| `domain/calculations/registry/_ids.py:16` | CasillaId | domain | calculations | pep695 |
| `domain/calculations/registry/_ids.py:17` | FormulaId | domain | calculations | pep695 |
| `domain/calculations/registry/_ids.py:18` | ParameterId | domain | calculations | pep695 |
| `domain/calculations/registry/_ids.py:19` | BindingId | domain | calculations | pep695 |
| `domain/calculations/registry/_ids.py:20` | RelationId | domain | calculations | pep695 |
| `domain/calculations/registry/_ids.py:21` | LegalRefId | domain | calculations | pep695 |
| `domain/calculations/registry/_ids.py:22` | SourceRefId | domain | calculations | pep695 |
| `domain/calculations/registry/_ids.py:23` | ExtractionProfileId | domain | calculations | pep695 |
| `domain/calculations/registry/_ids.py:24` | CrossReferenceId | domain | calculations | pep695 |
| `domain/calculations/registry/_ids.py:25` | WorkbookParityRefId | domain | calculations | pep695 |
| `domain/calculations/registry/_ids.py:26` | VerificationExpectationId | domain | calculations | pep695 |
| `domain/calculations/registry/_ids.py:27` | ApplicationLinkId | domain | calculations | pep695 |
| `domain/calculations/registry/_ids.py:28` | DeadlineWindowId | domain | calculations | pep695 |
| `domain/calculations/registry/_ids.py:29` | SupportRemovalDecisionId | domain | calculations | pep695 |
| `domain/calculations/registry/_ids.py:30` | ConstructId | domain | calculations | pep695 |
| `domain/calculations/registry/_ids.py:31` | DependencyClassificationId | domain | calculations | pep695 |
| `domain/calculations/registry/_ids.py:32` | ExportLayoutId | domain | calculations | pep695 |
| `domain/calculations/registry/_ids.py:33` | RecordId | domain | calculations | pep695 |
| `domain/calculations/registry/_ids.py:34` | ExportFieldId | domain | calculations | pep695 |
| `domain/calculations/registry/_ids.py:35` | WorkbookFixtureId | domain | calculations | pep695 |
| `domain/calculations/registry/_ids.py:36` | OracleId | domain | calculations | pep695 |
| `domain/calculations/registry/_schema.py:517` | BindingSelectorValue | domain | calculations | union_alias |
| `domain/calculations/registry/_schema.py:529` | BindingSelectorMap | domain | calculations | generic_subscript |
| `domain/calculations/registry/_schema.py:944` | ProfileFactValue | domain | calculations | union_alias |
| `domain/calculations/registry/_snapshot.py:15` | _SnapshotCacheKey | domain | calculations | generic_subscript |
| `domain/calculations/registry/_snapshot.py:16` | _SnapshotCacheValue | domain | calculations | generic_subscript |
| `domain/calculations/registry/_snapshot.py:17` | _ValidationCacheKey | domain | calculations | generic_subscript |
| `domain/calculations/registry/_snapshot.py:18` | _ValidationCacheValue | domain | calculations | generic_subscript |
| `domain/calculations/registry/_validate_cache.py:9` | _CatalogueCacheKey | domain | calculations | generic_subscript |
| `domain/calculations/registry/_validate_cache.py:10` | _CatalogueCacheValue | domain | calculations | generic_subscript |
| `domain/calculations/registry/_validate_cache.py:11` | _ModeloValidationCacheKey | domain | calculations | generic_subscript |
| `domain/calculations/registry/_validate_cache.py:12` | _ModeloValidationCacheValue | domain | calculations | generic_subscript |
| `domain/calculations/registry/_validate_cache.py:18` | _RegistryValidationCacheKey | domain | calculations | generic_subscript |
| `domain/calculations/registry/_validate_cache.py:19` | _RegistryValidationCacheValue | domain | calculations | generic_subscript |
| `domain/calculations/registry/_validate_evidence.py:12` | _SourceTextCacheKey | domain | calculations | generic_subscript |
| `domain/calculations/registry/_validate_evidence.py:13` | _SourceTextCacheValue | domain | calculations | generic_subscript |
| `domain/filing/_amendment.py:37` | ModeloCode | domain | filing | pep695 |
| `domain/filing/_amendment.py:38` | CasillaInputs | domain | filing | pep695 |
| `domain/filing/_amendment.py:66` | CasillaDelta | domain | filing | pep695 |
| `domain/filing/_complementaria_repository.py:27` | ModeloAmendment | domain | filing | pep695 |
| `domain/filing/_protocols.py:194` | ModeloInputScalar | domain | filing | pep695 |
| `domain/filing/_protocols.py:204` | ModeloInputValue | domain | filing | pep695 |
| `domain/filing/_protocols.py:215` | ModeloInputs | domain | filing | pep695 |
| `domain/filing/_schema.py:42` | ModeloScalar | domain | filing | union_alias |
| `domain/modelos/_row_models.py:340` | ModeloDetailRow | domain | modelos | union_alias |
| `domain/normatives/_schema.py:112` | LocalizedText | domain | normatives | generic_subscript |
| `domain/transactions/_service.py:28` | _EntrySignature | domain | transactions | generic_subscript |
| `domain/user_profile/_values.py:48` | ProfileFactValue | domain | user_profile | pep695 |
| `adapters/inbound/pdf/test_shared.py:22` | _PrintedValue | test | non-domain | union_alias |
| `adapters/persistence/storage/master_key/test_dek_wrap.py:42` | _REFERENCE_CIPHERTEXT | test | non-domain | generic_subscript |
| `adapters/persistence/storage/master_key/test_dek_wrap.py:43` | _REFERENCE_TAG | test | non-domain | generic_subscript |
| `adapters/persistence/storage/test_sensitive_persistence_policy.py:13` | _ROOT | test | non-domain | generic_subscript |
| `application/live/test_iva_wallet_privacy_static_guard.py:12` | _PROJECT_ROOT | test | non-domain | generic_subscript |
| `core/resources/test_single_surface_invariant.py:29` | _REPO_ROOT | test | non-domain | generic_subscript |
| `domain/calculations/registry/test_casilla_field_kind_enrollment.py:21` | _REPO_ROOT | test | calculations | generic_subscript |
| `domain/calculations/registry/test_renta_cuota_chain_contract.py:79` | _FULL_CUOTA_CHAIN_TARGETS | test | calculations | union_alias |
| `entrypoints/cli/test_retired_cli_literals.py:9` | PROJECT_ROOT | test | non-domain | generic_subscript |
| `locales/test_locale_translation_honesty.py:33` | _LocaleNode | test | non-domain | pep695 |
| `test_mock_inventory.py:39` | _REPO_ROOT | test | non-domain | generic_subscript |
| `test_monkeypatch_inventory.py:53` | _REPO_ROOT | test | non-domain | generic_subscript |
| `test_no_skip_xfail.py:32` | _REPO_ROOT | test | non-domain | generic_subscript |
| `test_no_tautology.py:38` | _REPO_ROOT | test | non-domain | generic_subscript |
| `tests/test_cross_module_imports_resolve.py:36` | SRC_AEAT | test | non-domain | generic_subscript |
| `tests/test_layout_import_smoke.py:20` | SRC_AEAT | test | non-domain | generic_subscript |
| `tests/test_marker_integrity.py:25` | _SRC_AEAT | test | non-domain | generic_subscript |
| `tests/test_marker_integrity.py:26` | _REPO_ROOT | test | non-domain | generic_subscript |
| `tests/test_marker_integrity.py:41` | _EXPECTED_CONFIGURED_MARKERS | test | non-domain | union_alias |
| `tests/test_release_config.py:33` | PROJECT_ROOT | test | non-domain | generic_subscript |
| `tests/test_wheel_bundles_corpus_and_registry.py:32` | _PROJECT_ROOT | test | non-domain | generic_subscript |
| `locales/manager.py:10` | LocaleNode | unknown | non-domain | pep695 |

## 3. TypedDict declarations (10)

| file:line | name | layer | fields |
|---|---|---|---|
| `adapters/inbound/financial/providers/_pdf_n26.py:62` | _InProgressRow | adapter | base_line, narrative, booked_date, amount, continuations |
| `adapters/inbound/financial/providers/_pdf_n26.py:72` | _ParsedRow | adapter | base_line, narrative, booked_date, amount, value_date, continuations, page_number, page_lines |
| `adapters/outbound/aeat/auth/_providers.py:130` | BrowserContextKwargs | adapter | client_certificates |
| `adapters/outbound/google/test_records.py:47` | _ClientKwargs | test | client_id, client_secret, project_id, auth_uri, token_uri, auth_provider_x509_cert_url, redirect_uris |
| `adapters/outbound/google/test_records.py:57` | _MetadataKwargs | test | account_email, granted_scopes, issued_at, last_refresh_at |
| `application/live/test_census_snapshot.py:39` | _DeriveKwargs | test | profile_id, captured_at, source_url, censo_facts |
| `application/overview/test_backlog.py:30` | _WindowArgs | test | from_date, to_date, as_of |
| `domain/calculations/registry/test_constraints_text_shape.py:26` | _ConstraintFields | test | sign, min_value, max_value, pattern, min_length, max_length, enum |
| `domain/calculations/registry/test_cross_boundary_roundtrip.py:46` | _ModeloDraftCommonKwargs | test | draft_id, modelo, period, profile_tax_id, status, values, binding_values, findings, created_at, updated_at, schema_version |
| `tests/cli_runner.py:19` | ClickInvokeKwargs | test | env, color, catch_exceptions, input |

## 4. NewType declarations (0)

Zero NewType declarations found.

## 5. Literal aliases (65)

| file:line | name | layer | domain | values |
|---|---|---|---|---|
| `adapters/inbound/financial/providers/_base.py:69` | CorpusVerificationSource | adapter | non-domain | real_bank_corpus_pdf / synthetic_from_bank_published_text / no_corpus |
| `adapters/inbound/sanitizer/_records.py:262` | _SurfaceName | adapter | non-domain | docinfo_title / docinfo_subject / docinfo_author / docinfo_keywords / docinfo_creator |
| `adapters/inbound/sanitizer/_records.py:298` | _EncodingName | adapter | non-domain | literal / hex / actualtext / docinfo_string / xmp_string |
| `adapters/inbound/sanitizer/_records.py:307` | _WarningCode | adapter | non-domain | unknown_surface_present / encoding_inferred / structtree_dropped_lossy / pdfa_claim_invalidated / digital_signature_present_refusing |
| `adapters/outbound/aeat/export/_formats/_record_spec.py:41` | FicheroBoeEncoding | adapter | non-domain | cp1252 / iso-8859-1 / iso-8859-15 |
| `application/aggregation/_source_mesh.py:35` | CalculationSourceDiagnosticReason | application | non-domain | duplicate_binding_owner / duplicate_bound_casilla_owner / duplicate_relation_owner / source_issue / storage_degraded |
| `application/diagnostics.py:39` | DiagnosticStatus | application | non-domain | ok / warn / fail |
| `application/diagnostics.py:67` | DiagnosticAudience | application | non-domain | operator / internal |
| `application/live/_verify.py:42` | VerifyVerdict | application | non-domain | valid / invalid / unknown |
| `application/repair_integrity.py:89` | _RepairDecisionOutcome | application | non-domain | preserve / quarantine / rebuild / export-required |
| `application/wizard/_persistence.py:29` | WizardPersistMode | application | non-domain | create / edit |
| `application/workflow/_engine.py:61` | _CertificateSeverityValue | application | non-domain | OK / WARN / CRITICAL / EXPIRED |
| `application/workflow/_profile_health.py:25` | ProfileHealthStatus | application | non-domain | none / dangling_pointer / missing_profile_record / profile_record_unreadable / manifest_unreadable |
| `application/workflow/_profile_health.py:35` | ProfileSource | application | non-domain | none / env_override / pointer |
| `core/parsing/_dates.py:111` | _DateFmt | core | non-domain | iso8601 / ddmmyyyy |
| `core/parsing/_dates.py:112` | _OnError | core | non-domain | raise / none |
| `domain/calculations/registry/_bindings.py:25` | _RectificationScope | domain | calculations | only_rectifications / exclude_rectifications / any |
| `domain/calculations/registry/_bindings.py:64` | _InvoiceGrouping | domain | calculations | operator_clave / operator_clave_period |
| `domain/calculations/registry/_bindings.py:65` | _InvoiceRowField | domain | calculations | party_tax_id / country_code / party_legal_name / clave / base_imponible |
| `domain/calculations/registry/_bindings.py:671` | _InvoiceFact | domain | calculations | operator_count / base_sum / rectified_base_delta_sum / row_field |
| `domain/calculations/registry/_bindings.py:1629` | CounterpartSourceKind | domain | calculations | invoice / ledger_transaction / purchase_invoice_evidence / payable_invoice / collectible_invoice |
| `domain/calculations/registry/_bindings.py:1895` | _WithholdingRowField | domain | calculations | perceptor_tax_id / perceptor_legal_name / country_code / clave / subclave |
| `domain/calculations/registry/_bindings.py:1906` | _WithholdingGrouping | domain | calculations | per_perceptor / per_perceptor_clave |
| `domain/calculations/registry/_bindings.py:1967` | _WithholdingFact | domain | calculations | row_field / perceptor_count / percibido_sum / retencion_sum |
| `domain/calculations/registry/_bindings.py:2176` | _RelatedPartyRowField | domain | calculations | counterparty_tax_id / counterparty_legal_name / country_code / operation_kind_code / transfer_pricing_method_code |
| `domain/calculations/registry/_bindings.py:2308` | _ForeignAssetRowField | domain | calculations | asset_class_code / country_code / currency_code / asset_identifier / valuation_amount |
| `domain/calculations/registry/_bindings.py:2439` | _AtributionRowField | domain | calculations | member_tax_id / member_legal_name / country_code / share_percentage / base_imponible_assigned |
| `domain/calculations/registry/_bindings.py:2555` | _RefundRowField | domain | calculations | member_state_code / operation_kind_code / operation_date / supplier_tax_id / refund_amount |
| `domain/calculations/registry/_bindings.py:2657` | _ManualInputDataType | domain | calculations | boolean / integer / text / decimal / money |
| `domain/calculations/registry/_citation_blocklist.py:10` | CitationSource | domain | calculations | ley / real_decreto / orden / reglamento / manual |
| `domain/calculations/registry/_coverage.py:16` | CoverageGateStatus | domain | calculations | satisfied / gap |
| `domain/calculations/registry/_coverage.py:17` | RequiredCoverageTier | domain | calculations | legal_authority / official_source_guidance / layout_authority |
| `domain/calculations/registry/_export.py:22` | _BindingExportDataType | domain | calculations | text / integer / decimal / money / date |
| `domain/calculations/registry/_export.py:23` | _ExportPadding | domain | calculations | left_zero / left_space / right_space / none |
| `domain/calculations/registry/_export.py:24` | _ExportJustification | domain | calculations | left / right / none |
| `domain/calculations/registry/_live_parity.py:75` | ParityVerdict | domain | calculations | match / mismatch / unverifiable / blocked |
| `domain/calculations/registry/_live_parity.py:76` | OracleSurfaceKind | domain | calculations | file_validator / open_simulator / vat_id_check / pre_filing_validator / integration_test_service |
| `domain/calculations/registry/_loader.py:77` | ModeloSourceLayout | domain | calculations | single_file / directory |
| `domain/calculations/registry/_loader.py:78` | ModeloRevisionSourceLayout | domain | calculations | revision_file / fragment_directory |
| `domain/calculations/registry/_parity_tapes.py:26` | ParityStatus | domain | calculations | match / mismatch |
| `domain/calculations/registry/_remote_state_guard.py:15` | CrossReferenceClassification | domain | calculations | open_simulator / integration_test_service / public_read_surface / authenticated_read_surface / static_official_only |
| `domain/calculations/registry/_remote_state_guard.py:23` | RemoteOperationKind | domain | calculations | http / browser_action / local_workbook |
| `domain/calculations/registry/_remote_state_guard.py:24` | RemoteGuardDecision | domain | calculations | allowed / blocked |
| `domain/calculations/registry/_remote_state_guard.py:25` | RemoteEvidenceTier | domain | calculations | official_source_guidance / executable_parity_evidence / layout_authority |
| `domain/calculations/registry/_scenarios.py:21` | ScenarioStatus | domain | calculations | match / mismatch |
| `domain/calculations/registry/_schema.py:548` | CalculationClass | domain | calculations | filing / informative / summary |
| `domain/calculations/registry/_schema.py:549` | ModeloCapability | domain | calculations | borrador / renta_ledger_default |
| `domain/calculations/registry/_schema.py:562` | ReviewStatus | domain | calculations | reviewed |
| `domain/calculations/registry/_schema.py:563` | DateAxis | domain | calculations | filing_period / devengo_date / transaction_date / invoice_date / submission_date |
| `domain/calculations/registry/_schema.py:564` | EvidenceTier | domain | calculations | legal_authority / official_source_guidance / executable_parity_evidence / layout_authority |
| `domain/calculations/registry/_schema.py:581` | FormulaOperator | domain | calculations | add / subtract / multiply / divide / percent |
| `domain/calculations/registry/_workbook_parity.py:39` | WorkbookKind | domain | calculations | formula_form / record_design_layout / validation_hints / static_layout / unsupported_binary_xls |
| `domain/calculations/registry/_workbook_parity.py:54` | WorkbookConversionStatus | domain | calculations | converted / failed |
| `domain/calculations/registry/_workbook_parity.py:55` | WorkbookRunnerStatus | domain | calculations | available |
| `domain/calculations/registry/_workbook_parity.py:56` | WorkbookRunnerEngine | domain | calculations | libreoffice-headless / excel-com |
| `domain/calculations/registry/_workbook_parity.py:57` | ParityStatus | domain | calculations | match / mismatch / not_run |
| `domain/calculations/registry/_workbook_parity.py:58` | EvidenceTier | domain | calculations | legal_authority / official_source_guidance / executable_parity_evidence / layout_authority |
| `domain/manuals/_schema.py:66` | RuleKind | domain | manuals | computation / applicability / valuation / deductibility / formal_obligation |
| `domain/modelos/_row_models.py:106` | _M232_TIPO_VINCULACION | domain | modelos | 1 / 2 / 3 / 4 / 5 |
| `domain/modelos/_row_models.py:112` | _M232_TIPO_OPERACION | domain | modelos | 01 / 02 / 03 / 04 / 05 |
| `domain/modelos/_row_models.py:119` | _M232_METODO | domain | modelos | CUP / RPM / CPM / PS / TNMM |
| `domain/modelos/_row_models.py:202` | _M349_CLAVE_OPERACION | domain | modelos | E / S / T / R / A |
| `domain/modelos/_row_models.py:279` | _M347_CLAVE_OPERACION | domain | modelos | A / B / C / D / E |
| `entrypoints/cli/_app_live.py:29` | _VerifyVerdict | entrypoint | non-domain | valid / invalid / unknown |
| `adapters/outbound/google/test_apply_adapter_helpers.py:38` | _Sign | test | non-domain | any / non_negative / non_positive |

## 6. Protocol declarations (84)

| file:line | name | layer | domain | methods |
|---|---|---|---|---|
| `adapters/inbound/borrador/_schema.py:48` | BorradorExtractionTarget | adapter | non-domain | casilla_id(self) |
| `adapters/inbound/borrador/_schema.py:55` | BorradorExtractionProfile | adapter | non-domain | id(self) / target_casillas(self) / min_coverage(self) |
| `adapters/inbound/financial/providers/_ofx.py:37` | _OfxTransactionLike | adapter | non-domain |  |
| `adapters/inbound/financial/providers/_ofx.py:49` | _OfxStatementLike | adapter | non-domain |  |
| `adapters/inbound/financial/providers/_ofx.py:57` | _OfxAccountLike | adapter | non-domain |  |
| `adapters/outbound/aeat/auth/_authenticator.py:263` | BrowserPageLike | adapter | non-domain | goto(self,url) / close(self) |
| `adapters/outbound/aeat/auth/_authenticator.py:282` | BrowserResponseLike | adapter | non-domain | status(self) |
| `adapters/outbound/aeat/auth/_authenticator.py:290` | BrowserContextLike | adapter | non-domain | new_page(self) / storage_state(self) / close(self) |
| `adapters/outbound/aeat/auth/_authenticator.py:304` | BrowserSessionLike | adapter | non-domain | create_context(self) |
| `adapters/outbound/aeat/auth/_authenticator.py:322` | CertificateHealthCheck | adapter | non-domain | __call__(self,path) |
| `adapters/outbound/aeat/auth/_authenticator.py:1307` | BrowserSessionFactory | adapter | non-domain | __call__(self,settings) |
| `adapters/outbound/aeat/auth/_providers.py:142` | BrowserContextProvisioner | adapter | non-domain | build_context_kwargs(self) / annotate_context(self,context) |
| `adapters/outbound/aeat/auth/certificate.py:284` | _BrowserContextLike | adapter | non-domain |  |
| `adapters/outbound/aeat/browser/evasion.py:15` | EvasionStrategy | adapter | non-domain | apply(self,context) |
| `adapters/outbound/aeat/sede/_browser_stage.py:13` | PlaywrightStageRunner | adapter | non-domain | __call__(self,operation) |
| `adapters/outbound/aeat/verify/__init__.py:60` | VerifyBrowserKeyboardLike | adapter | non-domain | type(self,value) / press(self,key) |
| `adapters/outbound/aeat/verify/__init__.py:67` | VerifyBrowserPageLike | adapter | non-domain | goto(self,url) / fill(self,selector,value) / press(self,selector,key) |
| `adapters/outbound/aeat/verify/__init__.py:78` | VerifyBrowserContextLike | adapter | non-domain | new_page(self) / close(self) |
| `adapters/outbound/aeat/verify/__init__.py:86` | VerifyBrowserSessionLike | adapter | non-domain | create_context(self) / close(self) |
| `adapters/outbound/google/_api.py:21` | _ExecutableRequest | adapter | non-domain | execute(self,http,num_retries) |
| `adapters/outbound/storage/_protocol.py:22` | StorageProvider | adapter | non-domain | put(self,namespace,object_key_hmac,payload) / get(self,namespace,object_key_hmac) / delete(self,namespace,object_key_hmac) |
| `adapters/persistence/storage/_rotation.py:55` | _RotationPlanSettings | adapter | non-domain |  |
| `adapters/persistence/storage/_rotation.py:69` | _BlobStoreSettings | adapter | non-domain |  |
| `adapters/persistence/storage/envelope/_envelope.py:164` | EnvelopeMigrator | adapter | non-domain | migrate(self,envelope) |
| `adapters/persistence/storage/master_key/_master_key.py:151` | MasterKeyProvider | adapter | non-domain | get_master_key(self) / provision_master_key(self) / __enter__(self) |
| `adapters/persistence/storage/master_key/_master_key.py:358` | KeyringClient | adapter | non-domain | probe_backend(self) / get_password(self,service,username) / set_password(self,service,username,password) |
| `application/aggregation/_source_mesh.py:159` | ModeloSourceResolver | application | non-domain | resolver_id(self) / owned_sources(self) / resolve(self,context) |
| `application/auth/__init__.py:75` | AuthProvider | application | non-domain | authenticate(self) / verify(self,session) / describe(self) |
| `application/calculations/_row_set_assembly.py:123` | _RowCellShape | application | non-domain | binding(self) / row_index(self) / value(self) |
| `application/filing/_complementaria.py:37` | _SubmittedOriginal | application | non-domain |  |
| `application/filing/_import.py:48` | _RegistryPeriodSubview | application | non-domain |  |
| `application/filing/_import.py:52` | RegistryImportSchemaProvider | application | non-domain | get_subview(self,modelo) |
| `application/filing/reconciliation/_reconcile.py:45` | _RegistryReconciliationSubview | application | non-domain | schema_version(self) / period_selector_periods(self) / verification_expectation_ids(self) |
| `application/filing/reconciliation/_reconcile.py:59` | _RegistryReconciliationProvider | application | non-domain | get_subview(self,modelo) |
| `application/filing/runtime.py:57` | TaxpayerProfileIdentity | application | non-domain | tax_id(self) |
| `application/live/_snapshot_base.py:86` | SnapshotRepository | application | non-domain | bucket_id(self) / exists(self,snapshot_id) / load(self,snapshot_id) |
| `application/repair_integrity.py:95` | _SecureObjectRepositoryProtocol | application | non-domain | list_namespaces(self) / probe_namespace_integrity(self,namespace) / list_keys(self,namespace) |
| `application/verification/_verify.py:43` | _DiscrepancyLike | application | non-domain | casilla_id(self) / computed_value(self) / user_value(self) |
| `application/wizard/_prompter.py:80` | Prompter | application | non-domain | ask(self,question) |
| `application/workflow/_protocols.py:37` | DeadlineEngineProtocol | application | non-domain | compute(self,profile,year) |
| `application/workflow/_protocols.py:52` | RegistryModeloDraftProtocol | application | non-domain |  |
| `application/workflow/_protocols.py:59` | ModeloDraftBuilderProtocol | application | non-domain | build(self) |
| `application/workflow/_protocols.py:76` | SubmissionEngineProtocol | application | non-domain | preflight(self,draft) |
| `application/workflow/_protocols.py:96` | CertificateBundleProtocol | application | non-domain | describe(self) |
| `application/workflow/_protocols.py:112` | ModeloInputsProviderProtocol | application | non-domain | load_inputs(self) |
| `application/workflow/_protocols.py:130` | WorkflowExpedienteProtocol | application | non-domain | modelo(self) / ejercicio(self) |
| `application/workflow/_protocols.py:138` | WorkflowNotificationProtocol | application | non-domain | tipo(self) / leida(self) / certificado_id(self) |
| `application/workflow/_protocols.py:152` | WorkflowNotificationsSnapshotProtocol | application | non-domain | rows(self) |
| `core/errors/__init__.py:15` | SiteHealthEvidenceLike | core | non-domain | url(self) / http_status(self) / detected_markers(self) |
| `core/errors/__init__.py:40` | SiteHealthStatusLike | core | non-domain | state(self) / evidence(self) / observed_at(self) |
| `core/json_contract.py:112` | _ReconfigurableStream | core | non-domain | reconfigure(self) |
| `core/profile.py:65` | ProjectAnswersFn | core | non-domain | __call__(self,flow,values) |
| `core/profile_catalogue.py:44` | WizardFlowProtocol | core | non-domain | id(self) |
| `core/resources/_repository.py:26` | ResourceRepository | core | non-domain | get(self,key) / all(self) / clear_cache(self) |
| `domain/attachments/_repository.py:19` | AttachmentStoreProtocol | domain | attachments | put_bytes(self,data) / put_file(self,source) / read_bytes(self,sha256) |
| `domain/calculations/registry/_aeat_nif_iva_oracle.py:78` | AeatNifIvaDriver | domain | calculations | mode(self) / planned_operations(self,payload) / collect_observation(self,payload) |
| `domain/calculations/registry/_bindings.py:1426` | RentaExpenseObservationProtocol | domain | calculations | modelo(self) / period(self) / target_casilla(self) |
| `domain/calculations/registry/_bindings.py:1581` | RentaIncomeObservationProtocol | domain | calculations | target_casilla(self) / gross_amount(self) / taxable_base_amount(self) |
| `domain/calculations/registry/_groi_oracle.py:96` | GroiDriver | domain | calculations | mode(self) / planned_operations(self,payload) / collect_observation(self,payload) |
| `domain/calculations/registry/_live_parity.py:164` | LiveParityOracle | domain | calculations | oracle_id(self) / surface_kind(self) / planned_operations(self,payload) |
| `domain/calculations/registry/_live_parity.py:647` | _CheckerDriver | domain | calculations | mode(self) / planned_operations(self,payload) / collect_observation(self,payload) |
| `domain/calculations/registry/_renta_web_open_oracle.py:85` | RentaWebOpenDriver | domain | calculations | mode(self) / planned_operations(self,payload) / collect_observation(self,payload) |
| `domain/calculations/registry/_validate_cross_domain_snapshot.py:11` | CrossDomainSnapshotCheck | domain | calculations | __call__(self,modelo_id,casilla_ids) |
| `domain/calculations/registry/_validate_cross_domain_snapshot.py:46` | _SnapshotReferenceChecker | domain | calculations |  |
| `domain/calculations/registry/_validate_semantic_role_typos.py:17` | _RoleObservationLike | domain | calculations |  |
| `domain/currency/_service.py:15` | ExchangeRateProvider | domain | currency | get_eur_rate(self,currency,rate_date) |
| `domain/deadlines/_engine.py:409` | ScheduleProducer | domain | deadlines | compute(self,profile,year) |
| `domain/filing/_protocols.py:22` | ModeloIdentity | domain | filing | id(self) / display_name(self) / cadence(self) |
| `domain/filing/_protocols.py:42` | CasillaSchema | domain | filing | id(self) / value_type(self) / required(self) |
| `domain/filing/_protocols.py:116` | CasillaCollection | domain | filing | schema_version(self) / __iter__(self) / get(self,casilla_id) |
| `domain/filing/_protocols.py:138` | CasillaSchemaProvider | domain | filing | get_collection(self,modelo) |
| `domain/filing/_protocols.py:147` | DeadlineStatus | domain | filing | due_date(self) / is_overdue(self) |
| `domain/filing/_protocols.py:162` | DeadlineChecker | domain | filing | check(self,modelo,period) |
| `domain/filing/_protocols.py:171` | ModeloProfile | domain | filing | tax_id(self) / display_name(self) |
| `domain/submission/_protocols.py:36` | AuthProviderDescriptionLike | domain | submission | kind(self) / label(self) / configured(self) |
| `domain/submission/_protocols.py:81` | AuthProviderProbe | domain | submission | kind(self) / describe(self) |
| `domain/submission/_protocols.py:95` | DeadlineWindowChecker | domain | submission | is_window_open(self,modelo,period,today) |
| `domain/submission/_protocols.py:159` | ModeloDraftLike | domain | submission | draft_id(self) / modelo(self) / period(self) |
| `domain/submission/_protocols.py:194` | ModeloDraftLoader | domain | submission | load(self,draft_path) |
| `domain/transactions/_llm.py:94` | LLMClassifier | domain | transactions | decided_by(self) / classify(self,transaction) |
| `entrypoints/cli/_errors.py:63` | _ReconfigurableTextIO | entrypoint | non-domain | reconfigure(self) |
| `entrypoints/cli/_ledger.py:234` | _TransactionRepo | entrypoint | non-domain | bucket_id(self) |
| `entrypoints/cli/_modelo.py:468` | _BindingReportLike | entrypoint | non-domain | code(self) |
| `core/observability/test_context_propagation.py:36` | _Step | test | non-domain | __call__(self,label) |

## 7. Abstract base classes (7)

| file:line | name | layer | bases | abstract methods |
|---|---|---|---|---|
| `adapters/inbound/financial/providers/_base.py:166` | FinancialProvider | adapter | ABC | ingest(self,path) / validate_source(self,path) |
| `adapters/outbound/aeat/auth/_certificate_backends/_base.py:29` | _CertBackend | adapter | ABC | preload(self,cert,context) / verify(self,cert,url) |
| `adapters/outbound/llm/_providers/base.py:67` | _ProviderAdapter | adapter | ABC | complete(self,request) |
| `adapters/persistence/storage/sql/repository.py:50` | SqlRecordRepository | adapter | ABC | list_all(self) / get(self,record_id) / upsert(self,record) |
| `application/live/_snapshot_base.py:181` | SnapshotService | application | ABC | _derive_snapshot_id(self) / _build_active_payload(self) / _payload_axis_key(self,payload) |
| `application/live/_snapshot_base.py:312` | StatelessSnapshotService | application | ABC | _derive_snapshot_id(self) / _build_payload(self) |
| `domain/calculations/registry/_live_parity.py:668` | BaseCheckerOracle | domain |  | oracle_id(self) / surface_kind(self) / planned_operations(self,payload) |

## 8. RootModel declarations (1)

| file:line | name | layer |
|---|---|---|
| `core/json_contract.py:65` | OutputRootSchema | core |

## 9. Annotated aliases (97)

| file:line | name | layer | domain |
|---|---|---|---|
| `adapters/inbound/sanitizer/_records.py:78` | _NonEmptyStr | adapter | non-domain |
| `application/aggregation/_iva_ledger.py:47` | _LedgerId | application | non-domain |
| `application/aggregation/_models.py:49` | _SpendingCategoryField | application | non-domain |
| `application/aggregation/_oss_ioss.py:59` | _LedgerId | application | non-domain |
| `application/aggregation/_prorrata.py:86` | _NonEmptyShortString | application | non-domain |
| `application/evidence/_ids.py:18` | BundleId | application | non-domain |
| `application/evidence/_ids.py:24` | EvidenceId | application | non-domain |
| `application/review/_models.py:122` | ReviewItem | application | non-domain |
| `application/user_profile/_aggregate.py:32` | _ProfileId | application | non-domain |
| `core/identity/_bucket.py:22` | BucketId | core | non-domain |
| `core/identity/_profile.py:26` | ProfileId | core | non-domain |
| `core/identity/_snapshot.py:30` | SnapshotId | core | non-domain |
| `core/identity/_transaction.py:20` | TransactionId | core | non-domain |
| `domain/attachments/_ids.py:19` | AttachmentId | domain | attachments |
| `domain/buckets/_event.py:29` | _EventId | domain | buckets |
| `domain/buckets/_event.py:33` | _ActorLabel | domain | buckets |
| `domain/buckets/_event.py:37` | _ObjectId | domain | buckets |
| `domain/buckets/_event.py:41` | _PayloadKey | domain | buckets |
| `domain/buckets/_event.py:45` | _PayloadValue | domain | buckets |
| `domain/calculations/registry/_schema.py:58` | DecimalValue | domain | calculations |
| `domain/calculations/registry/_schema.py:78` | NifString | domain | calculations |
| `domain/calculations/registry/_schema.py:125` | InputKindValue | domain | calculations |
| `domain/calculations/registry/_schema.py:183` | CasillaFieldKindValue | domain | calculations |
| `domain/calculations/registry/_schema.py:214` | ModeloYear | domain | calculations |
| `domain/calculations/registry/_schema.py:251` | PeriodCode | domain | calculations |
| `domain/calculations/registry/_schema.py:286` | CountryCode | domain | calculations |
| `domain/calculations/registry/_schema.py:329` | IbanString | domain | calculations |
| `domain/calculations/registry/_schema.py:351` | PersonOrEntityName | domain | calculations |
| `domain/calculations/registry/_schema.py:372` | NifIvaString | domain | calculations |
| `domain/calculations/registry/_schema.py:413` | CCAACode | domain | calculations |
| `domain/calculations/registry/_schema.py:432` | ProvinceCode | domain | calculations |
| `domain/calculations/registry/_schema.py:449` | PostalCode | domain | calculations |
| `domain/calculations/registry/_schema.py:466` | MunicipalityCode | domain | calculations |
| `domain/calculations/registry/_schema.py:484` | BicString | domain | calculations |
| `domain/calculations/registry/_schema.py:502` | CalendarDate | domain | calculations |
| `domain/calculations/registry/_schema.py:514` | WorkbookCellRefStr | domain | calculations |
| `domain/calculations/registry/_schema.py:546` | SensitivityClassField | domain | calculations |
| `domain/calculations/registry/_schema.py:570` | LegalRefs | domain | calculations |
| `domain/calculations/registry/_schema.py:571` | SourceRefs | domain | calculations |
| `domain/calculations/registry/_schema.py:572` | SourceCitationText | domain | calculations |
| `domain/calculations/registry/_schema.py:573` | ContinuidadId | domain | calculations |
| `domain/deadlines/_festivos.py:114` | _NonEmptyShortString | domain | deadlines |
| `domain/invoices/_ids.py:19` | InvoiceId | domain | invoices |
| `domain/iva/_prorrata.py:89` | SectorId | domain | iva |
| `domain/iva/_schema.py:121` | _ArticleRef | domain | iva |
| `domain/iva/_schema.py:128` | _BoeOrDirectiveRef | domain | iva |
| `domain/iva/_schema.py:135` | _NormativeId | domain | iva |
| `domain/iva/_schema.py:147` | _ManualRef | domain | iva |
| `domain/manuals/_schema.py:25` | _StableId | domain | manuals |
| `domain/manuals/_schema.py:36` | _Reviewer | domain | manuals |
| `domain/manuals/_schema.py:42` | _CasillaRef | domain | manuals |
| `domain/manuals/_schema.py:53` | _LegalActRef | domain | manuals |
| `domain/manuals/_schema.py:78` | _YearField | domain | manuals |
| `domain/manuals/_schema.py:280` | _Sha256 | domain | manuals |
| `domain/modelos/_calculation_revision.py:82` | _ActorLabel | domain | modelos |
| `domain/modelos/_calculation_revision.py:86` | _DiscardReason | domain | modelos |
| `domain/modelos/_calculation_revision.py:90` | _CasillaKey | domain | modelos |
| `domain/modelos/_filing_record.py:41` | _Period | domain | modelos |
| `domain/modelos/_filing_record.py:45` | _ActorLabel | domain | modelos |
| `domain/modelos/_filing_record.py:49` | _Notes | domain | modelos |
| `domain/modelos/_filing_record.py:84` | _EvidenceReference | domain | modelos |
| `domain/modelos/_ids.py:30` | WorkUnitId | domain | modelos |
| `domain/modelos/_ids.py:36` | CalculationRevisionId | domain | modelos |
| `domain/modelos/_ids.py:42` | FilingRecordId | domain | modelos |
| `domain/modelos/_ids.py:48` | VerificationReportId | domain | modelos |
| `domain/modelos/_row_models.py:39` | _NifStr | domain | modelos |
| `domain/modelos/_row_models.py:40` | _NameStr | domain | modelos |
| `domain/modelos/_row_models.py:41` | _IsoCountryCode | domain | modelos |
| `domain/modelos/_verification_report.py:33` | _ReportId | domain | modelos |
| `domain/modelos/_verification_report.py:38` | _ActorLabel | domain | modelos |
| `domain/modelos/_verification_report.py:42` | _FindingMessage | domain | modelos |
| `domain/modelos/_verification_report.py:46` | _CasillaRef | domain | modelos |
| `domain/modelos/_work_unit.py:51` | _ActorLabel | domain | modelos |
| `domain/modelos/_work_unit.py:55` | _DiscardReason | domain | modelos |
| `domain/modelos/_work_unit.py:59` | _StaleReason | domain | modelos |
| `domain/modelos/_work_unit.py:63` | _OptionalHex64 | domain | modelos |
| `domain/modelos/_work_unit.py:75` | _Period | domain | modelos |
| `domain/modelos/_work_unit.py:79` | _RevisionId | domain | modelos |
| `domain/modelos/_work_unit.py:83` | _DisplayName | domain | modelos |
| `domain/normatives/_schema.py:47` | _StableId | domain | normatives |
| `domain/normatives/_schema.py:59` | _Reviewer | domain | normatives |
| `domain/normatives/_schema.py:66` | _NormativeNumber | domain | normatives |
| `domain/normatives/_schema.py:78` | _ArticuloNumero | domain | normatives |
| `domain/normatives/_schema.py:90` | _TagField | domain | normatives |
| `domain/normatives/_schema.py:102` | _BoeIdField | domain | normatives |
| `domain/profile/_constants.py:26` | ProfileName | domain | profile |
| `domain/user_profile/_schema.py:20` | _SchemaId | domain | user_profile |
| `domain/user_profile/_schema.py:24` | _SectionKey | domain | user_profile |
| `domain/user_profile/_schema.py:28` | _FieldKey | domain | user_profile |
| `domain/user_profile/_schema.py:32` | _FieldPath | domain | user_profile |
| `domain/user_profile/_schema.py:41` | _Selector | domain | user_profile |
| `domain/user_profile/_schema.py:45` | _Description | domain | user_profile |
| `domain/user_profile/_values.py:28` | _ProfileId | domain | user_profile |
| `domain/user_profile/_values.py:32` | _SnapshotId | domain | user_profile |
| `domain/user_profile/_values.py:36` | _FieldPath | domain | user_profile |
| `domain/user_profile/_values.py:45` | _DisplayName | domain | user_profile |
| `domain/user_profile/_values.py:46` | _Source | domain | user_profile |

## 10. Cross-domain coupling matrix

63 raw import events. 34 unique (name, decl_domain, imp_domain) triples.

| declared_domain | importer_domain | event_count |
|---|---|---|
| iva | calculations | 21 |
| deadlines | calculations | 9 |
| categories | renta | 8 |
| iva | invoices | 5 |
| submission | filing | 4 |
| transactions | invoices | 4 |
| transactions | test_runtime_repository_enrollment.py | 2 |
| profile | deadlines | 2 |
| calculations | filing | 1 |
| buckets | modelos | 1 |
| modelos | calculations | 1 |
| modelos | filing | 1 |
| iva | transactions | 1 |
| calculations | user_profile | 1 |
| categories | calculations | 1 |
| categories | usage_ratios | 1 |

### All 34 unique cross-domain pairs

| name | decl_domain | decl_file | imp_domain | imp_file |
|---|---|---|---|---|
| ModeloDraftStatus | submission | `domain/submission/_protocols.py` | filing | `domain/filing/__init__.py` |
| BindingId | calculations | `domain/calculations/registry/_ids.py` | filing | `domain/filing/_schema.py` |
| BucketEventType | buckets | `domain/buckets/_event.py` | modelos | `domain/modelos/test_work_unit.py` |
| InvoiceKind | iva | `domain/iva/_classification.py` | calculations | `domain/calculations/registry/test_ledger_oss_aggregation_binding.py` |
| InvoiceKind | iva | `domain/iva/_classification.py` | invoices | `domain/invoices/_models.py` |
| CalculationRevisionState | modelos | `domain/modelos/_calculation_revision.py` | calculations | `domain/calculations/registry/test_cross_boundary_roundtrip.py` |
| CalculationRevisionState | modelos | `domain/modelos/_calculation_revision.py` | filing | `domain/filing/test_secure_storage_roundtrip.py` |
| SourceFormat | transactions | `domain/transactions/_raw_transaction.py` | invoices | `domain/invoices/test_reconciliation.py` |
| SourceFormat | transactions | `domain/transactions/_raw_transaction.py` | test_runtime_repository_enrollment.py | `domain/test_runtime_repository_enrollment.py` |
| TransactionDirection | transactions | `domain/transactions/_enums.py` | invoices | `domain/invoices/test_reconciliation.py` |
| TransactionDirection | transactions | `domain/transactions/_enums.py` | test_runtime_repository_enrollment.py | `domain/test_runtime_repository_enrollment.py` |
| EUMemberState | iva | `domain/iva/_schema.py` | calculations | `domain/calculations/registry/test_ledger_oss_aggregation_binding.py` |
| EUMemberState | iva | `domain/iva/_schema.py` | transactions | `domain/transactions/_models.py` |
| IvaCategory | iva | `domain/iva/_schema.py` | calculations | `domain/calculations/registry/_bindings.py` |
| IvaFlowDirection | iva | `domain/iva/_flow.py` | calculations | `domain/calculations/registry/test_ledger_iva_aggregation_binding.py` |
| IvaFlowDirection | iva | `domain/iva/_flow.py` | invoices | `domain/invoices/test_models.py` |
| IvaRateKind | iva | `domain/iva/_schema.py` | calculations | `domain/calculations/registry/test_ledger_iva_aggregation_binding.py` |
| OssIossRegime | iva | `domain/iva/_oss.py` | calculations | `domain/calculations/registry/test_ledger_oss_aggregation_binding.py` |
| TransactionKind | iva | `domain/iva/_classification.py` | calculations | `domain/calculations/registry/test_ledger_oss_aggregation_binding.py` |
| FiscalResidency | profile | `domain/profile/_renta_codes.py` | deadlines | `domain/deadlines/__init__.py` |
| IVARegime | deadlines | `domain/deadlines/_models.py` | calculations | `domain/calculations/registry/test_modelo_200_cuota_integra_lanes.py` |
| ProfileFactValue | calculations | `domain/calculations/registry/_schema.py` | user_profile | `domain/user_profile/__init__.py` |
| IrpfEstimationRegime | deadlines | `domain/deadlines/_models.py` | calculations | `domain/calculations/registry/test_modelo_applicability.py` |
| IrpfIncomeCategory | deadlines | `domain/deadlines/_models.py` | calculations | `domain/calculations/registry/test_modelo_applicability.py` |
| EntityType | deadlines | `domain/deadlines/_models.py` | calculations | `domain/calculations/registry/test_modelo_200_cuota_integra_lanes.py` |
| LegalEntityForm | deadlines | `domain/deadlines/_models.py` | calculations | `domain/calculations/registry/test_modelo_200_cuota_integra_lanes.py` |
| IrpfSpecialRegime | deadlines | `domain/deadlines/_models.py` | calculations | `domain/calculations/registry/test_modelo_applicability.py` |
| SpendingCategory | categories | `domain/categories/_spending_category.py` | calculations | `domain/calculations/registry/test_ledger_renta_expense_binding.py` |
| SpendingCategory | categories | `domain/categories/_spending_category.py` | renta | `domain/renta/_ledger_expenses.py` |
| SpendingCategoryFamily | categories | `domain/categories/_spending_category.py` | renta | `domain/renta/_ledger_expenses.py` |
| SpendingCategoryFamily | categories | `domain/categories/_spending_category.py` | usage_ratios | `domain/usage_ratios/_service.py` |
| CategoryCitationSource | categories | `domain/categories/_proportionality.py` | renta | `domain/renta/test_ledger_expenses.py` |
| ProportionalityKind | categories | `domain/categories/_proportionality.py` | renta | `domain/renta/_ledger_expenses.py` |
| StatutoryCapPeriod | categories | `domain/categories/_proportionality.py` | renta | `domain/renta/_ledger_expenses.py` |

## 11. Cross-layer coupling matrix

584 raw import events across layer pairs.

| declared_layer | importer_layer | event_count |
|---|---|---|
| domain | test | 274 |
| domain | application | 124 |
| application | test | 69 |
| core | test | 31 |
| adapter | test | 23 |
| domain | entrypoint | 14 |
| adapter | application | 11 |
| domain | adapter | 9 |
| core | application | 7 |
| domain | core | 6 |
| application | entrypoint | 4 |
| core | adapter | 3 |
| core | domain | 3 |
| test | core | 2 |
| application | adapter | 1 |
| core | unknown | 1 |
| adapter | entrypoint | 1 |
| entrypoint | test | 1 |

Interpretation: domain->test (274) and domain->application (124) are expected.
domain->adapter (9) and domain->entrypoint (14) are structural concerns per hexagonal rules.

## 12. Same-name multi-declaration list (19 names)

Every name declared in 2 or more files across the codebase.

### BrowserSessionFactory (2 declarations)

- `adapters/outbound/aeat/sede/_censo_live.py:42` layer=adapter domain=non-domain cat=type_aliases
- `adapters/outbound/aeat/auth/_authenticator.py:1307` layer=adapter domain=non-domain cat=protocols

### EvidenceTier (2 declarations)

- `domain/calculations/registry/_schema.py:564` layer=domain domain=calculations cat=literals
- `domain/calculations/registry/_workbook_parity.py:58` layer=domain domain=calculations cat=literals

### PROJECT_ROOT (2 declarations)

- `entrypoints/cli/test_retired_cli_literals.py:9` layer=test domain=non-domain cat=type_aliases
- `tests/test_release_config.py:33` layer=test domain=non-domain cat=type_aliases

### ParityStatus (2 declarations)

- `domain/calculations/registry/_parity_tapes.py:26` layer=domain domain=calculations cat=literals
- `domain/calculations/registry/_workbook_parity.py:57` layer=domain domain=calculations cat=literals

### ProfileFactValue (2 declarations)

- `domain/calculations/registry/_schema.py:944` layer=domain domain=calculations cat=type_aliases
- `domain/user_profile/_values.py:48` layer=domain domain=user_profile cat=type_aliases

### SRC_AEAT (2 declarations)

- `tests/test_cross_module_imports_resolve.py:36` layer=test domain=non-domain cat=type_aliases
- `tests/test_layout_import_smoke.py:20` layer=test domain=non-domain cat=type_aliases

### _ActorLabel (5 declarations)

- `domain/buckets/_event.py:33` layer=domain domain=buckets cat=annotated_aliases
- `domain/modelos/_calculation_revision.py:82` layer=domain domain=modelos cat=annotated_aliases
- `domain/modelos/_filing_record.py:45` layer=domain domain=modelos cat=annotated_aliases
- `domain/modelos/_verification_report.py:38` layer=domain domain=modelos cat=annotated_aliases
- `domain/modelos/_work_unit.py:51` layer=domain domain=modelos cat=annotated_aliases

### _CasillaRef (2 declarations)

- `domain/manuals/_schema.py:42` layer=domain domain=manuals cat=annotated_aliases
- `domain/modelos/_verification_report.py:46` layer=domain domain=modelos cat=annotated_aliases

### _DiscardReason (2 declarations)

- `domain/modelos/_calculation_revision.py:86` layer=domain domain=modelos cat=annotated_aliases
- `domain/modelos/_work_unit.py:55` layer=domain domain=modelos cat=annotated_aliases

### _DisplayName (2 declarations)

- `domain/modelos/_work_unit.py:83` layer=domain domain=modelos cat=annotated_aliases
- `domain/user_profile/_values.py:45` layer=domain domain=user_profile cat=annotated_aliases

### _FieldPath (2 declarations)

- `domain/user_profile/_schema.py:32` layer=domain domain=user_profile cat=annotated_aliases
- `domain/user_profile/_values.py:36` layer=domain domain=user_profile cat=annotated_aliases

### _LedgerId (2 declarations)

- `application/aggregation/_iva_ledger.py:47` layer=application domain=non-domain cat=annotated_aliases
- `application/aggregation/_oss_ioss.py:59` layer=application domain=non-domain cat=annotated_aliases

### _NonEmptyShortString (2 declarations)

- `application/aggregation/_prorrata.py:86` layer=application domain=non-domain cat=annotated_aliases
- `domain/deadlines/_festivos.py:114` layer=domain domain=deadlines cat=annotated_aliases

### _PROJECT_ROOT (2 declarations)

- `application/live/test_iva_wallet_privacy_static_guard.py:12` layer=test domain=non-domain cat=type_aliases
- `tests/test_wheel_bundles_corpus_and_registry.py:32` layer=test domain=non-domain cat=type_aliases

### _Period (2 declarations)

- `domain/modelos/_filing_record.py:41` layer=domain domain=modelos cat=annotated_aliases
- `domain/modelos/_work_unit.py:75` layer=domain domain=modelos cat=annotated_aliases

### _ProfileId (2 declarations)

- `application/user_profile/_aggregate.py:32` layer=application domain=non-domain cat=annotated_aliases
- `domain/user_profile/_values.py:28` layer=domain domain=user_profile cat=annotated_aliases

### _REPO_ROOT (7 declarations)

- `core/resources/test_single_surface_invariant.py:29` layer=test domain=non-domain cat=type_aliases
- `domain/calculations/registry/test_casilla_field_kind_enrollment.py:21` layer=test domain=calculations cat=type_aliases
- `test_mock_inventory.py:39` layer=test domain=non-domain cat=type_aliases
- `test_monkeypatch_inventory.py:53` layer=test domain=non-domain cat=type_aliases
- `test_no_skip_xfail.py:32` layer=test domain=non-domain cat=type_aliases
- `test_no_tautology.py:38` layer=test domain=non-domain cat=type_aliases
- `tests/test_marker_integrity.py:26` layer=test domain=non-domain cat=type_aliases

### _Reviewer (2 declarations)

- `domain/manuals/_schema.py:36` layer=domain domain=manuals cat=annotated_aliases
- `domain/normatives/_schema.py:59` layer=domain domain=normatives cat=annotated_aliases

### _StableId (2 declarations)

- `domain/manuals/_schema.py:25` layer=domain domain=manuals cat=annotated_aliases
- `domain/normatives/_schema.py:47` layer=domain domain=normatives cat=annotated_aliases

## 13. Compat re-export list (319 entries)

Every __all__ entry that re-exports a name not declared in that module.

- `adapters/inbound/borrador/__init__.py`: ArtefactKind, BorradorExtractionProfile, BorradorParseMode
- `adapters/inbound/borrador/_extractors/__init__.py`: ArtefactKind
- `adapters/inbound/financial/__init__.py`: CorpusVerificationSource, FinancialProvider
- `adapters/inbound/financial/providers/__init__.py`: CorpusVerificationSource, FinancialProvider
- `adapters/inbound/justificante/__init__.py`: JustificanteParserBackend
- `adapters/outbound/aeat/auth/__init__.py`: AuthLoginAssertionDetail, AuthProvider, AuthProviderKind, AuthSessionDetail, BrowserContextLike, BrowserContextProvisioner, BrowserPageLike, BrowserResponseLike, BrowserSessionFactory, BrowserSessionLike, CertificateBackend, CertificateHealthSeverity, ClaveMovilFailureMode
- `adapters/outbound/aeat/auth/_providers.py`: AuthProvider, AuthProviderKind
- `adapters/outbound/aeat/auth/certificate.py`: CertificateBackend
- `adapters/outbound/aeat/browser/__init__.py`: BrowserFailureMode, EvasionStrategy, SiteHealthState
- `adapters/outbound/aeat/export/__init__.py`: AuthProviderProbe, DeadlineWindowChecker, ModeloDraftLike, ModeloDraftLoader, ModeloDraftStatus
- `adapters/outbound/aeat/export/_formats/__init__.py`: DateFmt, FicheroBoeEncoding, FieldKind, Justification, SignedMode
- `adapters/outbound/aeat/sede/__init__.py`: SedeFailureMode
- `adapters/outbound/llm/__init__.py`: LLMProvider
- `adapters/outbound/storage/__init__.py`: ProviderKind, RemoteMirrorIssueKind, StorageProvider
- `adapters/persistence/storage/__init__.py`: AeadAlgorithm, AtRestTreatment, EnvelopeMigrator, MasterKeyProvider, PortalAuthMethod, RedactionStrategy, SensitivityClass, SqlRecordRepository, StorageNamespaceScope, StoragePathKind, StorageRemoteMirrorPolicy, StorageRuntimeReadinessCode
- `adapters/persistence/storage/envelope/__init__.py`: AeadAlgorithm, EnvelopeMigrator
- `adapters/persistence/storage/master_key/__init__.py`: MasterKeyProvider
- `adapters/persistence/storage/sql/__init__.py`: PortalAuthMethod, SqlRecordRepository
- `application/aggregation/__init__.py`: AggregationSourceKind, CalculationSourceDiagnosticReason, ForeignAssetClass, IvaLedgerAggregationIssueReason, IvaLedgerInputKind, IvaOperationKind, ModeloSourceResolver, OperationKind347, OperationKind349, PerModeloAggregationProvider, PeriodKind, Quarter, RentaLedgerAggregationIssueReason, RetencionScheme
- `application/aggregation/_service.py`: AggregationSourceKind
- `application/auth/__init__.py`: AuthAcquisitionLockState
- `application/calculations/__init__.py`: AssembledObservations, IvaCompensationExpiryReviewState
- `application/evidence/__init__.py`: BundleVerificationState, VerificationCheck
- `application/export/__init__.py`: ExportSerializationFormat
- `application/filing/__init__.py`: AmendmentKind, CasillaCollection, CasillaDelta, CasillaInputs, CasillaSchema, CasillaSchemaProvider, DeadlineChecker, DeadlineStatus, DeclaracionCalculateNextAction, DeclaracionExportFormat, DeclaracionVerifyVerdict, ModeloApprovalStaleReason, ModeloCode, ModeloDraftStatus, ModeloIdentity, ModeloInputs, ModeloProfile, ModeloScalar, ModeloValueKind
- `application/filing/_complementaria.py`: AmendmentKind, CasillaDelta, CasillaInputs, ModeloCode
- `application/filing/reconciliation/__init__.py`: ModeloDivergenceKind, ReconciliationStatus
- `application/ledger/__init__.py`: LedgerPreflightIssueReason
- `application/live/__init__.py`: LiveIvaAcquisitionFailureMode, SnapshotLifecycleState
- `application/modelo/__init__.py`: TaxationRecommendation
- `application/operator_surface/__init__.py`: BucketEventSuffix, CrudVerb, HelpSurface, KeyValueVerb, LifecycleStateVerb, ModeloLifecycleStep, MountedCommandDomain, NounGroupExceptionKind, OperatorMutability, OrthogonalAxis, RootSurfaceName, SourceKind
- `application/overview/__init__.py`: ApplicabilityVerdict, FilingStatus
- `application/registry/__init__.py`: RegistryManualId
- `application/review/__init__.py`: DeclaracionReviewFilterKey, DeclaracionReviewStatus, InvoiceEditKey, InvoiceReviewFilterKey, InvoiceReviewStatus, LedgerEditKey, LedgerReviewFilterKey, LedgerReviewIssue, LedgerReviewStatus, ReviewFormat, ReviewItem, ReviewItemKind, ReviewSeverity, ReviewState
- `application/storage/calc_sheets/__init__.py`: TabName
- `application/transactions/__init__.py`: LedgerImportDiagnosticKind
- `application/user_profile/__init__.py`: CensoComparisonStatus, CensoFactSource, ProfileFactValue, UserProfileStatus
- `application/verification/__init__.py`: DiscrepancyCause, VerificationStatus
- `application/wizard/_widgets.py`: WizardWidget
- `application/workflow/__init__.py`: CertificateBundleProtocol, DeadlineEngineProtocol, ModeloDraftBuilderProtocol, ModeloInputScalar, ModeloInputValue, ModeloInputs, ModeloInputsProviderProtocol, RegistryModeloDraftProtocol, SubmissionEngineProtocol, WorkflowAbortReason, WorkflowPurpose, WorkflowStage
- `application/workflow/_engine.py`: ExpedientesSource, NotificationsSource
- `application/workflow/_protocols.py`: ModeloInputScalar, ModeloInputValue, ModeloInputs
- `core/errors/__init__.py`: BaseSeverity, ErrorCategory
- `core/identity/__init__.py`: BucketId, IdentityDocument, ProfileId, SnapshotId, TransactionId
- `core/observability/__init__.py`: ArgumentSource, RunEventKind, RunOutcome
- `core/resources/__init__.py`: ResourceRepository
- `diagnostics/test_identity_primitive_placement.py`: InvoiceId
- `domain/attachments/__init__.py`: AttachmentKind, AttachmentSource, AttachmentStoreProtocol
- `domain/buckets/__init__.py`: BucketEventObjectType, BucketEventType
- `domain/calculations/registry/__init__.py`: ApplicabilityVerdict, CasillaFieldKind, CasillaFieldKindValue, CensoModeloEventKind, CensoModeloRole, CrossDomainSnapshotCheck, EvidenceTier, GroiDriver, InputKind, InputKindValue, LiveParityOracle, Modelo202Modality, ModeloCapability, OracleEnvironment, OracleSurfaceKind, ParityVerdict, PayerFact, RentaIncomeObservationProtocol, RentaWebOpenDriver, TaxRoute
- `domain/calculations/registry/applicability.py`: ApplicabilityVerdict, Modelo202Modality, PayerFact, TaxRoute
- `domain/categories/__init__.py`: CategoryCitationSource, IvaDeductibilityHint, ProportionalityKind, SpendingCategory, SpendingCategoryFamily, StatutoryCapPeriod
- `domain/currency/__init__.py`: CurrencyNormalizationStatus, ExchangeRateProvider
- `domain/deadlines/__init__.py`: CalendarCCAA, EntityType, FiscalResidency, HolidayJurisdiction, IVARegime, IrpfEstimationRegime, IrpfIncomeCategory, IrpfSpecialRegime, LegalEntityForm, ObligationStatus, ScheduleProducer
- `domain/deadlines/taxpayer_model.py`: EntityType, IrpfEstimationRegime, IrpfIncomeCategory, IrpfSpecialRegime
- `domain/filing/__init__.py`: AmendmentKind, CasillaCollection, CasillaDelta, CasillaInputs, CasillaSchema, CasillaSchemaProvider, DeadlineChecker, DeadlineStatus, ModeloCode, ModeloDraftStatus, ModeloIdentity, ModeloInputScalar, ModeloInputValue, ModeloInputs, ModeloProfile, ModeloScalar, ModeloValueKind
- `domain/fincas/__init__.py`: ExpenseCategory, ReduccionTier, UseType
- `domain/invoices/__init__.py`: InvoiceKind, IvaRate, PaymentStatus
- `domain/invoices/_enums.py`: InvoiceKind
- `domain/iva/__init__.py`: CustomerTaxStatus, DeductionScope, EUMemberState, InputClassification, InvoiceKind, IossFilerRole, IvaCategory, IvaCitationSource, IvaFlowDirection, IvaRateKind, IvaSettlementSide, IvaTerritorialScope, OssIossRegime, ProrrataKind, ProrrataRegime, RegimePeriodicity, TransactionKind
- `domain/justificante/__init__.py`: JustificanteParserBackend
- `domain/manuals/__init__.py`: ManualId, ManualPart, RuleKind
- `domain/modelos/__init__.py`: ModeloCode, ModeloDetailRow
- `domain/normatives/__init__.py`: NormativeKind
- `domain/portals/__init__.py`: AuthMethod, Portal, PortalCategory, Subdomain, UrlStability
- `domain/profile/__init__.py`: CCAA, ProfileKeyRequirement, ProfileName, RentaDeclaracionType, RentaDisabilityGrade, RentaMaritalStatus, RentaSexCode, SituacionFamiliar
- `domain/renta/__init__.py`: EstimacionDirectaModalidad, RentaDeductibilityStatus, RentaExpenseDirection, RentaIncomeType, RentaInvoiceEvidenceStatus, RentaReconciliationStatus
- `domain/submission/__init__.py`: AuthProviderProbe, DeadlineWindowChecker, ModeloDraftLike, ModeloDraftLoader, ModeloDraftStatus, SubmissionStatus
- `domain/transactions/__init__.py`: BusinessClassification, LLMClassifier, ModelCapability, ModelTier, SourceFormat, SplitRole, TransactionDirection, TransactionLifecycleState
- `domain/transactions/_ids.py`: TransactionId
- `domain/transactions/_llm.py`: ModelTier
- `domain/user_profile/__init__.py`: ProfileFactValue, ProfileFieldType, ProfileRemovePolicy, ProfileSnapshotPolicy, UserProfileRegistryContractSeverity, UserProfileStatus
- `entrypoints/cli/_schemas.py`: OutputRootSchema

## 14. Parse failures (0)

No files failed AST parsing. All 1,655 .py files processed successfully.

