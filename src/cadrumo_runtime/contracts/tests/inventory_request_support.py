"""A well-formed worker automation inventory request for the contract and transport tests."""

from __future__ import annotations

from uuid import UUID, uuid4

from cadrumo.application.user_profile.automation_operations import AUTOMATION_INVENTORY_OPERATION_DEFINITION_ID
from cadrumo.core.operations import OperationFrontendProjection
from cadrumo_client.contracts.access_vocabulary import (
    AccessAction,
    Availability,
    OperationAccessPolicy,
    OperationAccessRequest,
)

from ..worker_authorization import WorkerAutomationInventoryRequest


def inventory_request(request_id: UUID | None = None) -> WorkerAutomationInventoryRequest:
    """Build the inventory start request of a CLI caller under a period-independent policy."""
    definition_id = AUTOMATION_INVENTORY_OPERATION_DEFINITION_ID
    return WorkerAutomationInventoryRequest(
        request_id=uuid4() if request_id is None else request_id,
        connection_id=uuid4(),
        session_id=uuid4(),
        operation_id="a" * 64,
        request=OperationAccessRequest(
            profile_id=uuid4(),
            definition_id=definition_id,
            action=AccessAction.START,
            frontend=OperationFrontendProjection.CLI,
            periods=frozenset(),
            period_independent=True,
            destination_id=uuid4(),
        ),
        policy=OperationAccessPolicy(
            definition_id=definition_id,
            definition_contract_digest="b" * 64,
            actions=frozenset({AccessAction.START}),
            disclosures=frozenset(),
            periods=None,
            allow_period_independent=True,
            backend=Availability.AVAILABLE,
            published_authority=Availability.AVAILABLE,
            provider=Availability.NOT_REQUIRED,
            transaction_authority_required=False,
        ),
    )
