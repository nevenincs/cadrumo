"""Profile-bound registered operations for the canonical inventory service."""

from __future__ import annotations

from typing import TYPE_CHECKING, Protocol, cast
from uuid import UUID

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
from .ports import InventoryServicePortsFactory

if TYPE_CHECKING:
    pass

from .registered_execution_result import (
    InventoryOperationExecutionResult,
)
from .registered_executor import InventoryOperationExecutor
from .registered_projections import (
    InventoryClosingAuthorityOperationProjection,
    InventoryCreateProjection,
    InventoryListProjection,
    InventoryMovementAddProjection,
    InventoryValuationOperationProjection,
)
from .registered_requests import (
    INVENTORY_CLOSING_AUTHORITY_RECORD_OPERATION_DEFINITION_ID,
    INVENTORY_CREATE_OPERATION_DEFINITION_ID,
    INVENTORY_LIST_OPERATION_DEFINITION_ID,
    INVENTORY_MOVEMENT_ADD_OPERATION_DEFINITION_ID,
    INVENTORY_VALUATION_PREVIEW_OPERATION_DEFINITION_ID,
    InventoryClosingAuthorityRecordRequest,
    InventoryCreateRequest,
    InventoryListRequest,
    InventoryMovementAddRequest,
    InventoryValuationPreviewRequest,
)
from .registered_result_projection import (
    project_inventory_closing_authority_result,
    project_inventory_create_result,
    project_inventory_list_result,
    project_inventory_movement_add_result,
    project_inventory_valuation_result,
)
from .registered_specs import INVENTORY_OPERATION_SHAPES


class _InventoryProfileScopedRequest(Protocol):
    profile_id: UUID


_MUTATING_IDS = frozenset(
    {
        INVENTORY_CREATE_OPERATION_DEFINITION_ID,
        INVENTORY_MOVEMENT_ADD_OPERATION_DEFINITION_ID,
        INVENTORY_VALUATION_PREVIEW_OPERATION_DEFINITION_ID,
        INVENTORY_CLOSING_AUTHORITY_RECORD_OPERATION_DEFINITION_ID,
    },
)


def resolve_inventory_operation_access(
    request: OperationRequest[BaseModel],
    context: OperationAccessContext,
    /,
) -> ResolvedOperationAccess:
    """Bind inventory disclosure and mutation authority to the exact profile."""
    shape = INVENTORY_OPERATION_SHAPES.get(request.definition_id)
    payload = request.payload
    if shape is None or type(payload) is not shape.request_type:
        raise ProfileAccessRefusedError(AccessDenialCode.OPERATION_UNAVAILABLE)
    profile_id = cast(_InventoryProfileScopedRequest, payload).profile_id
    resolved = resolve_ledger_read_access(request, context, profile_id=profile_id, periods=frozenset())
    if request.definition_id not in _MUTATING_IDS:
        return resolved
    return with_commit_action(resolved)


def _definition(
    definition_id: str,
    request_type: type[BaseModel],
    ports_factory: InventoryServicePortsFactory,
) -> OperationDefinition:
    shape = INVENTORY_OPERATION_SHAPES[definition_id]
    if shape.request_type is not request_type:
        raise ValueError("inventory operation builder request type does not match its registration")
    return build_single_phase_definition(
        definition_id=definition_id,
        request_type=request_type,
        result_type=InventoryOperationExecutionResult,
        executor_type=InventoryOperationExecutor,
        build=lambda: InventoryOperationExecutor(ports_factory, definition_id=definition_id),
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
    shape = INVENTORY_OPERATION_SHAPES[definition.definition_id]
    if shape.request_type is not request_type or shape.projection_type is not projection_type:
        raise ValueError("inventory operation registration does not match its canonical schema")
    return OperationPublicDefinitionRegistrationV1.compose_request_result(
        definition=definition,
        public_result_type=projection_type,
        result_projector=projector,
        access_resolver=resolve_inventory_operation_access,
    )


def build_inventory_list_definition(ports_factory: InventoryServicePortsFactory) -> OperationDefinition:
    """Build the exact-profile inventory-list worker definition."""
    return _definition(INVENTORY_LIST_OPERATION_DEFINITION_ID, InventoryListRequest, ports_factory)


def build_inventory_create_definition(ports_factory: InventoryServicePortsFactory) -> OperationDefinition:
    """Build the guarded exact-profile ledger-creation definition."""
    return _definition(INVENTORY_CREATE_OPERATION_DEFINITION_ID, InventoryCreateRequest, ports_factory)


def build_inventory_movement_add_definition(ports_factory: InventoryServicePortsFactory) -> OperationDefinition:
    """Build the guarded exact-profile movement append definition."""
    return _definition(INVENTORY_MOVEMENT_ADD_OPERATION_DEFINITION_ID, InventoryMovementAddRequest, ports_factory)


def build_inventory_valuation_preview_definition(ports_factory: InventoryServicePortsFactory) -> OperationDefinition:
    """Build the audited exact-profile valuation preview definition."""
    return _definition(
        INVENTORY_VALUATION_PREVIEW_OPERATION_DEFINITION_ID,
        InventoryValuationPreviewRequest,
        ports_factory,
    )


def build_inventory_closing_authority_record_definition(
    ports_factory: InventoryServicePortsFactory,
) -> OperationDefinition:
    """Build the guarded exact-profile closing-authority write definition."""
    return _definition(
        INVENTORY_CLOSING_AUTHORITY_RECORD_OPERATION_DEFINITION_ID,
        InventoryClosingAuthorityRecordRequest,
        ports_factory,
    )


def build_inventory_list_registration(definition: OperationDefinition) -> OperationPublicDefinitionRegistrationV1:
    """Bind the safe inventory-list projection and profile disclosure policy."""
    return _registration(
        definition,
        request_type=InventoryListRequest,
        projection_type=InventoryListProjection,
        projector=project_inventory_list_result,
    )


def build_inventory_create_registration(definition: OperationDefinition) -> OperationPublicDefinitionRegistrationV1:
    """Bind redacted ledger-create results and typed refusal explanations."""
    return _registration(
        definition,
        request_type=InventoryCreateRequest,
        projection_type=InventoryCreateProjection,
        projector=project_inventory_create_result,
    )


def build_inventory_movement_add_registration(
    definition: OperationDefinition,
) -> OperationPublicDefinitionRegistrationV1:
    """Bind redacted movement results and typed refusal explanations."""
    return _registration(
        definition,
        request_type=InventoryMovementAddRequest,
        projection_type=InventoryMovementAddProjection,
        projector=project_inventory_movement_add_result,
    )


def build_inventory_valuation_preview_registration(
    definition: OperationDefinition,
) -> OperationPublicDefinitionRegistrationV1:
    """Bind valuation facts with their audit-effect receipt."""
    return _registration(
        definition,
        request_type=InventoryValuationPreviewRequest,
        projection_type=InventoryValuationOperationProjection,
        projector=project_inventory_valuation_result,
    )


def build_inventory_closing_authority_record_registration(
    definition: OperationDefinition,
) -> OperationPublicDefinitionRegistrationV1:
    """Bind fingerprint-only closing-authority results and typed refusals."""
    return _registration(
        definition,
        request_type=InventoryClosingAuthorityRecordRequest,
        projection_type=InventoryClosingAuthorityOperationProjection,
        projector=project_inventory_closing_authority_result,
    )


__all__ = [
    "build_inventory_closing_authority_record_definition",
    "build_inventory_closing_authority_record_registration",
    "build_inventory_create_definition",
    "build_inventory_create_registration",
    "build_inventory_list_definition",
    "build_inventory_list_registration",
    "build_inventory_movement_add_definition",
    "build_inventory_movement_add_registration",
    "build_inventory_valuation_preview_definition",
    "build_inventory_valuation_preview_registration",
    "resolve_inventory_operation_access",
]
