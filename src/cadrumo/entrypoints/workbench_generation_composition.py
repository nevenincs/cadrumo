"""Compose the canonical secure workbench generation outside any frontend."""

from __future__ import annotations

from collections.abc import Callable
from typing import TYPE_CHECKING

from ..application.workbench_generation import (
    InstalledWorkbenchGenerationProviderV1,
    ModeloWorkspaceProjectedReadV1,
    SecureProfileWorkbenchGenerationReadDoorV1,
    WorkbenchGenerationV1,
)

if TYPE_CHECKING:
    from ..application.modelo.workspace_models import ModeloWorkspaceResultV1, ModeloWorkspaceStaticInspectionResultV1
    from ..application.operations.registry import OperationPublicContractSetV1
    from ..application.overview.home import HomeAccountSession
    from ..core.authority_grade import RegistryAuthorityGrade
    from ..core.external_constants import OutputLanguage
    from ..core.period import Period
    from ..domain.calculations.registry.authority import PinnedAuthorityOperation
    from ..domain.modelos.work_unit import WorkUnit


def compose_secure_workbench_generation_provider(
    *,
    profile_id: str,
    operation: PinnedAuthorityOperation,
    operation_contracts: OperationPublicContractSetV1,
    account_session_reader: Callable[[], HomeAccountSession],
) -> Callable[[], WorkbenchGenerationV1]:
    """Bind one explicit profile and pinned authority to the existing read door.

    The caller owns authentication and the exact profile session. A fresh
    session check precedes each capture and the repository composition it
    performs; neither this builder nor its readers select an active profile.
    """
    from ..adapters.persistence.profile.modelos_filing import ModeloRecordCatalogueRepository
    from ..adapters.persistence.profile.modelos_verification_reports import VerificationReportCatalogueRepository
    from ..application.user_profile.profile_record_repository import ProfileRecordRepository
    from ..core.time.clock import now
    from .ledger_action_composition import compose_ledger_action_ports

    account_session_reader()

    def read_door() -> SecureProfileWorkbenchGenerationReadDoorV1:
        ledger_action_ports = compose_ledger_action_ports(bucket_id=profile_id, operation=operation)
        return SecureProfileWorkbenchGenerationReadDoorV1(
            profile_id=profile_id,
            operation=operation,
            profile_repository=ProfileRecordRepository.for_current_session(
                profile_id,
                profile_decode_context=operation.profile_decode_context(),
            ),
            work_unit_repository=ledger_action_ports.work_unit_repository,
            calculation_repository=ledger_action_ports.calculation_repository,
            filing_repository=ModeloRecordCatalogueRepository(bucket_id=profile_id),
            clock=now,
            account_session_reader=account_session_reader,
            transaction_repository=ledger_action_ports.transaction_repository,
            invoice_repository=ledger_action_ports.invoice_repository,
            bucket_event_repository=ledger_action_ports.bucket_event_repository,
            ledger_action_ports=ledger_action_ports,
            verification_repository=VerificationReportCatalogueRepository(bucket_id=profile_id),
            notification_custody_reader=_notification_custody_reader(profile_id),
            result_casilla_reader=_declaration_result_casilla_reader(operation),
            operation_contracts=operation_contracts,
            modelo_projection_reader=_modelo_projection_reader(operation),
        )

    def capture() -> WorkbenchGenerationV1:
        # Ledger ports capture current evidence; keep them per generation.
        account_session_reader()
        return InstalledWorkbenchGenerationProviderV1(read_door())()

    return capture


def _notification_custody_reader(profile_id: str) -> Callable[[], int]:
    """Count this profile's existing notification snapshots without bytes."""

    def read() -> int:
        from ..adapters.persistence.profile.notification_documents import notification_document_repository
        from ..core.config import load_settings

        return len(notification_document_repository(profile_id, load_settings()).list_snapshots())

    return read


def _declaration_result_casilla_reader(
    operation: PinnedAuthorityOperation,
) -> Callable[[str, int, Period], str | None]:
    """Resolve the selected result casilla through the pinned authority."""

    def read(modelo: str, filing_year: int, period: Period) -> str | None:
        from ..application.modelo.settlement_casilla import declaration_result_casilla_id

        snapshot = operation.snapshot(str(modelo), filing_year=filing_year, period=period.registry_token)
        return declaration_result_casilla_id(snapshot.revision)

    return read


def _modelo_projection_reader(
    operation: PinnedAuthorityOperation,
) -> Callable[[WorkUnit], ModeloWorkspaceProjectedReadV1]:
    """Try graded first and retain its typed refusal on static fallback."""
    from ..application.modelo.workspace_models import ModeloWorkspaceRefusedResultV1
    from ..core.authority_grade import RegistryAuthorityGrade
    from ..core.external_constants import OutputLanguage
    from ..core.i18n.render import output_language as resolve_output_language

    def project(unit: WorkUnit) -> ModeloWorkspaceProjectedReadV1:
        language = OutputLanguage(resolve_output_language())
        result = resolve_modelo_workspace_graded_snapshot(
            unit,
            operation=operation,
            output_language=language,
            required_grade=RegistryAuthorityGrade.CALCULATION,
        )
        if isinstance(result, ModeloWorkspaceRefusedResultV1):
            static = resolve_modelo_workspace_static_inspection(
                unit,
                operation=operation,
                output_language=language,
            )
            return ModeloWorkspaceProjectedReadV1(projection=static.projection, graded_refusal=result.refusal)
        return ModeloWorkspaceProjectedReadV1(projection=result.projection)

    return project


def resolve_modelo_workspace_static_inspection(
    unit: WorkUnit, *, operation: PinnedAuthorityOperation, output_language: OutputLanguage
) -> ModeloWorkspaceStaticInspectionResultV1:
    """Read one exact work unit at static inspection admission."""
    from ..adapters.persistence.profile.modelos_work_units import WorkUnitCatalogueRepository
    from ..application.modelo.work_addressing import ModeloExactWorkUnitTarget
    from ..application.modelo.workspace import resolve_static_inspection_result
    from ..application.modelo.workspace_models import ModeloWorkspaceExactWorkUnitTargetV1

    return resolve_static_inspection_result(
        ModeloWorkspaceExactWorkUnitTargetV1(
            target=ModeloExactWorkUnitTarget(work_unit_id=unit.work_unit_id, bucket_id=unit.bucket_id)
        ),
        bucket_id=unit.bucket_id,
        catalogue_repository=WorkUnitCatalogueRepository(bucket_id=unit.bucket_id),
        authority=operation,
        output_language=output_language,
    )


def resolve_modelo_workspace_graded_snapshot(
    unit: WorkUnit,
    *,
    operation: PinnedAuthorityOperation,
    output_language: OutputLanguage,
    required_grade: RegistryAuthorityGrade,
) -> ModeloWorkspaceResultV1:
    """Read one exact work unit at graded admission or retain its refusal."""
    from ..adapters.persistence.profile.modelos_work_units import WorkUnitCatalogueRepository
    from ..application.modelo.work_addressing import ModeloExactWorkUnitTarget
    from ..application.modelo.workspace import resolve_graded_snapshot_result
    from ..application.modelo.workspace_models import ModeloWorkspaceExactWorkUnitTargetV1
    from .adapter_composition import (
        build_calculation_action_ports,
        build_diagnostics_ports,
        build_state_projection_read_ports,
    )

    return resolve_graded_snapshot_result(
        ModeloWorkspaceExactWorkUnitTargetV1(
            target=ModeloExactWorkUnitTarget(work_unit_id=unit.work_unit_id, bucket_id=unit.bucket_id)
        ),
        required_grade=required_grade,
        bucket_id=unit.bucket_id,
        catalogue_repository=WorkUnitCatalogueRepository(bucket_id=unit.bucket_id),
        calculation_ports=build_calculation_action_ports(bucket_id=unit.bucket_id, operation=operation),
        readiness_read_ports=build_state_projection_read_ports(
            diagnostics_ports=build_diagnostics_ports(bucket_id=unit.bucket_id)
        ),
        operation=operation,
        output_language=output_language,
    )


__all__ = [
    "compose_secure_workbench_generation_provider",
    "resolve_modelo_workspace_graded_snapshot",
    "resolve_modelo_workspace_static_inspection",
]
