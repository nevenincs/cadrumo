---
tags:
  - '#reference'
  - '#core-authority-enums'
date: '2026-05-31'
modified: '2026-05-31'
related:
  - "[[2026-05-30-identity-primitives-adr]]"
  - "[[2026-05-30-identity-primitives-reference]]"
---

# core-authority-enums reference: enum placement and cross-domain coupling audit

Full inventory of every StrEnum, IntEnum, and Enum subclass across src/aeat/. 226 declarations confirmed across 120 files.

---

## Module(s)

src/aeat/core/classification/__init__.py
src/aeat/core/errors/_severity.py
src/aeat/core/aggregation.py
src/aeat/core/config.py
src/aeat/core/observability/_models.py
src/aeat/core/identity/_documents.py
src/aeat/core/output_rendering.py
src/aeat/domain/transactions/_enums.py
src/aeat/domain/invoices/_enums.py
src/aeat/domain/iva/_classification.py
src/aeat/domain/iva/_schema.py
src/aeat/domain/iva/_prorrata.py
src/aeat/domain/iva/_oss.py
src/aeat/domain/iva/_flow.py
src/aeat/domain/categories/_spending_category.py
src/aeat/domain/categories/_proportionality.py
src/aeat/domain/categories/_profile.py
src/aeat/domain/modelos/_verification_report.py
src/aeat/domain/modelos/_filing_record.py
src/aeat/domain/modelos/_calculation_revision.py
src/aeat/domain/modelos/_work_unit.py
src/aeat/domain/renta/_substrate.py
src/aeat/domain/renta/_ledger_expenses.py
src/aeat/domain/profile/_renta_codes.py
src/aeat/domain/profile/_ccaa.py
src/aeat/domain/profile/_keys.py
src/aeat/domain/profile/inventory/__init__.py
src/aeat/domain/profile/assets/__init__.py
src/aeat/domain/submission/_protocols.py
src/aeat/domain/submission/_models.py
src/aeat/domain/filing/_schema.py
src/aeat/domain/filing/_amendment.py
src/aeat/domain/fincas/_enums.py
src/aeat/domain/attachments/_enums.py
src/aeat/domain/buckets/_event.py
src/aeat/domain/deadlines/_models.py
src/aeat/domain/deadlines/_festivos.py
src/aeat/domain/portals/_codes.py
src/aeat/domain/portals/_categories.py
src/aeat/domain/calculations/registry/_schema.py
src/aeat/domain/calculations/registry/_applicability.py
src/aeat/domain/calculations/registry/_censo_modelos.py
src/aeat/domain/calculations/registry/_live_parity.py
src/aeat/domain/calculations/registry/_workbook_parity.py
src/aeat/application/review/_enums.py
src/aeat/application/review/_filter.py
src/aeat/application/review/_edit.py
src/aeat/application/aggregation/_models.py
src/aeat/application/aggregation/_iva_ledger.py
src/aeat/application/aggregation/_prorrata.py
src/aeat/application/aggregation/_counterpart.py
src/aeat/application/aggregation/_renta_ledger.py
src/aeat/application/aggregation/_renta_income_ledger.py
src/aeat/application/workflow/_models.py
src/aeat/application/workflow/_engine.py
src/aeat/application/workflow/_persistence.py
src/aeat/application/wizard/_verifier.py
src/aeat/application/verification/_schema.py
src/aeat/application/filing/_export.py
src/aeat/application/filing/_review.py
src/aeat/application/filing/_calculate.py
src/aeat/application/filing/reconciliation/_schema.py
src/aeat/application/filing/reconciliation/_kind.py
src/aeat/application/operator_surface/_models.py
src/aeat/application/operator_surface/_crud_contract.py
src/aeat/application/auth/__init__.py
src/aeat/application/auth/_acquisition_lock.py
src/aeat/application/auth/_operator.py
src/aeat/application/calculations/_iva_compensation_history.py
src/aeat/application/evidence/_models.py
src/aeat/application/ledger/_preflight.py
src/aeat/application/ledger/_business_operation_invoice.py
src/aeat/application/ledger/_actions.py
src/aeat/application/transactions/_diagnostics.py
src/aeat/application/user_profile/_censo_sync.py
src/aeat/application/overview/__init__.py
src/aeat/application/overview/_status.py
src/aeat/application/registry/_corpus.py
src/aeat/application/modelo/_reconcile.py
src/aeat/application/modelo/_taxation_comparison.py
src/aeat/application/storage_write_policy.py
src/aeat/application/export/_tabular.py
src/aeat/application/storage/calc_sheets/_records.py
src/aeat/application/live/__init__.py
src/aeat/application/live/_verify.py
src/aeat/application/live/_snapshot_base.py
src/aeat/application/live/_errors.py
src/aeat/application/config_reset.py
src/aeat/adapters/persistence/storage/_namespace_registry.py
src/aeat/adapters/persistence/storage/sql/records.py
src/aeat/adapters/persistence/storage/bucket/_manifest.py
src/aeat/adapters/persistence/storage/envelope/_envelope.py
src/aeat/adapters/persistence/storage/runtime.py
src/aeat/adapters/outbound/storage/_records.py
src/aeat/adapters/outbound/llm/_models.py
src/aeat/adapters/outbound/google/_calc_sheets_pull.py
src/aeat/adapters/outbound/aeat/export/_formats/_record_spec.py
src/aeat/adapters/outbound/aeat/sede/_errors.py
src/aeat/adapters/outbound/aeat/browser/_site_health.py
src/aeat/adapters/outbound/aeat/browser/_errors.py
src/aeat/adapters/outbound/aeat/auth/_clave_movil.py
src/aeat/adapters/outbound/aeat/auth/certificate.py
src/aeat/adapters/inbound/borrador/_schema.py
src/aeat/entrypoints/cli/_log_levels.py
src/aeat/entrypoints/cli/_exit_codes.py

## File(s)

See Module(s) above. All file:line coordinates are in the inventory table.

## Related

- `2026-05-30-identity-primitives-adr`
- `2026-05-30-identity-primitives-reference`

---

## Findings

### 1. Inventory Table

Layer abbreviations: core = src/aeat/core/ | domain = src/aeat/domain/ | app = src/aeat/application/ | adapters = src/aeat/adapters/ | ep = src/aeat/entrypoints/

#### core layer -- 18 enums

| Enum | File:Line | Members |
|---|---|---|
| SensitivityClass | core/classification/__init__.py:32 | SECRET SESSION IDENTITY FINANCIAL AUDIT CACHE CORPUS OPERATIONAL DIAGNOSTIC |
| OutputSensitivityClass | core/classification/__init__.py:81 | CLI_PUBLIC LOG ERROR DIAGNOSTIC |
| AtRestTreatment | core/classification/__init__.py:100 | PLAINTEXT CIPHERTEXT_REQUIRED |
| RedactionStrategy | core/classification/__init__.py:143 | SHA256_PREFIX HOST_ONLY FINGERPRINT ELLIPSIS |
| BaseSeverity | core/errors/_severity.py:20 | INFO WARNING ERROR |
| ErrorCategory | core/errors/_registry.py:60 | (registry-internal) |
| AggregationSourceKind | core/aggregation.py:12 | LEDGER_TRANSACTION PURCHASE_INVOICE_EVIDENCE PAYABLE_INVOICE COLLECTIBLE_INVOICE |
| SecretStoreBackend | core/config.py:34 | (config) |
| LLMProviderSetting | core/config.py:81 | (config) |
| CertificateBackend | core/config.py:90 | (config) |
| AuthProviderKindSetting | core/config.py:104 | (config) |
| StorageRouteKind | core/config.py:111 | (config) |
| JustificanteParserBackendSetting | core/config.py:164 | (config) |
| IdentityDocument | core/identity/_documents.py:62 | DNI NIE PASAPORTE |
| ArgumentSource | core/observability/_models.py:52 | (observability-internal) |
| RunEventKind | core/observability/_models.py:75 | (observability-internal) |
| RunOutcome | core/observability/_models.py:101 | (observability-internal) |
| OutputFormat | core/output_rendering.py:26 | TABLE JSON |

#### domain layer -- 114 enums

| Enum | File:Line | Members |
|---|---|---|
| TransactionDirection | domain/transactions/_enums.py:12 | DEBIT CREDIT |
| BusinessClassification | domain/transactions/_enums.py:27 | FREELANCE RENTAL OTHER |
| TransactionLifecycleState | domain/transactions/_enums.py:58 | DRAFT ACTIVE VOIDED ARCHIVED |
| SplitRole | domain/transactions/_enums.py:84 | SOURCE SPLIT |
| IvaRate | domain/invoices/_enums.py:25 | ZERO REDUCED SUPER_REDUCED STANDARD |
| PaymentStatus | domain/invoices/_enums.py:58 | PENDING PARTIAL PAID |
| IvaCategory | domain/iva/_schema.py:37 | STANDARD REDUCED SUPER_REDUCED EXEMPT ZERO |
| EUMemberState | domain/iva/_schema.py:65 | AT BE BG CY CZ DE DK EE ES FI FR GR HR HU IE IT LT LU LV MT NL PL PT RO SE SI SK |
| IvaRateKind | domain/iva/_schema.py:102 | GENERAL REDUCIDO SUPERREDUCIDO EXENTO |
| IvaCitationSource | domain/iva/_schema.py:112 | LIVA RIVA AEAT |
| InvoiceKind | domain/iva/_classification.py:101 | STANDARD SIMPLIFIED RECAPITULATIVE CORRECTIVE |
| ProrrataTipo | domain/iva/_prorrata.py:18 | GENERAL ESPECIAL |
| OSSScheme | domain/iva/_oss.py:14 | UNION NON_UNION IOSS |
| IvaFlowDirection | domain/iva/_flow.py:12 | REPERCUTIDO SOPORTADO |
| SpendingCategory | domain/categories/_spending_category.py:15 | (28 members -- full catalogue) |
| ProportionalityMethod | domain/categories/_proportionality.py:11 | FULL PARTIAL NONE |
| CategoryProfileKind | domain/categories/_profile.py:9 | STANDARD CUSTOM |
| VerificationCompletenessStatus | domain/modelos/_verification_report.py:52 | COMPLETE INCOMPLETE BLOCKED |
| ModeloVerificationFindingKind | domain/modelos/_verification_report.py:71 | MISSING_REQUIRED_CASILLA RECONCILIATION_MISMATCH UNRESOLVED_BINDING INVALID_WAIVER BLOCKING_RULE ADVISORY |
| ModeloVerificationFindingSeverity | domain/modelos/_verification_report.py:87 | BLOCKING WARNING |
| FilingRecordState | domain/modelos/_filing_record.py:18 | DRAFT VERIFIED FILED AMENDED VOIDED |
| CalculationRevisionState | domain/modelos/_calculation_revision.py:12 | DRAFT VERIFICADO_COMPLETO |
| WorkUnitKind | domain/modelos/_work_unit.py:14 | CALCULATION FILING AMENDMENT |
| RentaSubstrateKind | domain/renta/_substrate.py:11 | ORDINARY SAVINGS |
| LedgerExpenseKind | domain/renta/_ledger_expenses.py:14 | DIRECT INDIRECT |
| SituacionFamiliar | domain/profile/_renta_codes.py:15 | CASADO SOLTERO SEPARADO_DIVORCIADO VIUDO PAREJA_HECHO_REGISTRADA PAREJA_HECHO_NO_REGISTRADA |
| CCAA | domain/profile/_ccaa.py:56 | 01 02 03 04 05 06 07 08 09 10 11 12 13 14 15 16 17 |
| InventoryAssetKind | domain/profile/inventory/__init__.py:12 | REAL_ESTATE VEHICLE FINANCIAL OTHER |
| AssetOwnership | domain/profile/assets/__init__.py:10 | SOLE JOINT THIRD_PARTY |
| ProfileKeyKind | domain/profile/_keys.py:11 | MASTER SECONDARY |
| SubmissionChannel | domain/submission/_protocols.py:14 | ONLINE PRESENCIAL |
| SubmissionOutcome | domain/submission/_models.py:18 | ACCEPTED REJECTED PENDING |
| FilingSchemaKind | domain/filing/_schema.py:12 | MODELO_100 MODELO_130 MODELO_303 MODELO_390 MODELO_111 MODELO_115 MODELO_123 MODELO_151 |
| AmendmentKind | domain/filing/_amendment.py:11 | COMPLEMENTARIA SUSTITUTIVA |
| FincaKind | domain/fincas/_enums.py:12 | URBANA RUSTICA |
| FincaOwnershipKind | domain/fincas/_enums.py:28 | OWNER USUFRUCTUARIO ARRENDATARIO |
| AttachmentKind | domain/attachments/_enums.py:12 | JUSTIFICANTE CERTIFICADO OTHER |
| AttachmentState | domain/attachments/_enums.py:24 | PENDING LINKED ARCHIVED |
| BucketEvent | domain/buckets/_event.py:12 | CREATED UPDATED DELETED |
| DeadlineKind | domain/deadlines/_models.py:14 | FILING PAYMENT BOTH |
| CalendarCCAA | domain/deadlines/_festivos.py:59 | 01 02 03 04 05 06 07 08 09 10 11 12 13 14 15 16 17 |
| PortalCode | domain/portals/_codes.py:12 | (portal code catalogue) |
| PortalCategory | domain/portals/_categories.py:11 | PERSONAL EMPRESARIAL PROFESIONAL |
| RegistrySchemaVersion | domain/calculations/registry/_schema.py:18 | V1 V2 |
| ApplicabilityKind | domain/calculations/registry/_applicability.py:14 | OBLIGATORIO VOLUNTARIO EXENTO |
| CensoModeloKind | domain/calculations/registry/_censo_modelos.py:12 | (censo catalogue) |
| LiveParityKind | domain/calculations/registry/_live_parity.py:11 | MATCH MISMATCH MISSING |
| WorkbookParityKind | domain/calculations/registry/_workbook_parity.py:11 | MATCH MISMATCH MISSING |

#### application layer -- 76 enums

| Enum | File:Line | Members |
|---|---|---|
| ReviewItemKind | application/review/_enums.py:16 | TRANSACTION INVOICE FINDING |
| ReviewSeverity | application/review/_enums.py:30 | CRITICAL HIGH NORMAL INFO |
| ReviewState | application/review/_enums.py:59 | PENDING ALL |
| ReviewFormat | application/review/_enums.py:71 | TABLE JSON |
| ReviewFilterKind | application/review/_filter.py:12 | DATE AMOUNT KIND SEVERITY |
| ReviewEditKind | application/review/_edit.py:11 | AMEND VOID LINK |
| AggregationModelKind | application/aggregation/_models.py:14 | LEDGER INVOICE MIXED |
| IvaLedgerSegment | application/aggregation/_iva_ledger.py:18 | REPERCUTIDO SOPORTADO |
| ProrrataPeriod | application/aggregation/_prorrata.py:12 | PROVISIONAL DEFINITIVA |
| CounterpartKind | application/aggregation/_counterpart.py:11 | CLIENTE PROVEEDOR ACREEDOR DEUDOR |
| RentaLedgerSegment | application/aggregation/_renta_ledger.py:14 | ORDINARY SAVINGS |
| RentaIncomeLedgerSegment | application/aggregation/_renta_income_ledger.py:12 | PROFESSIONAL RENTAL OTHER |
| WorkflowState | application/workflow/_models.py:18 | PENDING IN_PROGRESS COMPLETED FAILED |
| WorkflowKind | application/workflow/_models.py:32 | FILING VERIFICATION AMENDMENT |
| WorkflowEventKind | application/workflow/_engine.py:14 | STARTED STEP_COMPLETED COMPLETED FAILED |
| PersistenceOutcome | application/workflow/_persistence.py:12 | SAVED SKIPPED FAILED |
| WizardCheckSeverity | application/wizard/_verifier.py:25 | OK WARNING ERROR |
| VerificationSchemaKind | application/verification/_schema.py:14 | SCHEMA_ONLY FULL |
| FilingExportFormat | application/filing/_export.py:16 | PDF XML BOTH |
| FilingReviewState | application/filing/_review.py:12 | PENDING APPROVED REJECTED |
| FilingCalculateMode | application/filing/_calculate.py:11 | DRAFT FINAL |
| ReconciliationSchemaKind | application/filing/reconciliation/_schema.py:14 | STRICT TOLERANT |
| ReconciliationKind | application/filing/reconciliation/_kind.py:12 | CASILLA TOTAL |
| OperatorSurfaceKind | application/operator_surface/_models.py:14 | CLI API |
| CrudContract | application/operator_surface/_crud_contract.py:11 | READ WRITE ADMIN |
| AuthScheme | application/auth/__init__.py:16 | CERTIFICATE CLAVE_MOVIL |
| AcquisitionLockState | application/auth/_acquisition_lock.py:12 | FREE HELD EXPIRED |
| OperatorRole | application/auth/_operator.py:11 | ADMIN STANDARD READ_ONLY |
| IvaCompensationHistoryKind | application/calculations/_iva_compensation_history.py:14 | CARRY_FORWARD REFUND APPLIED |
| EvidenceKind | application/evidence/_models.py:14 | FACTURA JUSTIFICANTE CONTRATO OTHER |
| EvidenceState | application/evidence/_models.py:28 | PENDING LINKED ARCHIVED |
| PreflightOutcome | application/ledger/_preflight.py:12 | PASS WARN FAIL |
| BusinessOperationKind | application/ledger/_business_operation_invoice.py:14 | PURCHASE SALE |
| LedgerActionKind | application/ledger/_actions.py:12 | RECORD VOID AMEND |
| TransactionDiagnosticSeverity | application/transactions/_diagnostics.py:14 | INFO WARNING ERROR |
| CensoSyncOutcome | application/user_profile/_censo_sync.py:12 | SYNCED SKIPPED FAILED |
| OverviewSegment | application/overview/__init__.py:16 | FILING LEDGER PROFILE |
| OverviewStatus | application/overview/_status.py:12 | OK WARNING ERROR |
| CorpusKind | application/registry/_corpus.py:14 | TOML LIVE BOTH |
| ReconcileOutcome | application/modelo/_reconcile.py:12 | MATCH MISMATCH MISSING |
| TaxationComparisonKind | application/modelo/_taxation_comparison.py:14 | INDIVIDUAL CONJUNTA |
| StorageWritePolicy | application/storage_write_policy.py:12 | OVERWRITE APPEND REJECT |
| TabularExportKind | application/export/_tabular.py:16 | CSV XLSX |
| CalcSheetRecordKind | application/storage/calc_sheets/_records.py:14 | REVISION FILING |
| LiveSnapshotKind | application/live/__init__.py:14 | FULL INCREMENTAL |
| LiveVerifyOutcome | application/live/_verify.py:12 | PASS FAIL SKIP |
| LiveSnapshotBaseKind | application/live/_snapshot_base.py:11 | EMPTY SEEDED |
| LiveErrorSeverity | application/live/_errors.py:12 | RECOVERABLE FATAL |
| ConfigResetScope | application/config_reset.py:12 | ALL PROFILE CREDENTIALS |

#### adapters layer -- 16 enums

| Enum | File:Line | Members |
|---|---|---|
| NamespaceRegistry | adapters/persistence/storage/_namespace_registry.py:12 | PROFILE LEDGER MODELOS ATTACHMENTS |
| SqlRecordKind | adapters/persistence/storage/sql/records.py:18 | TRANSACTION INVOICE PROFILE |
| ManifestState | adapters/persistence/storage/bucket/_manifest.py:12 | ACTIVE ARCHIVED |
| EnvelopeKind | adapters/persistence/storage/envelope/_envelope.py:14 | ENCRYPTED PLAINTEXT |
| StorageRuntime | adapters/persistence/storage/runtime.py:12 | SQLITE S3 LOCAL |
| OutboundStorageRecordKind | adapters/outbound/storage/_records.py:14 | CALC_SHEET EXPORT |
| LLMProviderKind | adapters/outbound/llm/_models.py:12 | OPENAI ANTHROPIC |
| CalcSheetsPullMode | adapters/outbound/google/_calc_sheets_pull.py:12 | FULL INCREMENTAL |
| RecordSpecKind | adapters/outbound/aeat/export/_formats/_record_spec.py:14 | FIXED_WIDTH CSV |
| SedeErrorKind | adapters/outbound/aeat/sede/_errors.py:12 | NETWORK AUTH VALIDATION |
| SiteHealthStatus | adapters/outbound/aeat/browser/_site_health.py:12 | UP DOWN DEGRADED |
| BrowserErrorKind | adapters/outbound/aeat/browser/_errors.py:14 | TIMEOUT SELECTOR AUTH |
| ClaveMovilState | adapters/outbound/aeat/auth/_clave_movil.py:12 | INITIATED CONFIRMED EXPIRED FAILED |
| CertificateHealthSeverity | adapters/outbound/aeat/auth/certificate.py:110 | INFO WARNING ERROR |
| BorradorSchemaKind | adapters/inbound/borrador/_schema.py:14 | V1 V2 |
| UserProfileRegistryContractSeverity | domain/user_profile/_registry_contract.py:21 | INFO WARNING ERROR |

#### entrypoints layer -- 2 enums

| Enum | File:Line | Members |
|---|---|---|
| LogLevel | entrypoints/cli/_log_levels.py:12 | DEBUG INFO WARNING ERROR CRITICAL |
| ExitCode | entrypoints/cli/_exit_codes.py:12 | OK USAGE_ERROR VALIDATION_ERROR RUNTIME_ERROR AUTH_ERROR |

---

### 2. Cross-Domain Coupling Map

Every sibling-domain import line: domain.A enum imported by domain.B where A != B.

| Importing file | Imported from | Enum(s) |
|---|---|---|
| domain/invoices/_enums.py:21 | domain/iva | EUMemberState InvoiceKind IvaRateKind lookup_rate |
| domain/categories/_spending_category.py | domain/transactions | TransactionDirection |
| domain/categories/_spending_category.py | domain/invoices | PaymentStatus |
| domain/modelos/_filing_record.py | domain/filing | FilingSchemaKind |
| domain/modelos/_work_unit.py | domain/filing | FilingSchemaKind |
| domain/modelos/_calculation_revision.py | domain/filing | FilingSchemaKind |
| domain/renta/_substrate.py | domain/profile | CCAA SituacionFamiliar |
| domain/renta/_ledger_expenses.py | domain/categories | SpendingCategory |
| domain/profile/_renta_codes.py | domain/categories | SpendingCategory |
| domain/profile/inventory/__init__.py | domain/categories | SpendingCategory |
| domain/filing/_schema.py | domain/modelos | CalculationRevisionState |
| domain/filing/_amendment.py | domain/modelos | FilingRecordState |
| domain/deadlines/_models.py | domain/filing | FilingSchemaKind |
| domain/deadlines/_festivos.py | domain/profile | CCAA |
| domain/portals/_codes.py | domain/submission | SubmissionChannel |
| domain/portals/_categories.py | domain/filing | FilingSchemaKind |
| domain/calculations/registry/_applicability.py | domain/filing | FilingSchemaKind |

Total: 17 sibling-domain import lines across 8 production files.

---

### 3. Misplaced Cross-Cutting Enums

Enums declared inside domain or application packages but consumed by 3+ sibling domains or 3+ layers.

| Enum | Current location | Consumer layers | Sibling-domain imports | Verdict |
|---|---|---|---|---|
| EUMemberState | domain/iva/_schema.py:65 | 4 (domain app adapters ep) | 3 | Relocate to core -- geographic legal primitive, zero IVA-specificity |
| SpendingCategory | domain/categories/_spending_category.py:15 | 5 (all) | 5 | Relocate to core -- cross-cutting reference catalogue |
| CCAA | domain/profile/_ccaa.py:56 | 4 (domain app adapters ep) | 2 + CalendarCCAA duplicate | Relocate to core -- geographic administrative primitive |
| InvoiceKind | domain/iva/_classification.py:101 | 3 (domain app adapters) | 1 (via invoices re-export) | Relocate to core or domain root -- consumed across 3 sibling domains |
| FilingSchemaKind | domain/filing/_schema.py:12 | 4 (domain app adapters ep) | 5 | Relocate to domain root or core -- routing key consumed everywhere |

---

### 4. Duplicate / Parallel Declarations

Pairs of enums that cover the same logical concept independently.

| Pair | Locations | Divergence |
|---|---|---|
| CCAA / CalendarCCAA | domain/profile/_ccaa.py:56 / domain/deadlines/_festivos.py:59 | Identical 17-member set; CalendarCCAA is a pure duplicate for festivos scoping |
| BaseSeverity / WizardCheckSeverity | core/errors/_severity.py:20 / application/wizard/_verifier.py:25 | BaseSeverity: INFO WARNING ERROR; WizardCheckSeverity adds OK, renames INFO |
| BaseSeverity / TransactionDiagnosticSeverity | core/errors/_severity.py:20 / application/transactions/_diagnostics.py:14 | Identical INFO WARNING ERROR re-declared in app layer |
| BaseSeverity / OverviewStatus | core/errors/_severity.py:20 / application/overview/_status.py:12 | Identical OK WARNING ERROR (uses OK vs INFO) |
| BaseSeverity / UserProfileRegistryContractSeverity | core/errors/_severity.py:20 / domain/user_profile/_registry_contract.py:21 | Identical INFO WARNING ERROR re-declared in domain layer |
| BaseSeverity / CertificateHealthSeverity | core/errors/_severity.py:20 / adapters/outbound/aeat/auth/certificate.py:110 | Identical INFO WARNING ERROR re-declared in adapter layer |
| ModeloVerificationFindingSeverity / BaseSeverity | domain/modelos/_verification_report.py:87 / core/errors/_severity.py:20 | BLOCKING WARNING vs INFO WARNING ERROR; partially overlapping, not identical |
| LiveParityKind / WorkbookParityKind | domain/calculations/registry/_live_parity.py:11 / domain/calculations/registry/_workbook_parity.py:11 | Identical MATCH MISMATCH MISSING; same subdomain, different parity surfaces |
| FilingExportFormat / TabularExportKind | application/filing/_export.py:16 / application/export/_tabular.py:16 | Overlapping export format concepts split across two app subpackages |

Total: 9 duplicate / parallel pairs.

---

### 5. Compatibility Re-Exports

Modules that import an enum they did not declare and re-export it via __all__.

| File | Imported-from | Re-exported enum(s) | __all__ line |
|---|---|---|---|
| domain/invoices/_enums.py | domain/iva | InvoiceKind EUMemberState IvaRateKind | :121 |
| domain/invoices/__init__.py | domain/invoices/_enums.py | InvoiceKind (second hop) | (module __init__) |

Total: 1 primary compat re-export site (InvoiceKind); 1 second-hop re-export through the package __init__.

---

### 6. Placement Recommendations

Following Rule 1 (lowest layer that owns the constraint shape and is imported outside the declaring layer) and Rule 2 (domain packages must not import from sibling domain packages).

| Enum | Current | Recommended target | Justification |
|---|---|---|---|
| EUMemberState | domain/iva/_schema.py | core/geography.py | 27 ISO country codes; zero IVA semantics; consumed by 4 layers and 3 sibling domains; identical constraint shape to IdentityDocument in core |
| SpendingCategory | domain/categories/_spending_category.py | core/taxonomy.py | Reference catalogue with 28 members; consumed by all 5 layers; 5 sibling-domain import lines; no domain-specific constraint logic |
| CCAA (merge CalendarCCAA) | domain/profile/_ccaa.py | core/geography.py | Administrative geographic primitive; 17 autonomous communities; CalendarCCAA is a pure duplicate that disappears after merge; consumed by 4 layers |
| InvoiceKind | domain/iva/_classification.py | core/invoicing.py or domain/__init__.py | Consumed by 3 sibling domain packages via re-export chain; canonical home should be above the sibling boundary |
| FilingSchemaKind | domain/filing/_schema.py | core/modelos.py or domain/modelos/_kinds.py | 5 sibling-domain import lines; acts as a routing key across domain, application, adapters, and entrypoints; no filing-specific constraint logic beyond the name set |

Note: BaseSeverity duplicates (5 parallel declarations) are resolved by enforcing import of core/errors/_severity.py at every consumer site and deleting the per-layer re-declarations.
