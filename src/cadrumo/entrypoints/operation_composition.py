"""Sole production composition seam for the supervised operation platform.

Every registered operation is built by one named composition group, one per
owning operation module. A group imports its builders inside its own function,
so composing one group costs only that operation family's imports. The eager
production registry composes every group; the manifest-backed registry answers
contracts from the generated manifest and composes a group only when one of
its operations is used.

Core types: :class:`~cadrumo.adapters.persistence.profile.transactions.TransactionCatalogueRepository`.
"""

from __future__ import annotations

import secrets
from collections.abc import Callable, Mapping
from dataclasses import replace
from datetime import timedelta
from functools import partial
from typing import TYPE_CHECKING

from ..application.operations.contract_manifest import (
    ManifestOperationRegistry,
    OperationContractManifestV1,
    OperationGroupBuild,
    load_operation_contract_manifest,
)
from ..application.operations.persistence.journal import OperationPersistedSnapshot
from ..application.operations.registry import OperationPublicContractSetV1, OperationRegistry
from ..application.operations.registry_schema_validation import operation_schema_compilation_scope
from ..core.config import Settings, load_settings
from ..core.errors.hierarchy import InternalInvariantError

if TYPE_CHECKING:
    from ..application.auth.operation_definitions import ProfileRotationFinalizer
    from ..application.auth.operator_scope_ports import OperatorScopePorts
    from ..application.bucket_event_repository import BucketEventHistoryRepositoryFactory
    from ..application.connectivity_probe import ConnectivityProbePort
    from ..application.invoices.catalogue_creation_ports import CatalogueCreationPortsFactory
    from ..application.invoices.catalogue_lifecycle_ports import CatalogueLifecyclePortsFactory
    from ..application.invoices.inspection_read_ports import InvoiceInspectionReadPortsFactory
    from ..application.ledger.action_ports import LedgerActionPortsFactory
    from ..application.ledger.counterparty_establishment_ports import CounterpartyEstablishmentRepositoryFactory
    from ..application.ledger.evidence_followup_contracts import LedgerEvidenceFollowupOperationPorts
    from ..application.ledger.own_account_ports import OwnAccountRepositoryFactory
    from ..application.ledger.participation_read import TransactionParticipationIndexRepositoryFactory
    from ..application.ledger.read_ports import LedgerReadPortsFactory
    from ..application.ledger.rule_repository import LedgerClassificationRuleRepositoryFactory
    from ..application.live.sede_view_ports import SedeViewStreamOpener
    from ..application.modelo.aggregate_ports import ModeloAggregateOperationPortsFactory
    from ..application.modelo.amendment_action_ports import AmendmentActionPortsFactory
    from ..application.modelo.calculation_action_ports import CalculationActionPortsFactory
    from ..application.modelo.dependency_read_ports import DependencyReadPortsFactory
    from ..application.modelo.edit_receipt_ports import ModeloEditReceiptRepositoryFactory
    from ..application.modelo.export_ports import ModeloExportPortsFactory
    from ..application.modelo.filing_action_ports import FilingActionPortsFactory
    from ..application.modelo.history_ports import ModeloHistoryPortsFactory
    from ..application.modelo.invoice_withholding_capture_contracts import (
        ModeloInvoiceWithholdingCapturePortsFactory,
    )
    from ..application.modelo.operation_shared import ModeloWorkVerifyProfileResolver
    from ..application.modelo.participation_index_rebuild_ports import ParticipationIndexRebuildPortsFactory
    from ..application.modelo.query_read_contracts import ModeloQueryReadPortsFactory
    from ..application.modelo.review_package_recipient_registry_ports import RecipientFingerprintRegistryPortsFactory
    from ..application.modelo.verification_repository_ports import VerificationRepositoryBundleFactory
    from ..application.modelo.work_lifecycle_ports import ActiveWorkLifecyclePortsFactory
    from ..application.modelo.workbench_read import ModeloWorkbenchReadPortsFactory
    from ..application.operations.authorization import OperationExecutionAuthority
    from ..application.operations.composition import OperationComposedServices
    from ..application.operations.execution_actor import OperationExecutionCallerReader
    from ..application.operations.operation_definition import OperationDefinition
    from ..application.operations.registry import OperationPublicDefinitionRegistrationV1
    from ..application.overview.pipeline_read_ports import PipelineReadPortsFactory
    from ..application.overview.read_ports import OverviewReadPortsFactory
    from ..application.user_profile.automation_operations import (
        AutomationAdministrationFactory,
        AutomationInventoryReader,
    )
    from ..application.workbench_generation_operation import WorkbenchGenerationReader
    from ..application.workflow.run_read_ports import WorkflowRunReadPortsFactory
    from ..core.hex import Hex64Str
    from ..domain.attachments.protocols import AttachmentStoreProtocol
    from ..domain.calculations.registry.authority import PinnedAuthorityOperation

from .operation_composition_general import (
    compose_actividad_asset_registered_operations,
    compose_auth_apoderado_operation,
    compose_auth_certificate_secret_operation,
    compose_auth_certificate_source_operation,
    compose_auth_diagnostic_report_operation,
    compose_auth_operation_definitions,
    compose_auth_read_operation,
    compose_bienes_inversion_registered_operation,
    compose_diagnostics_operation,
    compose_diagnostics_repair_composition,
    compose_export_calculation_review_xlsx_operation,
    compose_export_google_operation,
    compose_export_google_review_operation,
    compose_inventory_registered_operation,
    compose_prorrata_register_registered_operations,
    compose_review_read_registration,
    compose_user_profile_archive_operation,
    compose_user_profile_automation_operations,
    compose_user_profile_censal_certificate_operation,
    compose_user_profile_censal_file_import_operation,
    compose_user_profile_censal_operation,
    compose_user_profile_censal_prepare_operation,
    compose_user_profile_censal_preview_operation,
    compose_user_profile_google_configuration_operation,
    compose_user_profile_history_operation,
    compose_user_profile_operations,
    compose_user_profile_recovery_revoke_operation,
    compose_user_profile_recovery_status_operation,
    compose_workbench_generation_operation,
)
from .operation_composition_inputs import OperationCompositionInputs
from .operation_composition_ledger import (
    compose_invoices_catalogue_add_operation,
    compose_invoices_catalogue_intake_operation,
    compose_invoices_catalogue_read_operation,
    compose_invoices_catalogue_remove_operation,
    compose_invoices_catalogue_update_operation,
    compose_ledger_add_operation,
    compose_ledger_allocate_operation,
    compose_ledger_attachment_mutation_operation,
    compose_ledger_bulk_classify_operation,
    compose_ledger_check_operation,
    compose_ledger_classify_operation,
    compose_ledger_counterparty_operation,
    compose_ledger_evidence_add_operation,
    compose_ledger_evidence_followup_registration,
    compose_ledger_evidence_ingestion_operation,
    compose_ledger_evidence_mutation_operation,
    compose_ledger_evidence_page_operation,
    compose_ledger_evidence_read_operation,
    compose_ledger_export_operation,
    compose_ledger_history_operation,
    compose_ledger_import_operation,
    compose_ledger_invoice_evidence_confirm_operation,
    compose_ledger_invoice_evidence_extract_operation,
    compose_ledger_lifecycle_mutation_operation,
    compose_ledger_link_operation,
    compose_ledger_list_operation,
    compose_ledger_llm_diagnostics_operation,
    compose_ledger_llm_review_operation,
    compose_ledger_merge_operation,
    compose_ledger_operator_iva_operation,
    compose_ledger_own_account_operation,
    compose_ledger_participation_operation,
    compose_ledger_participation_rebuild_operation,
    compose_ledger_preflight_operation,
    compose_ledger_ratios_operation,
    compose_ledger_remove_operation,
    compose_ledger_reset_operation,
    compose_ledger_review_operation,
    compose_ledger_rule_operation,
    compose_ledger_split_operation,
    compose_ledger_status_operation,
    compose_ledger_track_operation,
    compose_ledger_update_operation,
    compose_ledger_view_operation,
    compose_overview_pipeline_operation,
    compose_overview_read_operation,
    compose_workflow_resume_operation,
    compose_workflow_run_read_operation,
)
from .operation_composition_live import (
    compose_live_borrador_100_operation,
    compose_live_expedientes_capture_operation,
    compose_live_expedientes_read_operation,
    compose_live_filed_bulk_capture_operation,
    compose_live_filed_history_operation,
    compose_live_filed_read_operation,
    compose_live_filed_single_capture_operation,
    compose_live_filed_source_capture_operation,
    compose_live_iva_remote_state_capture_operation,
    compose_live_iva_wallet_capture_operation,
    compose_live_iva_wallet_history_capture_operation,
    compose_live_iva_wallet_history_operation,
    compose_live_justificante_capture_operation,
    compose_live_justificante_read_operation,
    compose_live_notification_document_capture_operation,
    compose_live_notification_document_read_operation,
    compose_live_notifications_capture_operation,
    compose_live_notifications_read_operation,
    compose_live_sede_view_operation,
    compose_live_sync_status_operation,
    compose_live_verify_capture_operation,
    compose_live_verify_read_operation,
)
from .operation_composition_modelo import (
    compose_modelo_aggregate_operation,
    compose_modelo_amendment_context_operation,
    compose_modelo_audit_operation,
    compose_modelo_calculation_report_verification_operation,
    compose_modelo_declarations_list_operation,
    compose_modelo_dependency_operation,
    compose_modelo_filing_record_import_operation,
    compose_modelo_filing_record_list_operation,
    compose_modelo_filing_record_view_operation,
    compose_modelo_filing_selection_operation,
    compose_modelo_history_operation,
    compose_modelo_history_timeline_operation,
    compose_modelo_invoice_withholding_capture_operation,
    compose_modelo_iva_wallet_balance_operation,
    compose_modelo_iva_wallet_correction_operation,
    compose_modelo_iva_wallet_override_operation,
    compose_modelo_iva_wallet_seed_operation,
    compose_modelo_lifecycle_history_operation,
    compose_modelo_local_observation_operation,
    compose_modelo_m036_operation,
    compose_modelo_m145_communication_operation,
    compose_modelo_m303_attestation_operation,
    compose_modelo_m360_solicitud_operation,
    compose_modelo_maritime_preview_operation,
    compose_modelo_metadata_read_operation,
    compose_modelo_operation_definitions,
    compose_modelo_projection_operation,
    compose_modelo_query_read_operation,
    compose_modelo_quickfile_operation,
    compose_modelo_reconciliation_export_operation,
    compose_modelo_reconciliation_import_operation,
    compose_modelo_reconciliation_list_operation,
    compose_modelo_reconciliation_pull_operation,
    compose_modelo_review_package_exchange_operation,
    compose_modelo_review_package_operation,
    compose_modelo_review_package_recipient_operations,
    compose_modelo_revision_inventory_operation,
    compose_modelo_revision_selection_operation,
    compose_modelo_revision_snapshot_operation,
    compose_modelo_spreadsheet_operation,
    compose_modelo_taxation_comparison_operation,
    compose_modelo_typed_query_operation,
    compose_modelo_verification_report_read_operation,
    compose_modelo_wizard_attempt_operation,
    compose_modelo_wizard_context_operation,
    compose_modelo_work_create_operation,
    compose_modelo_work_inventory_operation,
    compose_modelo_work_review_operation,
    compose_modelo_workbench_operations,
)

type _GroupComposer = Callable[[OperationCompositionInputs], OperationGroupBuild]

_LEASE_DURATION = timedelta(minutes=10)
_EXECUTION_TIMEOUT = timedelta(hours=1)
_CLEANUP_TIMEOUT = timedelta(minutes=2)


#: Every composition group, keyed by the module that owns its operations. A new
#: operation is enrolled here as well as in its owning module.
_OPERATION_COMPOSITION_GROUPS: Mapping[str, _GroupComposer] = {
    "application.actividad_asset.registered_operations": compose_actividad_asset_registered_operations,
    "application.aeat_sync.status_operation": compose_live_sync_status_operation,
    "application.auth.apoderado_operation": compose_auth_apoderado_operation,
    "application.auth.certificate_secret_operation": compose_auth_certificate_secret_operation,
    "application.auth.certificate_source_operation": compose_auth_certificate_source_operation,
    "application.auth.diagnostic_report_operation": compose_auth_diagnostic_report_operation,
    "application.auth.operation_definitions": compose_auth_operation_definitions,
    "application.auth.read_operation": compose_auth_read_operation,
    "application.bienes_inversion.registered_operation": compose_bienes_inversion_registered_operation,
    "application.diagnostics_operation": compose_diagnostics_operation,
    "application.export.calculation_review_xlsx_operation": compose_export_calculation_review_xlsx_operation,
    "application.export.google_operation": compose_export_google_operation,
    "application.export.google_review_operation": compose_export_google_review_operation,
    "application.inventory.registered_operation": compose_inventory_registered_operation,
    "application.invoices.catalogue_add_operation": compose_invoices_catalogue_add_operation,
    "application.invoices.catalogue_intake_operation": compose_invoices_catalogue_intake_operation,
    "application.invoices.catalogue_read_operation": compose_invoices_catalogue_read_operation,
    "application.invoices.catalogue_remove_operation": compose_invoices_catalogue_remove_operation,
    "application.invoices.catalogue_update_operation": compose_invoices_catalogue_update_operation,
    "application.ledger.add_operation": compose_ledger_add_operation,
    "application.ledger.allocate_operation": compose_ledger_allocate_operation,
    "application.ledger.attachment_mutation_operation": compose_ledger_attachment_mutation_operation,
    "application.ledger.bulk_classify_operation": compose_ledger_bulk_classify_operation,
    "application.ledger.check_operation": compose_ledger_check_operation,
    "application.ledger.classify_operation": compose_ledger_classify_operation,
    "application.ledger.counterparty_operation": compose_ledger_counterparty_operation,
    "application.ledger.evidence_add_operation": compose_ledger_evidence_add_operation,
    "application.ledger.evidence_followup_registration": compose_ledger_evidence_followup_registration,
    "application.ledger.evidence_ingestion_operation": compose_ledger_evidence_ingestion_operation,
    "application.ledger.evidence_mutation_operation": compose_ledger_evidence_mutation_operation,
    "application.ledger.evidence_page_operation": compose_ledger_evidence_page_operation,
    "application.ledger.evidence_read_operation": compose_ledger_evidence_read_operation,
    "application.ledger.export_operation": compose_ledger_export_operation,
    "application.ledger.history_operation": compose_ledger_history_operation,
    "application.ledger.import_operation": compose_ledger_import_operation,
    "application.ledger.invoice_evidence_confirm_operation": compose_ledger_invoice_evidence_confirm_operation,
    "application.ledger.invoice_evidence_extract_operation": compose_ledger_invoice_evidence_extract_operation,
    "application.ledger.lifecycle_mutation_operation": compose_ledger_lifecycle_mutation_operation,
    "application.ledger.link_operation": compose_ledger_link_operation,
    "application.ledger.list_operation": compose_ledger_list_operation,
    "application.ledger.llm_diagnostics_operation": compose_ledger_llm_diagnostics_operation,
    "application.ledger.llm_review_operation": compose_ledger_llm_review_operation,
    "application.ledger.merge_operation": compose_ledger_merge_operation,
    "application.ledger.operator_iva_operation": compose_ledger_operator_iva_operation,
    "application.ledger.own_account_operation": compose_ledger_own_account_operation,
    "application.ledger.participation_operation": compose_ledger_participation_operation,
    "application.ledger.participation_rebuild_operation": compose_ledger_participation_rebuild_operation,
    "application.ledger.preflight_operation": compose_ledger_preflight_operation,
    "application.ledger.ratios_operation": compose_ledger_ratios_operation,
    "application.ledger.remove_operation": compose_ledger_remove_operation,
    "application.ledger.reset_operation": compose_ledger_reset_operation,
    "application.ledger.review_operation": compose_ledger_review_operation,
    "application.ledger.rule_operation": compose_ledger_rule_operation,
    "application.ledger.split_operation": compose_ledger_split_operation,
    "application.ledger.status_operation": compose_ledger_status_operation,
    "application.ledger.track_operation": compose_ledger_track_operation,
    "application.ledger.update_operation": compose_ledger_update_operation,
    "application.ledger.view_operation": compose_ledger_view_operation,
    "application.live.borrador_100_operation": compose_live_borrador_100_operation,
    "application.live.expedientes_capture_operation": compose_live_expedientes_capture_operation,
    "application.live.expedientes_read_operation": compose_live_expedientes_read_operation,
    "application.live.filed_bulk_capture_operation": compose_live_filed_bulk_capture_operation,
    "application.live.filed_history_operation": compose_live_filed_history_operation,
    "application.live.filed_read_operation": compose_live_filed_read_operation,
    "application.live.filed_single_capture_operation": compose_live_filed_single_capture_operation,
    "application.live.filed_source_capture_operation": compose_live_filed_source_capture_operation,
    "application.live.iva_remote_state_capture_operation": compose_live_iva_remote_state_capture_operation,
    "application.live.iva_wallet_capture_operation": compose_live_iva_wallet_capture_operation,
    "application.live.iva_wallet_history_capture_operation": compose_live_iva_wallet_history_capture_operation,
    "application.live.iva_wallet_history_operation": compose_live_iva_wallet_history_operation,
    "application.live.justificante_capture_operation": compose_live_justificante_capture_operation,
    "application.live.justificante_read_operation": compose_live_justificante_read_operation,
    "application.live.notification_document_capture_operation": compose_live_notification_document_capture_operation,
    "application.live.notification_document_read_operation": compose_live_notification_document_read_operation,
    "application.live.notifications_capture_operation": compose_live_notifications_capture_operation,
    "application.live.notifications_read_operation": compose_live_notifications_read_operation,
    "application.live.sede_view_operation": compose_live_sede_view_operation,
    "application.live.verify_capture_operation": compose_live_verify_capture_operation,
    "application.live.verify_read_operation": compose_live_verify_read_operation,
    "application.modelo.aggregate_operation": compose_modelo_aggregate_operation,
    "application.modelo.amendment_context_operation": compose_modelo_amendment_context_operation,
    "application.modelo.audit_operation": compose_modelo_audit_operation,
    "application.modelo.calculation_report_verification_operation": (
        compose_modelo_calculation_report_verification_operation
    ),
    "application.modelo.declarations_list_operation": compose_modelo_declarations_list_operation,
    "application.modelo.dependency_operation": compose_modelo_dependency_operation,
    "application.modelo.filing_record_import_operation": compose_modelo_filing_record_import_operation,
    "application.modelo.filing_record_list_operation": compose_modelo_filing_record_list_operation,
    "application.modelo.filing_record_view_operation": compose_modelo_filing_record_view_operation,
    "application.modelo.filing_selection_operation": compose_modelo_filing_selection_operation,
    "application.modelo.history_operation": compose_modelo_history_operation,
    "application.modelo.history_timeline_operation": compose_modelo_history_timeline_operation,
    "application.modelo.invoice_withholding_capture_operation": compose_modelo_invoice_withholding_capture_operation,
    "application.modelo.iva_wallet_balance_operation": compose_modelo_iva_wallet_balance_operation,
    "application.modelo.iva_wallet_correction_operation": compose_modelo_iva_wallet_correction_operation,
    "application.modelo.iva_wallet_override_operation": compose_modelo_iva_wallet_override_operation,
    "application.modelo.iva_wallet_seed_operation": compose_modelo_iva_wallet_seed_operation,
    "application.modelo.lifecycle_history_operation": compose_modelo_lifecycle_history_operation,
    "application.modelo.local_observation_operation": compose_modelo_local_observation_operation,
    "application.modelo.m036_operation": compose_modelo_m036_operation,
    "application.modelo.m145_communication_operation": compose_modelo_m145_communication_operation,
    "application.modelo.m303_attestation_operation": compose_modelo_m303_attestation_operation,
    "application.modelo.m360_solicitud_operation": compose_modelo_m360_solicitud_operation,
    "application.modelo.maritime_preview_operation": compose_modelo_maritime_preview_operation,
    "application.modelo.typed_query_operation": compose_modelo_typed_query_operation,
    "application.modelo.metadata_read_operation": compose_modelo_metadata_read_operation,
    "application.modelo.modelo_spreadsheet_operation": compose_modelo_spreadsheet_operation,
    "application.modelo.operation_definitions": compose_modelo_operation_definitions,
    "application.modelo.projection_operation": compose_modelo_projection_operation,
    "application.modelo.query_read_operation": compose_modelo_query_read_operation,
    "application.modelo.quickfile_operation": compose_modelo_quickfile_operation,
    "application.modelo.reconciliation_export_operation": compose_modelo_reconciliation_export_operation,
    "application.modelo.reconciliation_import_operation": compose_modelo_reconciliation_import_operation,
    "application.modelo.reconciliation_list_operation": compose_modelo_reconciliation_list_operation,
    "application.modelo.reconciliation_pull_operation": compose_modelo_reconciliation_pull_operation,
    "application.modelo.review_package_exchange_operation": compose_modelo_review_package_exchange_operation,
    "application.modelo.review_package_operation": compose_modelo_review_package_operation,
    "application.modelo.review_package_recipient_operations": compose_modelo_review_package_recipient_operations,
    "application.modelo.revision_inventory_operation": compose_modelo_revision_inventory_operation,
    "application.modelo.revision_selection_operation": compose_modelo_revision_selection_operation,
    "application.modelo.revision_snapshot_operation": compose_modelo_revision_snapshot_operation,
    "application.modelo.taxation_comparison_operation": compose_modelo_taxation_comparison_operation,
    "application.modelo.verification_report_read_operation": compose_modelo_verification_report_read_operation,
    "application.modelo.wizard_attempt_operation": compose_modelo_wizard_attempt_operation,
    "application.modelo.wizard_context_operation": compose_modelo_wizard_context_operation,
    "application.modelo.work_create_operation": compose_modelo_work_create_operation,
    "application.modelo.work_inventory_operation": compose_modelo_work_inventory_operation,
    "application.modelo.work_review_operation": compose_modelo_work_review_operation,
    "application.modelo.workbench_operations": compose_modelo_workbench_operations,
    "application.overview.pipeline_operation": compose_overview_pipeline_operation,
    "application.overview.read_operation": compose_overview_read_operation,
    "application.prorrata_register.registered_operations": compose_prorrata_register_registered_operations,
    "application.review.read_registration": compose_review_read_registration,
    "application.user_profile.archive_operation": compose_user_profile_archive_operation,
    "application.user_profile.automation_operations": compose_user_profile_automation_operations,
    "application.user_profile.censal_certificate_operation": compose_user_profile_censal_certificate_operation,
    "application.user_profile.censal_file_import_operation": compose_user_profile_censal_file_import_operation,
    "application.user_profile.censal_operation": compose_user_profile_censal_operation,
    "application.user_profile.censal_prepare_operation": compose_user_profile_censal_prepare_operation,
    "application.user_profile.censal_preview_operation": compose_user_profile_censal_preview_operation,
    "application.user_profile.google_configuration_operation": compose_user_profile_google_configuration_operation,
    "application.user_profile.history_operation": compose_user_profile_history_operation,
    "application.user_profile.operations": compose_user_profile_operations,
    "application.user_profile.recovery_revoke_operation": compose_user_profile_recovery_revoke_operation,
    "application.user_profile.recovery_status_operation": compose_user_profile_recovery_status_operation,
    "application.workbench_generation_operation": compose_workbench_generation_operation,
    "application.workflow.resume_operation": compose_workflow_resume_operation,
    "application.workflow.run_read_operation": compose_workflow_run_read_operation,
    "entrypoints.diagnostics_repair_composition": compose_diagnostics_repair_composition,
}


def compose_operation_group(inputs: OperationCompositionInputs, group: str) -> OperationGroupBuild:
    """Build the operations of one named composition group, or refuse an unknown group."""
    composer = _OPERATION_COMPOSITION_GROUPS.get(group)
    if composer is None:
        raise InternalInvariantError(f"no operation composition group is named {group!r}")
    with operation_schema_compilation_scope():
        return composer(inputs)


def _compose_every_group(inputs: OperationCompositionInputs) -> tuple[OperationRegistry, dict[str, str]]:
    """Compose every group eagerly; return the registry and each definition's group."""
    composed_contracts: list[OperationPublicContractSetV1] = []

    def registry_contracts() -> OperationPublicContractSetV1:
        if not composed_contracts:
            raise InternalInvariantError("the operation registry's contracts are read before it is composed")
        return composed_contracts[0]

    bound = replace(inputs, contracts=registry_contracts)
    definitions: list[OperationDefinition] = []
    registrations: list[OperationPublicDefinitionRegistrationV1] = []
    groups: dict[str, str] = {}
    with operation_schema_compilation_scope():
        for group, composer in _OPERATION_COMPOSITION_GROUPS.items():
            built = composer(bound)
            definitions.extend(built.definitions)
            registrations.extend(built.registrations)
            for definition in built.definitions:
                groups[definition.definition_id] = group
    registry = OperationRegistry(
        definitions=tuple(sorted(definitions, key=lambda item: item.definition_id)),
        public_registrations=tuple(sorted(registrations, key=lambda item: item.contract.definition_id)),
    )
    composed_contracts.append(registry.public_contract_set)
    return registry, groups


def build_production_operation_registry(
    *,
    settings: Settings | None = None,
    auth_definitions: tuple[OperationDefinition, ...] | None = None,
    censal_definition: OperationDefinition | None = None,
    verify_nif_iva_definition: OperationDefinition | None = None,
    verify_tgvi_definition: OperationDefinition | None = None,
    google_export_definition: OperationDefinition | None = None,
    evidence_followup_ports: LedgerEvidenceFollowupOperationPorts | None = None,
    modelo_query_read_ports_factory: ModeloQueryReadPortsFactory | None = None,
    recipient_registry_ports_factory: RecipientFingerprintRegistryPortsFactory | None = None,
    recipient_event_repository_factory: BucketEventHistoryRepositoryFactory | None = None,
    modelo_export_ports_factory: ModeloExportPortsFactory | None = None,
    calculation_action_ports_factory: CalculationActionPortsFactory | None = None,
    attachment_store_factory: Callable[[str], AttachmentStoreProtocol] | None = None,
    amendment_action_ports_factory: AmendmentActionPortsFactory | None = None,
    filing_action_ports_factory: FilingActionPortsFactory | None = None,
    work_lifecycle_ports_factory: ActiveWorkLifecyclePortsFactory | None = None,
    modelo_history_ports_factory: ModeloHistoryPortsFactory | None = None,
    workflow_run_read_ports_factory: WorkflowRunReadPortsFactory | None = None,
    dependency_read_ports_factory: DependencyReadPortsFactory | None = None,
    pipeline_read_ports_factory: PipelineReadPortsFactory | None = None,
    overview_read_ports_factory: OverviewReadPortsFactory | None = None,
    invoice_inspection_read_ports_factory: InvoiceInspectionReadPortsFactory | None = None,
    invoice_creation_ports_factory: CatalogueCreationPortsFactory | None = None,
    modelo_aggregate_operation_ports_factory: ModeloAggregateOperationPortsFactory | None = None,
    modelo_invoice_withholding_capture_ports_factory: ModeloInvoiceWithholdingCapturePortsFactory | None = None,
    invoice_lifecycle_ports_factory: CatalogueLifecyclePortsFactory | None = None,
    modelo_edit_receipt_repository_factory: ModeloEditReceiptRepositoryFactory | None = None,
    verification_repository_bundle_factory: VerificationRepositoryBundleFactory | None = None,
    ledger_action_ports_factory: LedgerActionPortsFactory | None = None,
    ledger_read_ports_factory: LedgerReadPortsFactory | None = None,
    ledger_rule_repository_factory: LedgerClassificationRuleRepositoryFactory | None = None,
    counterparty_repository_factory: CounterpartyEstablishmentRepositoryFactory | None = None,
    own_account_repository_factory: OwnAccountRepositoryFactory | None = None,
    ledger_participation_repository_factory: TransactionParticipationIndexRepositoryFactory | None = None,
    participation_rebuild_ports_factory: ParticipationIndexRebuildPortsFactory | None = None,
    operator_scope_ports: OperatorScopePorts | None = None,
    automation_administration_factory: AutomationAdministrationFactory | None = None,
    automation_inventory_reader: AutomationInventoryReader | None = None,
    workbench_generation_reader: WorkbenchGenerationReader | None = None,
    profile_rotation_finalizer: ProfileRotationFinalizer | None = None,
    modelo_profile_resolver: ModeloWorkVerifyProfileResolver | None = None,
    modelo_workbench_read_ports_factory: ModeloWorkbenchReadPortsFactory | None = None,
    execution_caller_reader: OperationExecutionCallerReader | None = None,
    connectivity_probe: ConnectivityProbePort | None = None,
) -> OperationRegistry:
    """Build the sole immutable production inventory by composing every group eagerly.

    This is the validation authority the contract manifest is generated from.
    A ``None`` capability selects its production default.
    ``connectivity_probe`` browses to the site the connectivity operation
    observes.
    """
    inputs = OperationCompositionInputs(
        settings=settings,
        auth_definitions=auth_definitions,
        censal_definition=censal_definition,
        verify_nif_iva_definition=verify_nif_iva_definition,
        verify_tgvi_definition=verify_tgvi_definition,
        google_export_definition=google_export_definition,
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
        ledger_action_ports_factory=ledger_action_ports_factory,
        ledger_read_ports_factory=ledger_read_ports_factory,
        ledger_rule_repository_factory=ledger_rule_repository_factory,
        counterparty_repository_factory=counterparty_repository_factory,
        own_account_repository_factory=own_account_repository_factory,
        ledger_participation_repository_factory=ledger_participation_repository_factory,
        participation_rebuild_ports_factory=participation_rebuild_ports_factory,
        operator_scope_ports=operator_scope_ports,
        automation_administration_factory=automation_administration_factory,
        automation_inventory_reader=automation_inventory_reader,
        workbench_generation_reader=workbench_generation_reader,
        profile_rotation_finalizer=profile_rotation_finalizer,
        modelo_profile_resolver=modelo_profile_resolver,
        modelo_workbench_read_ports_factory=modelo_workbench_read_ports_factory,
        execution_caller_reader=execution_caller_reader,
        connectivity_probe=connectivity_probe,
    )
    return _compose_every_group(inputs)[0]


def build_production_operation_contract_manifest() -> OperationContractManifestV1:
    """Record every production operation's contract and composition group from the eager registry."""
    registry, groups = _compose_every_group(OperationCompositionInputs())
    return OperationContractManifestV1.from_registry(registry, groups)


def build_manifest_operation_registry(
    inputs: OperationCompositionInputs | None = None, *, manifest: OperationContractManifestV1 | None = None
) -> ManifestOperationRegistry:
    """Bind the shipped contract manifest to the composition groups that build its operations.

    Contracts are answered from the manifest without composing any operation.
    An operation's group is composed on its first use and admitted only when it
    reproduces the manifest exactly. ``manifest`` defaults to the one shipped
    with this installation.
    """
    resolved = manifest if manifest is not None else load_operation_contract_manifest()
    bound = replace(inputs or OperationCompositionInputs(), contracts=lambda: resolved.contract_set)
    return ManifestOperationRegistry.from_manifest(resolved, partial(compose_operation_group, bound))


def compose_operation_dependencies(
    *,
    authority_operation: PinnedAuthorityOperation,
    operation_owner_id: Hex64Str | None = None,
    settings: Settings | None = None,
    evidence_followup_ports: LedgerEvidenceFollowupOperationPorts | None = None,
    modelo_query_read_ports_factory: ModeloQueryReadPortsFactory | None = None,
    recipient_registry_ports_factory: RecipientFingerprintRegistryPortsFactory | None = None,
    recipient_event_repository_factory: BucketEventHistoryRepositoryFactory | None = None,
    modelo_export_ports_factory: ModeloExportPortsFactory | None = None,
    calculation_action_ports_factory: CalculationActionPortsFactory | None = None,
    attachment_store_factory: Callable[[str], AttachmentStoreProtocol] | None = None,
    amendment_action_ports_factory: AmendmentActionPortsFactory | None = None,
    filing_action_ports_factory: FilingActionPortsFactory | None = None,
    work_lifecycle_ports_factory: ActiveWorkLifecyclePortsFactory | None = None,
    modelo_history_ports_factory: ModeloHistoryPortsFactory | None = None,
    workflow_run_read_ports_factory: WorkflowRunReadPortsFactory | None = None,
    dependency_read_ports_factory: DependencyReadPortsFactory | None = None,
    pipeline_read_ports_factory: PipelineReadPortsFactory | None = None,
    overview_read_ports_factory: OverviewReadPortsFactory | None = None,
    invoice_inspection_read_ports_factory: InvoiceInspectionReadPortsFactory | None = None,
    invoice_creation_ports_factory: CatalogueCreationPortsFactory | None = None,
    modelo_aggregate_operation_ports_factory: ModeloAggregateOperationPortsFactory | None = None,
    modelo_invoice_withholding_capture_ports_factory: ModeloInvoiceWithholdingCapturePortsFactory | None = None,
    invoice_lifecycle_ports_factory: CatalogueLifecyclePortsFactory | None = None,
    modelo_edit_receipt_repository_factory: ModeloEditReceiptRepositoryFactory | None = None,
    verification_repository_bundle_factory: VerificationRepositoryBundleFactory | None = None,
    operator_scope_ports: OperatorScopePorts | None = None,
    automation_administration_factory: AutomationAdministrationFactory | None = None,
    automation_inventory_reader: AutomationInventoryReader | None = None,
    workbench_generation_reader: WorkbenchGenerationReader | None = None,
    profile_rotation_finalizer: ProfileRotationFinalizer | None = None,
    execution_authority: OperationExecutionAuthority | None = None,
    execution_authority_factory: Callable[[OperationRegistry], OperationExecutionAuthority] | None = None,
    modelo_profile_resolver: ModeloWorkVerifyProfileResolver | None = None,
    execution_caller_reader: OperationExecutionCallerReader | None = None,
    sede_view_stream_opener: SedeViewStreamOpener | None = None,
    journal_committed: Callable[[OperationPersistedSnapshot], None] | None = None,
) -> OperationComposedServices:
    """Compose the manifest-backed production registry and all public services.

    Construction is deliberately explicit: the caller supplies the one
    already-pinned registry operation that every governed executor in this
    graph shares. It opens no browser and starts no supervised operation.
    Profile-bound repositories resolve only when an operation uses them, so
    the same graph can own pre-login and post-login execution without retaining
    a stale profile repository. ``journal_committed`` is told each operation
    whose journal commit succeeded, for a host that reports progress.
    ``sede_view_stream_opener`` is the worker host's view stream; without it
    the Sede view refuses every run.
    """
    from ..adapters.persistence.operations.durability_router import DurabilityRoutedOperationPersistence
    from ..adapters.persistence.operations.journal import OperationJournalRepository
    from ..adapters.persistence.operations.lease import OperationLeaseFilesystemRepository
    from ..adapters.persistence.operations.secure_references import operation_secure_reference_repository
    from ..adapters.persistence.operations.typed_financial_operand_custody import (
        OperationTypedFinancialOperandCustodyFilesystemRepository,
    )
    from ..application.operations.composition import compose_operation_services
    from ..core.paths import effective_storage_root
    from ..core.time.clock import now

    if execution_authority is not None and execution_authority_factory is not None:
        raise ValueError("operation authority must have one owner")
    inputs = OperationCompositionInputs(
        settings=settings or load_settings(),
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
        operator_scope_ports=operator_scope_ports,
        automation_administration_factory=automation_administration_factory,
        automation_inventory_reader=automation_inventory_reader,
        workbench_generation_reader=workbench_generation_reader,
        profile_rotation_finalizer=profile_rotation_finalizer,
        modelo_profile_resolver=modelo_profile_resolver,
        execution_caller_reader=execution_caller_reader,
        sede_view_stream_opener=sede_view_stream_opener,
    )
    resolved_settings = inputs.resolved_settings
    storage_root = effective_storage_root(settings=resolved_settings)
    registry = build_manifest_operation_registry(inputs)
    journal = OperationJournalRepository(storage_root=storage_root)
    if execution_authority_factory is not None:
        execution_authority = execution_authority_factory(registry)
    # Operations declared ephemeral run in this process's memory; every other is journaled durably.
    persistence = DurabilityRoutedOperationPersistence(
        journal=journal,
        event_stream=journal,
        reader=journal,
        leases=OperationLeaseFilesystemRepository(storage_root=storage_root),
        operands=operation_secure_reference_repository(),
        committed=journal_committed,
    )
    return compose_operation_services(
        registry=registry,
        authority_operation=authority_operation,
        journal=persistence,
        reader=persistence,
        event_stream=persistence,
        leases=persistence,
        operands=persistence,
        ephemeral=persistence,
        owner_id=secrets.token_hex(32) if operation_owner_id is None else operation_owner_id,
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
