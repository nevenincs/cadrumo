---
tags:
  - '#exec'
  - '#canonical-identifiers'
date: '2026-08-13'
modified: '2026-08-13'
body_schema: 'body-v1'
body_hash: 'sha256:dce86f524daf67dcc1a370e197f7b4a565f77b459eca45a33af7b23d7b412b4d'
step_id: 'S55'
related:
  - "[[2026-08-07-canonical-identifiers-plan]]"
---
# enumerate every registered `OutputSchema` class carrying an identifier field this plan retyped, cross-referenced against the wire census's roughly-fifty-class sweep

## Scope

- `src/cadrumo/entrypoints/cli/`

## Description

Measure and record the full current external identifier surface so S56 pins every actual CLI and MCP projection.

## Method

- Drive the real CLI payload discovery to populate `SCHEMA_REGISTRY`, then resolve every reachable Pydantic model before classifying fields against canonical identifier aliases.
- Attribute a nested identifier field to its owning model rather than double-counting it through each parent result.
- Deduplicate command aliases and re-exports by the runtime canonical declaration: `__module__` plus class name.
- Partition every discovered class by its live MCP route so S56 pins actual externally exposed result schemas rather than a guessed CLI-only subset.

## Outcome

The registered wire census is complete, canonicalized by runtime declaration, and partitioned against actual MCP exposure.

### Current live inventory

This current-working-tree measurement calls the production `build_tool_descriptors()` route, walks populated `SCHEMA_REGISTRY`, and resolves `typing.get_type_hints(..., include_extras=True)` before inspecting fields. It does not estimate a denominator from filenames, decorator grep, or re-export imports.

| measure | count |
|---|---:|
| registered command paths | 311 |
| canonical registered result classes | 301 |
| Pydantic models reachable from registered results | 547 |
| direct registered classes carrying an identifier field | 77 |
| direct registered identifier-field sites | 166 |
| reachable identifier-bearing model classes | 113 |
| reachable alias-typed identifier field sites | 221 |
| MCP-exposable command paths | 308 |

The full S56 scope is 113 reachable classes and 221 field sites. The smaller direct slice is 77 classes and 166 fields; the remaining 36 classes and 55 fields are nested payload models. Every identifier-bearing class reaches at least one MCP-exposable command; none is CLI-only.

| alias family | sites | validation-mode published shape |
|---|---:|---|
| `aeat_csv` | 2 | `type: string`, `minLength: 8`, `maxLength: 32`; pattern intentionally absent in validation mode |
| `aeat_expediente_id` | 1 | `type: string`, `minLength: 12`, `maxLength: 32`, leading-year-run pattern |
| `bucket_id` | 71 | `type: string`, `minLength: 1`, `maxLength: 128` |
| `hex64` | 142 | `type: string`, `minLength: 64`, `maxLength: 64`, `pattern: ^[0-9a-f]{64}$` |
| `profile_id` | 3 | `type: string`, `minLength: 1`, `maxLength: 36`, UUIDv4 pattern |
| `tax_id_identity_token` | 2 | bare `type: string` validator-only alias |

### Canonical declaration inventory

Format: `module.class | field:family[, ...] | MCP`. The runtime class declaration is canonical. A re-export or repeated `register_schema` path does not create a second row.

```text
cadrumo.application.calculations._observations_repository.PriorDomiciliationElectionProjection | baseline_filing_record_id:hex64 | MCP
cadrumo.application.modelo._work_review.ModeloWorkReview | bucket_id:bucket_id,calculation_revision_id:hex64,work_unit_id:hex64 | MCP
cadrumo.application.state_projection.ProjectionModeloReadiness | profile_id:profile_id | MCP
cadrumo.core.telemetry._schema.TelemetryEventPayload | workspace_hash:hex64 | MCP
cadrumo.entrypoints.cli._app_live_payloads.Borrador100LatestResult | bucket_id:bucket_id,snapshot_id:hex64 | MCP
cadrumo.entrypoints.cli._app_live_payloads.Borrador100ListResult | bucket_id:bucket_id | MCP
cadrumo.entrypoints.cli._app_live_payloads.Borrador100SnapshotSummaryPayload | snapshot_id:hex64 | MCP
cadrumo.entrypoints.cli._app_live_payloads.Borrador100ViewResult | bucket_id:bucket_id,snapshot_id:hex64 | MCP
cadrumo.entrypoints.cli._app_live_payloads.ExpedienteDeclarationPayload | expediente_id:aeat_expediente_id | MCP
cadrumo.entrypoints.cli._app_live_payloads.JustificanteCaptureResult | bucket_id:bucket_id,pdf_sha256:hex64 | MCP
cadrumo.entrypoints.cli._app_live_payloads.JustificanteSnapshotSummaryPayload | pdf_sha256:hex64 | MCP
cadrumo.entrypoints.cli._app_live_payloads.JustificanteViewResult | bucket_id:bucket_id,pdf_sha256:hex64 | MCP
cadrumo.entrypoints.cli._app_live_payloads.NotificationDocumentPullResult | attachment_id:hex64,bucket_id:bucket_id,document_sha256:hex64 | MCP
cadrumo.entrypoints.cli._app_live_payloads.NotificationDocumentViewResult | attachment_id:hex64,bucket_id:bucket_id,document_sha256:hex64 | MCP
cadrumo.entrypoints.cli._app_live_payloads.NotificationSnapshotListingPayload | snapshot_id:hex64 | MCP
cadrumo.entrypoints.cli._app_live_payloads.NotificationsCaptureResult | bucket_id:bucket_id,snapshot_id:hex64 | MCP
cadrumo.entrypoints.cli._app_live_payloads.NotificationsLatestResult | bucket_id:bucket_id,snapshot_id:hex64 | MCP
cadrumo.entrypoints.cli._app_live_payloads.NotificationsListResult | bucket_id:bucket_id | MCP
cadrumo.entrypoints.cli._app_live_payloads.NotificationsViewResult | bucket_id:bucket_id,snapshot_id:hex64 | MCP
cadrumo.entrypoints.cli._app_live_payloads.SancionReadingPayload | document_sha256:hex64 | MCP
cadrumo.entrypoints.cli._app_maintenance_payloads.ReconciledProfileExportPayload | operation_id:hex64 | MCP
cadrumo.entrypoints.cli._app_quickfile_payloads.QuickfileResultPayload | calculation_revision_id:hex64 | MCP
cadrumo.entrypoints.cli._config_bucket_history_payloads.BucketHistoryEventPayload | event_id:hex64 | MCP
cadrumo.entrypoints.cli._config_payloads.ApoderadoCheckResult | bucket_id:bucket_id | MCP
cadrumo.entrypoints.cli._config_payloads.ApoderadoClearResult | bucket_id:bucket_id | MCP
cadrumo.entrypoints.cli._config_payloads.ApoderadoConfigureResult | bucket_id:bucket_id | MCP
cadrumo.entrypoints.cli._config_payloads.ApoderadoStatusResult | bucket_id:bucket_id | MCP
cadrumo.entrypoints.cli._config_payloads.ConfigLoginResult | profile_id:bucket_id | MCP
cadrumo.entrypoints.cli._config_payloads.ConfigProfileArchiveExportResult | manifest_digest:hex64 | MCP
cadrumo.entrypoints.cli._config_payloads.ConfigProfileArchiveImportResult | manifest_digest:hex64,profile_id:bucket_id | MCP
cadrumo.entrypoints.cli._config_payloads.ConfigProfileArchiveInspectResult | manifest_digest:hex64,profile_id:bucket_id | MCP
cadrumo.entrypoints.cli._config_payloads.ConfigProfileDeleteResult | profile_id:bucket_id | MCP
cadrumo.entrypoints.cli._config_payloads.ConfigProfileDuplicateResult | source_profile_id:bucket_id,target_profile_id:bucket_id | MCP
cadrumo.entrypoints.cli._config_payloads.ConfigProfilePreflightResult | profile_id:profile_id | MCP
cadrumo.entrypoints.cli._config_payloads.ConfigProfileRenameResult | profile_id:bucket_id | MCP
cadrumo.entrypoints.cli._config_payloads.ConfigProfileShowResult | profile_id:bucket_id | MCP
cadrumo.entrypoints.cli._config_payloads.ConfigProfileValidateResult | profile_id:profile_id | MCP
cadrumo.entrypoints.cli._config_payloads.ProfilePointerPayload | bucket_id:bucket_id | MCP
cadrumo.entrypoints.cli._config_sandbox_payloads.ConfigProfileSandboxArchiveResult | bucket_id:bucket_id | MCP
cadrumo.entrypoints.cli._config_sandbox_payloads.ConfigProfileSandboxCreateResult | bucket_id:bucket_id | MCP
cadrumo.entrypoints.cli._config_sandbox_payloads.ConfigProfileSandboxDiscardResult | bucket_id:bucket_id | MCP
cadrumo.entrypoints.cli._config_sandbox_payloads.ConfigProfileSandboxRestoreResult | bucket_id:bucket_id | MCP
cadrumo.entrypoints.cli._ledger_business_payloads.EvidenceExtractResult | customer_tax_id:tax_id_identity_token,supplier_tax_id:tax_id_identity_token | MCP
cadrumo.entrypoints.cli._ledger_catalogue_invoice_payloads.CatalogueInvoiceCreatePayload | bucket_id:bucket_id,invoice_id:hex64,linked_transaction_ids:hex64 | MCP
cadrumo.entrypoints.cli._ledger_catalogue_invoice_payloads.CatalogueInvoiceImportResult | bucket_id:bucket_id,created_invoice_ids:hex64 | MCP
cadrumo.entrypoints.cli._ledger_catalogue_invoice_payloads.CatalogueInvoiceListResult | bucket_id:bucket_id | MCP
cadrumo.entrypoints.cli._ledger_catalogue_invoice_payloads.CatalogueInvoiceRecordPayload | bucket_id:bucket_id,invoice_id:hex64,linked_transaction_ids:hex64 | MCP
cadrumo.entrypoints.cli._ledger_catalogue_invoice_payloads.CatalogueInvoiceRemovePayload | bucket_id:bucket_id,invoice_id:hex64,linked_transaction_ids:hex64 | MCP
cadrumo.entrypoints.cli._ledger_catalogue_invoice_payloads.CatalogueInvoiceUpdatePayload | bucket_id:bucket_id,invoice_id:hex64,linked_transaction_ids:hex64 | MCP
cadrumo.entrypoints.cli._ledger_catalogue_invoice_payloads.CatalogueInvoiceViewResult | bucket_id:bucket_id,invoice_id:hex64,linked_transaction_ids:hex64 | MCP
cadrumo.entrypoints.cli._ledger_catalogue_invoice_payloads.CatalogueInvoiceWizardResult | bucket_id:bucket_id,invoice_id:hex64,linked_transaction_ids:hex64 | MCP
cadrumo.entrypoints.cli._ledger_payloads.LedgerExportPayload | bucket_id:bucket_id,export_id:hex64,sha256:hex64 | MCP
cadrumo.entrypoints.cli._ledger_payloads.LedgerExportRowPayload | bucket_id:bucket_id,transaction_id:hex64 | MCP
cadrumo.entrypoints.cli._ledger_payloads.LedgerImportPayload | bucket_id:bucket_id | MCP
cadrumo.entrypoints.cli._ledger_payloads.LedgerImportTransactionRefPayload | bucket_id:bucket_id,transaction_id:hex64 | MCP
cadrumo.entrypoints.cli._ledger_payloads.LedgerRemovalBlockerPayload | calculation_revision_id:hex64 | MCP
cadrumo.entrypoints.cli._ledger_payloads.LedgerReviewResult | id:hex64 | MCP
cadrumo.entrypoints.cli._ledger_payloads.LedgerReviewRowPayload | id:hex64 | MCP
cadrumo.entrypoints.cli._ledger_payloads.LedgerStatusResult | bucket_id:bucket_id | MCP
cadrumo.entrypoints.cli._ledger_payloads.LedgerTransactionParticipationEntryPayload | calculation_revision_id:hex64 | MCP
cadrumo.entrypoints.cli._ledger_payloads.TransactionPayload | transaction_id:hex64 | MCP
cadrumo.entrypoints.cli._ledger_rule_payloads.ClassificationRulePayload | rule_id:hex64 | MCP
cadrumo.entrypoints.cli._ledger_rule_payloads.RuleAddResult | rule_id:hex64 | MCP
cadrumo.entrypoints.cli._ledger_rule_payloads.RuleApplyAppliedPayload | matched_rule_id:hex64 | MCP
cadrumo.entrypoints.cli._ledger_rule_payloads.RuleApplyMatchPayload | matched_rule_id:hex64 | MCP
cadrumo.entrypoints.cli._modelo_amend_wizard_payloads.WorkAmendWizardResult | amends_filing_record_id:hex64,bucket_id:bucket_id,calculation_revision_id:hex64,filing_record_id:hex64,superseded_by_filing_record_id:hex64,work_unit_id:hex64 | MCP
cadrumo.entrypoints.cli._modelo_aux_payloads.EvidenceRecordRefPayload | content_sha256:hex64 | MCP
cadrumo.entrypoints.cli._modelo_aux_payloads.ModeloAuditCheckResult | bundle_id:hex64 | MCP
cadrumo.entrypoints.cli._modelo_aux_payloads.ModeloAuditExportResult | bucket_id:bucket_id,bundle_id:hex64 | MCP
cadrumo.entrypoints.cli._modelo_aux_payloads.ModeloAuditShowResult | bucket_id:bucket_id,bundle_id:hex64,calculation_revision_id:hex64,filing_record_id:hex64,work_unit_id:hex64 | MCP
cadrumo.entrypoints.cli._modelo_aux_payloads.WorkUnitHistoryEventPayload | event_id:hex64 | MCP
cadrumo.entrypoints.cli._modelo_payloads.CalculationRevisionPayload | calculation_revision_id:hex64,work_unit_id:hex64 | MCP
cadrumo.entrypoints.cli._modelo_payloads.CrossPeriodDependencyEvidencePayload | calculation_revision_id:hex64 | MCP
cadrumo.entrypoints.cli._modelo_payloads.FilingRecordImportResult | amends_filing_record_id:hex64,bucket_id:bucket_id,calculation_revision_id:hex64,filing_record_id:hex64,superseded_by_filing_record_id:hex64,work_unit_id:hex64 | MCP
cadrumo.entrypoints.cli._modelo_payloads.ModeloExportPayload | calculation_revision_id:hex64 | MCP
cadrumo.entrypoints.cli._modelo_payloads.ModeloLifecycleEventPayload | event_id:hex64 | MCP
cadrumo.entrypoints.cli._modelo_payloads.ModeloRecordPayload | amends_filing_record_id:hex64,bucket_id:bucket_id,calculation_revision_id:hex64,filing_record_id:hex64,superseded_by_filing_record_id:hex64,work_unit_id:hex64 | MCP
cadrumo.entrypoints.cli._modelo_payloads.ModeloRecordShowResult | amends_filing_record_id:hex64,bucket_id:bucket_id,calculation_revision_id:hex64,filing_record_id:hex64,superseded_by_filing_record_id:hex64,work_unit_id:hex64 | MCP
cadrumo.entrypoints.cli._modelo_payloads.VerificationReportPayload | calculation_revision_id:hex64,verification_report_id:hex64 | MCP
cadrumo.entrypoints.cli._modelo_payloads.VerificationReportShowResult | calculation_revision_id:hex64,verification_report_id:hex64 | MCP
cadrumo.entrypoints.cli._modelo_payloads.WorkAmendResult | amends_filing_record_id:hex64,bucket_id:bucket_id,calculation_revision_id:hex64,filing_record_id:hex64,superseded_by_filing_record_id:hex64,work_unit_id:hex64 | MCP
cadrumo.entrypoints.cli._modelo_payloads.WorkCalculateResult | calculation_revision_id:hex64,work_unit_id:hex64 | MCP
cadrumo.entrypoints.cli._modelo_payloads.WorkCreateResult | bucket_id:bucket_id,current_calculation_revision_id:hex64,current_filing_record_id:hex64,filed_calculation_revision_id:hex64,work_unit_id:hex64 | MCP
cadrumo.entrypoints.cli._modelo_payloads.WorkDiscardResult | bucket_id:bucket_id,current_calculation_revision_id:hex64,current_filing_record_id:hex64,filed_calculation_revision_id:hex64,work_unit_id:hex64 | MCP
cadrumo.entrypoints.cli._modelo_payloads.WorkFileResult | amends_filing_record_id:hex64,bucket_id:bucket_id,calculation_revision_id:hex64,filing_record_id:hex64,superseded_by_filing_record_id:hex64,work_unit_id:hex64 | MCP
cadrumo.entrypoints.cli._modelo_payloads.WorkRenameResult | bucket_id:bucket_id,current_calculation_revision_id:hex64,current_filing_record_id:hex64,filed_calculation_revision_id:hex64,work_unit_id:hex64 | MCP
cadrumo.entrypoints.cli._modelo_payloads.WorkResumeResult | calculation_revision_id:hex64 | MCP
cadrumo.entrypoints.cli._modelo_payloads.WorkStatusResult | bucket_id:bucket_id,current_calculation_revision_id:hex64,current_filing_record_id:hex64,filed_calculation_revision_id:hex64,work_unit_id:hex64 | MCP
cadrumo.entrypoints.cli._modelo_payloads.WorkUnitPayload | bucket_id:bucket_id,current_calculation_revision_id:hex64,current_filing_record_id:hex64,filed_calculation_revision_id:hex64,work_unit_id:hex64 | MCP
cadrumo.entrypoints.cli._modelo_payloads.WorkVerifyResult | calculation_revision_id:hex64,verification_report_id:hex64 | MCP
cadrumo.entrypoints.cli._modelo_payloads_m036.M036DeclarationListResult | bucket_id:bucket_id | MCP
cadrumo.entrypoints.cli._modelo_payloads_m036.M036DeclarationRecordResult | bucket_id:bucket_id | MCP
cadrumo.entrypoints.cli._modelo_payloads_m036.M036DeclarationRowPayload | bucket_id:bucket_id | MCP
cadrumo.entrypoints.cli._modelo_payloads_m036.M036DeclarationShowResult | bucket_id:bucket_id | MCP
cadrumo.entrypoints.cli._modelo_payloads_m036.ModeloReconciliationHistoryResult | bucket_id:bucket_id,work_unit_id:hex64 | MCP
cadrumo.entrypoints.cli._modelo_payloads_m036.ModeloReconciliationHistoryRowPayload | bucket_id:bucket_id,work_unit_id:hex64 | MCP
cadrumo.entrypoints.cli._modelo_payloads_m145.M145CommunicationExportResultPayload | bucket_id:bucket_id | MCP
cadrumo.entrypoints.cli._modelo_payloads_m145.M145CommunicationRecordPayload | bucket_id:bucket_id | MCP
cadrumo.entrypoints.cli._modelo_payloads_m145.M145CommunicationValidationResultPayload | bucket_id:bucket_id | MCP
cadrumo.entrypoints.cli._modelo_review_package_payloads.ModeloReviewPackageBuildResult | bucket_id:bucket_id,calculation_revision_id:hex64,work_unit_id:hex64 | MCP
cadrumo.entrypoints.cli._modelo_review_package_payloads.ModeloReviewPackageCounterSignResult | bucket_id:bucket_id | MCP
cadrumo.entrypoints.cli._modelo_review_package_payloads.ModeloReviewPackageDecryptResult | bucket_id:bucket_id | MCP
cadrumo.entrypoints.cli._modelo_review_package_payloads.ModeloReviewPackageEncryptFeedbackResult | calculation_revision_id:hex64,work_unit_id:hex64 | MCP
cadrumo.entrypoints.cli._modelo_review_package_payloads.ModeloReviewPackageImportFeedbackResult | bucket_id:bucket_id,calculation_revision_id:hex64,work_unit_id:hex64 | MCP
cadrumo.entrypoints.cli._modelo_review_package_payloads.ModeloReviewPackageSignResult | calculation_revision_id:hex64 | MCP
cadrumo.entrypoints.cli._modelo_review_package_payloads.ModeloReviewPackageVerifyResult | bucket_id:bucket_id,calculation_revision_id:hex64,work_unit_id:hex64 | MCP
cadrumo.entrypoints.cli._modelo_work_revision_payloads.WorkObservationsResult | calculation_revision_id:hex64,work_unit_id:hex64 | MCP
cadrumo.entrypoints.cli._modelo_work_revision_payloads.WorkRevisionResult | calculation_revision_id:hex64,work_unit_id:hex64 | MCP
cadrumo.entrypoints.cli._modelo_work_wizard_payloads.WorkWizardResult | calculation_revision_id:hex64,work_unit_id:hex64 | MCP
cadrumo.entrypoints.cli._overview_payloads.OverviewCalendarEventPayload | verified_justificante_csv:aeat_csv | MCP
cadrumo.entrypoints.cli._overview_payloads.OverviewCalendarFilingEvidencePayload | local_calculation_revision_id:hex64,verified_justificante_csv:aeat_csv | MCP
cadrumo.entrypoints.cli._payloads_modelo_reconcile.ModeloReconcileResult | bucket_id:bucket_id,work_unit_id:hex64 | MCP
cadrumo.entrypoints.cli._review_payloads.ReviewQueueRowPayload | bucket_id:bucket_id | MCP
```

### Re-export and exclusion audit

The 311 registered command paths resolve to 301 canonical class declarations. Seven declarations serve multiple paths, contributing ten additional paths; they are deliberately deduplicated above:
- `cadrumo.entrypoints.cli._config_payloads.CertificateSourceMutationPayload`: `config.auth.certificate.register`, `config.auth.certificate.remove`, `config.auth.certificate.select`
- `cadrumo.entrypoints.cli._config_payloads.CertificateSourceSecretMutationPayload`: `config.auth.certificate.secret.remove`, `config.auth.certificate.secret.set`
- `cadrumo.entrypoints.cli._ledger_payloads.LedgerAttachResult`: `ledger.attach`, `ledger.doclink`
- `cadrumo.entrypoints.cli._modelo_payloads_m036.M036DeclarationRecordResult`: `modelo.m036.alta`, `modelo.m036.baja`, `modelo.m036.modificacion`
- `cadrumo.entrypoints.cli._modelo_payloads_m145.M145CommunicationRecordResult`: `modelo.m145.create`, `modelo.m145.mark_delivered_to_payer`, `modelo.m145.mark_locally_completed`
- `cadrumo.entrypoints.cli._payloads_modelo_reconcile.ModeloReconcileResult`: `modelo.reconcile.file`, `modelo.reconcile.pull`
- `cadrumo.entrypoints.cli._registry_payloads.RegistryInspectResult`: `registry.inspect`, `registry.verify`

Nine enrolled aliases have no reachable field on this operator wire and are excluded from S56 pin coverage until a registered payload adopts one: `Hex16Str`, `RegistrySnapshotId`, `ProfileLabel`, `ContentDigestOrAbsent`, `AeatCertificadoId`, `AeatClaveLiquidacion`, `AeatPresentationId`, `AeatBoxNumber`, and `SubjectTaxId`.

Three identifier-bearing roots are exposed only through deliberately thinned MCP results; their retained identifier fields remain in S56: `WorkCalculateResult` (`modelo.work.calculate`), `WorkObservationsResult` (`modelo.work.observations`), and `WorkRevisionResult` (`modelo.work.revision`).

## Notes

Counts are a current-working-tree measurement, not a durable fixed denominator. Re-run the registry walk before a later pin expansion; do not infer coverage from this record's class names alone.
