"""Runtime custody broker for transient financial operands supplied mid-flight.

The broker owns nothing new. It composes the three pieces that already define
what an operand is: the declaration and settlement contracts, the fixed custody
order, and the durable checkpoint repository. Its whole job is to hold one
amount in process memory between the operator submitting it and the executor
reading it, and to make sure the durable record of that window is written
before the amount is exposed rather than after.

The order of the durable writes is the load-bearing part. A submission that is
accepted is journalled open, bound, and delivery-started in that order, all
before the executor can read it, so a process that dies while the executor
holds the amount reconciles as delivery-uncertain. Writing the checkpoints
after the read would let the same crash reconcile as not-delivered, which is a
manufactured claim that the executor never saw a figure it may well have acted
on.

Nothing here stores an amount anywhere but a private mapping, and nothing here
returns a durable derivative of one. The value leaves only through
:meth:`OperationTransientFinancialOperandBroker.grant_access`, scoped to the
executor that declared it.

See Also:
    :class:`~cadrumo.application.operations.financial_operand.OperationTransientFinancialOperandProtocolV1`
        The broker contract this class implements.
    :class:`~cadrumo.application.operations.secret_submission.EphemeralSecretBroker`
        The sibling broker for credential material, deliberately separate.
"""

from __future__ import annotations

from threading import RLock
from typing import TYPE_CHECKING, Protocol, runtime_checkable

from ...core.hashing import content_hash_hex
from .financial_operand import (
    OperationFinancialOperandRefusalReason,
    OperationTransientFinancialOperandAccess,
    OperationTransientFinancialOperandAcknowledgement,
    OperationTransientFinancialOperandDeclaration,
    OperationTransientFinancialOperandExpiry,
    OperationTransientFinancialOperandRefusal,
    OperationTransientFinancialOperandRelease,
    OperationTransientFinancialOperandRequirement,
)
from .financial_operand_custody import (
    OperationFinancialOperandCustodyCheckpoint,
    OperationFinancialOperandCustodyState,
    advance_custody,
    open_custody,
    reconcile_on_restart,
)

if TYPE_CHECKING:
    from collections.abc import Callable
    from datetime import datetime
    from decimal import Decimal

    from .financial_operand import (
        OperationFinancialOperandKind,
        OperationTransientFinancialOperandDelivery,
    )
    from .interactions import OperationInteractionId
    from .models import OperationId, OperationIdentity, OperationRevision
    from .persistence.financial_operand_custody import (
        OperationFinancialOperandCustodyRepository,
    )


def financial_operand_interaction_id(
    *,
    identity: OperationIdentity,
    revision: OperationRevision,
    operand_kind: OperationFinancialOperandKind,
) -> OperationInteractionId:
    """Derive the one interaction identifier a declared operand wait is addressed by.

    The derivation is deterministic so an operator frontend can address the
    wait it is answering without the executor having to hand it a handle
    first, and so a redeclaration inside the executor names the same wait.
    """
    return content_hash_hex(
        {
            "schema_version": 1,
            "identity": identity.model_dump(mode="json"),
            "revision": revision,
            "operand_kind": operand_kind,
        }
    )


class _OperandWait:
    """One live wait: what was declared, where custody stands, and the amount."""

    __slots__ = ("amount", "checkpoint", "declaration", "requirement")

    def __init__(
        self,
        *,
        declaration: OperationTransientFinancialOperandDeclaration,
        requirement: OperationTransientFinancialOperandRequirement,
        checkpoint: OperationFinancialOperandCustodyCheckpoint,
    ) -> None:
        self.declaration = declaration
        self.requirement = requirement
        self.checkpoint = checkpoint
        self.amount: Decimal | None = None


@runtime_checkable
class OperationFinancialOperandContextAccess(Protocol):
    """The operand surface an executor context exposes for one invocation."""

    def declare_requirement(
        self,
        declaration: OperationTransientFinancialOperandDeclaration,
    ) -> OperationTransientFinancialOperandRequirement:
        """Open the bounded wait for one operand this definition declared."""
        ...

    def grant_access(
        self,
        requirement: OperationTransientFinancialOperandRequirement,
    ) -> OperationTransientFinancialOperandAccess:
        """Return scoped access to the amount accepted for one requirement."""
        ...


class GrantedTransientFinancialOperandAccess:
    """Executor-scoped read of one accepted operand, bound to its requirement."""

    def __init__(
        self,
        *,
        requirement: OperationTransientFinancialOperandRequirement,
        broker: OperationTransientFinancialOperandBroker,
    ) -> None:
        """Bind one accepted requirement to the broker holding its amount."""
        self._requirement = requirement
        self._broker = broker

    @property
    def requirement(self) -> OperationTransientFinancialOperandRequirement:
        """Return the exact requirement this access was granted for."""
        return self._requirement

    def declared_operand(
        self,
        requirement: OperationTransientFinancialOperandRequirement,
    ) -> Decimal:
        """Return the amount in custody for one requirement this executor owns."""
        if requirement != self._requirement:
            raise ValueError("transient financial operand access does not cover this requirement")
        return self._broker.read_operand(requirement)


class BoundTransientFinancialOperandAccess:
    """The one operand surface an executor sees, scoped to its own invocation.

    The executor names a declaration its definition already carries; the
    identity, revision and derived interaction identifier come from the
    supervisor, so an executor cannot open a wait against another invocation
    or against an operand kind it never declared.
    """

    def __init__(
        self,
        *,
        declarations: tuple[OperationTransientFinancialOperandDeclaration, ...],
        broker: OperationTransientFinancialOperandBroker | None,
        identity: OperationIdentity,
        revision: OperationRevision,
    ) -> None:
        """Bind one invocation to the declarations its definition carries."""
        self._declarations = declarations
        self._broker = broker
        self._identity = identity
        self._revision = revision

    def declare_requirement(
        self,
        declaration: OperationTransientFinancialOperandDeclaration,
    ) -> OperationTransientFinancialOperandRequirement:
        """Open the bounded wait for one operand this definition declared."""
        broker = self._require_broker()
        if declaration not in self._declarations:
            raise ValueError("operation definition does not declare this transient financial operand")
        return broker.declare_requirement(
            declaration,
            identity=self._identity,
            interaction_id=financial_operand_interaction_id(
                identity=self._identity,
                revision=self._revision,
                operand_kind=declaration.operand_kind,
            ),
            revision=self._revision,
        )

    def grant_access(
        self,
        requirement: OperationTransientFinancialOperandRequirement,
    ) -> GrantedTransientFinancialOperandAccess:
        """Return scoped access to the amount accepted for one requirement."""
        broker = self._require_broker()
        if requirement.identity != self._identity:
            raise ValueError("transient financial operand requirement belongs to another invocation")
        return broker.grant_access(requirement)

    def _require_broker(self) -> OperationTransientFinancialOperandBroker:
        if self._broker is None or not self._declarations:
            raise ValueError("operation definition does not declare a transient financial operand")
        return self._broker


class OperationTransientFinancialOperandBroker:
    """Supervisor-private operand custody over a durable checkpoint repository."""

    def __init__(
        self,
        *,
        custody: OperationFinancialOperandCustodyRepository,
        clock: Callable[[], datetime],
    ) -> None:
        """Bind the durable custody repository and the supervisor clock."""
        self._custody = custody
        self._clock = clock
        self._waits: dict[OperationInteractionId, _OperandWait] = {}
        self._by_operation: dict[OperationId, set[OperationInteractionId]] = {}
        self._closed = False
        self._lock = RLock()

    def declare_requirement(
        self,
        declaration: OperationTransientFinancialOperandDeclaration,
        *,
        identity: OperationIdentity,
        interaction_id: OperationInteractionId,
        revision: OperationRevision,
    ) -> OperationTransientFinancialOperandRequirement:
        """Open one bounded wait for the operand this declaration describes.

        Redeclaring the same wait returns the requirement already open rather
        than restarting its lifetime, so an executor and an operator frontend
        that both address the wait cannot disagree about when it lapses.
        """
        with self._lock:
            if self._closed:
                raise ValueError("transient financial operand channel is closed")
            existing = self._waits.get(interaction_id)
            if existing is not None:
                if existing.declaration != declaration or existing.requirement.identity != identity:
                    raise ValueError("transient financial operand wait was already declared differently")
                return existing.requirement
            now = self._clock()
            requirement = OperationTransientFinancialOperandRequirement(
                identity=identity,
                interaction_id=interaction_id,
                revision=revision,
                operand_kind=declaration.operand_kind,
                expires_at=now + declaration.lifetime,
            )
            self._waits[interaction_id] = _OperandWait(
                declaration=declaration,
                requirement=requirement,
                checkpoint=open_custody(requirement, now=now),
            )
            self._by_operation.setdefault(identity.operation_id, set()).add(interaction_id)
            return requirement

    async def deliver(
        self,
        requirement: OperationTransientFinancialOperandRequirement,
        amount: Decimal,
        *,
        observed_at: datetime,
    ) -> OperationTransientFinancialOperandDelivery:
        """Settle one submission against the declaration that opened its wait.

        The durable checkpoints are written here, before the amount becomes
        readable, and the wait is journalled open whether the submission is
        accepted or refused so a refused wait is still reconcilable.
        """
        wait = self._require_open_wait(requirement)
        await self._journal_open(wait)
        refusal = self._refusal_reason(wait, amount, observed_at=observed_at)
        if refusal is not None:
            return OperationTransientFinancialOperandRefusal(
                requirement=requirement,
                reason=refusal,
                refused_at=observed_at,
            )
        await self._advance(wait, OperationFinancialOperandCustodyState.BOUND, now=observed_at)
        await self._advance(wait, OperationFinancialOperandCustodyState.DELIVERY_STARTED, now=observed_at)
        with self._lock:
            wait.amount = amount
        return OperationTransientFinancialOperandAcknowledgement(
            requirement=requirement,
            accepted_at=observed_at,
        )

    def grant_access(
        self,
        requirement: OperationTransientFinancialOperandRequirement,
    ) -> GrantedTransientFinancialOperandAccess:
        """Return executor-scoped access to one accepted operand."""
        with self._lock:
            wait = self._waits.get(requirement.interaction_id)
            if wait is None or wait.requirement != requirement:
                raise ValueError("transient financial operand requirement is unknown")
            if wait.amount is None:
                raise ValueError("transient financial operand requirement has no accepted submission")
        return GrantedTransientFinancialOperandAccess(requirement=requirement, broker=self)

    def read_operand(
        self,
        requirement: OperationTransientFinancialOperandRequirement,
    ) -> Decimal:
        """Return the amount held for one requirement, refusing a released wait."""
        with self._lock:
            wait = self._waits.get(requirement.interaction_id)
            if wait is None or wait.requirement != requirement or wait.amount is None:
                raise ValueError("transient financial operand requirement holds no amount")
            return wait.amount

    def release(
        self,
        requirement: OperationTransientFinancialOperandRequirement,
    ) -> OperationTransientFinancialOperandRelease:
        """End runtime custody of one operand and clear the buffer holding it."""
        with self._lock:
            wait = self._waits.pop(requirement.interaction_id, None)
            if wait is None or wait.requirement != requirement:
                raise ValueError("transient financial operand requirement is unknown")
            wait.amount = None
            interactions = self._by_operation.get(requirement.identity.operation_id)
            if interactions is not None:
                interactions.discard(requirement.interaction_id)
                if not interactions:
                    del self._by_operation[requirement.identity.operation_id]
            return OperationTransientFinancialOperandRelease(
                requirement=requirement,
                released_at=self._clock(),
            )

    def expire_lapsed(
        self,
        *,
        now: datetime,
    ) -> tuple[OperationTransientFinancialOperandExpiry, ...]:
        """Settle every wait whose declared lifetime has elapsed."""
        with self._lock:
            lapsed = [wait for wait in self._waits.values() if now >= wait.requirement.expires_at]
            expiries: list[OperationTransientFinancialOperandExpiry] = []
            for wait in lapsed:
                self.release(wait.requirement)
                expiries.append(OperationTransientFinancialOperandExpiry(requirement=wait.requirement, expired_at=now))
            return tuple(expiries)

    async def settle(
        self,
        requirement: OperationTransientFinancialOperandRequirement,
        *,
        now: datetime,
    ) -> OperationTransientFinancialOperandRelease:
        """Acknowledge delivery durably, then end runtime custody exactly once."""
        wait = self._require_open_wait(requirement)
        await self._journal_open(wait)
        if wait.amount is not None:
            await self._advance(wait, OperationFinancialOperandCustodyState.DELIVERY_ACKNOWLEDGED, now=now)
            await self._advance(wait, OperationFinancialOperandCustodyState.RELEASED, now=now)
        else:
            await self._advance(wait, OperationFinancialOperandCustodyState.CANCELLED, now=now)
        return self.release(requirement)

    async def settle_operation(self, operation_id: OperationId, *, now: datetime) -> None:
        """Settle every wait one finished operation still holds."""
        with self._lock:
            interaction_ids = tuple(self._by_operation.get(operation_id, ()))
            requirements = [
                self._waits[interaction_id].requirement
                for interaction_id in interaction_ids
                if interaction_id in self._waits
            ]
        for requirement in requirements:
            await self.settle(requirement, now=now)

    async def reconcile_owner_restart(
        self,
        *,
        now: datetime,
    ) -> tuple[OperationFinancialOperandCustodyCheckpoint, ...]:
        """Settle every durable wait an earlier process left unfinished."""
        settled: list[OperationFinancialOperandCustodyCheckpoint] = []
        for checkpoint in await self._custody.unsettled():
            successor = reconcile_on_restart(checkpoint, now=now)
            if successor is checkpoint:
                continue
            await self._custody.advance(checkpoint, successor)
            settled.append(successor)
        return tuple(settled)

    def close(self) -> None:
        """Drop every held amount and refuse further declarations."""
        with self._lock:
            self._closed = True
            for wait in self._waits.values():
                wait.amount = None
            self._waits.clear()
            self._by_operation.clear()

    def _require_open_wait(
        self,
        requirement: OperationTransientFinancialOperandRequirement,
    ) -> _OperandWait:
        with self._lock:
            if self._closed:
                raise ValueError("transient financial operand channel is closed")
            wait = self._waits.get(requirement.interaction_id)
            if wait is None or wait.requirement != requirement:
                raise ValueError("transient financial operand requirement is unknown")
            return wait

    @staticmethod
    def _refusal_reason(
        wait: _OperandWait,
        amount: Decimal,
        *,
        observed_at: datetime,
    ) -> OperationFinancialOperandRefusalReason | None:
        if observed_at >= wait.requirement.expires_at:
            return OperationFinancialOperandRefusalReason.EXPIRED
        if wait.amount is not None:
            return OperationFinancialOperandRefusalReason.ALREADY_SETTLED
        exponent = amount.as_tuple().exponent
        if not isinstance(exponent, int) or -exponent > wait.declaration.scale:
            return OperationFinancialOperandRefusalReason.SCALE_NOT_REPRESENTABLE
        if not wait.declaration.admits(amount):
            return OperationFinancialOperandRefusalReason.OUT_OF_DECLARED_RANGE
        return None

    async def _journal_open(self, wait: _OperandWait) -> None:
        if await self._custody.read(wait.checkpoint.interaction_id) is None:
            await self._custody.open(wait.checkpoint)

    async def _advance(
        self,
        wait: _OperandWait,
        target: OperationFinancialOperandCustodyState,
        *,
        now: datetime,
    ) -> None:
        successor = advance_custody(wait.checkpoint, target, now=now)
        await self._custody.advance(wait.checkpoint, successor)
        with self._lock:
            wait.checkpoint = successor


__all__ = [
    "BoundTransientFinancialOperandAccess",
    "GrantedTransientFinancialOperandAccess",
    "OperationFinancialOperandContextAccess",
    "OperationTransientFinancialOperandBroker",
    "financial_operand_interaction_id",
]
