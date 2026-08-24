"""Owner-only assembly of runtime operation authority into safe services."""

from __future__ import annotations

from collections.abc import Awaitable, Callable
from dataclasses import dataclass
from datetime import datetime, timedelta

from ._journal import OperationEventStream, OperationJournal, OperationLeaseRepository, OperationObservationReader, OperationSecureReferenceStore
from ._observation import OperationObservationService
from ._projection_services import (
    OperationCancellationService,
    OperationDetachService,
    OperationResponseControlService,
    OperationReviewProjectionService,
    OperationSecureResponseAuthority,
    OperationWorkspaceRefreshTargetService,
)
from ._registry import OperationRegistry
from ._supervisor import OperationSupervisor


@dataclass(frozen=True, slots=True)
class OperationComposedServices:
    """The only service family a frontend composition result can expose."""

    observation: OperationObservationService
    review: OperationReviewProjectionService
    refresh: OperationWorkspaceRefreshTargetService
    cancellation: OperationCancellationService
    detach: OperationDetachService
    _response_factory: Callable[[OperationSecureResponseAuthority], OperationResponseControlService]
    _shutdown: Callable[[], Awaitable[None]]

    async def shutdown(self) -> None:
        """Settle owner-held runtime resources without exposing them."""
        await self._shutdown()

    def response(self, authority: OperationSecureResponseAuthority) -> OperationResponseControlService:
        """Bind the separately held REVIEW response authority at the owner seam."""
        return self._response_factory(authority)


def compose_operation_services(
    *,
    registry: OperationRegistry,
    journal: OperationJournal,
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
    )
    reader: OperationObservationReader = journal
    observation = OperationObservationService(reader=reader, registry=registry)
    return OperationComposedServices(
        observation=observation,
        review=OperationReviewProjectionService(reader=reader, registry=registry, operands=operands, clock=clock),
        refresh=OperationWorkspaceRefreshTargetService(reader=reader, registry=registry),
        cancellation=OperationCancellationService(reader=reader, registry=registry, supervisor=supervisor),
        detach=OperationDetachService(reader=reader, registry=registry, supervisor=supervisor),
        _response_factory=lambda authority: OperationResponseControlService(
            reader=reader,
            registry=registry,
            authority=authority,
        ),
        _shutdown=supervisor.shutdown,
    )


__all__ = ["OperationComposedServices", "compose_operation_services"]
