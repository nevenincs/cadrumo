"""One-shot custody of exact typed batches under the supervisor transition lock."""

from __future__ import annotations

import asyncio
import secrets
from collections.abc import AsyncGenerator, Awaitable, Callable
from contextlib import asynccontextmanager
from dataclasses import dataclass, field
from datetime import datetime
from hashlib import sha256
from hmac import compare_digest
from typing import Never

from pydantic import BaseModel

from ...core.async_cleanup import await_cancellation_complete
from ...core.errors.hierarchy import InternalInvariantError
from ...core.logging import get_logger
from ...core.operations import OperationEffect
from .financial_operand_contract import (
    OperationFinancialOperandEffectReceiptV1,
    OperationFinancialOperandRefusalCode,
    OperationFinancialOperandRefusedError,
    OperationTransientFinancialOperandDeclarationV1,
    OperationTransientFinancialOperandRequirementV1,
    OperationTransientFinancialOperandSubmissionV1,
)
from .financial_operand_custody import (
    OperationFinancialOperandCustodyCheckpointV1,
    OperationFinancialOperandCustodyState,
)
from .models import OperationId, OperationIdentity, OperationRevision
from .persistence.financial_operand_custody import OperationTypedFinancialOperandCustodyRepository

type FinancialOperandBindingGuard = Callable[[OperationTransientFinancialOperandRequirementV1], Awaitable[None]]
type FinancialOperandExpirySettlement = Callable[[OperationTransientFinancialOperandRequirementV1], Awaitable[None]]

_log = get_logger(__name__)

_PRE_DELIVERY = frozenset(
    {
        OperationFinancialOperandCustodyState.AWAITING_SUBMISSION,
        OperationFinancialOperandCustodyState.BOUND,
    }
)


@dataclass(slots=True)
class _TypedWait:
    declaration: OperationTransientFinancialOperandDeclarationV1
    checkpoint: OperationFinancialOperandCustodyCheckpointV1
    operand: BaseModel | None = field(default=None, repr=False)
    delivery_complete: asyncio.Event = field(default_factory=asyncio.Event, repr=False)


class OperationTypedFinancialOperandBroker:
    """Hold one model until its executor takes it, without serialization or value hashing.

    Every durable transition and binding guard runs under the exact lock used
    by operation settlement. The lock is released while application code uses
    the batch. Delivery custody cannot expire or cancel after consumption.
    """

    def __init__(
        self,
        *,
        custody: OperationTypedFinancialOperandCustodyRepository,
        clock: Callable[[], datetime],
        lock_for: Callable[[OperationId], asyncio.Lock],
        require_current: FinancialOperandBindingGuard,
        settle_expiry: FinancialOperandExpirySettlement,
    ) -> None:
        """Bind durable custody to the supervisor's exact operation lock and guards."""
        self._custody = custody
        self._clock = clock
        self._lock_for = lock_for
        self._require_current = require_current
        self._settle_expiry = settle_expiry
        self._waits: dict[OperationId, _TypedWait] = {}
        self._timers: dict[OperationId, asyncio.Task[None]] = {}
        self._closed = False
        self._close_tasks: dict[OperationId, asyncio.Task[None]] = {}

    async def open(
        self,
        *,
        declaration: OperationTransientFinancialOperandDeclarationV1,
        identity: OperationIdentity,
        revision: OperationRevision,
        domain_baseline_ref: str,
        bind_requirement: FinancialOperandBindingGuard | None = None,
    ) -> OperationTransientFinancialOperandSubmissionV1:
        """Create one amount-free requirement and return its private call-scoped grant."""
        grant = bytearray(secrets.token_bytes(32))
        requirement = OperationTransientFinancialOperandRequirementV1(
            identity=identity,
            invocation_revision=revision,
            handoff_id=secrets.token_hex(32),
            grant_fingerprint=sha256(grant).hexdigest(),
            operand_schema=declaration.operand_schema,
            baseline_schema=declaration.baseline_schema,
            domain_baseline_ref=domain_baseline_ref,
            expires_at=self._clock() + declaration.lifetime,
        )
        submission = OperationTransientFinancialOperandSubmissionV1(requirement, grant, None)
        try:
            async with self._lock_for(identity.operation_id):

                async def establish() -> None:
                    if self._closed:
                        self._refuse(OperationFinancialOperandRefusalCode.OWNER_LOST)
                    if bind_requirement is not None:
                        await bind_requirement(requirement)
                    await self._require_current(requirement)
                    if identity.operation_id in self._waits:
                        self._refuse(OperationFinancialOperandRefusalCode.DUPLICATE_SUBMISSION)
                    checkpoint = OperationFinancialOperandCustodyCheckpointV1(
                        requirement=requirement,
                        sequence=1,
                        state=OperationFinancialOperandCustodyState.AWAITING_SUBMISSION,
                        recorded_at=self._clock(),
                    )

                    async def persist() -> None:
                        await self._custody.open(checkpoint)
                        self._waits[identity.operation_id] = _TypedWait(declaration, checkpoint)
                        timer = asyncio.create_task(
                            self._expire_at(requirement), name=f"financial-custody-expiry-{identity.operation_id}"
                        )
                        self._timers[identity.operation_id] = timer
                        timer.add_done_callback(self._expiry_completed)

                    await persist()

                await await_cancellation_complete(establish(), task_name="financial-custody-open")
            return submission
        except BaseException:
            submission.release()
            raise

    async def submit(self, submission: OperationTransientFinancialOperandSubmissionV1) -> None:
        """Bind the exact complete model once and always discard the submitting bearer."""
        requirement = submission.requirement
        operand: BaseModel | None = None
        try:
            async with self._lock_for(requirement.identity.operation_id):
                wait = self._exact_wait(requirement)
                await self._require_current(requirement)
                self._require_unexpired(requirement)
                if wait.checkpoint.state is not OperationFinancialOperandCustodyState.AWAITING_SUBMISSION:
                    self._refuse(OperationFinancialOperandRefusalCode.DUPLICATE_SUBMISSION)
                if len(submission.grant) != 32 or not compare_digest(
                    sha256(submission.grant).hexdigest(), requirement.grant_fingerprint
                ):
                    self._refuse(OperationFinancialOperandRefusalCode.WRONG_GRANT)
                operand = submission.operand
                if operand is None or type(operand) is not wait.declaration.operand_type:
                    self._refuse(OperationFinancialOperandRefusalCode.WRONG_MODEL)
                baseline = wait.declaration.baseline_accessor(operand)
                if type(baseline) is not wait.declaration.baseline_type or (
                    wait.declaration.baseline_reference(baseline) != requirement.domain_baseline_ref
                ):
                    self._refuse(OperationFinancialOperandRefusalCode.WRONG_BASELINE)

                async def bind() -> None:
                    await self._advance(wait, OperationFinancialOperandCustodyState.BOUND)
                    wait.operand = operand

                await await_cancellation_complete(bind(), task_name="financial-custody-bind")
        finally:
            operand = None
            submission.release()

    @asynccontextmanager
    async def consume(
        self,
        requirement: OperationTransientFinancialOperandRequirementV1,
        declaration: OperationTransientFinancialOperandDeclarationV1,
    ) -> AsyncGenerator[BaseModel]:
        """Persist delivery before removing the only broker reference, then release it."""
        operand: BaseModel | None = None
        owns_delivery = False
        delivery_complete: asyncio.Event | None = None
        wait: _TypedWait | None = None
        try:
            async with self._lock_for(requirement.identity.operation_id):
                wait = self._exact_wait(requirement)
                await self._require_current(requirement)
                if wait.declaration is not declaration:
                    self._refuse(OperationFinancialOperandRefusalCode.WRONG_MODEL)
                if wait.checkpoint.state is not OperationFinancialOperandCustodyState.BOUND or wait.operand is None:
                    self._refuse(OperationFinancialOperandRefusalCode.DUPLICATE_CONSUMPTION)
                self._require_unexpired(requirement)

                async def take() -> None:
                    nonlocal operand, owns_delivery, delivery_complete
                    await self._advance(wait, OperationFinancialOperandCustodyState.DELIVERY_STARTED)
                    operand, wait.operand = wait.operand, None
                    owns_delivery = True
                    delivery_complete = wait.delivery_complete
                    await self._advance(wait, OperationFinancialOperandCustodyState.DELIVERY_ACKNOWLEDGED)

                await await_cancellation_complete(take(), task_name="financial-custody-consume")
            if operand is None:
                raise InternalInvariantError("financial custody delivered no operand")
            yield operand
        finally:
            operand = None
            try:
                if (
                    owns_delivery
                    and wait is not None
                    and wait.checkpoint.state is OperationFinancialOperandCustodyState.DELIVERY_ACKNOWLEDGED
                ):

                    async def release() -> None:
                        async with self._lock_for(requirement.identity.operation_id):
                            if wait.checkpoint.state is OperationFinancialOperandCustodyState.DELIVERY_ACKNOWLEDGED:
                                await self._advance(wait, OperationFinancialOperandCustodyState.RELEASED)

                    await await_cancellation_complete(release(), task_name="financial-custody-release")

            finally:
                if delivery_complete is not None:
                    delivery_complete.set()

    async def require_ready(self, requirement: OperationTransientFinancialOperandRequirementV1) -> None:
        """Refuse executor entry until the exact unexpired batch is bound."""
        async with self._lock_for(requirement.identity.operation_id):
            wait = self._exact_wait(requirement)
            await self._require_current(requirement)
            self._require_unexpired(requirement)
            if wait.checkpoint.state is not OperationFinancialOperandCustodyState.BOUND or wait.operand is None:
                self._refuse(OperationFinancialOperandRefusalCode.DUPLICATE_CONSUMPTION)

    async def cancel(self, requirement: OperationTransientFinancialOperandRequirementV1) -> bool:
        """Cancel only pre-delivery custody; the executor owns any consumed batch."""
        async with self._lock_for(requirement.identity.operation_id):
            wait = self._exact_wait(requirement)
            await self._require_current(requirement)
            if wait.checkpoint.state not in _PRE_DELIVERY:
                return False
            await await_cancellation_complete(
                self._end_wait(wait, OperationFinancialOperandCustodyState.CANCELLED),
                task_name="financial-custody-cancel",
            )
            return True

    async def reconcile(
        self,
        requirement: OperationTransientFinancialOperandRequirementV1,
        declaration: OperationTransientFinancialOperandDeclarationV1,
    ) -> OperationFinancialOperandEffectReceiptV1:
        """Use only exact co-committed domain proof after owner loss, never refreshed state."""
        async with self._lock_for(requirement.identity.operation_id):
            checkpoint = await self._custody.read(requirement.handoff_id)
            if checkpoint is None or checkpoint.requirement != requirement:
                self._refuse(OperationFinancialOperandRefusalCode.UNKNOWN_REQUIREMENT)
            receipt = await declaration.effect_receipt_resolver(requirement)
            if receipt is not None:
                if (
                    receipt.identity != requirement.identity
                    or receipt.handoff_id != requirement.handoff_id
                    or receipt.domain_baseline_ref != requirement.domain_baseline_ref
                ):
                    self._refuse(OperationFinancialOperandRefusalCode.WRONG_BASELINE)
                return receipt
            effect = (
                OperationEffect.NONE
                if checkpoint.state
                in _PRE_DELIVERY
                | {
                    OperationFinancialOperandCustodyState.EXPIRED,
                    OperationFinancialOperandCustodyState.CANCELLED,
                }
                else OperationEffect.UNKNOWN
            )
            return OperationFinancialOperandEffectReceiptV1(
                identity=requirement.identity,
                handoff_id=requirement.handoff_id,
                domain_baseline_ref=requirement.domain_baseline_ref,
                effect=effect,
            )

    async def settle_operation(self, operation_id: OperationId) -> None:
        """Finish or refuse custody before settlement can publish a terminal receipt."""
        async with self._lock_for(operation_id):
            wait = self._waits.get(operation_id)
            if wait is None:
                return
            wait.operand = None
            if wait.checkpoint.state in _PRE_DELIVERY:
                await self._advance(wait, OperationFinancialOperandCustodyState.CANCELLED)
            elif wait.checkpoint.state is OperationFinancialOperandCustodyState.DELIVERY_ACKNOWLEDGED:
                if not wait.delivery_complete.is_set():
                    raise InternalInvariantError("financial executor still owns its delivery scope")
                await self._advance(wait, OperationFinancialOperandCustodyState.RELEASED)
            elif wait.checkpoint.state is OperationFinancialOperandCustodyState.DELIVERY_STARTED:
                raise InternalInvariantError("financial delivery acknowledgement is not proven")

    def begin_close(self) -> dict[OperationId, asyncio.Task[None]]:
        """Drop retained batches immediately and expose every close task for bounded drain."""
        self._closed = True
        for timer in self._timers.values():
            timer.cancel()
        for operation_id, wait in self._waits.items():
            wait.operand = None
            if operation_id not in self._close_tasks:

                async def finish(identifier: OperationId = operation_id) -> None:
                    timer = self._timers.get(identifier)
                    if timer is not None:
                        await asyncio.gather(timer, return_exceptions=True)
                    await await_cancellation_complete(
                        self._close_delivery(identifier),
                        task_name="financial-custody-close",
                    )

                task = asyncio.create_task(finish(), name=f"financial-custody-close-{operation_id}")
                self._close_tasks[operation_id] = task
        return dict(self._close_tasks)

    async def _close_delivery(self, operation_id: OperationId) -> None:
        """Wait for a delivered scope to drop its batch before releasing custody."""
        async with self._lock_for(operation_id):
            wait = self._waits[operation_id]
            delivered = wait.checkpoint.state in {
                OperationFinancialOperandCustodyState.DELIVERY_STARTED,
                OperationFinancialOperandCustodyState.DELIVERY_ACKNOWLEDGED,
            }
        if delivered:
            await wait.delivery_complete.wait()
        await self.settle_operation(operation_id)

    async def close(self) -> None:
        """Await owned close tasks; hosts use begin_close to retain their total drain bound."""
        tasks = tuple(self.begin_close().values())
        if tasks:
            await asyncio.gather(*tasks)

    @staticmethod
    def _expiry_completed(task: asyncio.Task[None]) -> None:
        if task.cancelled():
            return
        failure = task.exception()
        if failure is not None:
            _log.error("financial custody expiry settlement failed: %s", task.get_name(), exc_info=failure)

    async def _expire_at(self, requirement: OperationTransientFinancialOperandRequirementV1) -> None:
        while True:
            remaining = (requirement.expires_at - self._clock()).total_seconds()
            if remaining <= 0:
                break
            await asyncio.sleep(remaining)
        expired = False
        async with self._lock_for(requirement.identity.operation_id):
            wait = self._exact_wait(requirement)
            if wait.checkpoint.state in _PRE_DELIVERY:
                await self._end_wait(wait, OperationFinancialOperandCustodyState.EXPIRED)
                expired = True
        if expired:
            # Settlement takes the operation lock itself, so it runs after custody released it.
            await self._settle_expiry(requirement)

    async def _end_wait(self, wait: _TypedWait, state: OperationFinancialOperandCustodyState) -> None:
        try:
            await self._advance(wait, state)
        finally:
            wait.operand = None

    async def _advance(self, wait: _TypedWait, state: OperationFinancialOperandCustodyState) -> None:
        successor = wait.checkpoint.successor(state, now=self._clock())
        await self._custody.advance(wait.checkpoint, successor)
        wait.checkpoint = successor

    def _exact_wait(self, requirement: OperationTransientFinancialOperandRequirementV1) -> _TypedWait:
        if self._closed:
            self._refuse(OperationFinancialOperandRefusalCode.OWNER_LOST)
        wait = self._waits.get(requirement.identity.operation_id)
        if wait is None or wait.checkpoint.requirement != requirement:
            self._refuse(OperationFinancialOperandRefusalCode.UNKNOWN_REQUIREMENT)
        return wait

    def _require_unexpired(self, requirement: OperationTransientFinancialOperandRequirementV1) -> None:
        if self._clock() >= requirement.expires_at:
            self._refuse(OperationFinancialOperandRefusalCode.EXPIRED)

    @staticmethod
    def _refuse(reason: OperationFinancialOperandRefusalCode) -> Never:
        raise OperationFinancialOperandRefusedError(reason)
