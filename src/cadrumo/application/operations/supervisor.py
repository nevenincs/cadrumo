"""Application-owned baseline operation supervision."""

from __future__ import annotations

import asyncio
from collections.abc import Callable
from datetime import datetime, timedelta

from pydantic import BaseModel

from ...core.async_cleanup import AsyncCloseable
from ...core.hex import Hex64Str
from ...core.operations import (
    OperationCancellation,
    OperationLifecycle,
    OperationTerminalCondition,
)
from . import supervisor_context as _supervisor_context
from ._execution_context import DefinitionBoundContext
from ._supervisor_execution import SupervisorExecutionMixin
from ._supervisor_lease import OperationSupervisorLeaseMixin
from ._supervisor_reconciliation import SupervisorReconciliationMixin
from ._supervisor_settlement import SupervisorSettlementMixin
from .event_replay import OperationEventCursor
from .financial_operand_submission import (
    BoundTransientFinancialOperandAccess,
    OperationTransientFinancialOperandBroker,
)
from .interactions import (
    OperationConsumedInteraction,
    OperationRejectResponse,
)
from .models import (
    OperationId,
    OperationIdentity,
    OperationRequest,
)
from .persistence.events import (
    OperationNoticeEvent,
)
from .persistence.financial_operand_custody import (
    OperationFinancialOperandCustodyRepository,
)
from .persistence.journal import (
    OperationEventStream,
    OperationJournal,
    OperationLeaseRepository,
    OperationPersistedSnapshot,
    OperationSecureReferenceStore,
)
from .persistence.leases import (
    OperationLeaseToken,
    OperationOwnerLease,
)
from .persistence.replay import (
    OperationReplayLimit,
    OperationReplayPage,
)
from .projection_services import OperationResponseAuthorityIssuer
from .registry import OperationDefinition, OperationRegistry
from .secret_submission import (
    EphemeralSecretBroker,
)


def _financial_operand_broker(
    custody: OperationFinancialOperandCustodyRepository | None,
    clock: Callable[[], datetime],
) -> OperationTransientFinancialOperandBroker | None:
    if custody is None:
        return None
    return OperationTransientFinancialOperandBroker(custody=custody, clock=clock)


def _require_positive_duration(name: str, duration: timedelta | None) -> None:
    if duration is not None and duration <= timedelta():
        raise ValueError(f"{name} must be positive when configured")


def _validate_supervisor_configuration(
    registry: OperationRegistry,
    lease_duration: timedelta,
    execution_timeout: timedelta | None,
    cleanup_timeout: timedelta | None,
    financial_operands: OperationTransientFinancialOperandBroker | None,
) -> None:
    if lease_duration <= timedelta():
        raise ValueError("operation lease duration must be positive")
    _require_positive_duration("operation execution timeout", execution_timeout)
    _require_positive_duration("operation cleanup timeout", cleanup_timeout)
    for definition in registry.definitions:
        declaration = definition.ephemeral_secret
        if declaration is not None and declaration.lifetime >= lease_duration:
            raise ValueError("ephemeral secret lifetime must be shorter than the owner lease")
        if definition.transient_financial_operands and financial_operands is None:
            raise ValueError("transient financial operand operations require a durable custody repository")


class OperationSupervisor(
    SupervisorExecutionMixin,
    SupervisorSettlementMixin,
    SupervisorReconciliationMixin,
    OperationSupervisorLeaseMixin,
):
    """Coordinate durable execution, interactions, recovery, and settlement."""

    def __init__(
        self,
        *,
        registry: OperationRegistry,
        journal: OperationJournal,
        event_stream: OperationEventStream,
        leases: OperationLeaseRepository,
        operands: OperationSecureReferenceStore | None,
        owner_id: Hex64Str,
        lease_token_factory: Callable[[], OperationLeaseToken],
        clock: Callable[[], datetime],
        lease_duration: timedelta,
        execution_timeout: timedelta | None = None,
        cleanup_timeout: timedelta | None = None,
        response_authority_issuer: OperationResponseAuthorityIssuer | None = None,
        response_token_factory: Callable[[], str] = _supervisor_context.new_response_token,
        financial_operand_custody: OperationFinancialOperandCustodyRepository | None = None,
    ) -> None:
        """Bind the registry and durable ports for one process owner."""
        self.registry = registry
        self._journal = journal
        self._event_stream = event_stream
        self._leases = leases
        self._operands = operands
        self._owner_id = owner_id
        self._lease_token = lease_token_factory()
        self._clock = clock
        self._lease_duration = lease_duration
        self._execution_timeout = execution_timeout
        self._cleanup_timeout = cleanup_timeout
        self._response_authority_issuer = response_authority_issuer
        self._response_token_factory = response_token_factory
        self._leases_by_operation: dict[OperationId, OperationOwnerLease] = {}
        self._lease_locks: dict[OperationId, asyncio.Lock] = {}
        self._resources: dict[OperationId, list[AsyncCloseable]] = {}
        self._contexts: dict[OperationId, DefinitionBoundContext] = {}
        self._executor_tasks: dict[OperationId, asyncio.Task[object]] = {}
        self._cleanup_tasks: dict[OperationId, asyncio.Task[None]] = {}
        self._continuation_tasks: dict[OperationId, asyncio.Task[OperationPersistedSnapshot]] = {}
        self._durable_change_events: dict[OperationId, asyncio.Event] = {}
        self._durable_revisions: dict[OperationId, int] = {}
        self._ephemeral_secrets = EphemeralSecretBroker()
        self._financial_operands = _financial_operand_broker(financial_operand_custody, clock)
        _validate_supervisor_configuration(
            registry,
            lease_duration,
            execution_timeout,
            cleanup_timeout,
            self._financial_operands,
        )

    @staticmethod
    def _validate_request_payload[RequestPayloadT: BaseModel](
        request: OperationRequest[RequestPayloadT], request_type: type[BaseModel]
    ) -> None:
        if not isinstance(request.payload, request_type):
            raise ValueError("request payload does not match definition")

    def _bound_financial_operand(
        self,
        identity: OperationIdentity,
        definition: OperationDefinition,
    ) -> BoundTransientFinancialOperandAccess:
        """Scope the operand broker to one invocation's own declarations."""
        return BoundTransientFinancialOperandAccess(
            declarations=definition.transient_financial_operands,
            broker=self._financial_operands,
            identity=identity,
            revision=0,
        )

    async def _settle_financial_operand_custody(self, operation_id: OperationId) -> None:
        """Acknowledge and release every operand one finished invocation held."""
        if self._financial_operands is None:
            return
        await self._financial_operands.settle_operation(operation_id, now=self._clock())

    async def shutdown(self) -> None:
        """Wipe every runtime-only secret retained by this supervisor instance."""
        self._ephemeral_secrets.close()
        if self._financial_operands is not None:
            self._financial_operands.close()

    def _require_cleanup_timeout(self, cancellation: OperationCancellation) -> None:
        if cancellation is not OperationCancellation.UNSUPPORTED and self._cleanup_timeout is None:
            raise ValueError("cancellable operation requires a configured cleanup timeout")

    @staticmethod
    def _acknowledged_cancellation_condition(snapshot: OperationPersistedSnapshot) -> OperationTerminalCondition:
        """Derive the sole terminal fact a cooperatively stopped executor permits."""
        requested_at = snapshot.cancellation_requested_at
        if requested_at is None or snapshot.cancellation_acknowledged_at is None:
            raise ValueError("automatic cancellation settlement requires durable request and acknowledgement")
        if snapshot.execution_deadline is not None and requested_at >= snapshot.execution_deadline:
            return OperationTerminalCondition.TIMED_OUT
        return OperationTerminalCondition.CANCELLED

    @staticmethod
    async def _wait_for_executor_or_deadline(
        executor_task: asyncio.Task[object],
        deadline: datetime,
        now: datetime,
    ) -> None:
        """Yield until a real task ends or the supervisor-owned UTC deadline arrives."""
        remaining_seconds = max((deadline - now).total_seconds(), 0.0)
        await asyncio.wait((executor_task,), timeout=remaining_seconds)

    async def inspect(self, operation_id: OperationId) -> OperationPersistedSnapshot:
        """Load the authoritative current snapshot for one operation."""
        return await self._load_pinned_snapshot(operation_id)

    async def observe(self, operation_id: OperationId) -> OperationPersistedSnapshot:
        """Return the latest durable operation observation."""
        return await self.inspect(operation_id)

    async def replay(
        self,
        operation_id: OperationId,
        cursor: OperationEventCursor,
        *,
        limit: OperationReplayLimit,
    ) -> OperationReplayPage:
        """Read one bounded authoritative event page after an exclusive cursor."""
        await self.inspect(operation_id)
        return await self._event_stream.read_after(operation_id, cursor, limit=limit)

    async def detach(self, operation_id: OperationId) -> OperationPersistedSnapshot:
        """Release a frontend without mutating the durable operation."""
        return await self.inspect(operation_id)

    def _continuation_completed(self, task: asyncio.Task[OperationPersistedSnapshot]) -> None:
        """Observe scheduled completion so task failures are never orphaned by asyncio."""
        if task.cancelled():
            return
        task.exception()

    async def reject(self, response: OperationRejectResponse) -> OperationConsumedInteraction:
        """Consume a rejected REVIEW response through the shared response transition."""
        return await self.respond(response)

    async def _cancel_pre_entry_secret(
        self,
        snapshot: OperationPersistedSnapshot,
    ) -> OperationPersistedSnapshot | None:
        """Acknowledge and settle a cancellation before executor entry."""
        if snapshot.secret_requirement is None or snapshot.executor_entered_at is not None:
            return None
        requested_at = self._clock()
        event = OperationNoticeEvent(
            identity=snapshot.identity,
            revision=0,
            sequence=1,
            timestamp=requested_at,
            code="operation.secret.cancelled",
            notice_code="operation.secret.cancelled",
        )
        acknowledged = await self._advance(
            snapshot,
            lifecycle=OperationLifecycle.SETTLING,
            events=(event,),
            cleanup_deadline=requested_at + self._lease_duration,
            cancellation_requested_at=requested_at,
            cancellation_acknowledged_at=requested_at,
            discard_ephemeral_secret=True,
        )
        return await self._settle_pre_entry_secret_wait(acknowledged, OperationTerminalCondition.CANCELLED)


__all__ = ["OperationSupervisor"]
