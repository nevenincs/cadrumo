"""Exact-profile registered operations for the IVA prorrata register."""

from __future__ import annotations

from pydantic import BaseModel

from cadrumo_client.contracts.access_refusals import AccessDenialCode

from ..ledger.read_access import resolve_ledger_read_access
from ..modelo.calculation_action_ports import CalculationActionPortsFactory
from ..operations.access_resolution import OperationAccessContext, ResolvedOperationAccess, with_commit_action
from ..operations.capabilities import (
    RECORDED_IDEMPOTENT_SECURE_INPUT_READ_CAPABILITIES,
    RECORDED_IDEMPOTENT_SECURE_INPUT_UPDATE_CAPABILITIES,
)
from ..operations.models import OperationRequest
from ..operations.operation_definition import OperationDefinition, build_single_phase_definition
from ..operations.registry import (
    OperationPublicDefinitionRegistrationV1,
    OperationResultProjector,
)
from ..operations.subject_reference import OperationSubjectReferenceV1
from ..user_profile.access_errors import ProfileAccessRefusedError
from . import operation_requests, result_contracts
from .executor import ProrrataOperationExecutor
from .ports import ProrrataRegisterRepositoryFactory
from .projection_contracts import (
    ProrrataListProjection,
    ProrrataMutationProjection,
)
from .result_projections import (
    project_prorrata_list_result,
    project_prorrata_mutation_result,
)


def _shape_access(
    request: OperationRequest[BaseModel],
    context: OperationAccessContext,
    *,
    definition_id: str,
    mutation: bool,
) -> ResolvedOperationAccess:
    shape = result_contracts.prorrata_operation_contract(definition_id)
    payload = request.payload
    if shape is None or type(payload) is not shape.request_type:
        raise ProfileAccessRefusedError(AccessDenialCode.OPERATION_UNAVAILABLE)
    if request.definition_id != definition_id:
        raise ProfileAccessRefusedError(AccessDenialCode.OPERATION_UNAVAILABLE)
    if not isinstance(payload, operation_requests.ProrrataProfileRequest):
        raise ProfileAccessRefusedError(AccessDenialCode.OPERATION_UNAVAILABLE)
    resolved = resolve_ledger_read_access(request, context, profile_id=payload.profile_id, periods=frozenset())
    if not mutation:
        return resolved
    return with_commit_action(resolved)


def resolve_prorrata_operation_access(
    request: OperationRequest[BaseModel],
    context: OperationAccessContext,
    /,
) -> ResolvedOperationAccess:
    """Bind each prorrata operation to complete all-period profile access."""
    shape = result_contracts.prorrata_operation_contract(request.definition_id)
    if shape is None:
        raise ProfileAccessRefusedError(AccessDenialCode.OPERATION_UNAVAILABLE)
    return _shape_access(request, context, definition_id=request.definition_id, mutation=shape.mutation)


def _definition(
    definition_id: str,
    request_type: type[BaseModel],
    repository_factory: ProrrataRegisterRepositoryFactory,
    *,
    calculation_action_ports_factory: CalculationActionPortsFactory | None = None,
) -> OperationDefinition:
    shape = result_contracts.prorrata_operation_contract(definition_id)
    if shape is None:
        raise KeyError(definition_id)
    if shape.request_type is not request_type:
        raise ValueError("prorrata operation request differs from its closed registration schema")
    return build_single_phase_definition(
        definition_id=definition_id,
        request_type=request_type,
        subject_reference=OperationSubjectReferenceV1.profile(),
        result_type=result_contracts.ProrrataOperationExecutionResult,
        executor_type=ProrrataOperationExecutor,
        build=lambda: ProrrataOperationExecutor(
            repository_factory,
            definition_id=definition_id,
            calculation_action_ports_factory=calculation_action_ports_factory,
        ),
        capabilities=(
            RECORDED_IDEMPOTENT_SECURE_INPUT_UPDATE_CAPABILITIES
            if shape.mutation
            else RECORDED_IDEMPOTENT_SECURE_INPUT_READ_CAPABILITIES
        ),
        refusal_detail_codes=shape.refusal_codes,
    )


def _registration(
    definition: OperationDefinition,
    *,
    request_type: type[BaseModel],
    projection_type: type[BaseModel],
    projector: OperationResultProjector,
) -> OperationPublicDefinitionRegistrationV1:
    shape = result_contracts.prorrata_operation_contract(definition.definition_id)
    if shape is None:
        raise KeyError(definition.definition_id)
    if shape.request_type is not request_type or shape.projection_type is not projection_type:
        raise ValueError("prorrata registration does not match its closed public schema")
    return OperationPublicDefinitionRegistrationV1.compose_request_result(
        definition=definition,
        public_result_type=projection_type,
        result_projector=projector,
        access_resolver=resolve_prorrata_operation_access,
    )


def build_prorrata_list_definition(repository_factory: ProrrataRegisterRepositoryFactory) -> OperationDefinition:
    """Build the complete profile prorrata-list definition."""
    return _definition(
        operation_requests.PRORRATA_LIST_OPERATION_DEFINITION_ID,
        operation_requests.ProrrataListRequest,
        repository_factory,
    )


def build_prorrata_declare_sector_definition(
    repository_factory: ProrrataRegisterRepositoryFactory,
) -> OperationDefinition:
    """Build the guarded differentiated-sector declaration definition."""
    return _definition(
        operation_requests.PRORRATA_DECLARE_SECTOR_OPERATION_DEFINITION_ID,
        operation_requests.ProrrataDeclareSectorRequest,
        repository_factory,
    )


def build_prorrata_elect_especial_definition(
    repository_factory: ProrrataRegisterRepositoryFactory,
) -> OperationDefinition:
    """Build the guarded special-prorrata election definition."""
    return _definition(
        operation_requests.PRORRATA_ELECT_ESPECIAL_OPERATION_DEFINITION_ID,
        operation_requests.ProrrataElectEspecialRequest,
        repository_factory,
    )


def build_prorrata_elect_general_definition(
    repository_factory: ProrrataRegisterRepositoryFactory,
) -> OperationDefinition:
    """Build the guarded general-prorrata election definition."""
    return _definition(
        operation_requests.PRORRATA_ELECT_GENERAL_OPERATION_DEFINITION_ID,
        operation_requests.ProrrataElectGeneralRequest,
        repository_factory,
    )


def build_prorrata_revoke_especial_definition(
    repository_factory: ProrrataRegisterRepositoryFactory,
) -> OperationDefinition:
    """Build the guarded evidence-backed special-prorrata revocation definition."""
    return _definition(
        operation_requests.PRORRATA_REVOKE_ESPECIAL_OPERATION_DEFINITION_ID,
        operation_requests.ProrrataRevokeEspecialRequest,
        repository_factory,
    )


def build_prorrata_seed_definition(
    repository_factory: ProrrataRegisterRepositoryFactory,
    calculation_action_ports_factory: CalculationActionPortsFactory,
) -> OperationDefinition:
    """Build the source-fenced whole-entity carried-seed definition."""
    return _definition(
        operation_requests.PRORRATA_SEED_OPERATION_DEFINITION_ID,
        operation_requests.ProrrataSeedRequest,
        repository_factory,
        calculation_action_ports_factory=calculation_action_ports_factory,
    )


def build_prorrata_seed_sector_definition(
    repository_factory: ProrrataRegisterRepositoryFactory,
) -> OperationDefinition:
    """Build the latest-candidate per-sector carried-seed definition."""
    return _definition(
        operation_requests.PRORRATA_SEED_SECTOR_OPERATION_DEFINITION_ID,
        operation_requests.ProrrataSeedSectorRequest,
        repository_factory,
    )


def build_prorrata_settle_sector_definition(
    repository_factory: ProrrataRegisterRepositoryFactory,
) -> OperationDefinition:
    """Build the latest-candidate year-end sector settlement definition."""
    return _definition(
        operation_requests.PRORRATA_SETTLE_SECTOR_OPERATION_DEFINITION_ID,
        operation_requests.ProrrataSettleSectorRequest,
        repository_factory,
    )


def build_prorrata_declare_gross_definition(
    repository_factory: ProrrataRegisterRepositoryFactory,
) -> OperationDefinition:
    """Build the latest-candidate operator gross-base declaration definition."""
    return _definition(
        operation_requests.PRORRATA_DECLARE_GROSS_OPERATION_DEFINITION_ID,
        operation_requests.ProrrataDeclareGrossRequest,
        repository_factory,
    )


def build_prorrata_remove_gross_definition(
    repository_factory: ProrrataRegisterRepositoryFactory,
) -> OperationDefinition:
    """Build the latest-candidate operator gross-base removal definition."""
    return _definition(
        operation_requests.PRORRATA_REMOVE_GROSS_OPERATION_DEFINITION_ID,
        operation_requests.ProrrataRemoveGrossRequest,
        repository_factory,
    )


def build_prorrata_list_registration(
    definition: OperationDefinition,
) -> OperationPublicDefinitionRegistrationV1:
    """Bind the list result to its complete all-period disclosure projection."""
    return _registration(
        definition,
        request_type=operation_requests.ProrrataListRequest,
        projection_type=ProrrataListProjection,
        projector=project_prorrata_list_result,
    )


def build_prorrata_mutation_registration(
    definition: OperationDefinition,
) -> OperationPublicDefinitionRegistrationV1:
    """Bind one complete mutation result and truthful refusal projection."""
    contract = result_contracts.prorrata_operation_contract(definition.definition_id)
    if contract is None:
        raise KeyError(definition.definition_id)
    return _registration(
        definition,
        request_type=contract.request_type,
        projection_type=ProrrataMutationProjection,
        projector=project_prorrata_mutation_result,
    )


__all__ = [
    "build_prorrata_declare_gross_definition",
    "build_prorrata_declare_sector_definition",
    "build_prorrata_elect_especial_definition",
    "build_prorrata_elect_general_definition",
    "build_prorrata_list_definition",
    "build_prorrata_list_registration",
    "build_prorrata_mutation_registration",
    "build_prorrata_remove_gross_definition",
    "build_prorrata_revoke_especial_definition",
    "build_prorrata_seed_definition",
    "build_prorrata_seed_sector_definition",
    "build_prorrata_settle_sector_definition",
    "resolve_prorrata_operation_access",
]
