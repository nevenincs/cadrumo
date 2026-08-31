"""Owner-only assembly of runtime operation authority into safe services."""

from __future__ import annotations

from collections.abc import Awaitable, Callable
from dataclasses import dataclass
from datetime import datetime, timedelta

from pydantic import BaseModel, TypeAdapter

from .frontend_contracts import OperationResponseControlRequestV1, OperationSubmissionReceiptV1
from .interactions import OperationActorReference
from .models import OperationId, OperationRequest
from .observation import OperationObservationService
from .persistence.financial_operand_custody import OperationFinancialOperandCustodyRepository
from .persistence.journal import (
    OperationEventStream,
    OperationJournal,
    OperationLeaseRepository,
    OperationObservationReader,
    OperationSecureReferenceStore,
)
from .projection_services import (
    OperationCancellationService,
    OperationDetachService,
    OperationResponseAuthorityBroker,
    OperationResponseCapability,
    OperationResponseControlService,
    OperationResultProjectionService,
    OperationReviewProjectionService,
    OperationWorkspaceRefreshTargetService,
    UnavailableOperationSecureResponseAuthority,
    UnavailableSnapshot,
    read_snapshot,
)
from .registry import OperationRegistry
from .secret_submission import OperationSecretRequirement
from .supervisor import OperationSupervisor

_ACTOR_REFERENCE_ADAPTER: TypeAdapter[OperationActorReference] = TypeAdapter(OperationActorReference)


@dataclass(frozen=True, slots=True)
class OperationSubmission:
    """Durable receipt plus its separately held process-local response capability."""

    receipt: OperationSubmissionReceiptV1
    response_capability: OperationResponseCapability


class OperationSubmissionService:
    """Public submit/start door over the private canonical supervisor."""

    def __init__(self, supervisor: OperationSupervisor, authority_broker: OperationResponseAuthorityBroker) -> None:
        """Bind the operational supervisor and response-capability authority."""
        self.supervisor = supervisor
        self._authority_broker = authority_broker

    async def submit[RequestPayloadT: BaseModel](
        self,
        request: OperationRequest[RequestPayloadT],
        *,
        actor_ref: str,
        operation_id: OperationId | None = None,
    ) -> OperationSubmission:
        """Durably submit one typed registered request without starting it."""
        validated_actor = _ACTOR_REFERENCE_ADAPTER.validate_python(actor_ref)
        submitted_id = await self.supervisor.submit(request, operation_id=operation_id)
        snapshot = await self.supervisor.inspect(submitted_id)
        receipt = OperationSubmissionReceiptV1(
            operation_id=submitted_id, secret_requirement=snapshot.secret_requirement
        )
        return OperationSubmission(
            receipt=receipt,
            response_capability=self._authority_broker.reserve(submitted_id, validated_actor),
        )

    async def submit_secret(self, requirement: OperationSecretRequirement, secret: bytearray) -> None:
        """Transfer one exact mutable secret buffer into runtime-only custody."""
        await self.supervisor.submit_ephemeral_secret(requirement, secret)

    async def start(self, operation_id: OperationId) -> OperationId:
        """Start one submitted operation without exposing its raw snapshot."""
        snapshot = await self.supervisor.start(operation_id)
        return snapshot.identity.operation_id


@dataclass(frozen=True, slots=True)
class OperationComposedServices:
    """The only service family a frontend composition result can expose."""

    submission: OperationSubmissionService
    observation: OperationObservationService
    review: OperationReviewProjectionService
    result: OperationResultProjectionService
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
    financial_operand_custody: OperationFinancialOperandCustodyRepository | None = None,
) -> OperationComposedServices:
    """Bind one immutable registry to real runtime adapters and safe services.

    ``financial_operand_custody`` is optional because only a registry holding a
    definition that declares transient financial operands needs it. The
    supervisor refuses to construct when such a definition is present without
    it, so omitting it stays a refusal rather than a silently operand-less
    supervisor.
    """
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
        financial_operand_custody=financial_operand_custody,
    )
    observation = OperationObservationService(reader=reader, registry=registry)

    async def bind_response(
        request: OperationResponseControlRequestV1,
        capability: OperationResponseCapability,
    ) -> OperationResponseControlService:
        snapshot = await read_snapshot(reader, request.operation_id)
        pending = (
            None if snapshot is None or isinstance(snapshot, UnavailableSnapshot) else snapshot.pending_interaction
        )
        authority = (
            UnavailableOperationSecureResponseAuthority()
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
        result=OperationResultProjectionService(reader=reader, registry=registry, operands=operands),
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
