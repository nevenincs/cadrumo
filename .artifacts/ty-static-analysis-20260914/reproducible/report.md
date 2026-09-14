# ty static signal report

Input SHA-256: `b4cedbdcf7cbb3c19996788071854876204301a2c6e4a48b399327a8d2b122f1`  
Diagnostics: **11,555** across **1,182** files  
Tests: **10,775** (93.25%)  
Non-tests: **780** (6.75%)

## Rule Pareto

| Rule | Count | % total |
|---|---:|---:|
| `unresolved-attribute` | 4,405 | 38.12% |
| `missing-argument` | 3,073 | 26.59% |
| `unknown-argument` | 1,935 | 16.75% |
| `invalid-argument-type` | 1,414 | 12.24% |
| `missing-override-decorator` | 278 | 2.41% |
| `unsound-return-statement` | 153 | 1.32% |
| `not-iterable` | 74 | 0.64% |
| `unresolved-import` | 55 | 0.48% |
| `not-subscriptable` | 33 | 0.29% |
| `invalid-return-type` | 22 | 0.19% |
| `unsound-assignment` | 22 | 0.19% |
| `call-non-callable` | 20 | 0.17% |

## Reproducible signal clusters

| Cluster | Exact definition | Diagnostics | Test | Non-test | Files | % total |
|---|---|---:|---:|---:|---:|---:|
| `class-static-member-access` | unresolved-attribute diagnostics exactly matching Class <owner> has no attribute <member> | 4,154 | 4,151 | 3 | 448 | 35.95% |
| `top-eight-class-member-owners` | subset of class-static-member-access for the eight highest-frequency owners | 2,518 | 2,518 | 0 | 359 | 21.79% |
| `ports-signature-migration` | all parsed missing/unknown call diagnostics for functions that both require missing ports and reject at least one old argument | 2,541 | 2,522 | 19 | 179 | 21.99% |
| `missing-operation-propagation` | missing-argument diagnostics whose parsed required-parameter list contains operation | 891 | 854 | 37 | 221 | 7.71% |
| `missing-profile-context` | missing-argument diagnostics containing profile_decode_context or profile_create_context | 266 | 262 | 4 | 72 | 2.30% |
| `missing-override-decorator` | all missing-override-decorator diagnostics | 278 | 75 | 203 | 60 | 2.41% |

Clusters overlap; percentages are not additive.

## Ordered exclusive burn-down

| Cluster | Raw | Exclusive | Earlier overlap | Test | Non-test | Completion |
|---|---:|---:|---:|---:|---:|---|
| `RC1-class-static-member-access` | 4,154 | 4,154 | 0 | 4,151 | 3 | `raw_count == 0` |
| `RC2-ports-signature-migration` | 2,541 | 2,541 | 0 | 2,522 | 19 | `raw_count == 0` |
| `RC3-object-typed-argument-flow` | 1,010 | 1,010 | 0 | 982 | 28 | `raw_count == 0` |
| `RC4-operation-propagation` | 891 | 891 | 0 | 854 | 37 | `raw_count == 0` |
| `RC5-missing-override-contract` | 278 | 278 | 0 | 75 | 203 | `raw_count == 0` |
| `RC6-profile-context-propagation` | 266 | 266 | 0 | 262 | 4 | `raw_count == 0` |
| `RESIDUAL-unclustered` | 2,415 | 2,415 | 0 | 1,929 | 486 | `exclusive_count == 0` |

## Actual offender hierarchy

### RC1-class-static-member-access

| Offender | Diagnostics | Files | Dominant sub-signals |
|---|---:|---:|---|
| `IvaCategory` | 733 | 159 | `DOMESTIC_GENERAL` (188), `INTRA_COMMUNITY_SUPPLY` (104), `DOMESTIC_EXEMPT` (59), `EXPORT_THIRD_COUNTRY_ZERO_RATED` (47), `INTRA_COMMUNITY_ACQUISITION_REVERSE_CHARGE` (46) |
| `IvaTerritorialScope` | 348 | 39 | `ES_MAINLAND` (147), `EU_MEMBER` (79), `ES_CANARIAS` (64), `THIRD_COUNTRY` (38), `ES_CEUTA_MELILLA` (20) |
| `SpendingCategory` | 304 | 53 | `MATERIAL_OFICINA` (47), `TELEFONIA_MOVIL` (47), `SUMINISTROS_HOME_OFFICE_LUZ` (35), `GASTOS_BANCARIOS` (31), `CUOTAS_AUTONOMOS_SS` (24) |
| `IvaRateKind` | 293 | 68 | `GENERAL` (168), `REDUCED` (51), `SUPER_REDUCED` (40), `ZERO` (25), `EXEMPT` (9) |
| `EUMemberState` | 242 | 52 | `DE` (90), `ES` (69), `FR` (26), `XI` (11), `IT` (6) |
| `IvaRate` | 219 | 74 | `RATE_21` (110), `EXEMPT` (31), `RATE_10` (19), `RATE_0` (15), `RATE_2` (15) |
| `IVARegime` | 197 | 87 | `GENERAL` (170), `EXENTO` (9), `SIMPLIFICADO` (8), `NO_APLICA` (4), `REAGP` (4) |
| `IvaFlowDirection` | 182 | 39 | `REPERCUTIDO` (77), `SOPORTADO` (58), `INVERSION_SUJETO_PASIVO` (40), `OPERACION_CON_INVERSION` (7) |
| `ProrrataRegisterRegime` | 161 | 32 | `GENERAL` (109), `ESPECIAL` (39), `NINGUNA` (13) |
| `IvaDeductionFactKind` | 111 | 50 | `DOMESTIC_CURRENT` (59), `INTRA_EU_CURRENT` (28), `IMPORT_CURRENT` (9), `INVESTMENT_GOODS_REGULARISATION` (6), `DOMESTIC_INVESTMENT` (5) |

### RC2-ports-signature-migration

| Offender | Diagnostics | Files | Dominant sub-signals |
|---|---:|---:|---|
| `calculate_modelo_revision` | 490 | 41 | `missing:ports` (127), `unknown:work_unit_repository` (124), `unknown:calculation_repository` (122), `unknown:bucket_event_repository` (115), `unknown:borrador_snapshot_repository` (2) |
| `calculate_modelo_revision_from_bucket_aggregation_with_diagnostics` | 450 | 41 | `missing:ports` (93), `unknown:calculation_repository` (91), `unknown:work_unit_repository` (91), `unknown:transaction_repository` (80), `unknown:invoice_repository` (52) |
| `create_work_unit` | 354 | 89 | `missing:ports` (182), `unknown:repository` (153), `unknown:bucket_event_repository` (19) |
| `create_manual_transaction` | 260 | 35 | `missing:ports` (84), `unknown:transaction_repository` (81), `unknown:bucket_event_repository` (80), `unknown:attachment_store` (5), `unknown:invoice_repository` (5) |
| `amend_modelo_revision` | 116 | 7 | `missing:ports` (24), `unknown:calculation_repository` (23), `unknown:filing_repository` (23), `unknown:work_unit_repository` (23), `unknown:bucket_event_repository` (22) |
| `file_modelo_revision` | 102 | 16 | `missing:certificate_secret_backend_factory+ports` (24), `unknown:calculation_repository` (18), `unknown:filing_repository` (18), `unknown:work_unit_repository` (18), `unknown:bucket_event_repository` (14) |
| `attach_manual_transaction_evidence` | 80 | 8 | `missing:ports` (21), `unknown:bucket_event_repository` (21), `unknown:transaction_repository` (21), `unknown:invoice_repository` (5), `unknown:attachment_store` (4) |
| `update_manual_transaction_fields` | 69 | 10 | `missing:ports` (22), `unknown:transaction_repository` (22), `unknown:bucket_event_repository` (21), `unknown:calculation_repository` (2), `unknown:work_unit_repository` (2) |
| `get_calculation_revision` | 60 | 11 | `missing:ports` (32), `unknown:calculation_repository` (27), `unknown:work_unit_repository` (1) |
| `aggregate_renta_ledger_expenses_from_repositories` | 47 | 3 | `missing:ports` (16), `unknown:transaction_repository` (16), `unknown:invoice_repository` (15) |

### RC3-object-typed-argument-flow

| Offender | Diagnostics | Files | Dominant sub-signals |
|---|---:|---:|---|
| `confirm_invoice_draft_from_evidence` | 936 | 13 | `str | None <- object` (205), `Decimal | None <- object` (199), `date | None <- object` (67), `str <- object` (67), `CatalogueCreationPorts <- object` (34) |
| `<unscoped-invalid-argument>` | 41 | 18 | `str | Buffer | SupportsInt | SupportsIndex | SupportsTrunc <- object` (14), `SecureObjectRepository | None <- object` (5), `CalculationRevisionCatalogueRepositoryProtocol <- object` (3), `Iterable[Unknown] <- object` (3), `SecureObjectRepository <- object` (3) |
| `_casilla` | 8 | 1 | `str <- object` (3), `str | None <- object` (2), `tuple[LegalRefId, ...] <- object` (2), `tuple[str, ...] <- object` (1) |
| `add_recipient_fingerprint` | 4 | 1 | `str <- object` (3), `datetime | None <- object` (1) |
| `extract_invoice_fields_from_text` | 4 | 2 | `InvoiceExtractionAuthorityValues | None <- object` (2), `Settings | None <- object` (2) |
| `_amendment_ledger_anchor` | 3 | 1 | `WorkUnit <- object` (3) |
| `pull_filed_history` | 3 | 1 | `OperationEventEmitter | None <- object` (1), `SyncRunRecordRepositoryProtocol | None <- object` (1), `TaxpayerProfile | None <- object` (1) |
| `fetch_notifications_query` | 2 | 1 | `AeatSession <- object` (1), `Settings | None <- object` (1) |
| `_selected_registry_ledger_declarations` | 1 | 1 | `WorkUnit <- object` (1) |
| `build_lexical_index` | 1 | 1 | `Iterable[CorpusChunk] <- object` (1) |

### RC4-operation-propagation

| Offender | Diagnostics | Files | Dominant sub-signals |
|---|---:|---:|---|
| `verify_modelo_revision` | 67 | 33 | `missing:operation` (41), `missing:certificate_secret_backend_factory+verification_repositories+operation` (26) |
| `classify_iva` | 62 | 12 | `missing:operation` (62) |
| `build_overview_calendar` | 52 | 10 | `missing:operation` (52) |
| `territorial_scope_for_country` | 47 | 10 | `missing:operation` (47) |
| `resolve_profile_sourced_bindings` | 29 | 9 | `missing:operation` (29) |
| `resolve_iva_ledger_binding_values` | 27 | 12 | `missing:operation` (27) |
| `country_code_for_printed_country_name` | 26 | 2 | `missing:operation` (26) |
| `extract_invoice_draft_from_evidence` | 26 | 10 | `missing:ports+operation+legends` (26) |
| `assemble_classification_criteria` | 24 | 7 | `missing:operation` (24) |
| `territorial_scope_for_spanish_postal_code` | 20 | 4 | `missing:operation` (20) |

### RC5-missing-override-contract

| Offender | Diagnostics | Files | Dominant sub-signals |
|---|---:|---:|---|
| `ActiveProfileSessionPresencePort.is_bound` | 5 | 5 | `is_bound` (5) |
| `CertificateHealthProbePort.evaluate` | 5 | 5 | `evaluate` (5) |
| `ClaveIdentityProbePort.classify` | 5 | 5 | `classify` (5) |
| `Collection.__len__` | 5 | 4 | `__len__` (5) |
| `Iterable.__iter__` | 5 | 4 | `__iter__` (5) |
| `NodeVisitor.visit_ClassDef` | 5 | 3 | `visit_ClassDef` (5) |
| `NodeVisitor.visit_FunctionDef` | 5 | 3 | `visit_FunctionDef` (5) |
| `TransactionCatalogueRepositoryProtocol.bucket_id` | 5 | 5 | `bucket_id` (5) |
| `TransactionCatalogueRepositoryProtocol.exists` | 5 | 5 | `exists` (5) |
| `TransactionCatalogueRepositoryProtocol.load` | 5 | 5 | `load` (5) |

### RC6-profile-context-propagation

| Offender | Diagnostics | Files | Dominant sub-signals |
|---|---:|---:|---|
| `register_profile_with_credentials` | 117 | 56 | `missing:profile_create_context+profile_decode_context` (117) |
| `login_profile` | 72 | 34 | `missing:profile_decode_context` (72) |
| `ProfileRecordSession.from_envelope` | 32 | 15 | `missing:profile_decode_context` (32) |
| `rotate_profile_passphrase` | 13 | 4 | `missing:profile_decode_context` (13) |
| `prepare_workbench_bootstrap` | 8 | 1 | `missing:profile_decode_context` (8) |
| `restore_profile_from_recovery_artifact` | 7 | 1 | `missing:profile_decode_context` (7) |
| `bind_resumed_profile_session` | 4 | 3 | `missing:profile_decode_context` (4) |
| `restore_profile_capsule_with_password` | 4 | 2 | `missing:profile_decode_context` (4) |
| `prepare_profile_export` | 3 | 1 | `missing:profile_decode_context` (3) |
| `build_secure_object_custody_payload` | 2 | 1 | `missing:profile_decode_context` (2) |

## Top class/member owners

| Owner | Diagnostics | Files | Unique members |
|---|---:|---:|---:|
| `IvaCategory` | 733 | 159 | 21 |
| `IvaTerritorialScope` | 348 | 39 | 5 |
| `SpendingCategory` | 304 | 53 | 27 |
| `IvaRateKind` | 293 | 68 | 5 |
| `EUMemberState` | 242 | 52 | 28 |
| `IvaRate` | 219 | 74 | 9 |
| `IVARegime` | 197 | 87 | 6 |
| `IvaFlowDirection` | 182 | 39 | 4 |
| `ProrrataRegisterRegime` | 161 | 32 | 3 |
| `IvaDeductionFactKind` | 111 | 50 | 7 |
| `TransactionKind` | 101 | 18 | 11 |
| `ProrrataProvisionalProvenance` | 99 | 27 | 4 |
| `EntityType` | 91 | 31 | 3 |
| `CustomerTaxStatus` | 87 | 15 | 5 |
| `DescendantRelacion` | 74 | 9 | 6 |
| `IvaDeductionEvidenceAuthority` | 56 | 40 | 6 |
| `FiscalResidency` | 52 | 13 | 2 |
| `BienInversionKind` | 49 | 13 | 2 |
| `IvaCashAccountingTreatment` | 49 | 21 | 3 |
| `M303RegimeComposition` | 49 | 24 | 3 |

## Top parsed call-signature cascades

| Function | Diagnostics | Files | Missing parameters | Unknown parameters |
|---|---:|---:|---|---|
| `calculate_modelo_revision` | 490 | 41 | `{"ports": 127}` | `{"borrador_snapshot_repository": 2, "bucket_event_repository": 115, "calculation_repository": 122, "work_unit_repository": 124}` |
| `calculate_modelo_revision_from_bucket_aggregation_with_diagnostics` | 450 | 41 | `{"ports": 93}` | `{"bucket_event_repository": 39, "calculation_repository": 91, "filing_repository": 1, "invoice_repository": 52, "iva_compensation_decision_repository": 3, "transaction_repository": 80, "work_unit_repository": 91}` |
| `create_work_unit` | 354 | 89 | `{"ports": 182}` | `{"bucket_event_repository": 19, "repository": 153}` |
| `create_manual_transaction` | 260 | 35 | `{"ports": 84}` | `{"attachment_store": 5, "bucket_event_repository": 80, "invoice_repository": 5, "transaction_repository": 81, "usage_ratio_profile": 5}` |
| `verify_modelo_revision` | 181 | 33 | `{"certificate_secret_backend_factory": 26, "operation": 67, "verification_repositories": 26}` | `{"bucket_event_repository": 19, "calculation_observation_repository": 6, "calculation_repository": 25, "filing_repository": 14, "transaction_repository": 8, "verification_repository": 17, "work_unit_repository": 25}` |
| `register_profile_with_credentials` | 117 | 56 | `{"profile_create_context": 117, "profile_decode_context": 117}` | `{}` |
| `amend_modelo_revision` | 116 | 7 | `{"ports": 24}` | `{"bucket_event_repository": 22, "calculation_repository": 23, "filing_repository": 23, "justificante_repository": 1, "work_unit_repository": 23}` |
| `file_modelo_revision` | 102 | 16 | `{"certificate_secret_backend_factory": 24, "ports": 24}` | `{"bucket_event_repository": 14, "calculation_observation_repository": 1, "calculation_repository": 18, "filing_repository": 18, "iva_compensation_decision_repository": 2, "verification_repository": 7, "work_unit_repository": 18}` |
| `attach_manual_transaction_evidence` | 80 | 8 | `{"ports": 21}` | `{"attachment_store": 4, "bucket_event_repository": 21, "calculation_repository": 4, "invoice_repository": 5, "transaction_repository": 21, "work_unit_repository": 4}` |
| `login_profile` | 72 | 34 | `{"profile_decode_context": 72}` | `{}` |
| `update_manual_transaction_fields` | 69 | 10 | `{"ports": 22}` | `{"bucket_event_repository": 21, "calculation_repository": 2, "transaction_repository": 22, "work_unit_repository": 2}` |
| `classify_iva` | 62 | 12 | `{"operation": 62}` | `{}` |
| `get_calculation_revision` | 60 | 11 | `{"ports": 32}` | `{"calculation_repository": 27, "work_unit_repository": 1}` |
| `aggregate_renta_income_ledger` | 56 | 15 | `{"activity_category_matcher": 56, "employment_category_matcher": 56, "modelo": 56, "target_casilla_id": 56}` | `{}` |
| `build_overview_calendar` | 52 | 10 | `{"operation": 52}` | `{}` |
| `aggregate_renta_ledger_expenses_from_repositories` | 47 | 3 | `{"ports": 16}` | `{"invoice_repository": 15, "transaction_repository": 16}` |
| `territorial_scope_for_country` | 47 | 10 | `{"operation": 47}` | `{}` |
| `build_catalogue_invoice` | 43 | 15 | `{"rate_provider": 43}` | `{}` |
| `split_transaction` | 39 | 4 | `{"ports": 13}` | `{"bucket_event_repository": 13, "transaction_repository": 13}` |
| `get_work_unit` | 35 | 7 | `{"ports": 18}` | `{"repository": 17}` |

## Top exact diagnostic messages

| Rule | Exact description | Count |
|---|---|---:|
| `missing-argument` | missing-argument: No arguments provided for required parameters `schema_id`, `schema_version` | 212 |
| `invalid-argument-type` | invalid-argument-type: Argument to function `confirm_invoice_draft_from_evidence` is incorrect: Expected `str &#124; None`, found `object` | 205 |
| `invalid-argument-type` | invalid-argument-type: Argument to function `confirm_invoice_draft_from_evidence` is incorrect: Expected `Decimal &#124; None`, found `object` | 199 |
| `unresolved-attribute` | unresolved-attribute: Class `IvaCategory` has no attribute `DOMESTIC_GENERAL` | 188 |
| `missing-argument` | missing-argument: No argument provided for required parameter `ports` of function `create_work_unit` | 182 |
| `unresolved-attribute` | unresolved-attribute: Class `IVARegime` has no attribute `GENERAL` | 170 |
| `unresolved-attribute` | unresolved-attribute: Class `IvaRateKind` has no attribute `GENERAL` | 168 |
| `unknown-argument` | unknown-argument: Argument `repository` does not match any known parameter of function `create_work_unit` | 153 |
| `unresolved-attribute` | unresolved-attribute: Class `IvaTerritorialScope` has no attribute `ES_MAINLAND` | 147 |
| `missing-argument` | missing-argument: No argument provided for required parameter `ports` of function `calculate_modelo_revision` | 127 |
| `unknown-argument` | unknown-argument: Argument `work_unit_repository` does not match any known parameter of function `calculate_modelo_revision` | 124 |
| `unknown-argument` | unknown-argument: Argument `calculation_repository` does not match any known parameter of function `calculate_modelo_revision` | 122 |
| `missing-argument` | missing-argument: No arguments provided for required parameters `profile_create_context`, `profile_decode_context` of function `register_profile_with_credentials` | 117 |
| `unknown-argument` | unknown-argument: Argument `bucket_event_repository` does not match any known parameter of function `calculate_modelo_revision` | 115 |
| `unresolved-attribute` | unresolved-attribute: Class `IvaRate` has no attribute `RATE_21` | 110 |
| `unresolved-attribute` | unresolved-attribute: Class `ProrrataRegisterRegime` has no attribute `GENERAL` | 109 |
| `unresolved-attribute` | unresolved-attribute: Class `IvaCategory` has no attribute `INTRA_COMMUNITY_SUPPLY` | 104 |
| `missing-argument` | missing-argument: No argument provided for required parameter `ports` of function `calculate_modelo_revision_from_bucket_aggregation_with_diagnostics` | 93 |
| `unknown-argument` | unknown-argument: Argument `calculation_repository` does not match any known parameter of function `calculate_modelo_revision_from_bucket_aggregation_with_diagnostics` | 91 |
| `unknown-argument` | unknown-argument: Argument `work_unit_repository` does not match any known parameter of function `calculate_modelo_revision_from_bucket_aggregation_with_diagnostics` | 91 |

## Method

The tool validates GitLab JSON structure and derives signals only from `check_name`, `description`, and diagnostic locations. It does not read source files or import project code.
