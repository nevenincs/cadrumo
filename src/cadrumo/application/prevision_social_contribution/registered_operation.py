"""Registration and access wiring for the pension contribution certificate operations."""

from __future__ import annotations

from dataclasses import dataclass

from pydantic import BaseModel

from ..ledger.read_access import resolve_ledger_exact_request_access
from ..operations.access_resolution import OperationAccessContext, ResolvedOperationAccess
from ..operations.capabilities import (
    RECORDED_IDEMPOTENT_SECURE_INPUT_PARTIAL_UPDATE_CAPABILITIES,
    RECORDED_IDEMPOTENT_SECURE_INPUT_READ_CAPABILITIES,
    RECORDED_IDEMPOTENT_SECURE_INPUT_UPDATE_CAPABILITIES,
    OperationCapabilities,
)
from ..operations.models import OperationRequest
from ..operations.operation_definition import OperationDefinition, build_single_phase_definition
from ..operations.registry import OperationPublicDefinitionRegistrationV1, OperationResultProjector
from ..operations.subject_reference import OperationSubjectReferenceV1
from .contracts import (
    PREVISION_SOCIAL_LIST_OPERATION_DEFINITION_ID,
    PREVISION_SOCIAL_RECORD_OPERATION_DEFINITION_ID,
    PREVISION_SOCIAL_REFUSAL_CODES,
    PREVISION_SOCIAL_REMOVE_OPERATION_DEFINITION_ID,
)
from .executor import PrevisionSocialContributionExecutor
from .ports import PrevisionSocialPortsFactory
from .projections import project_prevision_social_list_result, project_prevision_social_mutation_result
from .requests import PrevisionSocialListRequest, PrevisionSocialRecordRequest, PrevisionSocialRemoveRequest
from .results import (
    PrevisionSocialListProjection,
    PrevisionSocialMutationProjection,
    PrevisionSocialOperationExecutionResult,
)


@dataclass(frozen=True, slots=True)
class _OperationShape:
    request_type: type[BaseModel]
    projection_type: type[BaseModel]
    refusal_codes: frozenset[str]
    mutation: bool
    keeps_certificate_bytes: bool = False
    """Whether the operation can keep certificate bytes in custody before it refuses the record."""


_SHAPES: dict[str, _OperationShape] = {
    PREVISION_SOCIAL_LIST_OPERATION_DEFINITION_ID: _OperationShape(
        PrevisionSocialListRequest, PrevisionSocialListProjection, frozenset(), mutation=False
    ),
    PREVISION_SOCIAL_RECORD_OPERATION_DEFINITION_ID: _OperationShape(
        PrevisionSocialRecordRequest,
        PrevisionSocialMutationProjection,
        PREVISION_SOCIAL_REFUSAL_CODES,
        mutation=True,
        keeps_certificate_bytes=True,
    ),
    PREVISION_SOCIAL_REMOVE_OPERATION_DEFINITION_ID: _OperationShape(
        PrevisionSocialRemoveRequest,
        PrevisionSocialMutationProjection,
        PREVISION_SOCIAL_REFUSAL_CODES,
        mutation=True,
    ),
}


def resolve_prevision_social_operation_access(
    request: OperationRequest[BaseModel],
    context: OperationAccessContext,
    /,
) -> ResolvedOperationAccess:
    """Bind each contribution operation to the exact profile and its all-period scope."""
    return resolve_ledger_exact_request_access(
        request,
        context,
        request_types={definition_id: shape.request_type for definition_id, shape in _SHAPES.items()},
        commit_definition_ids=frozenset(definition_id for definition_id, shape in _SHAPES.items() if shape.mutation),
    )


def _capabilities(shape: _OperationShape) -> OperationCapabilities:
    if shape.keeps_certificate_bytes:
        return RECORDED_IDEMPOTENT_SECURE_INPUT_PARTIAL_UPDATE_CAPABILITIES
    if shape.mutation:
        return RECORDED_IDEMPOTENT_SECURE_INPUT_UPDATE_CAPABILITIES
    return RECORDED_IDEMPOTENT_SECURE_INPUT_READ_CAPABILITIES


def _definition(definition_id: str, ports_factory: PrevisionSocialPortsFactory) -> OperationDefinition:
    shape = _SHAPES[definition_id]
    return build_single_phase_definition(
        definition_id=definition_id,
        request_type=shape.request_type,
        subject_reference=OperationSubjectReferenceV1.profile(),
        result_type=PrevisionSocialOperationExecutionResult,
        executor_type=PrevisionSocialContributionExecutor,
        build=lambda: PrevisionSocialContributionExecutor(ports_factory, definition_id=definition_id),
        capabilities=_capabilities(shape),
        refusal_detail_codes=shape.refusal_codes,
    )


def _registration(
    definition: OperationDefinition, projector: OperationResultProjector
) -> OperationPublicDefinitionRegistrationV1:
    return OperationPublicDefinitionRegistrationV1.compose_request_result(
        definition=definition,
        public_result_type=_SHAPES[definition.definition_id].projection_type,
        result_projector=projector,
        access_resolver=resolve_prevision_social_operation_access,
    )


def build_prevision_social_list_definition(ports_factory: PrevisionSocialPortsFactory) -> OperationDefinition:
    """Build the per-ejercicio contribution-record list definition."""
    return _definition(PREVISION_SOCIAL_LIST_OPERATION_DEFINITION_ID, ports_factory)


def build_prevision_social_record_definition(ports_factory: PrevisionSocialPortsFactory) -> OperationDefinition:
    """Build the revision-guarded record-or-correct definition."""
    return _definition(PREVISION_SOCIAL_RECORD_OPERATION_DEFINITION_ID, ports_factory)


def build_prevision_social_remove_definition(ports_factory: PrevisionSocialPortsFactory) -> OperationDefinition:
    """Build the revision-guarded removal definition."""
    return _definition(PREVISION_SOCIAL_REMOVE_OPERATION_DEFINITION_ID, ports_factory)


def build_prevision_social_list_registration(
    definition: OperationDefinition,
) -> OperationPublicDefinitionRegistrationV1:
    """Bind the list projection to its disclosure guard."""
    return _registration(definition, project_prevision_social_list_result)


def build_prevision_social_mutation_registration(
    definition: OperationDefinition,
) -> OperationPublicDefinitionRegistrationV1:
    """Bind a record or removal projection and its typed refusal contract."""
    return _registration(definition, project_prevision_social_mutation_result)


__all__ = [
    "build_prevision_social_list_definition",
    "build_prevision_social_list_registration",
    "build_prevision_social_mutation_registration",
    "build_prevision_social_record_definition",
    "build_prevision_social_remove_definition",
    "resolve_prevision_social_operation_access",
]
