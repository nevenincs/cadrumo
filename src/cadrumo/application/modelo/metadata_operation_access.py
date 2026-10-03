"""Resolve metadata-operation scope from the addressed persisted work unit."""

from __future__ import annotations

from pydantic import BaseModel

from ...core.operations import profile_operation_subject
from ...core.period import Period
from ...domain.modelos.work_unit import WorkUnit
from ..operations.access_port import OperationAccessResolver
from ..operations.access_resolution import (
    ADMISSION_REPLAY_ACTIONS,
    COMMITTING_LIFECYCLE_SELECTED_PERIODS_REGISTERED_RESULT_TAX_VALUES_ACCESS,
    OperationAccessContext,
    ResolvedOperationAccess,
    bind_operation_access_profile,
    require_single_period_admission,
)
from ..operations.models import OperationRequest
from ..user_profile.access_contracts import (
    AccessDenialCode,
    OperationAccessRequest,
)
from ..user_profile.access_errors import ProfileAccessRefusedError
from .m303_attestation_operation import (
    MODELO_WORK_M303_ATTESTATION_OPERATION_DEFINITION_ID,
    ModeloWorkM303AttestationRequest,
)
from .operation_definitions import (
    MODELO_EDIT_APPLY_OPERATION_DEFINITION_ID,
    MODELO_WORK_CALCULATE_OPERATION_DEFINITION_ID,
    MODELO_WORK_DISCARD_OPERATION_DEFINITION_ID,
    MODELO_WORK_RENAME_OPERATION_DEFINITION_ID,
    ModeloEditApplyOperationRequestV1,
    ModeloWorkCalculateRequest,
    ModeloWorkDiscardRequest,
    ModeloWorkRenameRequest,
)
from .work_lifecycle import get_work_unit
from .work_lifecycle_ports import ActiveWorkLifecyclePortsFactory


def compose_modelo_metadata_access(ports_factory: ActiveWorkLifecyclePortsFactory) -> OperationAccessResolver:
    """Bind the canonical work-unit reader without treating a supplied ID as scope."""

    def resolve(request: OperationRequest[BaseModel], context: OperationAccessContext, /) -> ResolvedOperationAccess:
        work_unit_id, explicit_periods = _metadata_target(request, context)
        if explicit_periods is not None:
            return _resolved_access(request, context, explicit_periods)
        if work_unit_id is None or request.subject_ref != work_unit_id:
            raise ProfileAccessRefusedError(AccessDenialCode.OPERATION_DENIED)
        periods = _persisted_metadata_periods(ports_factory, request.payload, context, work_unit_id)
        return _resolved_access(request, context, periods)

    return resolve


def _metadata_target(
    request: OperationRequest[BaseModel], context: OperationAccessContext
) -> tuple[str | None, frozenset[Period] | None]:
    target = _rename_target(request)
    if target is not None:
        return target, None
    target = _discard_target(request)
    if target is not None:
        return target, None
    target = _calculate_target(request)
    if target is not None:
        return target, None
    target = _edit_target(request, context)
    if target is not None:
        return target, None
    attestation = _m303_attestation_target(request, context)
    if attestation is not None:
        return attestation
    raise ProfileAccessRefusedError(AccessDenialCode.OPERATION_UNAVAILABLE)


def _rename_target(request: OperationRequest[BaseModel]) -> str | None:
    payload = request.payload
    if request.definition_id == MODELO_WORK_RENAME_OPERATION_DEFINITION_ID and isinstance(
        payload, ModeloWorkRenameRequest
    ):
        return payload.work_unit_id
    return None


def _discard_target(request: OperationRequest[BaseModel]) -> str | None:
    payload = request.payload
    if request.definition_id == MODELO_WORK_DISCARD_OPERATION_DEFINITION_ID and isinstance(
        payload, ModeloWorkDiscardRequest
    ):
        return payload.baseline.work_unit_id
    return None


def _calculate_target(request: OperationRequest[BaseModel]) -> str | None:
    payload = request.payload
    if request.definition_id == MODELO_WORK_CALCULATE_OPERATION_DEFINITION_ID and isinstance(
        payload, ModeloWorkCalculateRequest
    ):
        return payload.work_unit_id
    return None


def _edit_target(request: OperationRequest[BaseModel], context: OperationAccessContext) -> str | None:
    payload = request.payload
    if request.definition_id != MODELO_EDIT_APPLY_OPERATION_DEFINITION_ID or not isinstance(
        payload, ModeloEditApplyOperationRequestV1
    ):
        return None
    baseline = payload.submission.baseline
    if baseline.bucket_id != str(context.profile_id):
        raise ProfileAccessRefusedError(AccessDenialCode.PROFILE_MISMATCH)
    return baseline.work_unit_id


def _m303_attestation_target(
    request: OperationRequest[BaseModel], context: OperationAccessContext
) -> tuple[str | None, frozenset[Period] | None] | None:
    payload = request.payload
    if request.definition_id != MODELO_WORK_M303_ATTESTATION_OPERATION_DEFINITION_ID or not isinstance(
        payload, ModeloWorkM303AttestationRequest
    ):
        return None
    return _attestation_target(request, context, payload)


def _attestation_target(
    request: OperationRequest[BaseModel],
    context: OperationAccessContext,
    payload: ModeloWorkM303AttestationRequest,
) -> tuple[str | None, frozenset[Period] | None]:
    if payload.profile_id != context.profile_id:
        raise ProfileAccessRefusedError(AccessDenialCode.PROFILE_MISMATCH)
    if request.subject_ref != payload.subject_ref:
        raise ProfileAccessRefusedError(AccessDenialCode.OPERATION_DENIED)
    admitted = context.admitted_request
    if admitted is not None and context.action in ADMISSION_REPLAY_ACTIONS:
        return None, _admitted_attestation_periods(admitted, request, context, payload)
    if payload.period is not None:
        if request.subject_ref != profile_operation_subject(str(context.profile_id)):
            raise ProfileAccessRefusedError(AccessDenialCode.OPERATION_DENIED)
        return None, frozenset({payload.period.to_period()})
    return payload.work_unit_id, None


def _admitted_attestation_periods(
    admitted: OperationAccessRequest,
    request: OperationRequest[BaseModel],
    context: OperationAccessContext,
    payload: ModeloWorkM303AttestationRequest,
) -> frozenset[Period]:
    periods = require_single_period_admission(
        admitted, profile_id=context.profile_id, definition_id=request.definition_id
    )
    if payload.period is not None and periods != frozenset({payload.period.to_period()}):
        raise ProfileAccessRefusedError(AccessDenialCode.OPERATION_UNAVAILABLE)
    return periods


def _persisted_metadata_periods(
    ports_factory: ActiveWorkLifecyclePortsFactory,
    payload: BaseModel,
    context: OperationAccessContext,
    work_unit_id: str,
) -> frozenset[Period]:
    ports = ports_factory()
    if ports.work_unit_repository.bucket_id != str(context.profile_id):
        raise ProfileAccessRefusedError(AccessDenialCode.PROFILE_MISMATCH)
    unit = get_work_unit(work_unit_id, ports=ports)
    if unit.bucket_id != str(context.profile_id):
        raise ProfileAccessRefusedError(AccessDenialCode.PROFILE_MISMATCH)
    _require_edit_baseline_coordinates(payload, unit)
    return frozenset({unit.period})


def _require_edit_baseline_coordinates(payload: BaseModel, unit: WorkUnit) -> None:
    if not isinstance(payload, ModeloEditApplyOperationRequestV1):
        return
    baseline = payload.submission.baseline
    if (
        baseline.modelo != unit.modelo
        or baseline.filing_year != unit.filing_year
        or baseline.period_filing_year != unit.period.filing_year
        or baseline.period_code != unit.period.code
    ):
        raise ProfileAccessRefusedError(AccessDenialCode.OPERATION_DENIED)


def _resolved_access(
    request: OperationRequest[BaseModel], context: OperationAccessContext, periods: frozenset[Period]
) -> ResolvedOperationAccess:
    return bind_operation_access_profile(
        context,
        COMMITTING_LIFECYCLE_SELECTED_PERIODS_REGISTERED_RESULT_TAX_VALUES_ACCESS,
        profile_id=context.profile_id,
        definition_id=request.definition_id,
        periods=periods,
    )
