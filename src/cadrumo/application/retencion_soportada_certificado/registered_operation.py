"""Registration and access wiring for the suffered-withholding certificate operations."""

from __future__ import annotations

from dataclasses import dataclass

from pydantic import BaseModel

from cadrumo_client.contracts.access_refusals import AccessDenialCode

from ..ledger.read_access import resolve_ledger_read_access
from ..operations.access_resolution import OperationAccessContext, ResolvedOperationAccess, with_commit_action
from ..operations.capabilities import (
    RECORDED_IDEMPOTENT_SECURE_INPUT_READ_CAPABILITIES,
    RECORDED_IDEMPOTENT_SECURE_INPUT_UPDATE_CAPABILITIES,
)
from ..operations.models import OperationRequest
from ..operations.operation_definition import OperationDefinition, build_single_phase_definition
from ..operations.registry import OperationPublicDefinitionRegistrationV1, OperationResultProjector
from ..operations.subject_reference import OperationSubjectReferenceV1
from ..user_profile.access_errors import ProfileAccessRefusedError
from .contracts import (
    RETENCION_SOPORTADA_LIST_OPERATION_DEFINITION_ID,
    RETENCION_SOPORTADA_RECORD_OPERATION_DEFINITION_ID,
    RETENCION_SOPORTADA_REFUSAL_CODES,
    RETENCION_SOPORTADA_REMOVE_OPERATION_DEFINITION_ID,
)
from .executor import RetencionSoportadaCertificadoExecutor
from .ports import RetencionSoportadaCertificadoPortsFactory
from .projections import project_retencion_soportada_list_result, project_retencion_soportada_mutation_result
from .requests import (
    RetencionSoportadaListRequest,
    RetencionSoportadaProfileRequest,
    RetencionSoportadaRecordRequest,
    RetencionSoportadaRemoveRequest,
)
from .results import (
    RetencionSoportadaListProjection,
    RetencionSoportadaMutationProjection,
    RetencionSoportadaOperationExecutionResult,
)


@dataclass(frozen=True, slots=True)
class _OperationShape:
    request_type: type[BaseModel]
    projection_type: type[BaseModel]
    refusal_codes: frozenset[str]
    mutation: bool


_SHAPES: dict[str, _OperationShape] = {
    RETENCION_SOPORTADA_LIST_OPERATION_DEFINITION_ID: _OperationShape(
        RetencionSoportadaListRequest, RetencionSoportadaListProjection, frozenset(), mutation=False
    ),
    RETENCION_SOPORTADA_RECORD_OPERATION_DEFINITION_ID: _OperationShape(
        RetencionSoportadaRecordRequest,
        RetencionSoportadaMutationProjection,
        RETENCION_SOPORTADA_REFUSAL_CODES,
        mutation=True,
    ),
    RETENCION_SOPORTADA_REMOVE_OPERATION_DEFINITION_ID: _OperationShape(
        RetencionSoportadaRemoveRequest,
        RetencionSoportadaMutationProjection,
        RETENCION_SOPORTADA_REFUSAL_CODES,
        mutation=True,
    ),
}


def resolve_retencion_soportada_operation_access(
    request: OperationRequest[BaseModel],
    context: OperationAccessContext,
    /,
) -> ResolvedOperationAccess:
    """Bind each certificate operation to the exact profile and its all-period scope."""
    shape = _SHAPES.get(request.definition_id)
    payload = request.payload
    if shape is None or type(payload) is not shape.request_type:
        raise ProfileAccessRefusedError(AccessDenialCode.OPERATION_UNAVAILABLE)
    if not isinstance(payload, RetencionSoportadaProfileRequest):
        raise ProfileAccessRefusedError(AccessDenialCode.OPERATION_UNAVAILABLE)
    resolved = resolve_ledger_read_access(request, context, profile_id=payload.profile_id, periods=frozenset())
    return with_commit_action(resolved) if shape.mutation else resolved


def _definition(
    definition_id: str,
    ports_factory: RetencionSoportadaCertificadoPortsFactory,
) -> OperationDefinition:
    shape = _SHAPES[definition_id]
    return build_single_phase_definition(
        definition_id=definition_id,
        request_type=shape.request_type,
        subject_reference=OperationSubjectReferenceV1.profile(),
        result_type=RetencionSoportadaOperationExecutionResult,
        executor_type=RetencionSoportadaCertificadoExecutor,
        build=lambda: RetencionSoportadaCertificadoExecutor(ports_factory, definition_id=definition_id),
        capabilities=(
            RECORDED_IDEMPOTENT_SECURE_INPUT_UPDATE_CAPABILITIES
            if shape.mutation
            else RECORDED_IDEMPOTENT_SECURE_INPUT_READ_CAPABILITIES
        ),
        refusal_detail_codes=shape.refusal_codes,
    )


def _registration(
    definition: OperationDefinition, projector: OperationResultProjector
) -> OperationPublicDefinitionRegistrationV1:
    return OperationPublicDefinitionRegistrationV1.compose_request_result(
        definition=definition,
        public_result_type=_SHAPES[definition.definition_id].projection_type,
        result_projector=projector,
        access_resolver=resolve_retencion_soportada_operation_access,
    )


def build_retencion_soportada_list_definition(
    ports_factory: RetencionSoportadaCertificadoPortsFactory,
) -> OperationDefinition:
    """Build the per-ejercicio payer-record list definition."""
    return _definition(RETENCION_SOPORTADA_LIST_OPERATION_DEFINITION_ID, ports_factory)


def build_retencion_soportada_record_definition(
    ports_factory: RetencionSoportadaCertificadoPortsFactory,
) -> OperationDefinition:
    """Build the revision-guarded payer-certificate record definition."""
    return _definition(RETENCION_SOPORTADA_RECORD_OPERATION_DEFINITION_ID, ports_factory)


def build_retencion_soportada_remove_definition(
    ports_factory: RetencionSoportadaCertificadoPortsFactory,
) -> OperationDefinition:
    """Build the revision-guarded payer-record removal definition."""
    return _definition(RETENCION_SOPORTADA_REMOVE_OPERATION_DEFINITION_ID, ports_factory)


def build_retencion_soportada_list_registration(
    definition: OperationDefinition,
) -> OperationPublicDefinitionRegistrationV1:
    """Bind the list projection to its disclosure guard."""
    return _registration(definition, project_retencion_soportada_list_result)


def build_retencion_soportada_mutation_registration(
    definition: OperationDefinition,
) -> OperationPublicDefinitionRegistrationV1:
    """Bind a record or removal projection and its typed refusal contract."""
    return _registration(definition, project_retencion_soportada_mutation_result)


__all__ = [
    "build_retencion_soportada_list_definition",
    "build_retencion_soportada_list_registration",
    "build_retencion_soportada_mutation_registration",
    "build_retencion_soportada_record_definition",
    "build_retencion_soportada_remove_definition",
    "resolve_retencion_soportada_operation_access",
]
