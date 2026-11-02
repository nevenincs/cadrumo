"""Trusted host access facts for one registered operation, shared by the ledger operation suites."""

from __future__ import annotations

from uuid import UUID, uuid4

from cadrumo_client.contracts.access_vocabulary import AccessAction, Availability, OperationAccessRequest

from ...operations.access_resolution import OperationAccessContext
from ...operations.registry import OperationFrontendProjection, OperationPublicDefinitionRegistrationV1


def registration_access_context(
    registration: OperationPublicDefinitionRegistrationV1,
    *,
    profile_id: UUID,
    action: AccessAction,
    frontend: OperationFrontendProjection = OperationFrontendProjection.CLI,
    destination_id: UUID | None = None,
    admitted_request: OperationAccessRequest | None = None,
) -> OperationAccessContext:
    """Build the access context for ``action`` on the registration's exact contract with a fresh destination by default."""
    return OperationAccessContext(
        profile_id=profile_id,
        destination_id=uuid4() if destination_id is None else destination_id,
        action=action,
        frontend=frontend,
        contract=registration.contract,
        published_authority=Availability.AVAILABLE,
        admitted_request=admitted_request,
    )
