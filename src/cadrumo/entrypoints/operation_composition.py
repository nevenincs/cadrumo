"""Sole production composition seam for the supervised operation platform.

Core types: :class:`~cadrumo.adapters.persistence.profile.transactions.TransactionCatalogueRepository`.
"""

from __future__ import annotations

import secrets
from collections.abc import Callable
from datetime import timedelta
from functools import partial
from typing import TYPE_CHECKING
from uuid import UUID

from ..adapters.outbound.aeat.browser.factory import BrowserRuntimeResourceScope, default_browser_session_factory
from ..adapters.outbound.aeat.export.registry_record_renderer import RegistryFixedWidthRecordRenderer
from ..adapters.outbound.aeat.sede.groi_check import collect_groi_observations
from ..adapters.outbound.aeat.sede.nif_iva_check import collect_nif_iva_check_observations
from ..adapters.outbound.calculation_summary_pdf.summary_container import write_calculation_summary_pdf
from ..adapters.outbound.google.calc_sheets_apply import apply_export_plan, preview_export_plan
from ..adapters.outbound.google.errors import GoogleAuthClientMetadataUnavailableError
from ..adapters.outbound.llm.role_fitness import probe_text_extraction_fitness
from ..adapters.outbound.model_runtime.process_control import run_runtime_installer, spawn_runtime_server
from ..adapters.outbound.storage.errors import OutboundStorageError, OutboundStorageValidationError
from ..adapters.outbound.storage.factory import build_google_credentials, resolve_drive_root_folder_id
from ..adapters.persistence.operations.journal import OperationJournalRepository
from ..adapters.persistence.operations.lease import OperationLeaseFilesystemRepository
from ..adapters.persistence.operations.secure_references import operation_secure_reference_repository
from ..adapters.persistence.operations.typed_financial_operand_custody import (
    OperationTypedFinancialOperandCustodyFilesystemRepository,
)
from ..adapters.persistence.profile.buckets import build_bucket_event_history_repository
from ..adapters.persistence.profile.calculation_revision_override_migration import GuardedCalculationRevisionMigration
from ..adapters.persistence.profile.catalogue_creation import (
    build_catalogue_creation_ports,
    build_catalogue_lifecycle_ports,
)
from ..adapters.persistence.profile.invoices import InvoiceCatalogueRepository
from ..adapters.persistence.profile.ledger_classification_rules import LedgerClassificationRuleRepository
from ..adapters.persistence.profile.m145_communication_records import build_m145_communication_records_ports
from ..adapters.persistence.profile.participation_index import TransactionParticipationIndexRepository
from ..adapters.persistence.profile.review_package_recipient_registry import build_recipient_fingerprint_registry_ports
from ..adapters.persistence.profile.review_package_signing import build_review_package_signing_keypair_capability
from ..adapters.persistence.profile.sync_runs import SyncRunRecordRepository
from ..adapters.persistence.profile.taxation_comparison import build_taxation_comparison_ports
from ..adapters.persistence.profile.transactions import TransactionCatalogueRepository
from ..adapters.persistence.profile.verify_observations import VerifyObservationRepository
from ..adapters.persistence.storage.certificate_secret_backend import build_certificate_secret_backend
from ..adapters.persistence.storage.operator_scope import build_operator_scope_ports
from ..application.actividad_asset.registered_operations import (
    build_activity_asset_claim_definition,
    build_activity_asset_claim_registration,
    build_activity_asset_correct_definition,
    build_activity_asset_correct_registration,
    build_activity_asset_create_definition,
    build_activity_asset_create_registration,
    build_activity_asset_filing_handoff_definition,
    build_activity_asset_filing_handoff_registration,
    build_activity_asset_forecast_definition,
    build_activity_asset_forecast_registration,
    build_activity_asset_inspect_definition,
    build_activity_asset_inspect_registration,
)
from ..application.auth.apoderado_operation import (
    build_apoderado_operation_definitions,
    build_apoderado_operation_registrations,
)
from ..application.auth.certificate_secret_operation import (
    CertificateSecretOperationPorts,
    build_certificate_secret_operation_definitions,
    build_certificate_secret_operation_registrations,
)
from ..application.auth.certificate_source_execution import CertificateSourceOperationPorts
from ..application.auth.certificate_source_operation import (
    build_certificate_source_check_definition,
    build_certificate_source_check_registration,
    build_certificate_source_list_definition,
    build_certificate_source_list_registration,
    build_certificate_source_register_definition,
    build_certificate_source_register_registration,
    build_certificate_source_remove_definition,
    build_certificate_source_remove_registration,
    build_certificate_source_select_definition,
    build_certificate_source_select_registration,
)
from ..application.auth.diagnostic_report_operation import (
    build_auth_diagnostic_report_definition,
    build_auth_diagnostic_report_registration,
)
from ..application.auth.operation_definitions import (
    AuthOperationPorts,
    ProfileRotationFinalizer,
    build_auth_operation_definitions,
    build_auth_operation_registrations,
)
from ..application.auth.operator_scope_ports import OperatorScopePorts
from ..application.auth.read_operation import build_auth_read_definition, build_auth_read_registration
from ..application.bienes_inversion.registered_operation import (
    build_bienes_inversion_declare_definition,
    build_bienes_inversion_declare_registration,
    build_bienes_inversion_list_definition,
    build_bienes_inversion_list_registration,
)
from ..application.bucket_event_repository import BucketEventHistoryRepositoryFactory
from ..application.diagnostics_operation import (
    build_diagnostics_read_definition,
    build_diagnostics_read_registration,
    build_diagnostics_telemetry_flush_definition,
    build_diagnostics_telemetry_flush_registration,
)
from ..application.exchange_rate_provider import exchange_rate_provider
from ..application.export.google_operation import (
    GoogleSheetsExportAuthDependencyError,
    GoogleSheetsExportClientMissingError,
    GoogleSheetsExportPreparedPort,
    GoogleSheetsExportRemoteResult,
    GoogleSheetsExportRootFolderRequiredError,
    GoogleSheetsExportTokenMissingError,
    build_google_sheets_export_operation_definition,
    build_google_sheets_export_operation_registration,
)
from ..application.inventory.registered_operation import (
    build_inventory_closing_authority_record_definition,
    build_inventory_closing_authority_record_registration,
    build_inventory_create_definition,
    build_inventory_create_registration,
    build_inventory_list_definition,
    build_inventory_list_registration,
    build_inventory_movement_add_definition,
    build_inventory_movement_add_registration,
    build_inventory_valuation_preview_definition,
    build_inventory_valuation_preview_registration,
)
from ..application.invoices.catalogue_add_operation import build_invoice_add_definition, build_invoice_add_registration
from ..application.invoices.catalogue_creation_ports import CatalogueCreationPortsFactory
from ..application.invoices.catalogue_intake_operation import (
    build_invoice_import_definition,
    build_invoice_intake_registration,
    build_invoice_wizard_definition,
)
from ..application.invoices.catalogue_lifecycle_ports import CatalogueLifecyclePortsFactory
from ..application.invoices.catalogue_read_operation import (
    build_invoice_list_definition,
    build_invoice_list_registration,
    build_invoice_view_definition,
    build_invoice_view_registration,
)
from ..application.invoices.catalogue_remove_operation import (
    build_invoice_remove_definition,
    build_invoice_remove_registration,
)
from ..application.invoices.catalogue_update_operation import (
    build_invoice_update_definition,
    build_invoice_update_registration,
)
from ..application.invoices.inspection_read_ports import InvoiceInspectionReadPortsFactory
from ..application.ledger.action_ports import LedgerActionPortsFactory
from ..application.ledger.add_operation import build_ledger_add_definition, build_ledger_add_registration
from ..application.ledger.allocate_operation import build_ledger_allocate_definition, build_ledger_allocate_registration
from ..application.ledger.attachment_mutation_operation import (
    build_ledger_attach_definition,
    build_ledger_attach_registration,
    build_ledger_detach_definition,
    build_ledger_detach_registration,
)
from ..application.ledger.bulk_classify_operation import (
    build_ledger_bulk_classify_definition,
    build_ledger_bulk_classify_registration,
)
from ..application.ledger.check_operation import build_ledger_check_definition, build_ledger_check_registration
from ..application.ledger.classify_operation import (
    build_ledger_classify_definition,
    build_ledger_classify_registration,
)
from ..application.ledger.counterparty_establishment_ports import CounterpartyEstablishmentRepositoryFactory
from ..application.ledger.counterparty_operation import (
    build_ledger_counterparty_definition,
    build_ledger_counterparty_registration,
)
from ..application.ledger.evidence_add_operation import (
    build_ledger_evidence_add_definition,
    build_ledger_evidence_add_registration,
)
from ..application.ledger.evidence_followup_contracts import (
    LedgerEvidenceFollowupOperationPorts,
)
from ..application.ledger.evidence_followup_registration import (
    build_ledger_evidence_followup_definitions,
    build_ledger_evidence_followup_registrations,
)
from ..application.ledger.evidence_ingestion_operation import (
    build_ledger_evidence_ingestion_definitions,
    build_ledger_evidence_ingestion_registrations,
)
from ..application.ledger.evidence_mutation_operation import (
    build_ledger_evidence_remove_definition,
    build_ledger_evidence_remove_registration,
    build_ledger_evidence_update_definition,
    build_ledger_evidence_update_registration,
)
from ..application.ledger.evidence_read_operation import (
    build_ledger_evidence_list_definition,
    build_ledger_evidence_list_registration,
    build_ledger_evidence_view_definition,
    build_ledger_evidence_view_registration,
)
from ..application.ledger.export_operation import build_ledger_export_definition, build_ledger_export_registration
from ..application.ledger.history_operation import (
    build_ledger_history_definition,
    build_ledger_history_registration,
)
from ..application.ledger.import_operation import (
    LedgerImportOperationPorts,
    build_ledger_import_definition,
    build_ledger_import_registration,
)
from ..application.ledger.invoice_evidence_confirm_operation import (
    build_ledger_evidence_confirm_definition,
    build_ledger_evidence_confirm_registration,
)
from ..application.ledger.invoice_evidence_extract_operation import (
    build_ledger_evidence_extract_definition,
    build_ledger_evidence_extract_registration,
)
from ..application.ledger.invoice_evidence_readiness_operation import (
    build_ledger_evidence_reader_readiness_definition,
    build_ledger_evidence_reader_readiness_registration,
)
from ..application.ledger.lifecycle_mutation_operation import (
    build_ledger_archive_definition,
    build_ledger_archive_registration,
    build_ledger_exclude_definition,
    build_ledger_exclude_registration,
    build_ledger_restore_definition,
    build_ledger_restore_registration,
    build_ledger_stash_definition,
    build_ledger_stash_registration,
)
from ..application.ledger.link_operation import build_ledger_link_definition, build_ledger_link_registration
from ..application.ledger.list_operation import build_ledger_list_definition, build_ledger_list_registration
from ..application.ledger.llm_diagnostics_operation import (
    build_ledger_llm_diagnostics_definition,
    build_ledger_llm_diagnostics_registration,
)
from ..application.ledger.llm_review_contracts import (
    LEDGER_CLASSIFY_REVIEW_DEFINITION_ID,
    LEDGER_SPLIT_REVIEW_DEFINITION_ID,
)
from ..application.ledger.llm_review_execution import LedgerLlmOperationPorts
from ..application.ledger.llm_review_operation import (
    build_ledger_llm_review_definition,
    build_ledger_llm_review_registration,
)
from ..application.ledger.merge_operation import build_ledger_merge_definition, build_ledger_merge_registration
from ..application.ledger.operator_iva_operation import (
    build_ledger_operator_iva_definition,
    build_ledger_operator_iva_registration,
)
from ..application.ledger.own_account_operation import (
    build_ledger_own_account_definition,
    build_ledger_own_account_registration,
)
from ..application.ledger.own_account_ports import OwnAccountRepositoryFactory
from ..application.ledger.participation_operation import (
    build_ledger_participation_definition,
    build_ledger_participation_registration,
)
from ..application.ledger.participation_read import TransactionParticipationIndexRepositoryFactory
from ..application.ledger.participation_rebuild_operation import (
    build_ledger_participation_rebuild_definition,
    build_ledger_participation_rebuild_registration,
)
from ..application.ledger.preflight_operation import (
    build_ledger_preflight_definition,
    build_ledger_preflight_registration,
)
from ..application.ledger.ratios_operation import (
    build_ledger_ratios_eligible_definition,
    build_ledger_ratios_eligible_registration,
    build_ledger_ratios_list_definition,
    build_ledger_ratios_list_registration,
    build_ledger_ratios_set_definition,
    build_ledger_ratios_set_registration,
    build_ledger_ratios_unset_definition,
    build_ledger_ratios_unset_registration,
    build_ledger_ratios_validate_definition,
    build_ledger_ratios_validate_registration,
)
from ..application.ledger.remove_operation import build_ledger_remove_definition, build_ledger_remove_registration
from ..application.ledger.reset_operation import build_ledger_reset_definition, build_ledger_reset_registration
from ..application.ledger.review_operation import build_ledger_review_definition, build_ledger_review_registration
from ..application.ledger.rule_operation import (
    build_ledger_rule_add_definition,
    build_ledger_rule_add_registration,
    build_ledger_rule_apply_definition,
    build_ledger_rule_apply_registration,
    build_ledger_rule_list_definition,
    build_ledger_rule_list_registration,
)
from ..application.ledger.rule_repository import LedgerClassificationRuleRepositoryFactory
from ..application.ledger.split_operation import build_ledger_split_definition, build_ledger_split_registration
from ..application.ledger.status_operation import (
    build_ledger_status_definition,
    build_ledger_status_registration,
)
from ..application.ledger.track_operation import build_ledger_track_definition, build_ledger_track_registration
from ..application.ledger.update_operation import build_ledger_update_definition, build_ledger_update_registration
from ..application.ledger.view_operation import build_ledger_view_definition, build_ledger_view_registration
from ..application.live.borrador_100_operation import (
    build_borrador_100_operation_definitions,
    build_borrador_100_operation_registrations,
)
from ..application.live.expedientes_capture_operation import (
    build_expedientes_bulk_capture_definition,
    build_expedientes_bulk_capture_registration,
    build_expedientes_single_capture_definition,
    build_expedientes_single_capture_registration,
)
from ..application.live.expedientes_read_operation import (
    build_expedientes_latest_definition,
    build_expedientes_latest_registration,
    build_expedientes_list_definition,
    build_expedientes_list_registration,
    build_expedientes_show_definition,
    build_expedientes_show_registration,
)
from ..application.live.filed_bulk_capture_operation import (
    build_filed_bulk_capture_definition,
    build_filed_bulk_capture_registration,
)
from ..application.live.filed_history_operation import (
    bind_shared_filed_history_pull,
    build_filed_history_operation_definition,
    build_filed_history_operation_registration,
)
from ..application.live.filed_read_operation import (
    build_filed_discover_definition,
    build_filed_discover_registration,
    build_filed_list_definition,
    build_filed_list_registration,
)
from ..application.live.filed_single_capture_operation import (
    build_filed_single_capture_definition,
    build_filed_single_capture_registration,
)
from ..application.live.filed_source_capture_operation import (
    build_filed_source_capture_definition,
    build_filed_source_capture_registration,
)
from ..application.live.iva_remote_state_capture_operation import (
    build_iva_remote_state_capture_definition,
    build_iva_remote_state_capture_registration,
)
from ..application.live.iva_wallet_capture_operation import (
    build_iva_wallet_capture_definition,
    build_iva_wallet_capture_registration,
)
from ..application.live.iva_wallet_history_capture_operation import (
    build_iva_wallet_history_capture_definition,
    build_iva_wallet_history_capture_registration,
)
from ..application.live.iva_wallet_history_operation import (
    build_iva_wallet_history_definition,
    build_iva_wallet_history_registration,
)
from ..application.live.justificante_capture_operation import (
    JustificanteCapturePorts,
    build_justificante_capture_definition,
    build_justificante_capture_registration,
)
from ..application.live.justificante_read_operation import (
    build_justificante_list_definition,
    build_justificante_list_registration,
    build_justificante_show_definition,
    build_justificante_show_registration,
)
from ..application.live.notification_document_capture_operation import (
    build_notification_document_capture_definition,
    build_notification_document_capture_registration,
)
from ..application.live.notification_document_read_operation import (
    build_notification_document_history_definition,
    build_notification_document_history_registration,
    build_notification_document_view_definition,
    build_notification_document_view_registration,
)
from ..application.live.notification_documents import NotificationDocumentService
from ..application.live.notification_ports import NotificationsPorts
from ..application.live.notifications_capture_operation import (
    build_notifications_capture_definition,
    build_notifications_capture_registration,
)
from ..application.live.notifications_read_operation import (
    build_notifications_latest_definition,
    build_notifications_latest_registration,
    build_notifications_list_definition,
    build_notifications_list_registration,
    build_notifications_show_definition,
    build_notifications_show_registration,
)
from ..application.live.verify import VerifySurface
from ..application.live.verify_capture_operation import (
    VerifyLiveObservation,
    build_verify_capture_definition,
    build_verify_capture_registration,
)
from ..application.live.verify_read_operation import (
    build_verify_latest_definition,
    build_verify_latest_registration,
    build_verify_list_definition,
    build_verify_list_registration,
    build_verify_view_definition,
    build_verify_view_registration,
)
from ..application.local_reader import read_local_reader_status
from ..application.local_reader_operation import (
    build_local_reader_operation_definition,
    build_local_reader_operation_registration,
)
from ..application.modelo.aggregate_operation import (
    build_modelo_aggregate_operation_definition,
    build_modelo_aggregate_operation_registration,
)
from ..application.modelo.aggregate_ports import ModeloAggregateOperationPorts, ModeloAggregateOperationPortsFactory
from ..application.modelo.amendment_action_ports import AmendmentActionPortsFactory
from ..application.modelo.amendment_context_operation import (
    build_modelo_work_amendment_context_definition,
    build_modelo_work_amendment_context_registration,
)
from ..application.modelo.audit_operation import (
    build_modelo_audit_operation_definitions,
    build_modelo_audit_operation_registrations,
)
from ..application.modelo.calculation_action_ports import CalculationActionPortsFactory
from ..application.modelo.calculation_report_verification_operation import (
    build_modelo_calculation_report_verify_definition,
    build_modelo_calculation_report_verify_registration,
)
from ..application.modelo.dependency_operation import (
    build_modelo_dependency_definition,
    build_modelo_dependency_registration,
)
from ..application.modelo.dependency_read_ports import DependencyReadPortsFactory
from ..application.modelo.edit_receipt_ports import ModeloEditReceiptRepositoryFactory
from ..application.modelo.edit_refusal_projection import ModeloEditRefusalProjectionStore
from ..application.modelo.export_ports import ModeloExportPortsFactory
from ..application.modelo.filing_action_ports import FilingActionPortsFactory
from ..application.modelo.filing_record_import_operation import (
    build_modelo_filing_record_import_definition,
    build_modelo_filing_record_import_registration,
)
from ..application.modelo.filing_record_list_operation import (
    build_modelo_filing_record_list_definition,
    build_modelo_filing_record_list_registration,
)
from ..application.modelo.filing_record_view_operation import (
    build_modelo_filing_record_view_definition,
    build_modelo_filing_record_view_registration,
)
from ..application.modelo.filing_selection_operation import (
    build_modelo_work_filing_record_definition,
    build_modelo_work_filing_record_registration,
)
from ..application.modelo.history_operation import (
    build_modelo_work_history_definition,
    build_modelo_work_history_registration,
)
from ..application.modelo.history_ports import ModeloHistoryPortsFactory
from ..application.modelo.history_timeline_operation import (
    build_modelo_history_timeline_definition,
    build_modelo_history_timeline_registration,
)
from ..application.modelo.invoice_withholding_capture_contracts import (
    ModeloInvoiceWithholdingCapturePorts,
    ModeloInvoiceWithholdingCapturePortsFactory,
)
from ..application.modelo.invoice_withholding_capture_operation import (
    build_modelo_invoice_withholding_capture_definition,
    build_modelo_invoice_withholding_capture_registration,
)
from ..application.modelo.iva_wallet_balance_operation import (
    build_modelo_iva_wallet_balance_definition,
    build_modelo_iva_wallet_balance_registration,
)
from ..application.modelo.iva_wallet_correction_operation import (
    build_modelo_iva_wallet_correction_definition,
    build_modelo_iva_wallet_correction_registration,
)
from ..application.modelo.iva_wallet_override_operation import (
    build_modelo_iva_wallet_override_definition,
    build_modelo_iva_wallet_override_registration,
)
from ..application.modelo.iva_wallet_seed_operation import (
    build_modelo_iva_wallet_seed_definition,
    build_modelo_iva_wallet_seed_registration,
)
from ..application.modelo.lifecycle_history_operation import (
    build_modelo_history_definition,
    build_modelo_history_registration,
)
from ..application.modelo.local_observation_operation import (
    build_modelo_local_observation_definition,
    build_modelo_local_observation_registration,
)
from ..application.modelo.m036_operation import (
    build_m036_operation_definitions,
    build_m036_operation_registrations,
)
from ..application.modelo.m145_communication_operation import (
    build_m145_communication_operation_definitions,
    build_m145_communication_operation_registrations,
)
from ..application.modelo.m303_attestation_operation import (
    build_modelo_work_m303_attestation_definition,
    build_modelo_work_m303_attestation_registration,
)
from ..application.modelo.m360_solicitud_operation import (
    build_modelo_360_solicitud_definition,
    build_modelo_360_solicitud_registration,
)
from ..application.modelo.maritime_preview_operation import (
    build_modelo_maritime_preview_definition,
    build_modelo_maritime_preview_registration,
)
from ..application.modelo.mcp_query_operation import (
    build_modelo_bindings_resolve_typed_definition,
    build_modelo_bindings_resolve_typed_registration,
    build_modelo_readiness_summary_definition,
    build_modelo_readiness_summary_registration,
)
from ..application.modelo.metadata_operation_access import compose_modelo_metadata_access
from ..application.modelo.metadata_read_operation import (
    build_modelo_metadata_definition,
    build_modelo_metadata_registration,
)
from ..application.modelo.modelo_spreadsheet_operation import (
    build_modelo_spreadsheet_definitions,
)
from ..application.modelo.modelo_spreadsheet_registration import (
    build_modelo_spreadsheet_registration,
)
from ..application.modelo.operation_definitions import (
    ModeloWorkVerifyProfileResolver,
    build_modelo_lifecycle_operation_definitions,
    build_modelo_lifecycle_operation_registrations,
    resolve_active_workflow_profile,
)
from ..application.modelo.participation_index_rebuild_ports import ParticipationIndexRebuildPortsFactory
from ..application.modelo.projection_operation import (
    build_modelo_compare_definition,
    build_modelo_compare_registration,
    build_modelo_project_definition,
    build_modelo_project_registration,
)
from ..application.modelo.query_read_contracts import ModeloQueryReadPortsFactory
from ..application.modelo.query_read_operation import (
    build_modelo_bindings_list_definition,
    build_modelo_bindings_list_registration,
    build_modelo_bindings_resolve_definition,
    build_modelo_bindings_resolve_registration,
    build_modelo_readiness_definition,
    build_modelo_readiness_registration,
    build_modelo_requires_definition,
    build_modelo_requires_registration,
)
from ..application.modelo.quickfile_operation import build_quickfile_definition, build_quickfile_registration
from ..application.modelo.reconciliation_import_operation import (
    build_modelo_reconciliation_import_definition,
    build_modelo_reconciliation_import_registration,
)
from ..application.modelo.reconciliation_list_operation import (
    build_modelo_reconciliation_list_definition,
    build_modelo_reconciliation_list_registration,
)
from ..application.modelo.reconciliation_pull_operation import (
    build_modelo_reconciliation_pull_definition,
    build_modelo_reconciliation_pull_registration,
)
from ..application.modelo.review_package_exchange_operation import (
    build_review_package_exchange_operation_definitions,
    build_review_package_exchange_operation_registrations,
)
from ..application.modelo.review_package_operation import (
    build_modelo_review_package_build_definition,
    build_modelo_review_package_build_registration,
)
from ..application.modelo.review_package_recipient_operations import (
    build_review_package_recipient_add_definition,
    build_review_package_recipient_add_registration,
    build_review_package_recipient_list_definition,
    build_review_package_recipient_list_registration,
    build_review_package_recipient_remove_definition,
    build_review_package_recipient_remove_registration,
)
from ..application.modelo.review_package_recipient_registry_ports import RecipientFingerprintRegistryPortsFactory
from ..application.modelo.revision_inventory_operation import (
    build_modelo_work_revisions_definition,
    build_modelo_work_revisions_registration,
)
from ..application.modelo.revision_operation_access import compose_modelo_revision_access
from ..application.modelo.revision_selection_operation import (
    build_modelo_work_revision_definition,
    build_modelo_work_revision_registration,
)
from ..application.modelo.revision_snapshot_operation import (
    build_modelo_work_revision_snapshot_definition,
    build_modelo_work_revision_snapshot_registration,
)
from ..application.modelo.taxation_comparison_operation import (
    build_modelo_taxation_comparison_definition,
    build_modelo_taxation_comparison_registration,
)
from ..application.modelo.verification_report_read_operation import (
    build_modelo_verification_report_list_definition,
    build_modelo_verification_report_list_registration,
    build_modelo_verification_report_view_definition,
    build_modelo_verification_report_view_registration,
)
from ..application.modelo.verification_repository_ports import VerificationRepositoryBundleFactory
from ..application.modelo.wizard_attempt_operation import (
    build_modelo_work_wizard_attempt_definition,
    build_modelo_work_wizard_attempt_registration,
)
from ..application.modelo.wizard_context_operation import (
    build_modelo_work_wizard_context_definition,
    build_modelo_work_wizard_context_registration,
)
from ..application.modelo.work_create_operation import (
    build_modelo_work_create_definition,
    build_modelo_work_create_registration,
)
from ..application.modelo.work_inventory_operation import (
    build_modelo_work_list_definition,
    build_modelo_work_list_registration,
)
from ..application.modelo.work_lifecycle_ports import ActiveWorkLifecyclePortsFactory
from ..application.modelo.work_review_operation import (
    build_modelo_work_review_definition,
    build_modelo_work_review_registration,
)
from ..application.modelo.workbench_operations import (
    build_modelo_workbench_operation_definitions,
    build_modelo_workbench_operation_registrations,
    compose_modelo_workbench_access,
)
from ..application.modelo.workbench_read import ModeloWorkbenchReadPorts, ModeloWorkbenchReadPortsFactory
from ..application.operations.authorization import OperationExecutionAuthority
from ..application.operations.composition import (
    OperationComposedServices,
    compose_operation_services,
)
from ..application.operations.operation_definition import OperationDefinition
from ..application.operations.registry import OperationPublicContractSetV1, OperationRegistry
from ..application.operations.registry_schema_validation import operation_schema_compilation_scope
from ..application.overview.pipeline_operation import (
    build_overview_pipeline_definition,
    build_overview_pipeline_registration,
)
from ..application.overview.pipeline_read_ports import PipelineReadPortsFactory
from ..application.overview.read_operation import (
    build_overview_read_definition,
    build_overview_read_registration,
)
from ..application.overview.read_ports import OverviewReadPortsFactory
from ..application.overview.read_request import OverviewReadKind
from ..application.prorrata_register.registered_operations import (
    build_prorrata_declare_sector_definition,
    build_prorrata_elect_especial_definition,
    build_prorrata_elect_general_definition,
    build_prorrata_list_definition,
    build_prorrata_list_registration,
    build_prorrata_mutation_registration,
    build_prorrata_revoke_especial_definition,
    build_prorrata_seed_definition,
    build_prorrata_seed_sector_definition,
    build_prorrata_settle_sector_definition,
)
from ..application.review.read_contracts import (
    ReviewReadOperationPorts,
)
from ..application.review.read_registration import (
    build_review_read_definitions,
    build_review_read_registrations,
)
from ..application.storage.calc_sheets.export_service import export_modelo_to_sheets
from ..application.storage.calc_sheets.records import SheetExportPlan, TabName
from ..application.user_profile.archive_operation import (
    build_profile_archive_operation_definitions,
    build_profile_archive_operation_registrations,
)
from ..application.user_profile.automation_operations import (
    AutomationAdministrationFactory,
    AutomationInventoryReader,
    build_automation_operation_definitions,
    build_automation_operation_registrations,
)
from ..application.user_profile.censal_file_import_operation import (
    build_censal_file_import_operation_definition,
    build_censal_file_import_operation_registration,
)
from ..application.user_profile.censal_operation import (
    build_censal_operation_definition,
    build_censal_operation_registration,
)
from ..application.user_profile.censal_prepare_operation import (
    build_censal_prepare_operation_definition,
    build_censal_prepare_operation_registration,
)
from ..application.user_profile.censal_preview_operation import (
    build_censal_preview_operation_definition,
    build_censal_preview_operation_registration,
)
from ..application.user_profile.google_configuration_operation import (
    build_google_configuration_definitions,
    build_google_configuration_registration,
)
from ..application.user_profile.history_operation import (
    ProfileHistoryReadPorts,
    build_profile_history_definition,
    build_profile_history_registration,
)
from ..application.user_profile.operations import (
    build_user_profile_operation_definitions,
    build_user_profile_operation_registrations,
)
from ..application.user_profile.recovery_status_operation import (
    build_recovery_status_definition,
    build_recovery_status_registration,
)
from ..application.workbench_generation_operation import (
    WorkbenchGenerationReader,
    build_workbench_generation_operation_definition,
    build_workbench_generation_operation_registration,
)
from ..application.workflow.resume_operation import build_workflow_resume_definition, build_workflow_resume_registration
from ..application.workflow.run_read_operation import (
    build_workflow_run_list_definition,
    build_workflow_run_list_registration,
    build_workflow_run_read_definition,
    build_workflow_run_read_registration,
)
from ..application.workflow.run_read_ports import WorkflowRunReadPortsFactory
from ..application.workstation_check_operation import (
    build_workstation_check_definition,
    build_workstation_check_registration,
)
from ..core.access_gate.gate import AeatAccessGate
from ..core.config import Settings, load_settings
from ..core.errors.hierarchy import InternalInvariantError
from ..core.identity.tax_id import tax_id_identity_token
from ..core.identity_check_verdict import IdentityCheckVerdictValue
from ..core.paths import effective_storage_root
from ..core.time.clock import now
from ..domain.currency.service import CurrencyNormalizationService
from .actividad_asset_composition import build_activity_asset_operation_ports
from .adapter_composition import (
    build_active_work_lifecycle_ports,
    build_amendment_action_ports,
    build_attachment_store,
    build_bienes_inversion_repository,
    build_calculation_action_ports,
    build_censal_fetch_port,
    build_draft_review_ports,
    build_expedientes_ports,
    build_filing_action_ports,
    build_inventory_service_ports,
    build_ledger_evidence_ports,
    build_modelo_edit_receipt_repository,
    build_modelo_export_ports,
    build_modelo_history_ports,
    build_modelo_iva_wallet_seed_ports,
    build_operator_probe_ports,
    build_participation_index_rebuild_ports,
    build_percepcion_observation_ports,
    build_prorrata_register_repository,
    build_retencion_observation_ports,
    build_verification_repository_bundle,
    build_withholding_observation_service,
)
from .auth_apoderado_composition import build_apoderado_operation_ports, build_auth_diagnostic_report_ports
from .auth_read_composition import compose_auth_read_ports
from .calculation_report_verification_operation_composition import build_modelo_calculation_report_verification_ports
from .diagnostics_operation_composition import (
    build_diagnostics_read_ports,
    build_diagnostics_telemetry_flush_ports,
)
from .evidence_followup_operation_composition import build_ledger_evidence_followup_operation_ports
from .google_configuration_operation_composition import build_google_configuration_operation_ports
from .invoice_evidence_operation_composition import build_invoice_evidence_operation_ports
from .invoice_inspection_composition import build_invoice_inspection_read_ports
from .invoice_intake_operation_composition import build_invoice_intake_ports
from .justificante_composition import (
    build_justificante_authenticity_verifier,
    build_justificante_capture_service,
    build_justificante_live_read_port,
    build_justificante_registration_ports,
    load_reconciliation_filed_observation,
)
from .ledger_action_composition import compose_ledger_action_ports, compose_ledger_import_ports
from .ledger_evidence_ingestion_operation_composition import build_ledger_evidence_ingestion_operation_ports
from .ledger_export_link_operation_composition import build_ledger_export_link_operation_ports
from .ledger_llm_composition import compose_ledger_llm
from .ledger_llm_diagnostics_composition import build_ledger_llm_diagnostics_operation_ports
from .live_borrador_operation_composition import build_borrador_100_operation_ports
from .live_state_composition import (
    compose_live_state,
    compose_notification_document_service,
    compose_notifications_ports,
    preflight_filed_history_provider,
    pull_filed_history_with_shared_composition,
)
from .m036_operation_composition import build_m036_operation_ports
from .modelo_audit_operation_composition import build_modelo_audit_operation_ports
from .modelo_dependency_composition import build_dependency_read_ports
from .modelo_maritime_operation_composition import build_modelo_maritime_preview_ports
from .modelo_query_read_operation_composition import build_modelo_query_read_ports
from .modelo_spreadsheet_operation_composition import build_modelo_spreadsheet_operation_ports
from .overview_pipeline_composition import build_pipeline_read_ports
from .overview_read_composition import build_overview_read_ports
from .profile_archive_operation_composition import build_profile_archive_operation_ports
from .quickfile_operation_composition import build_quickfile_operation_ports
from .review_package_exchange_operation_composition import build_review_package_exchange_operation_ports
from .workflow_run_composition import build_workflow_run_read_ports
from .workstation_check_operation_composition import build_workstation_check_operation_ports

_LEASE_DURATION = timedelta(minutes=10)
_EXECUTION_TIMEOUT = timedelta(hours=1)
_CLEANUP_TIMEOUT = timedelta(minutes=2)


def _build_profile_history_read_ports(
    *, bucket_id: str, operation: PinnedAuthorityOperation
) -> ProfileHistoryReadPorts:
    """Bind canonical event history to the worker's exact profile and authority pin."""
    return ProfileHistoryReadPorts(
        bucket_id=bucket_id,
        operation=operation,
        event_repository=build_bucket_event_history_repository(bucket_id=bucket_id),
    )


def _build_modelo_invoice_withholding_capture_ports(*, profile_id: str) -> ModeloInvoiceWithholdingCapturePorts:
    """Bind canonical withholding services to the selected encrypted profile."""
    return ModeloInvoiceWithholdingCapturePorts(
        profile_id=profile_id,
        invoice_catalogue_repository=InvoiceCatalogueRepository(bucket_id=profile_id),
        retencion_observation_repository=build_retencion_observation_ports(bucket_id=profile_id).repository,
        withholding_observation_service=build_withholding_observation_service(bucket_id=profile_id),
    )


def _build_modelo_workbench_read_ports(bucket_id: str, operation: PinnedAuthorityOperation) -> ModeloWorkbenchReadPorts:
    """Bind the repositories one declaration's workbench reads from to the worker's profile."""
    from ..adapters.persistence.storage.runtime_repository import secure_object_repository_for_bucket
    from .adapter_composition import build_borrador_100_snapshot_repository
    from .calculation_revision_composition import bind_calculation_revision_persistence_from_profile

    objects = secure_object_repository_for_bucket(bucket_id)
    calculation_binding = bind_calculation_revision_persistence_from_profile(
        bucket_id=bucket_id,
        objects=objects,
        operation=operation,
    )
    ports = build_calculation_action_ports(bucket_id=bucket_id, operation=operation, objects=objects)
    return ModeloWorkbenchReadPorts(
        work_units=ports.work_unit_repository,
        calculations=ports.calculation_repository,
        verifications=calculation_binding.verification_repository(),
        borrador_snapshots=build_borrador_100_snapshot_repository(bucket_id=bucket_id),
        holiday_territory=partial(_profile_holiday_territory, bucket_id, operation),
        bucket_events=ports.bucket_event_repository,
    )


def _profile_holiday_territory(bucket_id: str, operation: PinnedAuthorityOperation) -> CalendarCCAA | None:
    """Read the profile's holiday territory, or ``None`` while the profile cannot say.

    An absent or incomplete profile leaves the deadline on the national
    holidays, which the form discloses, rather than keeping the workbench shut.
    """
    from ..application.modelo.action_errors import ModeloProfileReadinessError
    from ..application.modelo.m303_regimen_simplificado_scope import taxpayer_profile_for_work
    from ..application.modelo.profile_readiness_gate import load_modelo_work_profile

    profile = load_modelo_work_profile(bucket_id=bucket_id, profile_decode_context=operation.profile_decode_context())
    try:
        return taxpayer_profile_for_work(profile).holiday_territory
    except ModeloProfileReadinessError:
        return None


def _build_modelo_aggregate_operation_ports(*, profile_id: str) -> ModeloAggregateOperationPorts:
    """Bind the existing aggregate and ledger-payment services to one profile."""
    return ModeloAggregateOperationPorts(
        profile_id=profile_id,
        transaction_catalogue_repository=TransactionCatalogueRepository(bucket_id=profile_id),
        retencion_observation_repository=build_retencion_observation_ports(bucket_id=profile_id).repository,
        percepcion_observation_repository=build_percepcion_observation_ports(bucket_id=profile_id).repository,
        withholding_observation_service=build_withholding_observation_service(bucket_id=profile_id),
    )


if TYPE_CHECKING:
    from ..domain.attachments.protocols import AttachmentStoreProtocol
    from ..domain.calculations.registry.authority import PinnedAuthorityOperation
    from ..domain.deadlines.festivos import CalendarCCAA


def _google_sheets_export_prepare_port(
    *,
    settings: Settings,
):
    """Compose the sole Google transport and mandatory sync-run provenance handoff."""

    def prepare(profile_id: str) -> GoogleSheetsExportPreparedPort:
        root_folder_id = resolve_drive_root_folder_id(profile=profile_id, settings=settings)
        if not root_folder_id:
            raise GoogleSheetsExportRootFolderRequiredError("Google Drive root folder is required")
        try:
            credentials = build_google_credentials(profile=profile_id)
        except GoogleAuthClientMetadataUnavailableError as exc:
            raise GoogleSheetsExportClientMissingError(str(exc)) from exc
        except OutboundStorageValidationError as exc:
            if exc.translated_message == "adapters.outbound.storage._factory.errors.google_token_missing":
                raise GoogleSheetsExportTokenMissingError(str(exc)) from exc
            raise
        except OutboundStorageError as exc:
            if exc.translated_message == "adapters.outbound.storage._factory.errors.google_auth_import_failed":
                raise GoogleSheetsExportAuthDependencyError(str(exc)) from exc
            raise

        class PreparedGoogleSheetsExport:
            def execute(self, plan: SheetExportPlan, dry_run: bool) -> GoogleSheetsExportRemoteResult:
                if dry_run:
                    preview = preview_export_plan(plan, credentials=credentials, root_folder_id=root_folder_id)
                    return GoogleSheetsExportRemoteResult(
                        dry_run=True,
                        root_folder_id=root_folder_id,
                        spreadsheet_exists=preview.spreadsheet_exists,
                        folder_id=preview.folder_id,
                        spreadsheet_id=preview.spreadsheet_id,
                        spreadsheet_url=preview.spreadsheet_url,
                        value_cells_written=len(plan.value_cells),
                        formula_cells_written=len(plan.formula_cells),
                        protected_ranges_written=len(plan.protected_ranges),
                        tab_count=len(TabName),
                        ranges_to_clear=preview.ranges_to_clear,
                        value_cells_changed=preview.value_cells_changed,
                        value_cells_unchanged=preview.value_cells_unchanged,
                        formula_cells_to_write=preview.formula_cells_to_write,
                    )
                applied = export_modelo_to_sheets(
                    plan,
                    credentials=credentials,
                    root_folder_id=root_folder_id,
                    sync_run_repository=SyncRunRecordRepository(),
                    apply_export_plan=apply_export_plan,
                )
                return GoogleSheetsExportRemoteResult(
                    dry_run=False,
                    root_folder_id=root_folder_id,
                    folder_id=applied.folder_id,
                    spreadsheet_id=applied.spreadsheet_id,
                    spreadsheet_url=applied.spreadsheet_url,
                    value_cells_written=applied.value_cells_written,
                    formula_cells_written=applied.formula_cells_written,
                    protected_ranges_written=applied.protected_ranges_written,
                    tab_count=applied.tab_count,
                )

        return PreparedGoogleSheetsExport()

    return prepare


def build_auth_operation_ports(operator_scope_ports: OperatorScopePorts | None = None) -> AuthOperationPorts:
    """Compose the outer capabilities the registered auth executors run against."""
    return AuthOperationPorts(
        certificate_secret_backend_factory=build_certificate_secret_backend,
        browser_session_factory=default_browser_session_factory,
        operator_probe_ports=build_operator_probe_ports(),
        operator_scope_ports=operator_scope_ports or build_operator_scope_ports(),
    )


@operation_schema_compilation_scope()
def build_production_operation_registry(
    *,
    settings: Settings | None = None,
    auth_definitions: tuple[OperationDefinition, ...] | None = None,
    censal_definition: OperationDefinition | None = None,
    verify_nif_iva_definition: OperationDefinition | None = None,
    verify_tgvi_definition: OperationDefinition | None = None,
    google_export_definition: OperationDefinition | None = None,
    evidence_followup_ports: LedgerEvidenceFollowupOperationPorts | None = None,
    modelo_query_read_ports_factory: ModeloQueryReadPortsFactory = build_modelo_query_read_ports,
    recipient_registry_ports_factory: RecipientFingerprintRegistryPortsFactory = (
        build_recipient_fingerprint_registry_ports
    ),
    recipient_event_repository_factory: BucketEventHistoryRepositoryFactory = build_bucket_event_history_repository,
    modelo_export_ports_factory: ModeloExportPortsFactory = build_modelo_export_ports,
    calculation_action_ports_factory: CalculationActionPortsFactory = build_calculation_action_ports,
    attachment_store_factory: Callable[[str], AttachmentStoreProtocol] = build_attachment_store,
    amendment_action_ports_factory: AmendmentActionPortsFactory = build_amendment_action_ports,
    filing_action_ports_factory: FilingActionPortsFactory = build_filing_action_ports,
    work_lifecycle_ports_factory: ActiveWorkLifecyclePortsFactory = build_active_work_lifecycle_ports,
    modelo_history_ports_factory: ModeloHistoryPortsFactory = build_modelo_history_ports,
    workflow_run_read_ports_factory: WorkflowRunReadPortsFactory = build_workflow_run_read_ports,
    dependency_read_ports_factory: DependencyReadPortsFactory = build_dependency_read_ports,
    pipeline_read_ports_factory: PipelineReadPortsFactory = build_pipeline_read_ports,
    overview_read_ports_factory: OverviewReadPortsFactory = build_overview_read_ports,
    invoice_inspection_read_ports_factory: InvoiceInspectionReadPortsFactory = build_invoice_inspection_read_ports,
    invoice_creation_ports_factory: CatalogueCreationPortsFactory = build_catalogue_creation_ports,
    modelo_aggregate_operation_ports_factory: ModeloAggregateOperationPortsFactory = (
        _build_modelo_aggregate_operation_ports
    ),
    modelo_invoice_withholding_capture_ports_factory: ModeloInvoiceWithholdingCapturePortsFactory = (
        _build_modelo_invoice_withholding_capture_ports
    ),
    invoice_lifecycle_ports_factory: CatalogueLifecyclePortsFactory = build_catalogue_lifecycle_ports,
    modelo_edit_receipt_repository_factory: ModeloEditReceiptRepositoryFactory = build_modelo_edit_receipt_repository,
    verification_repository_bundle_factory: VerificationRepositoryBundleFactory = build_verification_repository_bundle,
    ledger_action_ports_factory: LedgerActionPortsFactory = compose_ledger_action_ports,
    ledger_rule_repository_factory: LedgerClassificationRuleRepositoryFactory = LedgerClassificationRuleRepository,
    counterparty_repository_factory: CounterpartyEstablishmentRepositoryFactory | None = None,
    own_account_repository_factory: OwnAccountRepositoryFactory | None = None,
    ledger_participation_repository_factory: TransactionParticipationIndexRepositoryFactory = (
        TransactionParticipationIndexRepository
    ),
    participation_rebuild_ports_factory: ParticipationIndexRebuildPortsFactory = (
        build_participation_index_rebuild_ports
    ),
    operator_scope_ports: OperatorScopePorts | None = None,
    automation_administration_factory: AutomationAdministrationFactory | None = None,
    automation_inventory_reader: AutomationInventoryReader | None = None,
    workbench_generation_reader: WorkbenchGenerationReader | None = None,
    profile_rotation_finalizer: ProfileRotationFinalizer | None = None,
    modelo_profile_resolver: ModeloWorkVerifyProfileResolver = resolve_active_workflow_profile,
    modelo_workbench_read_ports_factory: ModeloWorkbenchReadPortsFactory = _build_modelo_workbench_read_ports,
) -> OperationRegistry:
    """Build the sole immutable production inventory from the owner facades."""
    resolved_settings = _production_registry_settings(settings)
    # A refused Apply's named prerequisite stays in this registry's worker
    # memory until the workbench reads it once; the journal never holds it.
    edit_prerequisites = ModeloEditRefusalProjectionStore()
    # Edit admission is judged against the contracts of the very registry
    # being composed, which exist only once it is built.
    composed_contracts: list[OperationPublicContractSetV1] = []

    def registry_contracts() -> OperationPublicContractSetV1:
        if not composed_contracts:
            raise InternalInvariantError("the operation registry's contracts are read before it is composed")
        return composed_contracts[0]

    review_read_definitions = build_review_read_definitions(
        ReviewReadOperationPorts(settings=resolved_settings, draft_review_ports_factory=build_draft_review_ports)
    )
    evidence_followup_definitions = build_ledger_evidence_followup_definitions(
        _production_registry_evidence_followup_ports(evidence_followup_ports, resolved_settings)
    )
    modelo_bindings_list_definition = build_modelo_bindings_list_definition()
    modelo_bindings_resolve_definition = build_modelo_bindings_resolve_definition()
    modelo_bindings_resolve_typed_definition = build_modelo_bindings_resolve_typed_definition()
    modelo_requires_definition = build_modelo_requires_definition()
    modelo_readiness_definition = build_modelo_readiness_definition(modelo_query_read_ports_factory)
    modelo_readiness_summary_definition = build_modelo_readiness_summary_definition(modelo_query_read_ports_factory)
    modelo_report_verify_definition = build_modelo_calculation_report_verify_definition(
        build_modelo_calculation_report_verification_ports
    )
    recipient_add_definition = build_review_package_recipient_add_definition(
        recipient_registry_ports_factory, recipient_event_repository_factory
    )
    recipient_list_definition = build_review_package_recipient_list_definition(recipient_registry_ports_factory)
    recipient_remove_definition = build_review_package_recipient_remove_definition(
        recipient_registry_ports_factory, recipient_event_repository_factory
    )
    resolved_operator_scope_ports = _production_registry_operator_scope(operator_scope_ports)
    resolved_auth_ports = build_auth_operation_ports(resolved_operator_scope_ports)
    resolved_auth_definitions = (
        auth_definitions
        if auth_definitions is not None
        else build_auth_operation_definitions(
            ports=resolved_auth_ports,
            finalize_rotation=profile_rotation_finalizer,
        )
    )
    profile_definitions = build_user_profile_operation_definitions()
    profile_history_definition = build_profile_history_definition(_build_profile_history_read_ports)
    certificate_source_ports = CertificateSourceOperationPorts(
        operator_scope_ports=resolved_operator_scope_ports,
        operator_probe_ports=resolved_auth_ports.operator_probe_ports,
        certificate_secret_backend_factory=resolved_auth_ports.certificate_secret_backend_factory,
    )
    certificate_secret_definitions = build_certificate_secret_operation_definitions(
        CertificateSecretOperationPorts(
            operator_scope_ports=resolved_operator_scope_ports,
            certificate_secret_backend_factory=resolved_auth_ports.certificate_secret_backend_factory,
        )
    )
    certificate_source_register_definition = build_certificate_source_register_definition(certificate_source_ports)
    certificate_source_list_definition = build_certificate_source_list_definition(certificate_source_ports)
    certificate_source_select_definition = build_certificate_source_select_definition(certificate_source_ports)
    certificate_source_remove_definition = build_certificate_source_remove_definition(certificate_source_ports)
    certificate_source_check_definition = build_certificate_source_check_definition(certificate_source_ports)
    ledger_ratios_list_definition = build_ledger_ratios_list_definition()
    ledger_ratios_set_definition = build_ledger_ratios_set_definition()
    ledger_ratios_unset_definition = build_ledger_ratios_unset_definition()
    ledger_ratios_eligible_definition = build_ledger_ratios_eligible_definition()
    ledger_ratios_validate_definition = build_ledger_ratios_validate_definition()
    activity_asset_create_definition = build_activity_asset_create_definition(build_activity_asset_operation_ports)
    activity_asset_inspect_definition = build_activity_asset_inspect_definition(build_activity_asset_operation_ports)
    activity_asset_correct_definition = build_activity_asset_correct_definition(build_activity_asset_operation_ports)
    activity_asset_forecast_definition = build_activity_asset_forecast_definition(build_activity_asset_operation_ports)
    activity_asset_claim_definition = build_activity_asset_claim_definition(build_activity_asset_operation_ports)
    activity_asset_filing_handoff_definition = build_activity_asset_filing_handoff_definition(
        build_activity_asset_operation_ports
    )
    inventory_list_definition = build_inventory_list_definition(build_inventory_service_ports)
    bienes_inversion_list_definition = build_bienes_inversion_list_definition(build_bienes_inversion_repository)
    bienes_inversion_declare_definition = build_bienes_inversion_declare_definition(build_bienes_inversion_repository)
    prorrata_list_definition = build_prorrata_list_definition(build_prorrata_register_repository)
    prorrata_mutation_definitions = (
        build_prorrata_declare_sector_definition(build_prorrata_register_repository),
        build_prorrata_elect_especial_definition(build_prorrata_register_repository),
        build_prorrata_elect_general_definition(build_prorrata_register_repository),
        build_prorrata_revoke_especial_definition(build_prorrata_register_repository),
        build_prorrata_seed_definition(build_prorrata_register_repository, calculation_action_ports_factory),
        build_prorrata_seed_sector_definition(build_prorrata_register_repository),
        build_prorrata_settle_sector_definition(build_prorrata_register_repository),
    )
    inventory_create_definition = build_inventory_create_definition(build_inventory_service_ports)
    inventory_movement_add_definition = build_inventory_movement_add_definition(build_inventory_service_ports)
    inventory_valuation_preview_definition = build_inventory_valuation_preview_definition(build_inventory_service_ports)
    inventory_closing_authority_record_definition = build_inventory_closing_authority_record_definition(
        build_inventory_service_ports
    )
    auth_read_definition = build_auth_read_definition(compose_auth_read_ports)
    apoderado_definitions = build_apoderado_operation_definitions(build_apoderado_operation_ports)
    auth_diagnostic_report_definition = build_auth_diagnostic_report_definition(build_auth_diagnostic_report_ports)
    diagnostics_read_definition = build_diagnostics_read_definition(build_diagnostics_read_ports)
    workstation_check_definition = build_workstation_check_definition(build_workstation_check_operation_ports)
    google_configuration_definitions = build_google_configuration_definitions(
        build_google_configuration_operation_ports
    )
    quickfile_definition = build_quickfile_definition(build_quickfile_operation_ports)
    evidence_ingestion_definitions = build_ledger_evidence_ingestion_definitions(
        build_ledger_evidence_ingestion_operation_ports
    )
    diagnostics_telemetry_flush_definition = build_diagnostics_telemetry_flush_definition(
        build_diagnostics_telemetry_flush_ports
    )
    ledger_llm_diagnostics_definition = build_ledger_llm_diagnostics_definition(
        build_ledger_llm_diagnostics_operation_ports
    )
    borrador_100_definitions = build_borrador_100_operation_definitions(build_borrador_100_operation_ports)
    m036_definitions = build_m036_operation_definitions(build_m036_operation_ports)
    modelo_audit_definitions = build_modelo_audit_operation_definitions(build_modelo_audit_operation_ports)
    modelo_maritime_preview_definition = build_modelo_maritime_preview_definition(build_modelo_maritime_preview_ports)
    modelo_spreadsheet_definitions = build_modelo_spreadsheet_definitions(build_modelo_spreadsheet_operation_ports)
    review_package_exchange_definitions = build_review_package_exchange_operation_definitions(
        build_review_package_exchange_operation_ports
    )
    profile_archive_definitions = build_profile_archive_operation_definitions(build_profile_archive_operation_ports)
    recovery_status_definition = build_recovery_status_definition()
    automation_definitions = build_automation_operation_definitions(
        automation_administration_factory, inventory_reader=automation_inventory_reader
    )
    m145_communication_definitions = build_m145_communication_operation_definitions(
        records_ports_factory=build_m145_communication_records_ports,
        renderer_factory=RegistryFixedWidthRecordRenderer,
    )
    modelo_definitions = build_modelo_lifecycle_operation_definitions(
        profile_resolver=modelo_profile_resolver,
        certificate_secret_backend_factory=build_certificate_secret_backend,
        operator_scope_ports=resolved_operator_scope_ports,
        export_ports_factory=modelo_export_ports_factory,
        # The calculation report's provenance key is derived from the profile's
        # existing review-package signing key, so the export enrolment is bound
        # to the adapter that already owns that key's custody.
        signing_keypair_capability_factory=build_review_package_signing_keypair_capability,
        # The summary PDF writer is the same adapter the command line hands the
        # report service, so both surfaces draw one revision's summary with one
        # writer. It imports ReportLab only when it draws.
        calculation_summary_pdf_writer=write_calculation_summary_pdf,
        calculation_action_ports_factory=calculation_action_ports_factory,
        attachment_store_factory=attachment_store_factory,
        amendment_action_ports_factory=amendment_action_ports_factory,
        filing_action_ports_factory=filing_action_ports_factory,
        work_lifecycle_ports_factory=work_lifecycle_ports_factory,
        receipt_repository_factory=modelo_edit_receipt_repository_factory,
        verification_repository_bundle_factory=verification_repository_bundle_factory,
        edit_prerequisite_observer=edit_prerequisites.retain,
    )
    workbench_definitions = build_modelo_workbench_operation_definitions(
        ports_factory=modelo_workbench_read_ports_factory,
        contracts=registry_contracts,
        prerequisites=edit_prerequisites,
    )
    resolved_google_export_definition = _production_registry_google_export(google_export_definition, resolved_settings)
    filed_history_definition = build_filed_history_operation_definition(
        sync_run_repository_factory=SyncRunRecordRepository,
        composition_factory=compose_live_state,
        browser_resources_factory=BrowserRuntimeResourceScope,
        pull=bind_shared_filed_history_pull(pull_filed_history_with_shared_composition),
        provider_preflight=preflight_filed_history_provider,
    )
    filed_single_definition = build_filed_single_capture_definition(
        compose_live_state, BrowserRuntimeResourceScope, preflight_filed_history_provider
    )
    filed_bulk_definition = build_filed_bulk_capture_definition(
        compose_live_state, BrowserRuntimeResourceScope, preflight_filed_history_provider, SyncRunRecordRepository
    )
    filed_source_definition = build_filed_source_capture_definition(
        compose_live_state, BrowserRuntimeResourceScope, preflight_filed_history_provider
    )
    filed_list_definition = build_filed_list_definition(
        compose_live_state, BrowserRuntimeResourceScope, preflight_filed_history_provider
    )
    filed_discover_definition = build_filed_discover_definition(
        compose_live_state, BrowserRuntimeResourceScope, preflight_filed_history_provider
    )
    iva_wallet_history_definition = build_iva_wallet_history_definition(
        lambda operation: compose_live_state(operation=operation).iva_remote_state_port
    )
    iva_wallet_history_capture_definition = build_iva_wallet_history_capture_definition(
        compose_live_state, BrowserRuntimeResourceScope, preflight_filed_history_provider
    )
    iva_wallet_capture_definition = build_iva_wallet_capture_definition(
        compose_live_state, BrowserRuntimeResourceScope, preflight_filed_history_provider
    )
    iva_remote_state_capture_definition = build_iva_remote_state_capture_definition(
        compose_live_state, BrowserRuntimeResourceScope, preflight_filed_history_provider
    )

    def notification_ports_factory() -> NotificationsPorts:
        return compose_notifications_ports(settings=resolved_settings)

    notifications_capture_definition = build_notifications_capture_definition(
        compose_live_state, BrowserRuntimeResourceScope, preflight_filed_history_provider
    )

    def notification_document_service_factory() -> NotificationDocumentService:
        return compose_notification_document_service(settings=resolved_settings)

    notification_document_capture_definition = build_notification_document_capture_definition(
        compose_live_state,
        notification_document_service_factory,
        BrowserRuntimeResourceScope,
        preflight_filed_history_provider,
    )
    notification_document_view_definition = build_notification_document_view_definition(
        notification_document_service_factory
    )
    notification_document_history_definition = build_notification_document_history_definition(
        notification_document_service_factory
    )
    notifications_list_definition = build_notifications_list_definition(notification_ports_factory)
    notifications_show_definition = build_notifications_show_definition(notification_ports_factory)
    notifications_latest_definition = build_notifications_latest_definition(notification_ports_factory)
    expedientes_list_definition = build_expedientes_list_definition(build_expedientes_ports)
    expedientes_show_definition = build_expedientes_show_definition(build_expedientes_ports)
    expedientes_latest_definition = build_expedientes_latest_definition(build_expedientes_ports)
    expedientes_single_capture_definition = build_expedientes_single_capture_definition(
        build_expedientes_ports,
        build_certificate_secret_backend,
        default_browser_session_factory,
        resolved_operator_scope_ports,
        BrowserRuntimeResourceScope,
        preflight_filed_history_provider,
    )
    expedientes_bulk_capture_definition = build_expedientes_bulk_capture_definition(
        build_expedientes_ports,
        build_certificate_secret_backend,
        default_browser_session_factory,
        resolved_operator_scope_ports,
        BrowserRuntimeResourceScope,
        preflight_filed_history_provider,
    )

    async def acquire_verify_observation(
        surface: VerifySurface,
        nif: str,
        expected: IdentityCheckVerdictValue | None,
        operation: PinnedAuthorityOperation,
    ) -> VerifyLiveObservation:
        return await _acquire_registry_verify_observation(
            surface, nif, expected, operation, resolved_settings=resolved_settings
        )

    def verify_live_preflight(profile_id: UUID, operation: PinnedAuthorityOperation) -> None:
        del profile_id, operation
        AeatAccessGate(resolved_settings).require_live_read()

    def verify_persistence_factory(bucket_id: str) -> VerifyObservationRepository:
        return VerifyObservationRepository(bucket_id=bucket_id, settings=resolved_settings)

    verify_nif_iva_capture_definition = verify_nif_iva_definition or build_verify_capture_definition(
        VerifySurface.NIF_IVA,
        persistence_factory=verify_persistence_factory,
        acquire=acquire_verify_observation,
        browser_resources_factory=BrowserRuntimeResourceScope,
        provider_preflight=verify_live_preflight,
    )
    verify_tgvi_capture_definition = verify_tgvi_definition or build_verify_capture_definition(
        VerifySurface.TGVI,
        persistence_factory=verify_persistence_factory,
        acquire=acquire_verify_observation,
        browser_resources_factory=BrowserRuntimeResourceScope,
        provider_preflight=verify_live_preflight,
    )
    verify_list_definition = build_verify_list_definition(verify_persistence_factory)
    verify_view_definition = build_verify_view_definition(verify_persistence_factory)
    verify_latest_definition = build_verify_latest_definition(verify_persistence_factory)

    def justificante_capture_ports(bucket_id: str, operation: PinnedAuthorityOperation) -> JustificanteCapturePorts:
        return JustificanteCapturePorts(
            service=build_justificante_capture_service(bucket_id),
            read_port=build_justificante_live_read_port(
                build_certificate_secret_backend, resolved_operator_scope_ports, operation
            ),
            registration_ports=build_justificante_registration_ports(operation),
            verifier=build_justificante_authenticity_verifier(),
        )

    justificante_capture_definition = build_justificante_capture_definition(
        justificante_capture_ports, BrowserRuntimeResourceScope, preflight_filed_history_provider
    )
    justificante_list_definition = build_justificante_list_definition(build_justificante_capture_service)
    justificante_show_definition = build_justificante_show_definition(build_justificante_capture_service)
    local_reader_definition = build_local_reader_operation_definition(
        spawn=spawn_runtime_server,
        run_installer=run_runtime_installer,
        text_probe=probe_text_extraction_fitness,
    )
    resolved_censal_definition = _production_registry_censal(censal_definition, resolved_operator_scope_ports)
    from .censal_readback_composition import read_stored_censal_observation

    censal_prepare_definition = build_censal_prepare_operation_definition(read_stored_censal_observation)
    censal_file_import_definition = build_censal_file_import_operation_definition()
    censal_preview_definition = build_censal_preview_operation_definition(
        certificate_secret_backend_factory=build_certificate_secret_backend,
        browser_session_factory=default_browser_session_factory,
        operator_scope_ports=resolved_operator_scope_ports,
        censal_fetch_port=build_censal_fetch_port(),
        browser_resources_factory=BrowserRuntimeResourceScope,
        provider_preflight=preflight_filed_history_provider,
    )
    workbench_definition = build_workbench_generation_operation_definition(workbench_generation_reader)
    metadata_definition = build_modelo_metadata_definition(work_lifecycle_ports_factory)
    history_definition = build_modelo_work_history_definition(modelo_history_ports_factory)
    lifecycle_history_definition = build_modelo_history_definition(modelo_history_ports_factory)
    history_timeline_definition = build_modelo_history_timeline_definition(modelo_history_ports_factory)
    projection_migration = GuardedCalculationRevisionMigration()
    project_definition = build_modelo_project_definition(
        factory=calculation_action_ports_factory, migration=projection_migration
    )
    compare_definition = build_modelo_compare_definition(
        factory=calculation_action_ports_factory, migration=projection_migration
    )
    reconciliation_import_definition = build_modelo_reconciliation_import_definition()
    reconciliation_pull_definition = build_modelo_reconciliation_pull_definition(
        build_justificante_capture_service, load_reconciliation_filed_observation
    )
    reconciliation_list_definition = build_modelo_reconciliation_list_definition()
    work_list_definition = build_modelo_work_list_definition(work_lifecycle_ports_factory)
    work_create_definition = build_modelo_work_create_definition(work_lifecycle_ports_factory)
    work_review_definition = build_modelo_work_review_definition(modelo_history_ports_factory)
    workflow_run_read_definition = build_workflow_run_read_definition(workflow_run_read_ports_factory)
    workflow_run_list_definition = build_workflow_run_list_definition(workflow_run_read_ports_factory)
    dependency_definition = build_modelo_dependency_definition(dependency_read_ports_factory)
    pipeline_definition = build_overview_pipeline_definition(pipeline_read_ports_factory)
    overview_definitions = tuple(
        build_overview_read_definition(kind, overview_read_ports_factory) for kind in OverviewReadKind
    )
    invoice_add_definition = build_invoice_add_definition(invoice_creation_ports_factory)
    invoice_import_definition = build_invoice_import_definition(build_invoice_intake_ports)
    invoice_wizard_definition = build_invoice_wizard_definition(build_invoice_intake_ports)
    modelo_aggregate_definition = build_modelo_aggregate_operation_definition(modelo_aggregate_operation_ports_factory)
    modelo_invoice_withholding_capture_definition = build_modelo_invoice_withholding_capture_definition(
        modelo_invoice_withholding_capture_ports_factory
    )
    invoice_list_definition = build_invoice_list_definition(invoice_inspection_read_ports_factory)
    invoice_view_definition = build_invoice_view_definition(invoice_inspection_read_ports_factory)
    invoice_remove_definition = build_invoice_remove_definition(invoice_lifecycle_ports_factory)
    invoice_update_definition = build_invoice_update_definition(invoice_lifecycle_ports_factory)
    workflow_resume_definition = build_workflow_resume_definition(
        workflow_run_read_ports_factory, calculation_action_ports_factory
    )
    wizard_context_definition = build_modelo_work_wizard_context_definition(work_lifecycle_ports_factory)
    wizard_attempt_definition = build_modelo_work_wizard_attempt_definition(
        calculation_action_ports_factory=calculation_action_ports_factory,
        attachment_store_factory=attachment_store_factory,
    )
    revision_definition = build_modelo_work_revision_definition(verification_repository_bundle_factory)
    revisions_definition = build_modelo_work_revisions_definition(verification_repository_bundle_factory)
    ledger_status_definition = build_ledger_status_definition(
        ledger_action_ports_factory, verification_repository_bundle_factory
    )
    ledger_history_definition = build_ledger_history_definition(ledger_action_ports_factory)
    ledger_export_definition = build_ledger_export_definition(build_ledger_export_link_operation_ports)
    ledger_link_definition = build_ledger_link_definition(build_ledger_export_link_operation_ports)

    if own_account_repository_factory is None:
        from ..adapters.persistence.profile.own_accounts import OwnAccountRepository

        own_account_repository_factory = OwnAccountRepository

    def ledger_import_ports_factory(
        *, bucket_id: str, operation: PinnedAuthorityOperation
    ) -> LedgerImportOperationPorts:
        ledger_ports = ledger_action_ports_factory(bucket_id=bucket_id, operation=operation)
        return LedgerImportOperationPorts(
            import_ports=compose_ledger_import_ports(),
            transaction_repository=ledger_ports.transaction_repository,
            bucket_event_repository=ledger_ports.bucket_event_repository,
            currency_normalizer=CurrencyNormalizationService(rate_provider=exchange_rate_provider()),
            operation=operation,
            own_accounts=own_account_repository_factory(bucket_id=bucket_id),
        )

    ledger_import_definition = build_ledger_import_definition(ledger_import_ports_factory)
    ledger_add_definition = build_ledger_add_definition(
        ledger_action_ports_factory,
        build_prorrata_register_repository,
        own_account_repository_factory,
    )
    ledger_allocate_definition = build_ledger_allocate_definition(ledger_action_ports_factory)
    ledger_classify_definition = build_ledger_classify_definition(ledger_action_ports_factory)
    ledger_operator_iva_definition = build_ledger_operator_iva_definition(ledger_action_ports_factory)

    def ledger_llm_operation_ports_factory(
        *, bucket_id: str, operation: PinnedAuthorityOperation
    ) -> LedgerLlmOperationPorts:
        return LedgerLlmOperationPorts(
            ledger=ledger_action_ports_factory(bucket_id=bucket_id, operation=operation),
            llm=compose_ledger_llm(bucket_id=bucket_id, settings=resolved_settings).ports,
            settings=resolved_settings,
        )

    ledger_classify_review_definition = build_ledger_llm_review_definition(
        LEDGER_CLASSIFY_REVIEW_DEFINITION_ID, ledger_llm_operation_ports_factory
    )
    ledger_split_review_definition = build_ledger_llm_review_definition(
        LEDGER_SPLIT_REVIEW_DEFINITION_ID, ledger_llm_operation_ports_factory
    )
    ledger_bulk_classify_definition = build_ledger_bulk_classify_definition(ledger_action_ports_factory)
    ledger_rule_add_definition = build_ledger_rule_add_definition(ledger_rule_repository_factory)
    ledger_rule_list_definition = build_ledger_rule_list_definition(ledger_rule_repository_factory)
    ledger_rule_apply_definition = build_ledger_rule_apply_definition(
        ledger_action_ports_factory, ledger_rule_repository_factory
    )
    ledger_evidence_add_definition = build_ledger_evidence_add_definition(build_ledger_evidence_ports)
    ledger_evidence_list_definition = build_ledger_evidence_list_definition(build_ledger_evidence_ports)
    ledger_evidence_view_definition = build_ledger_evidence_view_definition(build_ledger_evidence_ports)
    ledger_evidence_update_definition = build_ledger_evidence_update_definition(build_ledger_evidence_ports)
    ledger_evidence_remove_definition = build_ledger_evidence_remove_definition(build_ledger_evidence_ports)
    ledger_evidence_reader_readiness_definition = build_ledger_evidence_reader_readiness_definition(
        read_local_reader_status
    )
    ledger_evidence_extract_definition = build_ledger_evidence_extract_definition(
        build_invoice_evidence_operation_ports
    )
    ledger_evidence_confirm_definition = build_ledger_evidence_confirm_definition(
        build_invoice_evidence_operation_ports
    )
    ledger_split_definition = build_ledger_split_definition(ledger_action_ports_factory)
    ledger_merge_definition = build_ledger_merge_definition(ledger_action_ports_factory)
    ledger_update_definition = build_ledger_update_definition(
        ledger_action_ports_factory, own_account_repository_factory
    )
    ledger_attach_definition = build_ledger_attach_definition(ledger_action_ports_factory)
    ledger_detach_definition = build_ledger_detach_definition(ledger_action_ports_factory)
    ledger_archive_definition = build_ledger_archive_definition(ledger_action_ports_factory)
    ledger_stash_definition = build_ledger_stash_definition(ledger_action_ports_factory)
    ledger_restore_definition = build_ledger_restore_definition(ledger_action_ports_factory)
    ledger_exclude_definition = build_ledger_exclude_definition(ledger_action_ports_factory)
    ledger_remove_definition = build_ledger_remove_definition(ledger_action_ports_factory)
    ledger_reset_definition = build_ledger_reset_definition(ledger_action_ports_factory)
    if counterparty_repository_factory is None:
        from ..adapters.persistence.profile.counterparty_establishment import (
            build_counterparty_establishment_repository,
        )

        counterparty_repository_factory = build_counterparty_establishment_repository
    ledger_counterparty_definition = build_ledger_counterparty_definition(counterparty_repository_factory)
    ledger_own_account_definition = build_ledger_own_account_definition(own_account_repository_factory)
    from ..adapters.persistence.profile.modelo_360_solicitud import Modelo360SolicitudRepository

    modelo_360_solicitud_definition = build_modelo_360_solicitud_definition(
        Modelo360SolicitudRepository, own_account_repository_factory
    )
    ledger_check_definition = build_ledger_check_definition(ledger_action_ports_factory)
    ledger_preflight_definition = build_ledger_preflight_definition(ledger_action_ports_factory)
    ledger_review_definition = build_ledger_review_definition(ledger_action_ports_factory)
    ledger_list_definition = build_ledger_list_definition(ledger_action_ports_factory)
    ledger_view_definition = build_ledger_view_definition(ledger_action_ports_factory)
    ledger_track_definition = build_ledger_track_definition(
        ledger_action_ports_factory, ledger_participation_repository_factory
    )
    ledger_participation_definition = build_ledger_participation_definition(
        ledger_action_ports_factory, ledger_participation_repository_factory
    )
    ledger_participation_rebuild_definition = build_ledger_participation_rebuild_definition(
        participation_rebuild_ports_factory
    )
    revision_snapshot_definition = build_modelo_work_revision_snapshot_definition(
        verification_repository_bundle_factory
    )
    filing_record_definition = build_modelo_work_filing_record_definition(verification_repository_bundle_factory)
    filing_record_list_definition = build_modelo_filing_record_list_definition(verification_repository_bundle_factory)
    filing_record_import_definition = build_modelo_filing_record_import_definition(calculation_action_ports_factory)
    filing_record_view_definition = build_modelo_filing_record_view_definition(verification_repository_bundle_factory)
    taxation_comparison_definition = build_modelo_taxation_comparison_definition(build_taxation_comparison_ports)
    local_observation_definition = build_modelo_local_observation_definition(calculation_action_ports_factory)
    verification_report_list_definition = build_modelo_verification_report_list_definition(
        verification_repository_bundle_factory
    )
    verification_report_view_definition = build_modelo_verification_report_view_definition(
        verification_repository_bundle_factory
    )
    amendment_context_definition = build_modelo_work_amendment_context_definition(
        verification_repository_bundle_factory
    )
    m303_attestation_definition = build_modelo_work_m303_attestation_definition(
        work_lifecycle_ports_factory=work_lifecycle_ports_factory,
        attachment_store_factory=attachment_store_factory,
    )
    iva_wallet_correction_definition = build_modelo_iva_wallet_correction_definition(build_modelo_iva_wallet_seed_ports)
    iva_wallet_balance_definition = build_modelo_iva_wallet_balance_definition(build_modelo_iva_wallet_seed_ports)
    iva_wallet_seed_definition = build_modelo_iva_wallet_seed_definition(build_modelo_iva_wallet_seed_ports)
    iva_wallet_override_definition = build_modelo_iva_wallet_override_definition(build_modelo_iva_wallet_seed_ports)
    review_package_definition = build_modelo_review_package_build_definition(
        profile_resolver=modelo_profile_resolver,
        export_ports_factory=modelo_export_ports_factory,
        repositories=verification_repository_bundle_factory,
    )
    definitions = tuple(
        sorted(
            (
                *resolved_auth_definitions,
                *review_read_definitions,
                *evidence_followup_definitions,
                *evidence_ingestion_definitions,
                workstation_check_definition,
                *google_configuration_definitions,
                quickfile_definition,
                modelo_bindings_list_definition,
                modelo_bindings_resolve_definition,
                modelo_bindings_resolve_typed_definition,
                modelo_requires_definition,
                modelo_readiness_definition,
                modelo_readiness_summary_definition,
                modelo_report_verify_definition,
                recipient_add_definition,
                recipient_list_definition,
                recipient_remove_definition,
                *certificate_secret_definitions,
                certificate_source_register_definition,
                certificate_source_list_definition,
                certificate_source_select_definition,
                certificate_source_remove_definition,
                certificate_source_check_definition,
                ledger_ratios_list_definition,
                ledger_ratios_set_definition,
                ledger_ratios_unset_definition,
                ledger_ratios_eligible_definition,
                ledger_ratios_validate_definition,
                activity_asset_create_definition,
                activity_asset_inspect_definition,
                activity_asset_correct_definition,
                activity_asset_forecast_definition,
                activity_asset_claim_definition,
                activity_asset_filing_handoff_definition,
                inventory_list_definition,
                bienes_inversion_list_definition,
                bienes_inversion_declare_definition,
                prorrata_list_definition,
                *prorrata_mutation_definitions,
                inventory_create_definition,
                inventory_movement_add_definition,
                inventory_valuation_preview_definition,
                inventory_closing_authority_record_definition,
                auth_read_definition,
                *apoderado_definitions,
                auth_diagnostic_report_definition,
                diagnostics_read_definition,
                diagnostics_telemetry_flush_definition,
                ledger_llm_diagnostics_definition,
                *borrador_100_definitions,
                *m036_definitions,
                *modelo_audit_definitions,
                modelo_maritime_preview_definition,
                *modelo_spreadsheet_definitions,
                *review_package_exchange_definitions,
                *profile_archive_definitions,
                recovery_status_definition,
                *profile_definitions,
                profile_history_definition,
                *automation_definitions,
                *m145_communication_definitions,
                *modelo_definitions,
                resolved_censal_definition,
                censal_prepare_definition,
                censal_file_import_definition,
                censal_preview_definition,
                filed_history_definition,
                filed_single_definition,
                filed_bulk_definition,
                filed_source_definition,
                filed_list_definition,
                filed_discover_definition,
                iva_wallet_history_definition,
                iva_wallet_history_capture_definition,
                iva_wallet_capture_definition,
                iva_remote_state_capture_definition,
                notifications_capture_definition,
                notification_document_capture_definition,
                notification_document_view_definition,
                notification_document_history_definition,
                notifications_list_definition,
                notifications_show_definition,
                notifications_latest_definition,
                expedientes_list_definition,
                expedientes_show_definition,
                expedientes_latest_definition,
                expedientes_single_capture_definition,
                expedientes_bulk_capture_definition,
                verify_nif_iva_capture_definition,
                verify_tgvi_capture_definition,
                verify_list_definition,
                verify_view_definition,
                verify_latest_definition,
                justificante_capture_definition,
                justificante_list_definition,
                justificante_show_definition,
                resolved_google_export_definition,
                local_reader_definition,
                workbench_definition,
                metadata_definition,
                wizard_context_definition,
                history_definition,
                lifecycle_history_definition,
                history_timeline_definition,
                project_definition,
                compare_definition,
                reconciliation_import_definition,
                reconciliation_pull_definition,
                reconciliation_list_definition,
                work_list_definition,
                work_create_definition,
                work_review_definition,
                workflow_run_read_definition,
                workflow_run_list_definition,
                dependency_definition,
                pipeline_definition,
                *overview_definitions,
                invoice_add_definition,
                invoice_import_definition,
                invoice_wizard_definition,
                modelo_aggregate_definition,
                modelo_invoice_withholding_capture_definition,
                invoice_list_definition,
                invoice_view_definition,
                invoice_remove_definition,
                invoice_update_definition,
                workflow_resume_definition,
                wizard_attempt_definition,
                revision_definition,
                revisions_definition,
                ledger_status_definition,
                ledger_history_definition,
                ledger_export_definition,
                ledger_link_definition,
                ledger_import_definition,
                ledger_add_definition,
                ledger_allocate_definition,
                ledger_classify_definition,
                ledger_operator_iva_definition,
                ledger_classify_review_definition,
                ledger_split_review_definition,
                ledger_bulk_classify_definition,
                ledger_rule_add_definition,
                ledger_rule_list_definition,
                ledger_rule_apply_definition,
                ledger_evidence_add_definition,
                ledger_evidence_list_definition,
                ledger_evidence_view_definition,
                ledger_evidence_update_definition,
                ledger_evidence_remove_definition,
                ledger_evidence_reader_readiness_definition,
                ledger_evidence_extract_definition,
                ledger_evidence_confirm_definition,
                ledger_split_definition,
                ledger_merge_definition,
                ledger_update_definition,
                ledger_attach_definition,
                ledger_detach_definition,
                ledger_archive_definition,
                ledger_stash_definition,
                ledger_restore_definition,
                ledger_exclude_definition,
                ledger_remove_definition,
                ledger_reset_definition,
                ledger_counterparty_definition,
                ledger_own_account_definition,
                modelo_360_solicitud_definition,
                ledger_check_definition,
                ledger_preflight_definition,
                ledger_review_definition,
                ledger_list_definition,
                ledger_view_definition,
                ledger_track_definition,
                ledger_participation_definition,
                ledger_participation_rebuild_definition,
                revision_snapshot_definition,
                filing_record_definition,
                filing_record_list_definition,
                filing_record_import_definition,
                filing_record_view_definition,
                taxation_comparison_definition,
                local_observation_definition,
                verification_report_list_definition,
                verification_report_view_definition,
                amendment_context_definition,
                m303_attestation_definition,
                iva_wallet_correction_definition,
                iva_wallet_balance_definition,
                iva_wallet_seed_definition,
                iva_wallet_override_definition,
                review_package_definition,
                *workbench_definitions,
            ),
            key=lambda item: item.definition_id,
        )
    )
    registrations = tuple(
        sorted(
            (
                *build_auth_operation_registrations(resolved_auth_definitions),
                *build_review_read_registrations(review_read_definitions),
                *build_ledger_evidence_followup_registrations(evidence_followup_definitions),
                *build_ledger_evidence_ingestion_registrations(evidence_ingestion_definitions),
                build_workstation_check_registration(workstation_check_definition),
                *(
                    build_google_configuration_registration(definition)
                    for definition in google_configuration_definitions
                ),
                build_quickfile_registration(quickfile_definition),
                build_modelo_bindings_list_registration(modelo_bindings_list_definition),
                build_modelo_bindings_resolve_registration(modelo_bindings_resolve_definition),
                build_modelo_bindings_resolve_typed_registration(modelo_bindings_resolve_typed_definition),
                build_modelo_requires_registration(modelo_requires_definition),
                build_modelo_readiness_registration(modelo_readiness_definition),
                build_modelo_readiness_summary_registration(modelo_readiness_summary_definition),
                build_modelo_calculation_report_verify_registration(modelo_report_verify_definition),
                build_review_package_recipient_add_registration(recipient_add_definition),
                build_review_package_recipient_list_registration(recipient_list_definition),
                build_review_package_recipient_remove_registration(recipient_remove_definition),
                *build_certificate_secret_operation_registrations(certificate_secret_definitions),
                build_certificate_source_register_registration(certificate_source_register_definition),
                build_certificate_source_list_registration(certificate_source_list_definition),
                build_certificate_source_select_registration(certificate_source_select_definition),
                build_certificate_source_remove_registration(certificate_source_remove_definition),
                build_certificate_source_check_registration(certificate_source_check_definition),
                build_ledger_ratios_list_registration(ledger_ratios_list_definition),
                build_ledger_ratios_set_registration(ledger_ratios_set_definition),
                build_ledger_ratios_unset_registration(ledger_ratios_unset_definition),
                build_ledger_ratios_eligible_registration(ledger_ratios_eligible_definition),
                build_ledger_ratios_validate_registration(ledger_ratios_validate_definition),
                build_activity_asset_create_registration(activity_asset_create_definition),
                build_activity_asset_inspect_registration(activity_asset_inspect_definition),
                build_activity_asset_correct_registration(activity_asset_correct_definition),
                build_activity_asset_forecast_registration(activity_asset_forecast_definition),
                build_activity_asset_claim_registration(activity_asset_claim_definition),
                build_activity_asset_filing_handoff_registration(activity_asset_filing_handoff_definition),
                build_inventory_list_registration(inventory_list_definition),
                build_bienes_inversion_list_registration(bienes_inversion_list_definition),
                build_bienes_inversion_declare_registration(bienes_inversion_declare_definition),
                build_prorrata_list_registration(prorrata_list_definition),
                *(build_prorrata_mutation_registration(definition) for definition in prorrata_mutation_definitions),
                build_inventory_create_registration(inventory_create_definition),
                build_inventory_movement_add_registration(inventory_movement_add_definition),
                build_inventory_valuation_preview_registration(inventory_valuation_preview_definition),
                build_inventory_closing_authority_record_registration(inventory_closing_authority_record_definition),
                build_auth_read_registration(auth_read_definition),
                *build_apoderado_operation_registrations(apoderado_definitions),
                build_auth_diagnostic_report_registration(auth_diagnostic_report_definition),
                build_diagnostics_read_registration(diagnostics_read_definition),
                build_diagnostics_telemetry_flush_registration(diagnostics_telemetry_flush_definition),
                build_ledger_llm_diagnostics_registration(ledger_llm_diagnostics_definition),
                *build_borrador_100_operation_registrations(borrador_100_definitions),
                *build_m036_operation_registrations(m036_definitions),
                *build_modelo_audit_operation_registrations(modelo_audit_definitions),
                build_modelo_maritime_preview_registration(modelo_maritime_preview_definition),
                *(build_modelo_spreadsheet_registration(definition) for definition in modelo_spreadsheet_definitions),
                *build_review_package_exchange_operation_registrations(review_package_exchange_definitions),
                *build_profile_archive_operation_registrations(profile_archive_definitions),
                build_recovery_status_registration(recovery_status_definition),
                *build_user_profile_operation_registrations(profile_definitions),
                build_profile_history_registration(profile_history_definition),
                *build_automation_operation_registrations(automation_definitions),
                *build_m145_communication_operation_registrations(m145_communication_definitions),
                *build_modelo_lifecycle_operation_registrations(
                    modelo_definitions,
                    metadata_access_resolver=compose_modelo_metadata_access(work_lifecycle_ports_factory),
                    revision_access_resolver=compose_modelo_revision_access(verification_repository_bundle_factory),
                ),
                build_censal_operation_registration(resolved_censal_definition),
                build_censal_prepare_operation_registration(censal_prepare_definition),
                build_censal_file_import_operation_registration(censal_file_import_definition),
                build_censal_preview_operation_registration(censal_preview_definition),
                build_filed_history_operation_registration(filed_history_definition),
                build_filed_single_capture_registration(filed_single_definition),
                build_filed_bulk_capture_registration(filed_bulk_definition),
                build_filed_source_capture_registration(filed_source_definition),
                build_filed_list_registration(filed_list_definition),
                build_filed_discover_registration(filed_discover_definition),
                build_iva_wallet_history_registration(iva_wallet_history_definition),
                build_iva_wallet_history_capture_registration(iva_wallet_history_capture_definition),
                build_iva_wallet_capture_registration(iva_wallet_capture_definition),
                build_iva_remote_state_capture_registration(iva_remote_state_capture_definition),
                build_notifications_capture_registration(notifications_capture_definition),
                build_notification_document_capture_registration(notification_document_capture_definition),
                build_notification_document_view_registration(notification_document_view_definition),
                build_notification_document_history_registration(notification_document_history_definition),
                build_notifications_list_registration(notifications_list_definition),
                build_notifications_show_registration(notifications_show_definition),
                build_notifications_latest_registration(notifications_latest_definition),
                build_expedientes_list_registration(expedientes_list_definition),
                build_expedientes_show_registration(expedientes_show_definition),
                build_expedientes_latest_registration(expedientes_latest_definition),
                build_expedientes_single_capture_registration(expedientes_single_capture_definition),
                build_expedientes_bulk_capture_registration(expedientes_bulk_capture_definition),
                build_verify_capture_registration(verify_nif_iva_capture_definition),
                build_verify_capture_registration(verify_tgvi_capture_definition),
                build_verify_list_registration(verify_list_definition),
                build_verify_view_registration(verify_view_definition),
                build_verify_latest_registration(verify_latest_definition),
                build_justificante_capture_registration(justificante_capture_definition),
                build_justificante_list_registration(justificante_list_definition),
                build_justificante_show_registration(justificante_show_definition),
                build_google_sheets_export_operation_registration(resolved_google_export_definition),
                build_local_reader_operation_registration(local_reader_definition),
                build_workbench_generation_operation_registration(workbench_definition),
                build_modelo_metadata_registration(metadata_definition, work_lifecycle_ports_factory),
                build_modelo_work_wizard_context_registration(wizard_context_definition, work_lifecycle_ports_factory),
                build_modelo_work_history_registration(history_definition, modelo_history_ports_factory),
                build_modelo_history_registration(lifecycle_history_definition),
                build_modelo_history_timeline_registration(history_timeline_definition),
                build_modelo_project_registration(project_definition),
                build_modelo_compare_registration(compare_definition),
                build_modelo_reconciliation_import_registration(reconciliation_import_definition),
                build_modelo_reconciliation_pull_registration(reconciliation_pull_definition),
                build_modelo_reconciliation_list_registration(reconciliation_list_definition),
                build_modelo_work_list_registration(work_list_definition),
                build_modelo_work_create_registration(work_create_definition),
                build_modelo_work_review_registration(work_review_definition, modelo_history_ports_factory),
                build_workflow_run_read_registration(workflow_run_read_definition, workflow_run_read_ports_factory),
                build_workflow_run_list_registration(workflow_run_list_definition, workflow_run_read_ports_factory),
                build_modelo_dependency_registration(dependency_definition),
                build_overview_pipeline_registration(pipeline_definition),
                *(build_overview_read_registration(definition) for definition in overview_definitions),
                build_invoice_add_registration(invoice_add_definition),
                build_invoice_intake_registration(invoice_import_definition),
                build_invoice_intake_registration(invoice_wizard_definition),
                build_modelo_aggregate_operation_registration(modelo_aggregate_definition),
                build_modelo_invoice_withholding_capture_registration(modelo_invoice_withholding_capture_definition),
                build_invoice_list_registration(invoice_list_definition),
                build_invoice_view_registration(invoice_view_definition),
                build_invoice_remove_registration(invoice_remove_definition),
                build_invoice_update_registration(invoice_update_definition),
                build_workflow_resume_registration(workflow_resume_definition),
                build_modelo_work_wizard_attempt_registration(wizard_attempt_definition, work_lifecycle_ports_factory),
                build_modelo_work_revision_registration(revision_definition, verification_repository_bundle_factory),
                build_modelo_work_revisions_registration(revisions_definition, verification_repository_bundle_factory),
                build_ledger_status_registration(ledger_status_definition),
                build_ledger_history_registration(ledger_history_definition),
                build_ledger_export_registration(ledger_export_definition),
                build_ledger_link_registration(ledger_link_definition),
                build_ledger_import_registration(ledger_import_definition),
                build_ledger_add_registration(ledger_add_definition),
                build_ledger_allocate_registration(ledger_allocate_definition),
                build_ledger_classify_registration(ledger_classify_definition),
                build_ledger_operator_iva_registration(ledger_operator_iva_definition),
                build_ledger_llm_review_registration(ledger_classify_review_definition),
                build_ledger_llm_review_registration(ledger_split_review_definition),
                build_ledger_bulk_classify_registration(ledger_bulk_classify_definition),
                build_ledger_rule_add_registration(ledger_rule_add_definition),
                build_ledger_rule_list_registration(ledger_rule_list_definition),
                build_ledger_rule_apply_registration(ledger_rule_apply_definition),
                build_ledger_evidence_add_registration(ledger_evidence_add_definition),
                build_ledger_evidence_list_registration(ledger_evidence_list_definition),
                build_ledger_evidence_view_registration(ledger_evidence_view_definition),
                build_ledger_evidence_update_registration(ledger_evidence_update_definition),
                build_ledger_evidence_remove_registration(ledger_evidence_remove_definition),
                build_ledger_evidence_reader_readiness_registration(ledger_evidence_reader_readiness_definition),
                build_ledger_evidence_extract_registration(ledger_evidence_extract_definition),
                build_ledger_evidence_confirm_registration(ledger_evidence_confirm_definition),
                build_ledger_split_registration(ledger_split_definition),
                build_ledger_merge_registration(ledger_merge_definition),
                build_ledger_update_registration(ledger_update_definition),
                build_ledger_attach_registration(ledger_attach_definition),
                build_ledger_detach_registration(ledger_detach_definition),
                build_ledger_archive_registration(ledger_archive_definition),
                build_ledger_stash_registration(ledger_stash_definition),
                build_ledger_restore_registration(ledger_restore_definition),
                build_ledger_exclude_registration(ledger_exclude_definition),
                build_ledger_remove_registration(ledger_remove_definition),
                build_ledger_reset_registration(ledger_reset_definition),
                build_ledger_counterparty_registration(ledger_counterparty_definition),
                build_ledger_own_account_registration(ledger_own_account_definition),
                build_modelo_360_solicitud_registration(modelo_360_solicitud_definition),
                build_ledger_check_registration(ledger_check_definition),
                build_ledger_preflight_registration(ledger_preflight_definition),
                build_ledger_review_registration(ledger_review_definition),
                build_ledger_list_registration(ledger_list_definition),
                build_ledger_view_registration(ledger_view_definition),
                build_ledger_track_registration(ledger_track_definition),
                build_ledger_participation_registration(ledger_participation_definition),
                build_ledger_participation_rebuild_registration(ledger_participation_rebuild_definition),
                build_modelo_work_revision_snapshot_registration(
                    revision_snapshot_definition,
                    access_resolver=compose_modelo_revision_access(verification_repository_bundle_factory),
                ),
                build_modelo_work_filing_record_registration(
                    filing_record_definition, verification_repository_bundle_factory
                ),
                build_modelo_filing_record_list_registration(filing_record_list_definition),
                build_modelo_filing_record_import_registration(
                    filing_record_import_definition, calculation_action_ports_factory
                ),
                build_modelo_filing_record_view_registration(
                    filing_record_view_definition, verification_repository_bundle_factory
                ),
                build_modelo_taxation_comparison_registration(
                    taxation_comparison_definition, build_taxation_comparison_ports
                ),
                build_modelo_local_observation_registration(local_observation_definition),
                build_modelo_verification_report_list_registration(
                    verification_report_list_definition, verification_repository_bundle_factory
                ),
                build_modelo_verification_report_view_registration(
                    verification_report_view_definition, verification_repository_bundle_factory
                ),
                build_modelo_work_amendment_context_registration(
                    amendment_context_definition, verification_repository_bundle_factory
                ),
                build_modelo_work_m303_attestation_registration(
                    m303_attestation_definition,
                    access_resolver=compose_modelo_metadata_access(work_lifecycle_ports_factory),
                ),
                build_modelo_iva_wallet_correction_registration(iva_wallet_correction_definition),
                build_modelo_iva_wallet_balance_registration(iva_wallet_balance_definition),
                build_modelo_iva_wallet_seed_registration(iva_wallet_seed_definition),
                build_modelo_iva_wallet_override_registration(iva_wallet_override_definition),
                build_modelo_review_package_build_registration(
                    review_package_definition,
                    access_resolver=compose_modelo_revision_access(verification_repository_bundle_factory),
                ),
                *build_modelo_workbench_operation_registrations(
                    workbench_definitions,
                    access_resolver=compose_modelo_workbench_access(work_lifecycle_ports_factory),
                ),
            ),
            key=lambda item: item.contract.definition_id,
        )
    )
    registry = OperationRegistry(definitions=definitions, public_registrations=registrations)
    composed_contracts.append(registry.public_contract_set)
    return registry


def compose_operation_dependencies(
    *,
    authority_operation: PinnedAuthorityOperation,
    settings: Settings | None = None,
    evidence_followup_ports: LedgerEvidenceFollowupOperationPorts | None = None,
    modelo_query_read_ports_factory: ModeloQueryReadPortsFactory = build_modelo_query_read_ports,
    recipient_registry_ports_factory: RecipientFingerprintRegistryPortsFactory = (
        build_recipient_fingerprint_registry_ports
    ),
    recipient_event_repository_factory: BucketEventHistoryRepositoryFactory = build_bucket_event_history_repository,
    modelo_export_ports_factory: ModeloExportPortsFactory = build_modelo_export_ports,
    calculation_action_ports_factory: CalculationActionPortsFactory = build_calculation_action_ports,
    attachment_store_factory: Callable[[str], AttachmentStoreProtocol] = build_attachment_store,
    amendment_action_ports_factory: AmendmentActionPortsFactory = build_amendment_action_ports,
    filing_action_ports_factory: FilingActionPortsFactory = build_filing_action_ports,
    work_lifecycle_ports_factory: ActiveWorkLifecyclePortsFactory = build_active_work_lifecycle_ports,
    modelo_history_ports_factory: ModeloHistoryPortsFactory = build_modelo_history_ports,
    workflow_run_read_ports_factory: WorkflowRunReadPortsFactory = build_workflow_run_read_ports,
    dependency_read_ports_factory: DependencyReadPortsFactory = build_dependency_read_ports,
    pipeline_read_ports_factory: PipelineReadPortsFactory = build_pipeline_read_ports,
    overview_read_ports_factory: OverviewReadPortsFactory = build_overview_read_ports,
    invoice_inspection_read_ports_factory: InvoiceInspectionReadPortsFactory = build_invoice_inspection_read_ports,
    invoice_creation_ports_factory: CatalogueCreationPortsFactory = build_catalogue_creation_ports,
    modelo_aggregate_operation_ports_factory: ModeloAggregateOperationPortsFactory = (
        _build_modelo_aggregate_operation_ports
    ),
    modelo_invoice_withholding_capture_ports_factory: ModeloInvoiceWithholdingCapturePortsFactory = (
        _build_modelo_invoice_withholding_capture_ports
    ),
    invoice_lifecycle_ports_factory: CatalogueLifecyclePortsFactory = build_catalogue_lifecycle_ports,
    modelo_edit_receipt_repository_factory: ModeloEditReceiptRepositoryFactory = build_modelo_edit_receipt_repository,
    verification_repository_bundle_factory: VerificationRepositoryBundleFactory = build_verification_repository_bundle,
    operator_scope_ports: OperatorScopePorts | None = None,
    automation_administration_factory: AutomationAdministrationFactory | None = None,
    automation_inventory_reader: AutomationInventoryReader | None = None,
    workbench_generation_reader: WorkbenchGenerationReader | None = None,
    profile_rotation_finalizer: ProfileRotationFinalizer | None = None,
    execution_authority: OperationExecutionAuthority | None = None,
    execution_authority_factory: Callable[[OperationRegistry], OperationExecutionAuthority] | None = None,
    modelo_profile_resolver: ModeloWorkVerifyProfileResolver = resolve_active_workflow_profile,
) -> OperationComposedServices:
    """Compose the immutable production registry and all public services.

    Construction is deliberately explicit: the caller supplies the one
    already-pinned registry operation that every governed executor in this
    graph shares. It opens no browser and starts no supervised operation.
    Profile-bound repositories resolve only when an operation uses them, so
    the same graph can own pre-login and post-login execution without retaining
    a stale profile repository.
    """
    if execution_authority is not None and execution_authority_factory is not None:
        raise ValueError("operation authority must have one owner")
    resolved_settings = settings or load_settings()
    resolved_operator_scope_ports = operator_scope_ports or build_operator_scope_ports()
    storage_root = effective_storage_root(settings=resolved_settings)
    registry = build_production_operation_registry(
        modelo_profile_resolver=modelo_profile_resolver,
        settings=resolved_settings,
        evidence_followup_ports=evidence_followup_ports,
        modelo_query_read_ports_factory=modelo_query_read_ports_factory,
        recipient_registry_ports_factory=recipient_registry_ports_factory,
        recipient_event_repository_factory=recipient_event_repository_factory,
        modelo_export_ports_factory=modelo_export_ports_factory,
        calculation_action_ports_factory=calculation_action_ports_factory,
        attachment_store_factory=attachment_store_factory,
        amendment_action_ports_factory=amendment_action_ports_factory,
        filing_action_ports_factory=filing_action_ports_factory,
        work_lifecycle_ports_factory=work_lifecycle_ports_factory,
        modelo_history_ports_factory=modelo_history_ports_factory,
        workflow_run_read_ports_factory=workflow_run_read_ports_factory,
        dependency_read_ports_factory=dependency_read_ports_factory,
        pipeline_read_ports_factory=pipeline_read_ports_factory,
        overview_read_ports_factory=overview_read_ports_factory,
        invoice_inspection_read_ports_factory=invoice_inspection_read_ports_factory,
        invoice_creation_ports_factory=invoice_creation_ports_factory,
        modelo_aggregate_operation_ports_factory=modelo_aggregate_operation_ports_factory,
        modelo_invoice_withholding_capture_ports_factory=modelo_invoice_withholding_capture_ports_factory,
        invoice_lifecycle_ports_factory=invoice_lifecycle_ports_factory,
        modelo_edit_receipt_repository_factory=modelo_edit_receipt_repository_factory,
        verification_repository_bundle_factory=verification_repository_bundle_factory,
        operator_scope_ports=resolved_operator_scope_ports,
        automation_administration_factory=automation_administration_factory,
        automation_inventory_reader=automation_inventory_reader,
        workbench_generation_reader=workbench_generation_reader,
        profile_rotation_finalizer=profile_rotation_finalizer,
    )
    journal = OperationJournalRepository(storage_root=storage_root)
    if execution_authority_factory is not None:
        execution_authority = execution_authority_factory(registry)
    leases = OperationLeaseFilesystemRepository(storage_root=storage_root)
    operands = operation_secure_reference_repository()
    return compose_operation_services(
        registry=registry,
        authority_operation=authority_operation,
        journal=journal,
        reader=journal,
        event_stream=journal,
        leases=leases,
        operands=operands,
        owner_id=secrets.token_hex(32),
        lease_token_factory=lambda: secrets.token_hex(32),
        clock=now,
        lease_duration=_LEASE_DURATION,
        execution_timeout=_EXECUTION_TIMEOUT,
        cleanup_timeout=_CLEANUP_TIMEOUT,
        typed_financial_operand_custody=OperationTypedFinancialOperandCustodyFilesystemRepository(
            settings=resolved_settings
        ),
        execution_authority=execution_authority,
    )


__all__ = [
    "build_production_operation_registry",
    "compose_operation_dependencies",
]


def _production_registry_settings(settings: Settings | None) -> Settings:
    """Retain the supplied settings or load the original production default."""
    return settings or load_settings()


def _production_registry_operator_scope(operator_scope_ports: OperatorScopePorts | None) -> OperatorScopePorts:
    """Retain an injected scope or compose the same native operator authority."""
    return operator_scope_ports or build_operator_scope_ports()


async def _acquire_registry_verify_observation(
    surface: VerifySurface,
    nif: str,
    expected: IdentityCheckVerdictValue | None,
    operation: PinnedAuthorityOperation,
    *,
    resolved_settings: Settings,
) -> VerifyLiveObservation:
    """Acquire exactly one canonical verdict observation under the same resolved settings."""
    del operation
    expected_by_nif = {tax_id_identity_token(nif): expected or "unknown"}
    if surface is VerifySurface.NIF_IVA:
        result = await collect_nif_iva_check_observations(b"", expected=expected_by_nif, settings=resolved_settings)
    else:
        result = await collect_groi_observations(b"", expected=expected_by_nif, settings=resolved_settings)
    if len(result.observations) != 1:
        raise ValueError("verify acquisition must return exactly one observation")
    return VerifyLiveObservation.model_validate(result.observations[0], from_attributes=True)


def _production_registry_google_export(
    google_export_definition: OperationDefinition | None, resolved_settings: Settings
) -> OperationDefinition:
    """Resolve the supplied definition before constructing its production capabilities."""
    return (
        google_export_definition
        if google_export_definition is not None
        else build_google_sheets_export_operation_definition(
            prepare_port=_google_sheets_export_prepare_port(settings=resolved_settings)
        )
    )


def _production_registry_censal(
    censal_definition: OperationDefinition | None, resolved_operator_scope_ports: OperatorScopePorts
) -> OperationDefinition:
    """Resolve the supplied definition before constructing its production capabilities."""
    return (
        censal_definition
        if censal_definition is not None
        else build_censal_operation_definition(
            certificate_secret_backend_factory=build_certificate_secret_backend,
            browser_session_factory=default_browser_session_factory,
            operator_scope_ports=resolved_operator_scope_ports,
            censal_fetch_port=build_censal_fetch_port(),
            provider_preflight=preflight_filed_history_provider,
        )
    )


def _production_registry_evidence_followup_ports(
    evidence_followup_ports: LedgerEvidenceFollowupOperationPorts | None, resolved_settings: Settings
) -> LedgerEvidenceFollowupOperationPorts:
    """Retain supplied evidence custody or construct the same production ports."""
    return evidence_followup_ports or build_ledger_evidence_followup_operation_ports(settings=resolved_settings)
