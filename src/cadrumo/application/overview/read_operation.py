"""Registered exact-profile overview reads over canonical capture ports."""

from __future__ import annotations

from functools import partial

from pydantic import BaseModel

from ...core.bucket_pointer import require_active_bucket_id
from ...core.config import override_settings
from ...core.operations import profile_operation_subject
from ...core.period import Period
from ...domain.calculations.registry.authority import PinnedAuthorityOperation
from ..ledger.read_access import resolve_ledger_read_access
from ..operations.access_resolution import OperationAccessContext, ResolvedOperationAccess
from ..operations.capabilities import RECORDED_IDEMPOTENT_JOURNALED_READ_CAPABILITIES
from ..operations.models import OperationRequest
from ..operations.operation_definition import OperationDefinition, OperationExecutorFactory
from ..operations.owner import OperationExecutorContext
from ..operations.read_capture import capture_read_result
from ..operations.registry import (
    ALL_OPERATION_FRONTENDS,
    OperationPublicDefinitionRegistrationV1,
    OperationReconciliationPolicy,
)
from ..user_profile.access_contracts import AccessDenialCode
from ..user_profile.access_errors import ProfileAccessRefusedError
from .read_ports import OverviewReadPortsFactory
from .read_request import (
    OVERVIEW_READ_DEFINITION_IDS as _OVERVIEW_READ_DEFINITION_IDS,
)
from .read_request import (
    OverviewReadKind as _OverviewReadKind,
)
from .read_request import (
    OverviewReadRequest as _OverviewReadRequest,
)
from .read_result import (
    OverviewReadProjection as _OverviewReadProjection,
)
from .read_result import (
    OverviewReadResult as _OverviewReadResult,
)
from .read_result import (
    project_overview_read_result as _project_overview_read_result,
)


class OverviewReadExecutor:
    """Capture one selected canonical overview report in the profile worker."""

    def __init__(self, factory: OverviewReadPortsFactory, definition_id: str) -> None:
        """Hold only the profile-bound read factory and operation identity."""
        self._factory = factory
        self._definition_id = definition_id

    def _capture(self, payload: _OverviewReadRequest, operation: PinnedAuthorityOperation) -> _OverviewReadResult:
        bucket_id = str(payload.profile_id)
        ports = self._factory(bucket_id=bucket_id, operation=operation)
        if ports.bucket_id != bucket_id:
            raise ProfileAccessRefusedError(AccessDenialCode.PROFILE_MISMATCH)
        with override_settings(cadrumo_output_language=payload.output_language.value):
            projection = ports.capture(payload, operation=operation)
        return _OverviewReadResult(profile_id=payload.profile_id, request=payload, payload=projection)

    async def execute(self, request: OperationRequest[_OverviewReadRequest], context: OperationExecutorContext) -> str:
        """Retain cancellation ownership through capture and encrypted publication."""
        payload = request.payload
        if (
            request.definition_id != self._definition_id
            or self._definition_id != _OVERVIEW_READ_DEFINITION_IDS[payload.kind]
            or request.subject_ref != profile_operation_subject(str(payload.profile_id))
            or context.identity.definition_id != request.definition_id
            or context.identity.subject_ref != request.subject_ref
            or require_active_bucket_id() != str(payload.profile_id)
        ):
            raise ProfileAccessRefusedError(AccessDenialCode.PROFILE_MISMATCH)
        await context.events.phase(self._definition_id)

        return await capture_read_result(
            context, partial(self._capture, payload, context.authority_operation), task_name="overview-read"
        )


def build_overview_read_definition(kind: _OverviewReadKind, factory: OverviewReadPortsFactory) -> OperationDefinition:
    """Build one installed overview leaf over the shared exact-profile seam."""
    definition_id = _OVERVIEW_READ_DEFINITION_IDS[kind]
    return OperationDefinition(
        definition_id=definition_id,
        request_type=_OverviewReadRequest,
        result_type=_OverviewReadResult,
        executor_factory=OperationExecutorFactory(
            request_type=_OverviewReadRequest,
            executor_type=OverviewReadExecutor,
            build=lambda: OverviewReadExecutor(factory, definition_id),
        ),
        phase_codes=(definition_id,),
        interaction_kinds=frozenset(),
        capabilities=RECORDED_IDEMPOTENT_JOURNALED_READ_CAPABILITIES,
        reconciliation_policy=OperationReconciliationPolicy.INTERRUPT,
        permitted_frontends=ALL_OPERATION_FRONTENDS,
    )


def resolve_overview_read_access(
    request: OperationRequest[BaseModel], context: OperationAccessContext, /
) -> ResolvedOperationAccess:
    """Require whole-profile consent except for exact period status/preparation."""
    payload = request.payload
    if (
        not isinstance(payload, _OverviewReadRequest)
        or request.definition_id != _OVERVIEW_READ_DEFINITION_IDS[payload.kind]
    ):
        raise ProfileAccessRefusedError(AccessDenialCode.OPERATION_UNAVAILABLE)
    periods: frozenset[Period] = frozenset[Period]()
    if payload.period is not None and payload.kind in {_OverviewReadKind.STATUS, _OverviewReadKind.PREPARE}:
        periods = frozenset({payload.period.to_period()})
    return resolve_ledger_read_access(request, context, profile_id=payload.profile_id, periods=periods)


def build_overview_read_registration(definition: OperationDefinition) -> OperationPublicDefinitionRegistrationV1:
    """Bind one named leaf to exact request and independent result schemas."""
    if definition.definition_id not in _OVERVIEW_READ_DEFINITION_IDS.values():
        raise ValueError("unrecognized overview read definition")
    return OperationPublicDefinitionRegistrationV1.compose_request_result(
        definition=definition,
        public_result_type=_OverviewReadProjection,
        result_projector=_project_overview_read_result,
        access_resolver=resolve_overview_read_access,
    )


__all__ = [
    "build_overview_read_definition",
    "build_overview_read_registration",
]
