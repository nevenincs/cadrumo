"""Trusted host access facts for one registered operation, shared by the Modelo operation suites."""

from __future__ import annotations

from uuid import UUID, uuid4

from cadrumo_client.contracts.access_vocabulary import AccessAction, Availability, OperationAccessRequest

from ....core.operations import OperationFrontendProjection
from ....domain.calculations.registry.authority import PinnedAuthorityOperation
from ...operations.access_resolution import OperationAccessContext
from ...operations.registry import OperationPublicDefinitionRegistrationV1


def registration_access_context(
    registration: OperationPublicDefinitionRegistrationV1,
    *,
    profile_id: UUID,
    action: AccessAction,
    frontend: OperationFrontendProjection = OperationFrontendProjection.CLI,
    authority_operation: PinnedAuthorityOperation | None = None,
    admitted_request: OperationAccessRequest | None = None,
) -> OperationAccessContext:
    """Build the access context for ``action`` on the registration's exact contract with a fresh destination."""
    return OperationAccessContext(
        profile_id=profile_id,
        destination_id=uuid4(),
        action=action,
        frontend=frontend,
        contract=registration.contract,
        published_authority=Availability.AVAILABLE,
        authority_operation=authority_operation,
        admitted_request=admitted_request,
    )
