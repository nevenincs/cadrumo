"""Resolve metadata-operation scope from the addressed persisted work unit."""

from __future__ import annotations

from pydantic import BaseModel

from ...core.operations import profile_operation_subject
from ...core.period import Period
from ..operations.access_port import OperationAccessResolver
from ..operations.access_resolution import OperationAccessContext, ResolvedOperationAccess
from ..operations.frontend_requests import OPERATION_OBSERVATION_PROJECTION_ID
from ..operations.models import OperationRequest
from ..user_profile.access_contracts import (
    AccessAction,
    AccessDenialCode,
    Availability,
    DisclosureCategory,
    DisclosurePermission,
    OperationAccessPolicy,
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
        payload = request.payload
        if request.definition_id == MODELO_WORK_RENAME_OPERATION_DEFINITION_ID and isinstance(
            payload, ModeloWorkRenameRequest
        ):
            work_unit_id = payload.work_unit_id
        elif request.definition_id == MODELO_WORK_DISCARD_OPERATION_DEFINITION_ID and isinstance(
            payload, ModeloWorkDiscardRequest
        ):
            work_unit_id = payload.baseline.work_unit_id
        elif request.definition_id == MODELO_WORK_CALCULATE_OPERATION_DEFINITION_ID and isinstance(
            payload, ModeloWorkCalculateRequest
        ):
            work_unit_id = payload.work_unit_id
        elif request.definition_id == MODELO_EDIT_APPLY_OPERATION_DEFINITION_ID and isinstance(
            payload, ModeloEditApplyOperationRequestV1
        ):
            baseline = payload.submission.baseline
            if baseline.bucket_id != str(context.profile_id):
                raise ProfileAccessRefusedError(AccessDenialCode.PROFILE_MISMATCH)
            work_unit_id = baseline.work_unit_id
        elif request.definition_id == MODELO_WORK_M303_ATTESTATION_OPERATION_DEFINITION_ID and isinstance(
            payload, ModeloWorkM303AttestationRequest
        ):
            if payload.profile_id != context.profile_id:
                raise ProfileAccessRefusedError(AccessDenialCode.PROFILE_MISMATCH)
            if request.subject_ref != payload.subject_ref:
                raise ProfileAccessRefusedError(AccessDenialCode.OPERATION_DENIED)
            admitted = context.admitted_request
            if admitted is not None and context.action in {
                AccessAction.OBSERVE,
                AccessAction.RESULT,
                AccessAction.CANCEL,
                AccessAction.DETACH,
            }:
                if (
                    admitted.profile_id != context.profile_id
                    or admitted.definition_id != request.definition_id
                    or admitted.action is not AccessAction.SUBMIT
                    or admitted.period_independent
                    or len(admitted.periods) != 1
                    or (payload.period is not None and admitted.periods != frozenset({payload.period.to_period()}))
                ):
                    raise ProfileAccessRefusedError(AccessDenialCode.OPERATION_UNAVAILABLE)
                return _resolved_access(request, context, admitted.periods)
            if payload.period is not None:
                if request.subject_ref != profile_operation_subject(str(context.profile_id)):
                    raise ProfileAccessRefusedError(AccessDenialCode.OPERATION_DENIED)
                return _resolved_access(request, context, frozenset({payload.period.to_period()}))
            work_unit_id = payload.work_unit_id
        else:
            raise ProfileAccessRefusedError(AccessDenialCode.OPERATION_UNAVAILABLE)
        if work_unit_id is None or request.subject_ref != work_unit_id:
            raise ProfileAccessRefusedError(AccessDenialCode.OPERATION_DENIED)
        ports = ports_factory()
        if ports.work_unit_repository.bucket_id != str(context.profile_id):
            raise ProfileAccessRefusedError(AccessDenialCode.PROFILE_MISMATCH)
        unit = get_work_unit(work_unit_id, ports=ports)
        if unit.bucket_id != str(context.profile_id):
            raise ProfileAccessRefusedError(AccessDenialCode.PROFILE_MISMATCH)
        if isinstance(payload, ModeloEditApplyOperationRequestV1):
            baseline = payload.submission.baseline
            if (
                baseline.modelo != unit.modelo
                or baseline.filing_year != unit.filing_year
                or baseline.period_filing_year != unit.period.filing_year
                or baseline.period_code != unit.period.code
            ):
                raise ProfileAccessRefusedError(AccessDenialCode.OPERATION_DENIED)
        periods = frozenset({unit.period})
        return _resolved_access(request, context, periods)

    return resolve


def _resolved_access(
    request: OperationRequest[BaseModel], context: OperationAccessContext, periods: frozenset[Period]
) -> ResolvedOperationAccess:
    disclosure = None
    if context.action in {AccessAction.OBSERVE, AccessAction.CANCEL, AccessAction.DETACH}:
        disclosure = DisclosurePermission(
            destination_id=context.destination_id,
            projection_id=OPERATION_OBSERVATION_PROJECTION_ID,
            category=DisclosureCategory.OPERATION_METADATA,
        )
    elif context.action is AccessAction.RESULT:
        schema = context.contract.result_schema
        if schema is None:
            raise ProfileAccessRefusedError(AccessDenialCode.OPERATION_UNAVAILABLE)
        disclosure = DisclosurePermission(
            destination_id=context.destination_id,
            projection_id=schema.schema_id,
            category=DisclosureCategory.TAX_VALUES,
        )
    return ResolvedOperationAccess(
        request=OperationAccessRequest(
            profile_id=context.profile_id,
            definition_id=request.definition_id,
            action=context.action,
            frontend=context.frontend,
            periods=periods,
            period_independent=False,
            destination_id=context.destination_id,
        ),
        policy=OperationAccessPolicy(
            definition_id=request.definition_id,
            definition_contract_digest=context.contract.definition_contract_digest,
            actions=frozenset(
                {
                    AccessAction.SUBMIT,
                    AccessAction.START,
                    AccessAction.RESUME,
                    AccessAction.COMMIT,
                    AccessAction.OBSERVE,
                    AccessAction.RESULT,
                    AccessAction.CANCEL,
                    AccessAction.DETACH,
                }
            ),
            disclosures=frozenset((disclosure,)) if disclosure is not None else frozenset(),
            periods=periods,
            allow_period_independent=False,
            backend=Availability.AVAILABLE,
            published_authority=context.published_authority,
            provider=Availability.NOT_REQUIRED,
            transaction_authority_required=False,
        ),
    )
