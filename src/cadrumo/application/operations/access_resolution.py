"""Trusted host context and owner-resolved policy for one operation boundary."""

from __future__ import annotations

from dataclasses import dataclass
from typing import TYPE_CHECKING
from uuid import UUID

from pydantic import BaseModel

from ..user_profile.access_contracts import (
    AccessAction,
    AccessDenialCode,
    Availability,
    OperationAccessPolicy,
    OperationAccessRequest,
)
from ..user_profile.access_errors import ProfileAccessRefusedError
from .models import OperationRequest
from .registry import OperationFrontendProjection, OperationPublicDefinitionContractV1, OperationRegistry

if TYPE_CHECKING:
    from ...domain.calculations.registry.authority import PinnedAuthorityOperation


@dataclass(frozen=True, slots=True)
class OperationAccessContext:
    """Fresh host facts supplied only after resolving the registered definition."""

    profile_id: UUID
    destination_id: UUID
    action: AccessAction
    frontend: OperationFrontendProjection
    contract: OperationPublicDefinitionContractV1
    published_authority: Availability
    admitted_request: OperationAccessRequest | None = None
    authority_operation: PinnedAuthorityOperation | None = None


@dataclass(frozen=True, slots=True)
class ResolvedOperationAccess:
    """A domain resolution to be checked against current session authority."""

    request: OperationAccessRequest
    policy: OperationAccessPolicy


def resolve_operation_access(
    *, registry: OperationRegistry, request: OperationRequest[BaseModel], context: OperationAccessContext
) -> ResolvedOperationAccess:
    """Require an exact live registration and validate every host-owned coordinate."""
    try:
        definition = registry.lookup(request.definition_id)
        registration = registry.lookup_public_registration(request.definition_id)
    except KeyError:
        raise ProfileAccessRefusedError(AccessDenialCode.OPERATION_UNAVAILABLE) from None
    resolver = registration.access_resolver
    if (
        resolver is None
        or type(request.payload) is not definition.request_type
        or context.contract != registration.contract
    ):
        raise ProfileAccessRefusedError(AccessDenialCode.OPERATION_UNAVAILABLE)
    resolved = resolver(request, context)
    access, policy = resolved.request, resolved.policy
    if (
        access.profile_id != context.profile_id
        or access.destination_id != context.destination_id
        or access.frontend is not context.frontend
        or access.action is not context.action
        or access.definition_id != request.definition_id
        or policy.definition_id != request.definition_id
        or policy.definition_contract_digest != context.contract.definition_contract_digest
    ):
        raise ProfileAccessRefusedError(AccessDenialCode.OPERATION_UNAVAILABLE)
    return resolved
