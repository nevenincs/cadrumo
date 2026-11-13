"""Registration and access wiring for the Modelo 232 related-party statements."""

from __future__ import annotations

from pydantic import BaseModel

from ..ledger.read_access import resolve_ledger_exact_request_access
from ..operations.access_resolution import OperationAccessContext, ResolvedOperationAccess
from ..operations.capabilities import (
    RECORDED_IDEMPOTENT_SECURE_INPUT_READ_CAPABILITIES,
    RECORDED_IDEMPOTENT_SECURE_INPUT_UPDATE_CAPABILITIES,
)
from ..operations.models import OperationRequest
from ..operations.operation_definition import OperationDefinition, build_single_phase_definition
from ..operations.registry import OperationPublicDefinitionRegistrationV1
from ..operations.subject_reference import OperationSubjectReferenceV1
from .contracts import (
    M232_RELATED_PARTY_LIST_OPERATION_DEFINITION_ID,
    M232_RELATED_PARTY_REFUSAL_CODES,
    M232_RELATED_PARTY_WRITE_DEFINITION_IDS,
)
from .executor import M232_RELATED_PARTY_REQUEST_TYPES, Modelo232RelatedPartyExecutor
from .ports import Modelo232RelatedPartyPortsFactory
from .projections import project_m232_related_party_list_result, project_m232_related_party_result
from .results import (
    Modelo232RelatedPartyExecutionResult,
    Modelo232RelatedPartyListProjection,
    Modelo232RelatedPartyMutationProjection,
)

__all__ = [
    "build_m232_related_party_definition",
    "build_m232_related_party_list_registration",
    "build_m232_related_party_registration",
    "resolve_m232_related_party_operation_access",
]


def resolve_m232_related_party_operation_access(
    request: OperationRequest[BaseModel],
    context: OperationAccessContext,
    /,
) -> ResolvedOperationAccess:
    """Bind each related-party operation to the exact profile and all periods; only writes commit."""
    return resolve_ledger_exact_request_access(
        request,
        context,
        request_types=M232_RELATED_PARTY_REQUEST_TYPES,
        commit_definition_ids=M232_RELATED_PARTY_WRITE_DEFINITION_IDS,
    )


def build_m232_related_party_definition(
    definition_id: str, ports_factory: Modelo232RelatedPartyPortsFactory
) -> OperationDefinition:
    """Build the listing, or one revision-guarded statement or withdrawal, under ``definition_id``."""
    request_type = M232_RELATED_PARTY_REQUEST_TYPES[definition_id]
    is_list = definition_id == M232_RELATED_PARTY_LIST_OPERATION_DEFINITION_ID
    return build_single_phase_definition(
        definition_id=definition_id,
        request_type=request_type,
        subject_reference=OperationSubjectReferenceV1.profile(),
        result_type=Modelo232RelatedPartyExecutionResult,
        executor_type=Modelo232RelatedPartyExecutor,
        build=lambda: Modelo232RelatedPartyExecutor(ports_factory, definition_id=definition_id),
        capabilities=(
            RECORDED_IDEMPOTENT_SECURE_INPUT_READ_CAPABILITIES
            if is_list
            else RECORDED_IDEMPOTENT_SECURE_INPUT_UPDATE_CAPABILITIES
        ),
        refusal_detail_codes=frozenset() if is_list else M232_RELATED_PARTY_REFUSAL_CODES,
    )


def build_m232_related_party_list_registration(
    definition: OperationDefinition,
) -> OperationPublicDefinitionRegistrationV1:
    """Bind the listing projection to its disclosure guard."""
    return OperationPublicDefinitionRegistrationV1.compose_request_result(
        definition=definition,
        public_result_type=Modelo232RelatedPartyListProjection,
        result_projector=project_m232_related_party_list_result,
        access_resolver=resolve_m232_related_party_operation_access,
    )


def build_m232_related_party_registration(
    definition: OperationDefinition,
) -> OperationPublicDefinitionRegistrationV1:
    """Bind a statement or withdrawal projection and its typed refusal contract."""
    return OperationPublicDefinitionRegistrationV1.compose_request_result(
        definition=definition,
        public_result_type=Modelo232RelatedPartyMutationProjection,
        result_projector=project_m232_related_party_result,
        access_resolver=resolve_m232_related_party_operation_access,
    )
