"""Sole production composition seam for the supervised operation platform."""

from __future__ import annotations

import secrets
from datetime import timedelta

from ..adapters.outbound.google import apply_export_plan, preview_export_plan
from ..adapters.outbound.storage import build_google_credentials, resolve_drive_root_folder_id
from ..adapters.persistence.operations.financial_operand_custody import (
    OperationFinancialOperandCustodyFilesystemRepository,
)
from ..adapters.persistence.operations.journal import OperationJournalRepository
from ..adapters.persistence.operations.lease import OperationLeaseFilesystemRepository
from ..adapters.persistence.operations.secure_references import operation_secure_reference_repository
from ..adapters.persistence.profile import SyncRunRecordRepository
from ..application.auth.operation_definitions import (
    build_auth_operation_definitions,
    build_auth_operation_registrations,
)
from ..application.export import (
    GoogleSheetsExportRemoteResult,
    GoogleSheetsExportRootFolderRequiredError,
    GoogleSheetsExportService,
    build_google_sheets_export_operation_definition,
    build_google_sheets_export_operation_registration,
    build_google_sheets_export_service,
)
from ..application.live.filed_history_operation import (
    build_filed_history_operation_definition,
    build_filed_history_operation_registration,
)
from ..application.modelo.operation_definitions import (
    build_modelo_lifecycle_operation_definitions,
    build_modelo_lifecycle_operation_registrations,
)
from ..application.operations.composition import (
    OperationComposedServices,
    compose_operation_services,
)
from ..application.operations.registry import (
    OperationDefinition,
    OperationRegistry,
)
from ..application.storage.calc_sheets import SheetExportPlan, TabName, export_modelo_to_sheets
from ..application.user_profile.censal_operation import CENSAL_OPERATION_DEFINITION, build_censal_operation_registration
from ..application.user_profile.operations import (
    build_user_profile_operation_definitions,
    build_user_profile_operation_registrations,
)
from ..core.config import Settings, load_settings
from ..core.paths import effective_storage_root
from ..core.time import now

_LEASE_DURATION = timedelta(minutes=10)
_EXECUTION_TIMEOUT = timedelta(hours=1)
_CLEANUP_TIMEOUT = timedelta(minutes=2)


def _google_sheets_export_port(
    *,
    settings: Settings,
):
    """Compose the sole Google transport and mandatory sync-run provenance handoff."""

    def export(profile_id: str, plan: SheetExportPlan, dry_run: bool) -> GoogleSheetsExportRemoteResult:
        credentials = build_google_credentials(profile=profile_id)
        root_folder_id = resolve_drive_root_folder_id(profile=profile_id, settings=settings)
        if not root_folder_id:
            raise GoogleSheetsExportRootFolderRequiredError("Google Drive root folder is required")
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

    return export


def compose_google_sheets_export_service(
    *,
    settings: Settings | None = None,
) -> GoogleSheetsExportService:
    """Return the canonical application service with its outer transport bound."""
    resolved_settings = settings or load_settings()
    return build_google_sheets_export_service(export_port=_google_sheets_export_port(settings=resolved_settings))


def build_production_operation_registry(
    *,
    settings: Settings | None = None,
    auth_definitions: tuple[OperationDefinition, ...] | None = None,
    censal_definition: OperationDefinition | None = None,
    google_export_definition: OperationDefinition | None = None,
) -> OperationRegistry:
    """Build the sole immutable production inventory from the owner facades."""
    resolved_settings = settings or load_settings()
    resolved_auth_definitions = auth_definitions if auth_definitions is not None else build_auth_operation_definitions()
    profile_definitions = build_user_profile_operation_definitions()
    modelo_definitions = build_modelo_lifecycle_operation_definitions()
    resolved_google_export_definition = (
        google_export_definition
        if google_export_definition is not None
        else build_google_sheets_export_operation_definition(
            export_port=_google_sheets_export_port(settings=resolved_settings)
        )
    )
    filed_history_definition = build_filed_history_operation_definition(
        sync_run_repository_factory=SyncRunRecordRepository
    )
    definitions = tuple(
        sorted(
            (
                *resolved_auth_definitions,
                *profile_definitions,
                *modelo_definitions,
                CENSAL_OPERATION_DEFINITION if censal_definition is None else censal_definition,
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
                build_censal_operation_registration(
                    CENSAL_OPERATION_DEFINITION if censal_definition is None else censal_definition
                ),
                build_filed_history_operation_registration(filed_history_definition),
                build_google_sheets_export_operation_registration(resolved_google_export_definition),
            ),
            key=lambda item: item.contract.definition_id,
        )
    )
    return OperationRegistry(definitions=definitions, public_registrations=registrations)


def compose_operation_dependencies(
    *,
    settings: Settings | None = None,
) -> OperationComposedServices:
    """Compose the immutable production registry and all public services.

    Construction is deliberately explicit and effect-light: it opens no
    browser and starts no operation. Profile-bound repositories resolve only
    when an operation uses them, so the same graph can own pre-login and
    post-login execution without retaining a stale profile repository.
    """
    resolved_settings = settings or load_settings()
    storage_root = effective_storage_root(settings=resolved_settings)
    registry = build_production_operation_registry(settings=resolved_settings)
    journal = OperationJournalRepository(storage_root=storage_root)
    leases = OperationLeaseFilesystemRepository(storage_root=storage_root)
    operands = operation_secure_reference_repository()
    return compose_operation_services(
        registry=registry,
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
    "compose_google_sheets_export_service",
    "compose_operation_dependencies",
]
