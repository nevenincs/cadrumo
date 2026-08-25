"""Owner-only assembly of runtime operation authority into safe services."""

from __future__ import annotations

from collections.abc import Awaitable, Callable
from dataclasses import dataclass
from datetime import datetime, timedelta

from pydantic import BaseModel, TypeAdapter

from ._interactions import OperationActorReference
from ._journal import (
    OperationEventStream,
    OperationJournal,
    OperationLeaseRepository,
    OperationObservationReader,
    OperationSecureReferenceStore,
)
from ._models import OperationId, OperationRequest
from ._observation import OperationObservationService
from ._projection_services import (
    OperationCancellationService,
    OperationDetachService,
    OperationResponseAuthorityBroker,
    OperationResponseCapability,
    OperationResponseControlService,
    OperationReviewProjectionService,
    OperationWorkspaceRefreshTargetService,
    _read_snapshot,
    _UnavailableOperationSecureResponseAuthority,
    _UnavailableSnapshot,
)
from ._public import OperationResponseControlRequestV1, OperationSubmissionReceiptV1
from ._registry import OperationRegistry
from ._secret_submission import OperationSecretRequirement
from ._supervisor import OperationSupervisor


@dataclass(frozen=True, slots=True)
class OperationSubmission:
    """Durable receipt plus its separately held process-local response capability."""

    receipt: OperationSubmissionReceiptV1
    response_capability: OperationResponseCapability


class OperationSubmissionService:
    """Public submit/start door over the private canonical supervisor."""

    def __init__(self, supervisor: OperationSupervisor, authority_broker: OperationResponseAuthorityBroker) -> None:
        self._supervisor = supervisor
        self._authority_broker = authority_broker

    async def submit(
        self,
        request: OperationRequest[BaseModel],
        *,
        actor_ref: str,
        operation_id: OperationId | None = None,
    ) -> OperationSubmission:
        """Durably submit one typed registered request without starting it."""
        validated_actor = TypeAdapter(OperationActorReference).validate_python(actor_ref)
        submitted_id = await self._supervisor.submit(request, operation_id=operation_id)
        snapshot = await self._supervisor.inspect(submitted_id)
        receipt = OperationSubmissionReceiptV1(
            operation_id=submitted_id, secret_requirement=snapshot.secret_requirement
        )
        return OperationSubmission(
            receipt=receipt,
            response_capability=self._authority_broker.reserve(submitted_id, validated_actor),
        )

    async def submit_secret(self, requirement: OperationSecretRequirement, secret: bytearray) -> None:
        """Transfer one exact mutable secret buffer into runtime-only custody."""
        await self._supervisor.submit_ephemeral_secret(requirement, secret)

    async def start(self, operation_id: OperationId) -> OperationId:
        """Start one submitted operation without exposing its raw snapshot."""
        snapshot = await self._supervisor.start(operation_id)
        return snapshot.identity.operation_id


@dataclass(frozen=True, slots=True)
class OperationComposedServices:
    """The only service family a frontend composition result can expose."""

    submission: OperationSubmissionService
    observation: OperationObservationService
    review: OperationReviewProjectionService
    refresh: OperationWorkspaceRefreshTargetService
    cancellation: OperationCancellationService
    detach: OperationDetachService
    _response_factory: Callable[
        [OperationResponseControlRequestV1, OperationResponseCapability],
        Awaitable[OperationResponseControlService],
    ]
    _shutdown: Callable[[], Awaitable[None]]

    async def shutdown(self) -> None:
        """Settle owner-held runtime resources without exposing them."""
        await self._shutdown()

    async def response(
        self,
        request: OperationResponseControlRequestV1,
        capability: OperationResponseCapability,
    ) -> OperationResponseControlService:
        """Bind caller identity to the exact process-local REVIEW authority."""
        return await self._response_factory(request, capability)


def compose_operation_services(
    *,
    registry: OperationRegistry,
    journal: OperationJournal,
    reader: OperationObservationReader,
    event_stream: OperationEventStream,
    leases: OperationLeaseRepository,
    operands: OperationSecureReferenceStore,
    owner_id: str,
    lease_token_factory: Callable[[], str],
    clock: Callable[[], datetime],
    lease_duration: timedelta,
    execution_timeout: timedelta,
    cleanup_timeout: timedelta,
) -> OperationComposedServices:
    """Bind one immutable registry to real runtime adapters and safe services."""
    authority_broker = OperationResponseAuthorityBroker()
    supervisor = OperationSupervisor(
        registry=registry,
        journal=journal,
        event_stream=event_stream,
        leases=leases,
        operands=operands,
        owner_id=owner_id,
        lease_token_factory=lease_token_factory,
        clock=clock,
        lease_duration=lease_duration,
        execution_timeout=execution_timeout,
        cleanup_timeout=cleanup_timeout,
        response_authority_issuer=authority_broker,
    )
    observation = OperationObservationService(reader=reader, registry=registry)

    async def bind_response(
        request: OperationResponseControlRequestV1,
        capability: OperationResponseCapability,
    ) -> OperationResponseControlService:
        snapshot = await _read_snapshot(reader, request.operation_id)
        pending = (
            None if snapshot is None or isinstance(snapshot, _UnavailableSnapshot) else snapshot.pending_interaction
        )
        authority = (
            _UnavailableOperationSecureResponseAuthority()
            if pending is None
            else authority_broker.bind(request, pending, capability, clock=clock)
        )
        return OperationResponseControlService(
            reader=reader,
            registry=registry,
            authority=authority,
            supervisor=supervisor,
        )

    async def shutdown() -> None:
        authority_broker.close()
        await supervisor.shutdown()

    return OperationComposedServices(
        submission=OperationSubmissionService(supervisor, authority_broker),
        observation=observation,
        review=OperationReviewProjectionService(reader=reader, registry=registry, operands=operands, clock=clock),
        refresh=OperationWorkspaceRefreshTargetService(reader=reader, registry=registry),
        cancellation=OperationCancellationService(reader=reader, registry=registry, supervisor=supervisor),
        detach=OperationDetachService(reader=reader, registry=registry, supervisor=supervisor),
        _response_factory=bind_response,
        _shutdown=shutdown,
    )


__all__ = [
    "OperationComposedServices",
    "OperationSubmission",
    "OperationSubmissionService",
    "compose_operation_services",
]
