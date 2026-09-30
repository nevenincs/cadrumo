"""Sole production composition seam for the supervised operation platform."""

from __future__ import annotations

import secrets
from collections.abc import Callable
from datetime import timedelta
from typing import TYPE_CHECKING

from ..adapters.outbound.aeat.browser.factory import BrowserRuntimeResourceScope, default_browser_session_factory
from ..adapters.outbound.calculation_summary_pdf.summary_container import write_calculation_summary_pdf
from ..adapters.outbound.google.calc_sheets_apply import apply_export_plan, preview_export_plan
from ..adapters.outbound.llm.role_fitness import probe_text_extraction_fitness
from ..adapters.outbound.model_runtime.process_control import run_runtime_installer, spawn_runtime_server
from ..adapters.outbound.storage.errors import OutboundStorageError, OutboundStorageValidationError
from ..adapters.outbound.storage.factory import build_google_credentials, resolve_drive_root_folder_id
from ..adapters.persistence.operations.financial_operand_custody import (
    OperationFinancialOperandCustodyFilesystemRepository,
)
from ..adapters.persistence.operations.journal import OperationJournalRepository
from ..adapters.persistence.operations.lease import OperationLeaseFilesystemRepository
from ..adapters.persistence.operations.secure_references import operation_secure_reference_repository
from ..adapters.persistence.profile.catalogue_creation import build_catalogue_lifecycle_ports
from ..adapters.persistence.profile.participation_index import TransactionParticipationIndexRepository
from ..adapters.persistence.profile.review_package_signing import build_review_package_signing_keypair_capability
from ..adapters.persistence.profile.sync_runs import SyncRunRecordRepository
from ..adapters.persistence.storage.certificate_secret_backend import build_certificate_secret_backend
from ..adapters.persistence.storage.operator_scope import build_operator_scope_ports
from ..application.auth.operation_definitions import (
    AuthOperationPorts,
    ProfileRotationFinalizer,
    build_auth_operation_definitions,
    build_auth_operation_registrations,
)
from ..application.auth.operator_scope_ports import OperatorScopePorts
from ..application.auth.read_operation import build_auth_read_definition, build_auth_read_registration
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
from ..application.ledger.check_operation import build_ledger_check_definition, build_ledger_check_registration
from ..application.ledger.history_operation import (
    build_ledger_history_definition,
    build_ledger_history_registration,
)
from ..application.ledger.list_operation import build_ledger_list_definition, build_ledger_list_registration
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
from ..application.ledger.review_operation import build_ledger_review_definition, build_ledger_review_registration
from ..application.ledger.status_operation import (
    build_ledger_status_definition,
    build_ledger_status_registration,
)
from ..application.ledger.track_operation import build_ledger_track_definition, build_ledger_track_registration
from ..application.ledger.view_operation import build_ledger_view_definition, build_ledger_view_registration
from ..application.live.filed_history_operation import (
    bind_shared_filed_history_pull,
    build_filed_history_operation_definition,
    build_filed_history_operation_registration,
)
from ..application.live.iva_wallet_history_operation import (
    build_iva_wallet_history_definition,
    build_iva_wallet_history_registration,
)
from ..application.local_reader_operation import (
    build_local_reader_operation_definition,
    build_local_reader_operation_registration,
)
from ..application.modelo.amendment_action_ports import AmendmentActionPortsFactory
from ..application.modelo.amendment_context_operation import (
    build_modelo_work_amendment_context_definition,
    build_modelo_work_amendment_context_registration,
)
from ..application.modelo.calculation_action_ports import CalculationActionPortsFactory
from ..application.modelo.dependency_operation import (
    build_modelo_dependency_definition,
    build_modelo_dependency_registration,
)
from ..application.modelo.dependency_read_ports import DependencyReadPortsFactory
from ..application.modelo.edit_receipt_ports import ModeloEditReceiptRepositoryFactory
from ..application.modelo.export_ports import ModeloExportPortsFactory
from ..application.modelo.filing_action_ports import FilingActionPortsFactory
from ..application.modelo.filing_selection_operation import (
    build_modelo_work_filing_record_definition,
    build_modelo_work_filing_record_registration,
)
from ..application.modelo.history_operation import (
    build_modelo_work_history_definition,
    build_modelo_work_history_registration,
)
from ..application.modelo.history_ports import ModeloHistoryPortsFactory
from ..application.modelo.m303_attestation_operation import (
    build_modelo_work_m303_attestation_definition,
    build_modelo_work_m303_attestation_registration,
)
from ..application.modelo.metadata_operation_access import compose_modelo_metadata_access
from ..application.modelo.metadata_read_operation import (
    build_modelo_metadata_definition,
    build_modelo_metadata_registration,
)
from ..application.modelo.operation_definitions import (
    ModeloWorkVerifyProfileResolver,
    build_modelo_lifecycle_operation_definitions,
    build_modelo_lifecycle_operation_registrations,
    resolve_active_workflow_profile,
)
from ..application.modelo.participation_index_rebuild_ports import ParticipationIndexRebuildPortsFactory
from ..application.modelo.review_package_operation import (
    build_modelo_review_package_build_definition,
    build_modelo_review_package_build_registration,
)
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
from ..application.operations.authorization import OperationExecutionAuthority
from ..application.operations.composition import (
    OperationComposedServices,
    compose_operation_services,
)
from ..application.operations.registry import (
    OperationDefinition,
    OperationRegistry,
)
from ..application.overview.pipeline_operation import (
    build_overview_pipeline_definition,
    build_overview_pipeline_registration,
)
from ..application.overview.pipeline_read_ports import PipelineReadPortsFactory
from ..application.overview.read_operation import (
    OverviewReadKind,
    build_overview_read_definition,
    build_overview_read_registration,
)
from ..application.overview.read_ports import OverviewReadPortsFactory
from ..application.storage.calc_sheets.export_service import export_modelo_to_sheets
from ..application.storage.calc_sheets.records import SheetExportPlan, TabName
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
from ..application.user_profile.operations import (
    build_user_profile_operation_definitions,
    build_user_profile_operation_registrations,
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
from ..core.config import Settings, load_settings
from ..core.paths import effective_storage_root
from ..core.time.clock import now
from .adapter_composition import (
    build_active_work_lifecycle_ports,
    build_amendment_action_ports,
    build_attachment_store,
    build_calculation_action_ports,
    build_censal_fetch_port,
    build_filing_action_ports,
    build_modelo_edit_receipt_repository,
    build_modelo_export_ports,
    build_modelo_history_ports,
    build_operator_probe_ports,
    build_participation_index_rebuild_ports,
    build_verification_repository_bundle,
)
from .auth_read_composition import compose_auth_read_ports
from .invoice_inspection_composition import build_invoice_inspection_read_ports
from .ledger_action_composition import compose_ledger_action_ports
from .live_state_composition import (
    compose_live_state,
    preflight_filed_history_provider,
    pull_filed_history_with_shared_composition,
)
from .modelo_dependency_composition import build_dependency_read_ports
from .overview_pipeline_composition import build_pipeline_read_ports
from .overview_read_composition import build_overview_read_ports
from .workflow_run_composition import build_workflow_run_read_ports

_LEASE_DURATION = timedelta(minutes=10)
_EXECUTION_TIMEOUT = timedelta(hours=1)
_CLEANUP_TIMEOUT = timedelta(minutes=2)


if TYPE_CHECKING:
    from ..domain.attachments.protocols import AttachmentStoreProtocol
    from ..domain.calculations.registry.authority import PinnedAuthorityOperation


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
        except OutboundStorageValidationError as exc:
            if exc.translated_message == "adapters.outbound.storage._factory.errors.google_client_missing":
                raise GoogleSheetsExportClientMissingError(str(exc)) from exc
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


def build_production_operation_registry(
    *,
    settings: Settings | None = None,
    auth_definitions: tuple[OperationDefinition, ...] | None = None,
    censal_definition: OperationDefinition | None = None,
    google_export_definition: OperationDefinition | None = None,
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
    invoice_lifecycle_ports_factory: CatalogueLifecyclePortsFactory = build_catalogue_lifecycle_ports,
    modelo_edit_receipt_repository_factory: ModeloEditReceiptRepositoryFactory = build_modelo_edit_receipt_repository,
    verification_repository_bundle_factory: VerificationRepositoryBundleFactory = build_verification_repository_bundle,
    ledger_action_ports_factory: LedgerActionPortsFactory = compose_ledger_action_ports,
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
) -> OperationRegistry:
    """Build the sole immutable production inventory from the owner facades."""
    resolved_settings = settings or load_settings()
    resolved_operator_scope_ports = operator_scope_ports or build_operator_scope_ports()
    resolved_auth_definitions = (
        auth_definitions
        if auth_definitions is not None
        else build_auth_operation_definitions(
            ports=build_auth_operation_ports(resolved_operator_scope_ports),
            finalize_rotation=profile_rotation_finalizer,
        )
    )
    profile_definitions = build_user_profile_operation_definitions()
    auth_read_definition = build_auth_read_definition(compose_auth_read_ports)
    automation_definitions = build_automation_operation_definitions(
        automation_administration_factory, inventory_reader=automation_inventory_reader
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
    )
    resolved_google_export_definition = (
        google_export_definition
        if google_export_definition is not None
        else build_google_sheets_export_operation_definition(
            prepare_port=_google_sheets_export_prepare_port(settings=resolved_settings)
        )
    )
    filed_history_definition = build_filed_history_operation_definition(
        sync_run_repository_factory=SyncRunRecordRepository,
        composition_factory=compose_live_state,
        pull=bind_shared_filed_history_pull(pull_filed_history_with_shared_composition),
    )
    iva_wallet_history_definition = build_iva_wallet_history_definition(
        lambda: compose_live_state().iva_remote_state_port
    )
    local_reader_definition = build_local_reader_operation_definition(
        spawn=spawn_runtime_server,
        run_installer=run_runtime_installer,
        text_probe=probe_text_extraction_fitness,
    )
    resolved_censal_definition = (
        censal_definition
        if censal_definition is not None
        else build_censal_operation_definition(
            certificate_secret_backend_factory=build_certificate_secret_backend,
            browser_session_factory=default_browser_session_factory,
            operator_scope_ports=resolved_operator_scope_ports,
            censal_fetch_port=build_censal_fetch_port(),
        )
    )
    censal_prepare_definition = build_censal_prepare_operation_definition()
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
    amendment_context_definition = build_modelo_work_amendment_context_definition(
        verification_repository_bundle_factory
    )
    m303_attestation_definition = build_modelo_work_m303_attestation_definition(
        work_lifecycle_ports_factory=work_lifecycle_ports_factory,
        attachment_store_factory=attachment_store_factory,
    )
    review_package_definition = build_modelo_review_package_build_definition(
        profile_resolver=modelo_profile_resolver,
        export_ports_factory=modelo_export_ports_factory,
        repositories=verification_repository_bundle_factory,
    )
    definitions = tuple(
        sorted(
            (
                *resolved_auth_definitions,
                auth_read_definition,
                *profile_definitions,
                *automation_definitions,
                *modelo_definitions,
                resolved_censal_definition,
                censal_prepare_definition,
                censal_file_import_definition,
                censal_preview_definition,
                filed_history_definition,
                iva_wallet_history_definition,
                resolved_google_export_definition,
                local_reader_definition,
                workbench_definition,
                metadata_definition,
                wizard_context_definition,
                history_definition,
                work_list_definition,
                work_create_definition,
                work_review_definition,
                workflow_run_read_definition,
                workflow_run_list_definition,
                dependency_definition,
                pipeline_definition,
                *overview_definitions,
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
                amendment_context_definition,
                m303_attestation_definition,
                review_package_definition,
            ),
            key=lambda item: item.definition_id,
        )
    )
    registrations = tuple(
        sorted(
            (
                *build_auth_operation_registrations(resolved_auth_definitions),
                build_auth_read_registration(auth_read_definition),
                *build_user_profile_operation_registrations(profile_definitions),
                *build_automation_operation_registrations(automation_definitions),
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
                build_iva_wallet_history_registration(iva_wallet_history_definition),
                build_google_sheets_export_operation_registration(resolved_google_export_definition),
                build_local_reader_operation_registration(local_reader_definition),
                build_workbench_generation_operation_registration(workbench_definition),
                build_modelo_metadata_registration(metadata_definition, work_lifecycle_ports_factory),
                build_modelo_work_wizard_context_registration(wizard_context_definition, work_lifecycle_ports_factory),
                build_modelo_work_history_registration(history_definition, modelo_history_ports_factory),
                build_modelo_work_list_registration(work_list_definition),
                build_modelo_work_create_registration(work_create_definition),
                build_modelo_work_review_registration(work_review_definition, modelo_history_ports_factory),
                build_workflow_run_read_registration(workflow_run_read_definition, workflow_run_read_ports_factory),
                build_workflow_run_list_registration(workflow_run_list_definition, workflow_run_read_ports_factory),
                build_modelo_dependency_registration(dependency_definition),
                build_overview_pipeline_registration(pipeline_definition),
                *(build_overview_read_registration(definition) for definition in overview_definitions),
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
                build_modelo_work_amendment_context_registration(
                    amendment_context_definition, verification_repository_bundle_factory
                ),
                build_modelo_work_m303_attestation_registration(
                    m303_attestation_definition,
                    access_resolver=compose_modelo_metadata_access(work_lifecycle_ports_factory),
                ),
                build_modelo_review_package_build_registration(
                    review_package_definition,
                    access_resolver=compose_modelo_revision_access(verification_repository_bundle_factory),
                ),
            ),
            key=lambda item: item.contract.definition_id,
        )
    )
    return OperationRegistry(definitions=definitions, public_registrations=registrations)


def compose_operation_dependencies(
    *,
    authority_operation: PinnedAuthorityOperation,
    settings: Settings | None = None,
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
        financial_operand_custody=OperationFinancialOperandCustodyFilesystemRepository(settings=resolved_settings),
        execution_authority=execution_authority,
    )


__all__ = [
    "build_production_operation_registry",
    "compose_operation_dependencies",
]
