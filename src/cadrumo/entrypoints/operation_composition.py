"""Sole production composition seam for the supervised operation platform."""

from __future__ import annotations

import secrets
from datetime import timedelta
from typing import TYPE_CHECKING

from ..adapters.outbound.aeat.browser.factory import default_browser_session_factory
from ..adapters.outbound.google.calc_sheets_apply import apply_export_plan, preview_export_plan
from ..adapters.outbound.storage.errors import OutboundStorageError, OutboundStorageValidationError
from ..adapters.outbound.storage.factory import build_google_credentials, resolve_drive_root_folder_id
from ..adapters.persistence.operations.financial_operand_custody import (
    OperationFinancialOperandCustodyFilesystemRepository,
)
from ..adapters.persistence.operations.journal import OperationJournalRepository
from ..adapters.persistence.operations.lease import OperationLeaseFilesystemRepository
from ..adapters.persistence.operations.secure_references import operation_secure_reference_repository
from ..adapters.persistence.profile.sync_runs import SyncRunRecordRepository
from ..adapters.persistence.storage.certificate_secret_backend import build_certificate_secret_backend
from ..adapters.persistence.storage.operator_scope import build_operator_scope_ports
from ..application.auth.operation_definitions import (
    build_auth_operation_definitions,
    build_auth_operation_registrations,
)
from ..application.auth.operator_scope_ports import OperatorScopePorts
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
from ..application.live.filed_history_operation import (
    build_filed_history_operation_definition,
    build_filed_history_operation_registration,
)
from ..application.modelo.amendment_action_ports import AmendmentActionPortsFactory
from ..application.modelo.calculation_action_ports import CalculationActionPortsFactory
from ..application.modelo.edit_receipt_ports import ModeloEditReceiptRepositoryFactory
from ..application.modelo.export_ports import ModeloExportPortsFactory
from ..application.modelo.filing_action_ports import FilingActionPortsFactory
from ..application.modelo.operation_definitions import (
    build_modelo_lifecycle_operation_definitions,
    build_modelo_lifecycle_operation_registrations,
)
from ..application.modelo.verification_repository_ports import VerificationRepositoryBundleFactory
from ..application.modelo.work_lifecycle_ports import ActiveWorkLifecyclePortsFactory
from ..application.operations.composition import (
    OperationComposedServices,
    compose_operation_services,
)
from ..application.operations.registry import (
    OperationDefinition,
    OperationRegistry,
)
from ..application.storage.calc_sheets.export_service import export_modelo_to_sheets
from ..application.storage.calc_sheets.records import SheetExportPlan, TabName
from ..application.user_profile.censal_operation import (
    build_censal_operation_definition,
    build_censal_operation_registration,
)
from ..application.user_profile.operations import (
    build_user_profile_operation_definitions,
    build_user_profile_operation_registrations,
)
from ..core.config import Settings, load_settings
from ..core.paths import effective_storage_root
from ..core.time.clock import now
from .adapter_composition import (
    build_active_work_lifecycle_ports,
    build_amendment_action_ports,
    build_calculation_action_ports,
    build_censal_fetch_port,
    build_filing_action_ports,
    build_modelo_edit_receipt_repository,
    build_modelo_export_ports,
    build_verification_repository_bundle,
)
from .live_state_composition import compose_live_state, pull_filed_history_with_shared_composition

_LEASE_DURATION = timedelta(minutes=10)
_EXECUTION_TIMEOUT = timedelta(hours=1)
_CLEANUP_TIMEOUT = timedelta(minutes=2)

if TYPE_CHECKING:
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


def build_production_operation_registry(
    *,
    settings: Settings | None = None,
    auth_definitions: tuple[OperationDefinition, ...] | None = None,
    censal_definition: OperationDefinition | None = None,
    google_export_definition: OperationDefinition | None = None,
    modelo_export_ports_factory: ModeloExportPortsFactory = build_modelo_export_ports,
    calculation_action_ports_factory: CalculationActionPortsFactory = build_calculation_action_ports,
    amendment_action_ports_factory: AmendmentActionPortsFactory = build_amendment_action_ports,
    filing_action_ports_factory: FilingActionPortsFactory = build_filing_action_ports,
    work_lifecycle_ports_factory: ActiveWorkLifecyclePortsFactory = build_active_work_lifecycle_ports,
    modelo_edit_receipt_repository_factory: ModeloEditReceiptRepositoryFactory = build_modelo_edit_receipt_repository,
    verification_repository_bundle_factory: VerificationRepositoryBundleFactory = build_verification_repository_bundle,
    operator_scope_ports: OperatorScopePorts | None = None,
) -> OperationRegistry:
    """Build the sole immutable production inventory from the owner facades."""
    resolved_settings = settings or load_settings()
    resolved_operator_scope_ports = operator_scope_ports or build_operator_scope_ports()
    resolved_auth_definitions = auth_definitions if auth_definitions is not None else build_auth_operation_definitions()
    profile_definitions = build_user_profile_operation_definitions()
    modelo_definitions = build_modelo_lifecycle_operation_definitions(
        certificate_secret_backend_factory=build_certificate_secret_backend,
        operator_scope_ports=resolved_operator_scope_ports,
        export_ports_factory=modelo_export_ports_factory,
        calculation_action_ports_factory=calculation_action_ports_factory,
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
        pull=pull_filed_history_with_shared_composition,
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
    definitions = tuple(
        sorted(
            (
                *resolved_auth_definitions,
                *profile_definitions,
                *modelo_definitions,
                resolved_censal_definition,
                filed_history_definition,
                resolved_google_export_definition,
            ),
            key=lambda item: item.definition_id,
        )
    )
    registrations = tuple(
        sorted(
            (
                *build_auth_operation_registrations(resolved_auth_definitions),
                *build_user_profile_operation_registrations(profile_definitions),
                *build_modelo_lifecycle_operation_registrations(modelo_definitions),
                build_censal_operation_registration(resolved_censal_definition),
                build_filed_history_operation_registration(filed_history_definition),
                build_google_sheets_export_operation_registration(resolved_google_export_definition),
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
    amendment_action_ports_factory: AmendmentActionPortsFactory = build_amendment_action_ports,
    filing_action_ports_factory: FilingActionPortsFactory = build_filing_action_ports,
    work_lifecycle_ports_factory: ActiveWorkLifecyclePortsFactory = build_active_work_lifecycle_ports,
    modelo_edit_receipt_repository_factory: ModeloEditReceiptRepositoryFactory = build_modelo_edit_receipt_repository,
    verification_repository_bundle_factory: VerificationRepositoryBundleFactory = build_verification_repository_bundle,
    operator_scope_ports: OperatorScopePorts | None = None,
) -> OperationComposedServices:
    """Compose the immutable production registry and all public services.

    Construction is deliberately explicit: the caller supplies the one
    already-pinned registry operation that every governed executor in this
    graph shares. It opens no browser and starts no supervised operation.
    Profile-bound repositories resolve only when an operation uses them, so
    the same graph can own pre-login and post-login execution without retaining
    a stale profile repository.
    """
    resolved_settings = settings or load_settings()
    resolved_operator_scope_ports = operator_scope_ports or build_operator_scope_ports()
    storage_root = effective_storage_root(settings=resolved_settings)
    registry = build_production_operation_registry(
        settings=resolved_settings,
        modelo_export_ports_factory=modelo_export_ports_factory,
        calculation_action_ports_factory=calculation_action_ports_factory,
        amendment_action_ports_factory=amendment_action_ports_factory,
        filing_action_ports_factory=filing_action_ports_factory,
        work_lifecycle_ports_factory=work_lifecycle_ports_factory,
        modelo_edit_receipt_repository_factory=modelo_edit_receipt_repository_factory,
        verification_repository_bundle_factory=verification_repository_bundle_factory,
        operator_scope_ports=resolved_operator_scope_ports,
    )
    journal = OperationJournalRepository(storage_root=storage_root)
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
    )


__all__ = [
    "build_production_operation_registry",
    "compose_operation_dependencies",
]
