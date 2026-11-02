# Detailed technical articles

[Technical overview](../architecture.md) · [Article index](catalogue.md) · [Snapshot and reading guide](../reading-guide.md)

> This page describes the analyzed source snapshot. Its findings and limitations are not a certification of the current branch.

The 204 articles are grouped by their original topic assignments. Each article retains its scope, mechanisms, findings, qualifications, and coverage appendix. Report identifiers preserve correspondence with the original analysis.

## Operator interfaces: command graph and principal workflows

[Read the topic overview](../topics/operator-interfaces-command-graph.md).

- [Entrypoint adapter composition](154-entrypoint-adapter-composition.md)
- [Entrypoint operation and read composition](155-entrypoint-operation-and-read-composition.md)
- [CLI command contracts and operator surfaces](156-cli-command-contracts-and-operator-surfaces.md)
- [Live AEAT CLI capture and snapshot surfaces](157-live-aeat-cli-capture-and-snapshot-surfaces.md)
- [CLI contracts, execution projection, diagnostics and evidence notices](158-cli-contracts-execution-projection-diagnostics-and-evidence-notices.md)
- [Ledger, invoice and document-evidence operator flows](159-ledger-invoice-and-document-evidence-operator-flows.md)
- [Ledger review, imports, rules, inventory and read surfaces](160-ledger-review-imports-rules-inventory-and-read-surfaces.md)
- [Modelo command support, discovery, amendment and export surfaces](161-modelo-command-support-discovery-amendment-and-export-surfaces.md)
- [Modelo local records, wallet, preview, and non-work command contracts](162-modelo-local-records-wallet-preview-and-non-work-command-contracts.md)
- [Modelo projection, readiness, filing evidence and sharing surfaces](163-modelo-projection-readiness-filing-evidence-and-sharing-surfaces.md)
- [Work inspection, overview, verification and profile authentication](164-work-inspection-overview-verification-and-profile-authentication.md)
- [Prorrata, review, root CLI and command authority](165-prorrata-review-root-cli-and-command-authority.md)
- [Shared CLI transport and profile configuration surfaces](166-shared-cli-transport-and-profile-configuration-surfaces.md)
- [Profile maintenance, repair, and Google operations](167-profile-maintenance-repair-and-google-operations.md)
- [Profile custody, provisioning, and runtime configuration](168-profile-custody-provisioning-and-runtime-configuration.md)

## Operator interfaces: secure transport and operation bridges

[Read the topic overview](../topics/operator-interfaces-transport-and-bridges.md).

- [Secure CLI input, profile bridges, and storage controls](169-secure-cli-input-profile-bridges-and-storage-controls.md)
- [CLI error handling, ledger actions, and Modelo work](170-cli-error-handling-ledger-actions-and-modelo-work.md)
- [CLI period, registered-operation, and ledger bridges](171-cli-period-registered-operation-and-ledger-bridges.md)
- [Ledger and Modelo CLI operations](172-ledger-and-modelo-cli-operations.md)
- [Modelo discovery, review exchange, profile admission, and workflow reads](173-modelo-discovery-review-exchange-profile-admission-and-workflow-reads.md)

## Installed runtime, terminal workbench, and MCP service

[Read the topic overview](../topics/runtime-tui-and-agent-harness.md).

- [Installed runtime, profile host, and worker authority](174-installed-runtime-profile-host-and-worker-authority.md)
- [Profile-worker request staging](175-profile-worker-request-staging.md)
- [Textual terminal workbench and Declarations calendar](176-textual-terminal-workbench-and-declarations-calendar.md)
- [Home, Declarations portfolio, and Ledger TUI flows](177-home-declarations-portfolio-and-ledger-tui-flows.md)
- [Ledger operations and Modelo lifecycle TUI doors](178-ledger-operations-and-modelo-lifecycle-tui-doors.md)
- [Modelo workbench, casilla editing, and lifecycle screens](179-modelo-workbench-casilla-editing-and-lifecycle-screens.md)
- [Modelo workbench issue review, progress and navigation](180-modelo-workbench-issue-review-progress-and-navigation.md)
- [Modelo workbench editing, source map, and operation flow](181-modelo-workbench-editing-source-map-and-operation-flow.md)
- [Supervised operation modal and profile manager](182-supervised-operation-modal-and-profile-manager.md)
- [Runtime TUI access, workbench and secret-entry flows](183-runtime-tui-access-workbench-and-secret-entry-flows.md)
- [Profile registration, recovery and runtime login](184-profile-registration-recovery-and-runtime-login.md)
- [Python typing package marker](185-python-typing-package-marker.md)

## Document and financial imports

[Read the topic overview](../topics/document-and-financial-imports.md).

- [Package namespaces](001-package-namespaces.md)
- [Inbound document and financial adapters](002-inbound-document-and-financial-adapters.md)
- [Financial providers, receipts, and notification PDFs](003-financial-providers-receipts-and-notification-pdfs.md)
- [Shared PDF text and provenance boundary](004-shared-pdf-text-and-provenance-boundary.md)

## External integrations and local runtime

[Read the topic overview](../topics/external-integrations-and-local-runtime.md).

- [Local runtime clients and native OS bindings](005-local-runtime-clients-and-native-os-bindings.md)
- [Local runtime transport, worker custody, and lifecycle](006-local-runtime-transport-worker-custody-and-lifecycle.md)
- [Windows login, process containment, and worker authority](007-windows-login-process-containment-and-worker-authority.md)
- [AEAT certificate and Cl@ve browser authentication](008-aeat-certificate-and-cl-ve-browser-authentication.md)
- [Cl@ve Permanente, browser support, and Sede read primitives](009-cl-ve-permanente-browser-support-and-sede-read-primitives.md)
- [Censal reads, filed-declaration capture, and GROI checks](010-censal-reads-filed-declaration-capture-and-groi-checks.md)
- [IVA wallet, notifications, VIES checks, and expediente reads](011-iva-wallet-notifications-vies-checks-and-expediente-reads.md)
- [PDF summaries, ECB rates, and Google Sheets exports](012-pdf-summaries-ecb-rates-and-google-sheets-exports.md)
- [Google Sheets readback, Drive ownership, and Google sign-in](013-google-sheets-readback-drive-ownership-and-google-sign-in.md)
- [LLM dispatch, consent, and invoice-reading pipeline](014-llm-dispatch-consent-and-invoice-reading-pipeline.md)
- [LLM provider adapters and Google Drive storage](015-llm-provider-adapters-and-google-drive-storage.md)
- [Local storage, remote ciphertext mirroring, and offline workbooks](016-local-storage-remote-ciphertext-mirroring-and-offline-workbooks.md)

## Persistence and secure storage

[Read the topic overview](../topics/persistence-and-secure-storage.md).

- [Persistence for LLM records, durable operations, and profile state](017-persistence-for-llm-records-durable-operations-and-profile-state.md)
- [Profile persistence for invoices, filings, and calculation evidence](018-profile-persistence-for-invoices-filings-and-calculation-evidence.md)
- [Profile persistence for transactions, review exchange, and workflows](019-profile-persistence-for-transactions-review-exchange-and-workflows.md)
- [Encrypted blobs, bucket archives, and custody filesystem](020-encrypted-blobs-bucket-archives-and-custody-filesystem.md)
- [Supervised key derivation and automation custody](021-supervised-key-derivation-and-automation-custody.md)
- [Profile capsule lifecycle and custody proof](022-profile-capsule-lifecycle-and-custody-proof.md)
- [Profile custody primitives, session state, and secure envelopes](023-profile-custody-primitives-session-state-and-secure-envelopes.md)
- [Profile custody adapter, storage routing, and secure-object contracts](024-profile-custody-adapter-storage-routing-and-secure-object-contracts.md)
- [Encrypted SQL repository, revision writes, and workflow storage](025-encrypted-sql-repository-revision-writes-and-workflow-storage.md)

## Application orchestration and diagnostics

[Read the topic overview](../topics/application-orchestration-and-diagnostics.md).

- [Configuration reset and diagnostics](026-configuration-reset-and-diagnostics.md)
- [Local reader provisioning, workstation health, and application contracts](027-local-reader-provisioning-workstation-health-and-application-contracts.md)
- [Runtime admission, canonical state, and storage-route policy](028-runtime-admission-canonical-state-and-storage-route-policy.md)
- [Installed workbench generations and workstation checks](029-installed-workbench-generations-and-workstation-checks.md)
- [Activity-asset claims and AEAT Sync workspace projection](030-activity-asset-claims-and-aeat-sync-workspace-projection.md)
- [Offline search, evidence bundles, and export boundaries](044-offline-search-evidence-bundles-and-export-boundaries.md)
- [Interactive flows and profile-bound inventory operations](048-interactive-flows-and-profile-bound-inventory-operations.md)

## Aggregation and calculation services

[Read the topic overview](../topics/aggregation-and-calculation-services.md).

- [Aggregation, IVA screening, and fiscal evidence](031-aggregation-iva-screening-and-fiscal-evidence.md)
- [Aggregation sources, evidence, and withholding projections](032-aggregation-sources-evidence-and-withholding-projections.md)
- [IVA ledger, filing drift, and withholding arrivals](033-iva-ledger-filing-drift-and-withholding-arrivals.md)
- [Model bindings, OSS/IOSS, and Renta expenses](034-model-bindings-oss-ioss-and-renta-expenses.md)
- [Renta ledgers, withholding rollups, and aggregation service](035-renta-ledgers-withholding-rollups-and-aggregation-service.md)
- [Source resolution contracts and withholding capture](036-source-resolution-contracts-and-withholding-capture.md)
- [Filing carries, cross-period clean state, and calculation advisories](041-filing-carries-cross-period-clean-state-and-calculation-advisories.md)
- [IVA compensation, M303 evidence, and annual handoffs](042-iva-compensation-m303-evidence-and-annual-handoffs.md)
- [Prorrata settlement, relation prefill, and row-set reconstruction](043-prorrata-settlement-relation-prefill-and-row-set-reconstruction.md)

## Authentication and storage management

[Read the topic overview](../topics/authentication-and-storage-management.md).

- [Authentication, certificate sources, and diagnostic privacy](037-authentication-certificate-sources-and-diagnostic-privacy.md)
- [Operator authentication, session custody, and access contracts](038-operator-authentication-session-custody-and-access-contracts.md)
- [Authenticated session lifecycle and identity binding](039-authenticated-session-lifecycle-and-identity-binding.md)
- [Capital-goods register and bucket deletion assessment](040-capital-goods-register-and-bucket-deletion-assessment.md)
- [Registry-backed calculation workbook plans and parity](098-registry-backed-calculation-workbook-plans-and-parity.md)
- [Workbook materialization and sync-run provenance](099-workbook-materialization-and-sync-run-provenance.md)
- [Storage lifecycle management and ledger-import diagnostics](100-storage-lifecycle-management-and-ledger-import-diagnostics.md)

## Filing exports and live state

[Read the topic overview](../topics/filing-and-live-state.md).

- [Filing draft, approval, and local export pipeline](045-filing-draft-approval-and-local-export-pipeline.md)
- [Filing-envelope integrity, export parity, and producer values](046-filing-envelope-integrity-export-parity-and-producer-values.md)
- [Filing producer facts, repeated-record projection, and runtime schema](047-filing-producer-facts-repeated-record-projection-and-runtime-schema.md)
- [Live snapshots and filed-data capture operations](063-live-snapshots-and-filed-data-capture-operations.md)
- [Filed declaration capture, evidence enrollment, and history sweep](064-filed-declaration-capture-evidence-enrollment-and-history-sweep.md)
- [IVA, receipt, and notification evidence surfaces](065-iva-receipt-and-notification-evidence-surfaces.md)
- [Notifications, verification, and shared live-state contracts](066-notifications-verification-and-shared-live-state-contracts.md)

## Ledger, invoices, evidence, and registers

[Read the topic overview](../topics/ledger-invoices-and-registers.md).

- [Invoice intake, catalogue lifecycle, and operation boundaries](049-invoice-intake-catalogue-lifecycle-and-operation-boundaries.md)
- [Invoice profile advisories, source-mesh resolution, and linking](050-invoice-profile-advisories-source-mesh-resolution-and-linking.md)
- [Ledger classification, import/export, and lifecycle services](051-ledger-classification-import-export-and-lifecycle-services.md)
- [Manual ledger services, evidence operations, and batch ingestion](052-manual-ledger-services-evidence-operations-and-batch-ingestion.md)
- [IVA classification assembly, confirmation checks, and readiness](053-iva-classification-assembly-confirmation-checks-and-readiness.md)
- [Confirmation gate, counterparty establishment, and evidence provenance](054-confirmation-gate-counterparty-establishment-and-evidence-provenance.md)
- [Evidence custody, review, and ingestion operations](055-evidence-custody-review-and-ingestion-operations.md)
- [Document grounding, evidence routing, history, and import/export](056-document-grounding-evidence-routing-history-and-import-export.md)
- [Invoice evidence extraction and reviewed confirmation](057-invoice-evidence-extraction-and-reviewed-confirmation.md)
- [Deterministic invoice labels and core ledger surfaces](058-deterministic-invoice-labels-and-core-ledger-surfaces.md)
- [LLM ledger review, diagnostics, and merge](059-llm-ledger-review-diagnostics-and-merge.md)
- [Ledger contracts, attribution, readiness, and ratios](060-ledger-contracts-attribution-readiness-and-ratios.md)
- [Ledger operations, rule application, and filing readiness](061-ledger-operations-rule-application-and-filing-readiness.md)
- [Ledger workspace projection and read boundaries](062-ledger-workspace-projection-and-read-boundaries.md)
- [Profile-scoped IVA prorrata register operations](095-profile-scoped-iva-prorrata-register-operations.md)

## Modelo work and revision lifecycle: calculation, export and filing

[Read the topic overview](../topics/modelo-work-calculation-and-filing.md).

- [Modelo calculation preparation, edits, and evidence gates](067-modelo-calculation-preparation-edits-and-evidence-gates.md)
- [Modelo reconciliation, advisories, and work projections](068-modelo-reconciliation-advisories-and-work-projections.md)
- [Aggregation operations, amendments, and profile bindings](069-aggregation-operations-amendments-and-profile-bindings.md)
- [Modelo calculation input and persistence orchestration](070-modelo-calculation-input-and-persistence-orchestration.md)
- [Calculation findings, reports, and PDF verification](071-calculation-findings-reports-and-pdf-verification.md)
- [Declaration projections, help, dependencies, and edit admission](072-declaration-projections-help-dependencies-and-edit-admission.md)
- [Edit value contracts and Modelo export](073-edit-value-contracts-and-modelo-export.md)
- [External filing evidence, local filing and filing views](074-external-filing-evidence-local-filing-and-filing-views.md)
- [Modelo history, invoice withholding capture, and IVA wallet](075-modelo-history-invoice-withholding-capture-and-iva-wallet.md)
- [Local observations, M036 records, and M145 communications](076-local-observations-m036-records-and-m145-communications.md)
- [Tax evidence, private previews, and spreadsheet operations](077-tax-evidence-private-previews-and-spreadsheet-operations.md)
- [Supervised filing lifecycle and operation contracts](078-supervised-filing-lifecycle-and-operation-contracts.md)
- [Profile-derived bindings and filing readiness](079-profile-derived-bindings-and-filing-readiness.md)
- [Modelo projections, queries, quickfile, and recipient encryption](080-modelo-projections-queries-quickfile-and-recipient-encryption.md)
- [Reconciliation, filing disposition, and accountant review packages](081-reconciliation-filing-disposition-and-accountant-review-packages.md)
- [Review-package exchange and Modelo revision persistence](082-review-package-exchange-and-modelo-revision-persistence.md)
- [Revision selection, settlement presentation, and verification](083-revision-selection-settlement-presentation-and-verification.md)

## Modelo work and revision lifecycle: verification, workbench and workspace

[Read the topic overview](../topics/modelo-work-verification-and-workspace.md).

- [Cross-period checks, verification reports, and work addressing](084-cross-period-checks-verification-reports-and-work-addressing.md)
- [Work creation, form editing, and inventory](085-work-creation-form-editing-and-inventory.md)
- [Work lifecycle, review, wizard, and workflow gate](086-work-lifecycle-review-wizard-and-workflow-gate.md)
- [Modelo workspace read projection](087-modelo-workspace-read-projection.md)
- [Workspace producer contracts and capture ports](088-workspace-producer-contracts-and-capture-ports.md)

## Operations, profiles and workflows

[Read the topic overview](../topics/operations-profiles-and-workflows.md).

- [Durable operation execution, access and public projections](089-durable-operation-execution-access-and-public-projections.md)
- [Operation contracts, observation and transient operands](090-operation-contracts-observation-and-transient-operands.md)
- [Operation authority, registry and private input custody](091-operation-authority-registry-and-private-input-custody.md)
- [Operator action and command-surface contracts](092-operator-action-and-command-surface-contracts.md)
- [Overview calendar, filing evidence, and readiness views](093-overview-calendar-filing-evidence-and-readiness-views.md)
- [Overview explain, Home, pipeline, and registered read projections](094-overview-explain-home-pipeline-and-registered-read-projections.md)
- [Unified review queue and local runtime contracts](096-unified-review-queue-and-local-runtime-contracts.md)
- [Ephemeral cross-workbench search](097-ephemeral-cross-workbench-search.md)
- [Profile access, automation custody, and portable exports](101-profile-access-automation-custody-and-portable-exports.md)
- [Encrypted profile custody and censal workflows](102-encrypted-profile-custody-and-censal-workflows.md)
- [Profile custody transactions and connected configuration](103-profile-custody-transactions-and-connected-configuration.md)
- [Profile login, maintenance operations, and history](104-profile-login-maintenance-operations-and-history.md)
- [Profile facts, registration, recovery, and session selection](105-profile-facts-registration-recovery-and-session-selection.md)
- [Profile session authority, access leases, and delegation](106-profile-session-authority-access-leases-and-delegation.md)
- [Setup wizard, profile editing, and command construction](107-setup-wizard-profile-editing-and-command-construction.md)
- [Wizard contracts and validation](108-wizard-contracts-and-validation.md)
- [Workflow execution and local filing orchestration](109-workflow-execution-and-local-filing-orchestration.md)
- [Workflow results, snapshots, and history disclosure](110-workflow-results-snapshots-and-history-disclosure.md)

## Core authority and shared controls

[Read the topic overview](../topics/core-authority-and-shared-controls.md).

- [Core configuration, profile selection, and durable writes](111-core-configuration-profile-selection-and-durable-writes.md)
- [Settings, storage routing, corpus citations, and credentials](112-settings-storage-routing-corpus-citations-and-credentials.md)
- [External-service constants, field provenance, and filing producers](113-external-service-constants-field-provenance-and-filing-producers.md)
- [Filing projections, workflow state, and JSON output contracts](114-filing-projections-workflow-state-and-json-output-contracts.md)
- [Logging, output privacy, model selection, and periods](115-logging-output-privacy-model-selection-and-periods.md)
- [Identity, profile sessions, result disposition, and storage taxonomy](116-identity-profile-sessions-result-disposition-and-storage-taxonomy.md)
- [Text normalization, legal categories, and validity contracts](117-text-normalization-legal-categories-and-validity-contracts.md)
- [Live access policy, corpus integrity, and decimal contracts](118-live-access-policy-corpus-integrity-and-decimal-contracts.md)
- [Error contracts, renderers, and record-fault projection](119-error-contracts-renderers-and-record-fault-projection.md)
- [Error registry catalogues and severity](120-error-registry-catalogues-and-severity.md)
- [Localization, identity validation, run traces, and date parsing](121-localization-identity-validation-run-traces-and-date-parsing.md)
- [Redaction, bundled resources, and time contracts](122-redaction-bundled-resources-and-time-contracts.md)

## Tax calculation domain

[Read the topic overview](../topics/tax-calculation-domain.md).

- [Registry formulas and filing-row materialization](124-registry-formulas-and-filing-row-materialization.md)
- [Taxpayer applicability and indexed registry authority](125-taxpayer-applicability-and-indexed-registry-authority.md)
- [Binding enrollment, prior filings, deadlines, and lineage](126-binding-enrollment-prior-filings-deadlines-and-lineage.md)
- [Casilla identity, legal vocabularies, and fixed-width exports](127-casilla-identity-legal-vocabularies-and-fixed-width-exports.md)
- [Governed facts and export conversion](128-governed-facts-and-export-conversion.md)
- [Formula evaluation, traceability, and row-source bindings](129-formula-evaluation-traceability-and-row-source-bindings.md)
- [Dated tax vocabularies, inheritance, and IVA carries](130-dated-tax-vocabularies-inheritance-and-iva-carries.md)
- [Ledger binding families and Modelo 303 evidence projections](131-ledger-binding-families-and-modelo-303-evidence-projections.md)
- [Modelo 303 projections, profile bindings, and registry scope](132-modelo-303-projections-profile-bindings-and-registry-scope.md)
- [Registry reporting, cross-filing relations, and coverage checks](133-registry-reporting-cross-filing-relations-and-coverage-checks.md)
- [Withholding bindings, revision validation, and registry schema](134-withholding-bindings-revision-validation-and-registry-schema.md)
- [Registry schemas for exports, extraction, forms, and governance](135-registry-schemas-for-exports-extraction-forms-and-governance.md)
- [Casilla verification contracts and filing snapshots](136-casilla-verification-contracts-and-filing-snapshots.md)
- [Revision selection, withholding aggregation, and row provenance](137-revision-selection-withholding-aggregation-and-row-provenance.md)

## Business and taxpayer domain

[Read the topic overview](../topics/business-and-taxpayer-domain.md).

- [Domain evidence, filing periods, and capital-goods registers](123-domain-evidence-filing-periods-and-capital-goods-registers.md)
- [Spending categories, proportionality, and census projections](138-spending-categories-proportionality-and-census-projections.md)
- [taxpayer and family domain records](139-taxpayer-and-family-domain-records.md)
- [inventory valuation and taxpayer-profile mechanics](140-inventory-valuation-and-taxpayer-profile-mechanics.md)
- [deadline, currency, and evidence-consent domain](141-deadline-currency-and-evidence-consent-domain.md)
- [filing drafts and invoice records](142-filing-drafts-and-invoice-records.md)
- [IVA classification and evidence substrate](143-iva-classification-and-evidence-substrate.md)
- [IVA rates, settlement and statutory projections](144-iva-rates-settlement-and-statutory-projections.md)
- [IVA compensation carry-forward and filing receipts](145-iva-compensation-carry-forward-and-filing-receipts.md)
- [modelo calculation, evidence and filing lifecycle](146-modelo-calculation-evidence-and-filing-lifecycle.md)
- [ledger evidence, detail rows and modelo verification](147-ledger-evidence-detail-rows-and-modelo-verification.md)
- [portal catalogue and annual prorrata register](148-portal-catalogue-and-annual-prorrata-register.md)
- [Renta expense rules and activity-asset amortization](149-renta-expense-rules-and-activity-asset-amortization.md)
- [Local submission preflight and audit records](150-local-submission-preflight-and-audit-records.md)
- [Transaction ledger domain and classifier contracts](151-transaction-ledger-domain-and-classifier-contracts.md)
- [Transaction mutations and registry-backed income predicates](152-transaction-mutations-and-registry-backed-income-predicates.md)
- [Usage ratios and user-profile domain](153-usage-ratios-and-user-profile-domain.md)

## Bundled knowledge and localization

[Read the topic overview](../topics/bundled-knowledge-and-localization.md).

- [Bundled data package marker](188-bundled-data-package-marker.md)
- [PDF color profile resource](189-pdf-color-profile-resource.md)
- [PDF summary typography assets](190-pdf-summary-typography-assets.md)
- [Corpus package marker](191-corpus-package-marker.md)
- [AEAT official reference corpus](192-aeat-official-reference-corpus.md)
- [EU VAT-rate reference sources](193-eu-vat-rate-reference-sources.md)
- [Facturae 3.2.2 enumerations and total composition](194-facturae-3-2-2-enumerations-and-total-composition.md)
- [Worked-example reference oracles](195-worked-example-reference-oracles.md)
- [AEAT practical-manual corpus](196-aeat-practical-manual-corpus.md)
- [Normative reference corpus](197-normative-reference-corpus.md)
- [GNOME native login observation](198-gnome-native-login-observation.md)
- [AEAT official manual corpus text](199-aeat-official-manual-corpus-text.md)
- [EU VAT reference text](200-eu-vat-reference-text.md)
- [AEAT manuals, extracted text](201-aeat-manuals-extracted-text.md)
- [Normative PDF text corpus](202-normative-pdf-text-corpus.md)
- [AEAT registry and model declarations](203-aeat-registry-and-model-declarations.md)
- [Cadrumo user-profile schema](204-cadrumo-user-profile-schema.md)
- [Terminology concept corpus](205-terminology-concept-corpus.md)
- [Localized interface and model-schema labels](206-localized-interface-and-model-schema-labels.md)
