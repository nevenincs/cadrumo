"""Compose the canonical secure workbench generation outside any frontend."""

from __future__ import annotations

import asyncio
from collections.abc import Callable
from typing import TYPE_CHECKING
from uuid import UUID

from ..application.workbench_generation import (
    InstalledWorkbenchGenerationProviderV1,
)
from ..application.workbench_generation_contracts import WorkbenchGenerationV1
from ..application.workbench_generation_reader import SecureProfileWorkbenchGenerationReadDoorV1

if TYPE_CHECKING:
    from ..application.modelo.workspace_models import (
        ModeloWorkspaceProjectionV1,
        ModeloWorkspaceRefusedResultV1,
        ModeloWorkspaceResultV1,
        ModeloWorkspaceStaticInspectionResultV1,
    )
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
    from ..adapters.persistence.profile.modelo_reconciliation import ModeloReconciliationRecordRepository
    from ..adapters.persistence.profile.modelos_filing import ModeloRecordCatalogueRepository
    from ..adapters.persistence.storage.runtime_repository import secure_object_repository_for_bucket
    from ..application.user_profile.profile_record_repository import ProfileRecordRepository
    from ..core.time.clock import now
    from .calculation_revision_composition import bind_calculation_revision_persistence_from_profile
    from .calendar_evidence_composition import compose_calendar_aeat_reader
    from .censal_readback_composition import read_stored_censal_observation
    from .ledger_action_composition import compose_ledger_action_ports

    account_session_reader()
    calendar_aeat_reader = compose_calendar_aeat_reader(operation)
    objects = secure_object_repository_for_bucket(profile_id)
    calculation_binding = bind_calculation_revision_persistence_from_profile(
        bucket_id=profile_id,
        objects=objects,
        operation=operation,
    )

    def read_door() -> SecureProfileWorkbenchGenerationReadDoorV1:
        ledger_action_ports = compose_ledger_action_ports(bucket_id=profile_id, operation=operation, objects=objects)
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
            verification_repository=calculation_binding.verification_repository(),
            reconciliation_reader=lambda: tuple(ModeloReconciliationRecordRepository(objects=objects).iter_records()),
            notification_custody_reader=_notification_custody_reader(profile_id),
            census_observation_reader=lambda: asyncio.run(read_stored_censal_observation(UUID(profile_id))),
            result_casilla_reader=_declaration_result_casilla_reader(operation),
            operation_contracts=operation_contracts,
            modelo_projection_reader=modelo_workspace_projection_reader(operation),
            calendar_aeat_reader=calendar_aeat_reader,
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
    """Name the casilla that settles one modelo revision, through the pinned authority.

    Resolution failures are answered with ``None`` rather than raised. A modelo
    or period the registry cannot select is a declaration whose result is
    UNKNOWN, which is exactly what the surface renders; letting it escape would
    take down a Home and Declarations read over a figure that is one column of
    one row.
    """

    def read(modelo: str, filing_year: int, period: Period) -> str | None:
        from ..application.modelo.settlement_casilla import declaration_result_casilla_id
        from ..core.errors.hierarchy import CadrumoError

        try:
            snapshot = operation.snapshot(str(modelo), filing_year=filing_year, period=period.registry_token)
            return declaration_result_casilla_id(snapshot.revision)
        except (CadrumoError, ValueError, LookupError):
            return None

    return read


MODELO_WORKSPACE_READ_ATTEMPTS = 3
"""Reads of one work unit before a declaration that keeps changing is reported."""


def modelo_workspace_projection_reader(
    operation: PinnedAuthorityOperation,
) -> Callable[[WorkUnit], ModeloWorkspaceProjectionV1]:
    """Read one work unit's canonical workspace projection for the generation.

    The read the workbench search indexes each declaration from. The output
    language is resolved per read rather than closed over, so a profile
    language change is honoured by the next capture.

    GRADED FIRST, static inspection second, and the order is the product
    behaviour rather than an optimisation. A graded snapshot is the admission
    that carries materialized values, their provenance and the canonical
    readiness report; a static inspection carries the form's layout and says
    plainly that it measured no values. Asking for the static one first would
    index a calculated declaration as if nothing had been measured.

    The graded arm is MATCHED, never assumed: a target with no calculation
    yet, or a revision whose declared authority cannot satisfy the requested
    grade, is answered with a typed refusal rather than an exception, and this
    seam answers it by reading the same target at the admission that CAN
    answer. Every taxpayer-facing refusal the graded resolver returns leaves
    the revision resolvable at static inspection's lower admission.

    A read whose stored data moved between its captures and its currentness
    pass refuses as ``WORKSPACE_CHANGED``; that is no answer about the
    declaration, so the unit is read again, at most
    :data:`MODELO_WORKSPACE_READ_ATTEMPTS` times, and a unit that never holds
    still raises the contended :class:`ProducerCaptureError` rather than
    retrying without limit.
    """
    from ..application.modelo.workspace_models import ModeloWorkspaceRefusalCode, ModeloWorkspaceRefusedResultV1
    from ..application.producer_capture import ProducerCaptureError
    from ..core.authority_grade import RegistryAuthorityGrade
    from ..core.errors.hierarchy import InternalInvariantError
    from ..core.external_constants import OutputLanguage
    from ..core.i18n.render import output_language as resolve_output_language

    def project(unit: WorkUnit) -> ModeloWorkspaceProjectionV1:
        for _attempt in range(MODELO_WORKSPACE_READ_ATTEMPTS):
            language = OutputLanguage(resolve_output_language())
            admission = resolve_modelo_workspace_graded_snapshot(
                unit,
                operation=operation,
                output_language=language,
                required_grade=RegistryAuthorityGrade.CALCULATION,
            )
            if not isinstance(admission, ModeloWorkspaceRefusedResultV1):
                return admission.projection
            if admission.refusal.code is ModeloWorkspaceRefusalCode.WORKSPACE_CHANGED:
                continue
            static = resolve_modelo_workspace_static_inspection(
                unit,
                operation=operation,
                output_language=language,
            )
            if isinstance(static, ModeloWorkspaceRefusedResultV1):
                if static.refusal.code is not ModeloWorkspaceRefusalCode.WORKSPACE_CHANGED:
                    raise InternalInvariantError(f"static inspection refused with {static.refusal.code.value}")
                continue
            return static.projection
        raise ProducerCaptureError(
            translated_message="errors.refused.producer_capture_not_current",
            context={"reason": "contended", "attempts": MODELO_WORKSPACE_READ_ATTEMPTS},
        )

    return project


def resolve_modelo_workspace_static_inspection(
    unit: WorkUnit, *, operation: PinnedAuthorityOperation, output_language: OutputLanguage
) -> ModeloWorkspaceStaticInspectionResultV1 | ModeloWorkspaceRefusedResultV1:
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
    from ..adapters.persistence.storage.runtime_repository import secure_object_repository_for_bucket
    from ..application.modelo.work_addressing import ModeloExactWorkUnitTarget
    from ..application.modelo.workspace import resolve_graded_snapshot_result
    from ..application.modelo.workspace_models import ModeloWorkspaceExactWorkUnitTargetV1
    from .adapter_composition import (
        build_calculation_action_ports,
        build_diagnostics_ports,
        build_state_projection_read_ports,
    )
    from .calculation_revision_composition import bind_calculation_revision_persistence_from_profile

    objects = secure_object_repository_for_bucket(unit.bucket_id)
    calculation_binding = bind_calculation_revision_persistence_from_profile(
        bucket_id=unit.bucket_id,
        objects=objects,
        operation=operation,
    )

    return resolve_graded_snapshot_result(
        ModeloWorkspaceExactWorkUnitTargetV1(
            target=ModeloExactWorkUnitTarget(work_unit_id=unit.work_unit_id, bucket_id=unit.bucket_id)
        ),
        required_grade=required_grade,
        bucket_id=unit.bucket_id,
        catalogue_repository=WorkUnitCatalogueRepository(bucket_id=unit.bucket_id),
        calculation_ports=build_calculation_action_ports(
            bucket_id=unit.bucket_id, operation=operation, objects=objects
        ),
        verification_repository=calculation_binding.verification_repository(),
        readiness_read_ports=build_state_projection_read_ports(
            diagnostics_ports=build_diagnostics_ports(bucket_id=unit.bucket_id),
            operation=operation,
            objects=objects,
            bucket_id=unit.bucket_id,
        ),
        operation=operation,
        output_language=output_language,
    )


__all__ = [
    "MODELO_WORKSPACE_READ_ATTEMPTS",
    "compose_secure_workbench_generation_provider",
    "modelo_workspace_projection_reader",
    "resolve_modelo_workspace_graded_snapshot",
    "resolve_modelo_workspace_static_inspection",
]
