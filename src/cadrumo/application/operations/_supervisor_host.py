"""Attribute and collaborator contract shared by the operation supervisor mixins.

:class:`~application.operations.supervisor.OperationSupervisor` composes the
execution, settlement, reconciliation and lease mixins. Each mixin calls
collaborators defined by its siblings, so they all inherit this one declaration
of the composed host instead of each restating the part it happens to use.
"""

from __future__ import annotations

import asyncio
from collections.abc import Callable, Coroutine
from datetime import datetime, timedelta
from decimal import Decimal
from typing import TYPE_CHECKING

from pydantic import BaseModel

if TYPE_CHECKING:
    from ...core.async_cleanup import AsyncCloseable
    from ...core.operations import (
        OperationCancellation,
        OperationDeadline,
        OperationEffect,
        OperationLifecycle,
        OperationTerminalCondition,
    )
    from ...domain.calculations.registry.authority import PinnedAuthorityOperation
    from ._execution_context import DefinitionBoundContext
    from .financial_operand import (
        OperationTransientFinancialOperandDelivery,
        OperationTransientFinancialOperandRequirement,
    )
    from .financial_operand_submission import (
        BoundTransientFinancialOperandAccess,
        OperationTransientFinancialOperandBroker,
    )
    from .interactions import (
        OperationApplyResponse,
        OperationConsumedInteraction,
        OperationPendingInteraction,
        OperationRejectResponse,
    )
    from .models import (
        OperationId,
        OperationIdentity,
        OperationReference,
        OperationRequest,
        OperationTerminalReceipt,
    )
    from .persistence.events import OperationEvent
    from .persistence.idempotency import OperationIdempotencyClaim
    from .persistence.journal import (
        OperationJournal,
        OperationLeaseRepository,
        OperationPersistedSnapshot,
        OperationSecureReferenceStore,
    )
    from .persistence.leases import OperationOwnerLease
    from .projection_services import OperationResponseAuthorityIssuer
    from .registry import OperationDefinition, OperationRegistry
    from .secret_submission import EphemeralSecretBroker, OperationSecretRequirement


class SupervisorHost:
    """The composed supervisor surface every stage mixin may rely on."""

    if TYPE_CHECKING:
        registry: OperationRegistry
        _authority_operation: PinnedAuthorityOperation
        _journal: OperationJournal
        _leases: OperationLeaseRepository
        _operands: OperationSecureReferenceStore | None
        _clock: Callable[[], datetime]
        _execution_timeout: timedelta | None
        _cleanup_timeout: timedelta | None
        _response_authority_issuer: OperationResponseAuthorityIssuer | None
        _response_token_factory: Callable[[], str]
        _leases_by_operation: dict[OperationId, OperationOwnerLease]
        _contexts: dict[OperationId, DefinitionBoundContext]
        _executor_tasks: dict[OperationId, asyncio.Task[OperationReference | None]]
        _continuation_tasks: dict[OperationId, asyncio.Task[OperationPersistedSnapshot]]
        _durable_change_events: dict[OperationId, asyncio.Event]
        _durable_revisions: dict[OperationId, int]
        _ephemeral_secrets: EphemeralSecretBroker
        _financial_operands: OperationTransientFinancialOperandBroker | None
        _resources: dict[OperationId, list[AsyncCloseable]]
        _cleanup_tasks: dict[OperationId, asyncio.Task[None]]

        @staticmethod
        def _validate_request_payload[RequestPayloadT: BaseModel](
            request: OperationRequest[RequestPayloadT], request_type: type[BaseModel]
        ) -> None: ...

        def _candidate(self, identity: OperationIdentity, now: datetime) -> OperationOwnerLease: ...

        def _lease_lock(self, operation_id: OperationId) -> asyncio.Lock: ...

        async def _resolve_idempotency(self, claim: OperationIdempotencyClaim | None) -> OperationId | None: ...

        async def _resolve_conflict_submission(self, claim: OperationIdempotencyClaim | None) -> OperationId: ...

        async def _release_exact_lease(self, lease: OperationOwnerLease, *, observed_at: datetime) -> None: ...

        async def _require_owned_lease_unlocked(
            self,
            identity: OperationIdentity,
            now: datetime,
        ) -> OperationOwnerLease: ...

        async def inspect(self, operation_id: OperationId) -> OperationPersistedSnapshot: ...

        async def request_cancel(
            self,
            operation_id: OperationId,
            *,
            expected_revision: int | None = None,
        ) -> OperationPersistedSnapshot: ...

        def _require_cleanup_timeout(self, cancellation: OperationCancellation) -> None: ...

        def _build_context(self, snapshot: OperationPersistedSnapshot) -> DefinitionBoundContext: ...

        def _bound_financial_operand(
            self,
            identity: OperationIdentity,
            definition: OperationDefinition,
        ) -> BoundTransientFinancialOperandAccess: ...

        async def _settle_financial_operand_custody(self, operation_id: OperationId) -> None: ...

        async def settle(
            self,
            operation_id: OperationId,
            receipt: OperationTerminalReceipt,
        ) -> OperationPersistedSnapshot: ...

        def _validate_cancelled_settlement(self, snapshot: OperationPersistedSnapshot) -> None: ...

        async def _renew_while_executing[ResultT](
            self,
            *,
            identity: OperationIdentity,
            executor: Coroutine[None, None, ResultT],
        ) -> ResultT: ...

        @staticmethod
        async def _wait_for_executor_or_deadline(
            executor_task: asyncio.Task[OperationReference | None], deadline: datetime, now: datetime
        ) -> None: ...

        @staticmethod
        def _acknowledged_cancellation_condition(
            snapshot: OperationPersistedSnapshot,
        ) -> OperationTerminalCondition: ...

        async def _escalate_cleanup_deadline(self, operation_id: OperationId) -> OperationPersistedSnapshot: ...

        def _notify_durable_change(self, snapshot: OperationPersistedSnapshot) -> None: ...

        async def _resume_from_checkpoint(
            self,
            snapshot: OperationPersistedSnapshot,
            definition: OperationDefinition,
            checkpoint: OperationPendingInteraction | OperationConsumedInteraction,
        ) -> OperationPersistedSnapshot: ...

        def _continuation_completed(self, task: asyncio.Task[OperationPersistedSnapshot]) -> None: ...

        async def submit[RequestPayloadT: BaseModel](
            self,
            request: OperationRequest[RequestPayloadT],
            *,
            operation_id: OperationId | None = None,
        ) -> OperationId: ...

        def _require_pinned_definition(self, snapshot: OperationPersistedSnapshot) -> OperationDefinition: ...

        async def _load_pinned_snapshot(self, operation_id: OperationId) -> OperationPersistedSnapshot: ...

        async def start(self, operation_id: OperationId) -> OperationPersistedSnapshot: ...

        async def submit_transient_financial_operand(
            self,
            requirement: OperationTransientFinancialOperandRequirement,
            amount: Decimal,
        ) -> OperationTransientFinancialOperandDelivery: ...

        async def submit_ephemeral_secret(
            self,
            requirement: OperationSecretRequirement,
            secret: bytearray,
        ) -> None: ...

        async def _resolve_request_payload(
            self,
            snapshot: OperationPersistedSnapshot,
            definition: OperationDefinition,
        ) -> BaseModel: ...

        async def _settle_pre_entry_secret_wait(
            self,
            snapshot: OperationPersistedSnapshot,
            condition: OperationTerminalCondition,
        ) -> OperationPersistedSnapshot: ...

        async def _settle_executor_failure(
            self,
            snapshot: OperationPersistedSnapshot,
            error: Exception,
        ) -> OperationPersistedSnapshot: ...

        async def _advance(
            self,
            snapshot: OperationPersistedSnapshot,
            *,
            lifecycle: OperationLifecycle,
            events: tuple[OperationEvent, ...] = (),
            pending: OperationPendingInteraction | None = None,
            consumed: tuple[OperationConsumedInteraction, ...] | None = None,
            effect: OperationEffect | None = None,
            execution_deadline: datetime | None = None,
            cleanup_deadline: datetime | None = None,
            cancellation_requested_at: datetime | None = None,
            cancellation_acknowledged_at: datetime | None = None,
            cancellation_deferred: bool | None = None,
            executor_entered_at: datetime | None = None,
            discard_ephemeral_secret: bool = False,
        ) -> OperationPersistedSnapshot: ...

        @staticmethod
        def _executor_failure_diagnostic_reference(
            snapshot: OperationPersistedSnapshot,
            error: Exception,
        ) -> str: ...

        def _execution_deadline_for(self, deadline_capability: OperationDeadline) -> datetime | None: ...

        async def _execute_with_deadlines(
            self,
            *,
            identity: OperationIdentity,
            context: DefinitionBoundContext,
            executor: Coroutine[None, None, OperationReference | None],
        ) -> OperationReference | None: ...

        async def _settle_returned_result(
            self,
            snapshot: OperationPersistedSnapshot,
            result_ref: OperationReference | None,
        ) -> OperationPersistedSnapshot: ...

        async def await_terminal(self, operation_id: OperationId) -> OperationPersistedSnapshot: ...

        async def respond(
            self,
            response: OperationApplyResponse | OperationRejectResponse,
        ) -> OperationConsumedInteraction: ...

        def _schedule_continuation(
            self,
            snapshot: OperationPersistedSnapshot,
            definition: OperationDefinition,
            continuation: OperationConsumedInteraction,
        ) -> None: ...

        async def _acknowledge_cancellation(
            self,
            context_snapshot: OperationPersistedSnapshot,
        ) -> OperationPersistedSnapshot: ...

        async def _set_cancellation_deferred(
            self,
            context_snapshot: OperationPersistedSnapshot,
            deferred: bool,
        ) -> OperationPersistedSnapshot: ...

        async def _cancel_pre_entry_secret(
            self,
            snapshot: OperationPersistedSnapshot,
        ) -> OperationPersistedSnapshot | None: ...

        def _validate_executor_stopped_for_settlement(
            self,
            snapshot: OperationPersistedSnapshot,
            condition: OperationTerminalCondition,
        ) -> None: ...
