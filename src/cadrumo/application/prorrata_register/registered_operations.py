"""Exact-profile registered operations for the IVA prorrata register."""

from __future__ import annotations

from dataclasses import replace

from pydantic import BaseModel

from ..ledger.read_access import resolve_ledger_read_access
from ..modelo.calculation_action_ports import CalculationActionPortsFactory
from ..operations.access_resolution import OperationAccessContext, ResolvedOperationAccess
from ..operations.capabilities import RECORDED_IDEMPOTENT_SECURE_INPUT_UPDATE_CAPABILITIES
from ..operations.models import OperationRequest
from ..operations.operation_definition import OperationDefinition, OperationExecutorFactory
from ..operations.registry import (
    ALL_OPERATION_FRONTENDS,
    OperationPublicDefinitionRegistrationV1,
    OperationReconciliationPolicy,
    OperationResultProjector,
)
from ..user_profile.access_contracts import AccessAction, AccessDenialCode, OperationAccessPolicy
from ..user_profile.access_errors import ProfileAccessRefusedError
from . import operation_requests as _requests
from . import result_contracts as _result_contracts
from .executor import ProrrataOperationExecutor as _ProrrataOperationExecutor
from .ports import ProrrataRegisterRepositoryFactory
from .projection_contracts import (
    ProrrataListProjection as _ProrrataListProjection,
)
from .projection_contracts import (
    ProrrataMutationProjection as _ProrrataMutationProjection,
)
from .result_projections import (
    project_prorrata_list_result as _project_prorrata_list_result,
)
from .result_projections import (
    project_prorrata_mutation_result as _project_prorrata_mutation_result,
)


def _shape_access(
    request: OperationRequest[BaseModel],
    context: OperationAccessContext,
    *,
    definition_id: str,
    mutation: bool,
) -> ResolvedOperationAccess:
    shape = _result_contracts.prorrata_operation_contract(definition_id)
    payload = request.payload
    if shape is None or type(payload) is not shape.request_type:
        raise ProfileAccessRefusedError(AccessDenialCode.OPERATION_UNAVAILABLE)
    if request.definition_id != definition_id:
        raise ProfileAccessRefusedError(AccessDenialCode.OPERATION_UNAVAILABLE)
    if not isinstance(payload, _requests.ProrrataProfileRequest):
        raise ProfileAccessRefusedError(AccessDenialCode.OPERATION_UNAVAILABLE)
    resolved = resolve_ledger_read_access(request, context, profile_id=payload.profile_id, periods=frozenset())
    if not mutation:
        return resolved
    policy = OperationAccessPolicy.model_validate(
        {**dict(resolved.policy), "actions": resolved.policy.actions | {AccessAction.COMMIT}},
    )
    return replace(resolved, policy=policy)


def resolve_prorrata_operation_access(
    request: OperationRequest[BaseModel],
    context: OperationAccessContext,
    /,
) -> ResolvedOperationAccess:
    """Bind each prorrata operation to complete all-period profile access."""
    shape = _result_contracts.prorrata_operation_contract(request.definition_id)
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
    shape = _result_contracts.prorrata_operation_contract(definition_id)
    if shape is None:
        raise KeyError(definition_id)
    if shape.request_type is not request_type:
        raise ValueError("prorrata operation request differs from its closed registration schema")
    return OperationDefinition(
        definition_id=definition_id,
        request_type=request_type,
        result_type=_result_contracts.ProrrataOperationExecutionResult,
        executor_factory=OperationExecutorFactory(
            request_type=request_type,
            executor_type=_ProrrataOperationExecutor,
            build=lambda: _ProrrataOperationExecutor(
                repository_factory,
                definition_id=definition_id,
                calculation_action_ports_factory=calculation_action_ports_factory,
            ),
        ),
        phase_codes=(definition_id,),
        interaction_kinds=frozenset(),
        capabilities=RECORDED_IDEMPOTENT_SECURE_INPUT_UPDATE_CAPABILITIES,
        reconciliation_policy=OperationReconciliationPolicy.INTERRUPT,
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
    shape = _result_contracts.prorrata_operation_contract(definition.definition_id)
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
        _requests.PRORRATA_LIST_OPERATION_DEFINITION_ID, _requests.ProrrataListRequest, repository_factory
    )


def build_prorrata_declare_sector_definition(
    repository_factory: ProrrataRegisterRepositoryFactory,
) -> OperationDefinition:
    """Build the guarded differentiated-sector declaration definition."""
    return _definition(
        _requests.PRORRATA_DECLARE_SECTOR_OPERATION_DEFINITION_ID,
        _requests.ProrrataDeclareSectorRequest,
        repository_factory,
    )


def build_prorrata_elect_especial_definition(
    repository_factory: ProrrataRegisterRepositoryFactory,
) -> OperationDefinition:
    """Build the guarded special-prorrata election definition."""
    return _definition(
        _requests.PRORRATA_ELECT_ESPECIAL_OPERATION_DEFINITION_ID,
        _requests.ProrrataElectEspecialRequest,
        repository_factory,
    )


def build_prorrata_elect_general_definition(
    repository_factory: ProrrataRegisterRepositoryFactory,
) -> OperationDefinition:
    """Build the guarded general-prorrata election definition."""
    return _definition(
        _requests.PRORRATA_ELECT_GENERAL_OPERATION_DEFINITION_ID,
        _requests.ProrrataElectGeneralRequest,
        repository_factory,
    )


def build_prorrata_revoke_especial_definition(
    repository_factory: ProrrataRegisterRepositoryFactory,
) -> OperationDefinition:
    """Build the guarded evidence-backed special-prorrata revocation definition."""
    return _definition(
        _requests.PRORRATA_REVOKE_ESPECIAL_OPERATION_DEFINITION_ID,
        _requests.ProrrataRevokeEspecialRequest,
        repository_factory,
    )


def build_prorrata_seed_definition(
    repository_factory: ProrrataRegisterRepositoryFactory,
    calculation_action_ports_factory: CalculationActionPortsFactory,
) -> OperationDefinition:
    """Build the source-fenced whole-entity carried-seed definition."""
    return _definition(
        _requests.PRORRATA_SEED_OPERATION_DEFINITION_ID,
        _requests.ProrrataSeedRequest,
        repository_factory,
        calculation_action_ports_factory=calculation_action_ports_factory,
    )


def build_prorrata_seed_sector_definition(
    repository_factory: ProrrataRegisterRepositoryFactory,
) -> OperationDefinition:
    """Build the latest-candidate per-sector carried-seed definition."""
    return _definition(
        _requests.PRORRATA_SEED_SECTOR_OPERATION_DEFINITION_ID,
        _requests.ProrrataSeedSectorRequest,
        repository_factory,
    )


def build_prorrata_settle_sector_definition(
    repository_factory: ProrrataRegisterRepositoryFactory,
) -> OperationDefinition:
    """Build the latest-candidate year-end sector settlement definition."""
    return _definition(
        _requests.PRORRATA_SETTLE_SECTOR_OPERATION_DEFINITION_ID,
        _requests.ProrrataSettleSectorRequest,
        repository_factory,
    )


def build_prorrata_list_registration(
    definition: OperationDefinition,
) -> OperationPublicDefinitionRegistrationV1:
    """Bind the list result to its complete all-period disclosure projection."""
    return _registration(
        definition,
        request_type=_requests.ProrrataListRequest,
        projection_type=_ProrrataListProjection,
        projector=_project_prorrata_list_result,
    )


def build_prorrata_mutation_registration(
    definition: OperationDefinition,
) -> OperationPublicDefinitionRegistrationV1:
    """Bind one complete mutation result and truthful refusal projection."""
    contract = _result_contracts.prorrata_operation_contract(definition.definition_id)
    if contract is None:
        raise KeyError(definition.definition_id)
    return _registration(
        definition,
        request_type=contract.request_type,
        projection_type=_ProrrataMutationProjection,
        projector=_project_prorrata_mutation_result,
    )


__all__ = [
    "build_prorrata_declare_sector_definition",
    "build_prorrata_elect_especial_definition",
    "build_prorrata_elect_general_definition",
    "build_prorrata_list_definition",
    "build_prorrata_list_registration",
    "build_prorrata_mutation_registration",
    "build_prorrata_revoke_especial_definition",
    "build_prorrata_seed_definition",
    "build_prorrata_seed_sector_definition",
    "build_prorrata_settle_sector_definition",
    "resolve_prorrata_operation_access",
]
