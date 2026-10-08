"""Registration and access wiring for capital-goods register operations."""

from __future__ import annotations

from dataclasses import (
    dataclass,
)

from pydantic import BaseModel

from ..ledger.read_access import resolve_ledger_read_access
from ..operations.access_resolution import OperationAccessContext, ResolvedOperationAccess, with_commit_action
from ..operations.capabilities import RECORDED_IDEMPOTENT_SECURE_INPUT_UPDATE_CAPABILITIES
from ..operations.models import OperationRequest
from ..operations.operation_definition import OperationDefinition, build_single_phase_definition
from ..operations.registry import (
    ALL_OPERATION_FRONTENDS,
    OperationPublicDefinitionRegistrationV1,
    OperationResultProjector,
)
from ..user_profile.access_contracts import (
    AccessDenialCode,
)
from ..user_profile.access_errors import ProfileAccessRefusedError
from .ports import BienesInversionIvaRegisterRepositoryFactory
from .registered_contracts import (
    BIENES_INVERSION_DECLARE_OPERATION_DEFINITION_ID,
    BIENES_INVERSION_LIST_OPERATION_DEFINITION_ID,
    BIENES_INVERSION_VALIDATION_REFUSAL_CODE,
)
from .registered_execution_result import BienesInversionOperationExecutionResult
from .registered_executor import BienesInversionOperationExecutor
from .registered_requests import (
    BienesInversionDeclareRequest,
    BienesInversionListRequest,
    BienesInversionProfileRequest,
)
from .registered_result_contracts import BienesInversionDeclareProjection, BienesInversionListProjection
from .registered_result_projection import project_bienes_inversion_declare_result, project_bienes_inversion_list_result


@dataclass(frozen=True, slots=True)
class _OperationShape:
    request_type: type[BaseModel]
    projection_type: type[BaseModel]
    refusal_codes: frozenset[str]


_SHAPES: dict[str, _OperationShape] = {
    BIENES_INVERSION_LIST_OPERATION_DEFINITION_ID: _OperationShape(
        request_type=BienesInversionListRequest,
        projection_type=BienesInversionListProjection,
        refusal_codes=frozenset(),
    ),
    BIENES_INVERSION_DECLARE_OPERATION_DEFINITION_ID: _OperationShape(
        request_type=BienesInversionDeclareRequest,
        projection_type=BienesInversionDeclareProjection,
        refusal_codes=frozenset({BIENES_INVERSION_VALIDATION_REFUSAL_CODE}),
    ),
}


def resolve_bienes_inversion_operation_access(
    request: OperationRequest[BaseModel],
    context: OperationAccessContext,
    /,
) -> ResolvedOperationAccess:
    """Bind list/declaration to the exact profile and all-period singleton scope."""
    shape = _SHAPES.get(request.definition_id)
    payload = request.payload
    if (
        shape is None
        or type(payload) is not shape.request_type
        or not isinstance(payload, BienesInversionProfileRequest)
    ):
        raise ProfileAccessRefusedError(AccessDenialCode.OPERATION_UNAVAILABLE)
    resolved = resolve_ledger_read_access(request, context, profile_id=payload.profile_id, periods=frozenset())
    if request.definition_id != BIENES_INVERSION_DECLARE_OPERATION_DEFINITION_ID:
        return resolved
    return with_commit_action(resolved)


def _definition(
    definition_id: str,
    request_type: type[BaseModel],
    repository_factory: BienesInversionIvaRegisterRepositoryFactory,
) -> OperationDefinition:
    shape = _SHAPES[definition_id]
    if shape.request_type is not request_type:
        raise ValueError("capital-goods operation request type does not match its registration")
    return build_single_phase_definition(
        definition_id=definition_id,
        request_type=request_type,
        result_type=BienesInversionOperationExecutionResult,
        executor_type=BienesInversionOperationExecutor,
        build=lambda: BienesInversionOperationExecutor(repository_factory, definition_id=definition_id),
        capabilities=RECORDED_IDEMPOTENT_SECURE_INPUT_UPDATE_CAPABILITIES,
        permitted_frontends=ALL_OPERATION_FRONTENDS,
        refusal_detail_codes=shape.refusal_codes,
    )


def _registration(
    definition: OperationDefinition,
    *,
    request_type: type[BaseModel],
    projection_type: type[BaseModel],
    projector: OperationResultProjector,
) -> OperationPublicDefinitionRegistrationV1:
    shape = _SHAPES[definition.definition_id]
    if shape.request_type is not request_type or shape.projection_type is not projection_type:
        raise ValueError("capital-goods registration does not match its closed schema")
    return OperationPublicDefinitionRegistrationV1.compose_request_result(
        definition=definition,
        public_result_type=projection_type,
        result_projector=projector,
        access_resolver=resolve_bienes_inversion_operation_access,
    )


def build_bienes_inversion_list_definition(
    repository_factory: BienesInversionIvaRegisterRepositoryFactory,
) -> OperationDefinition:
    """Build the all-profile capital-goods list definition."""
    return _definition(BIENES_INVERSION_LIST_OPERATION_DEFINITION_ID, BienesInversionListRequest, repository_factory)


def build_bienes_inversion_declare_definition(
    repository_factory: BienesInversionIvaRegisterRepositoryFactory,
) -> OperationDefinition:
    """Build the guarded capital-good declaration definition."""
    return _definition(
        BIENES_INVERSION_DECLARE_OPERATION_DEFINITION_ID,
        BienesInversionDeclareRequest,
        repository_factory,
    )


def build_bienes_inversion_list_registration(
    definition: OperationDefinition,
) -> OperationPublicDefinitionRegistrationV1:
    """Bind the complete list projection to its current disclosure guard."""
    return _registration(
        definition,
        request_type=BienesInversionListRequest,
        projection_type=BienesInversionListProjection,
        projector=project_bienes_inversion_list_result,
    )


def build_bienes_inversion_declare_registration(
    definition: OperationDefinition,
) -> OperationPublicDefinitionRegistrationV1:
    """Bind the declaration projection and typed refusal contract."""
    return _registration(
        definition,
        request_type=BienesInversionDeclareRequest,
        projection_type=BienesInversionDeclareProjection,
        projector=project_bienes_inversion_declare_result,
    )


__all__ = [
    "build_bienes_inversion_declare_definition",
    "build_bienes_inversion_declare_registration",
    "build_bienes_inversion_list_definition",
    "build_bienes_inversion_list_registration",
    "resolve_bienes_inversion_operation_access",
]
