"""Direct executor fixtures using the real typed broker and its canonical CAS protocol.

Filesystem custody and supervisor ownership are exercised in their owning
adapter tests. This finite repository supplies exactly the canonical port to
tests of executor behavior; it never returns an operand to the executor.
"""

from __future__ import annotations

import asyncio
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager
from datetime import UTC, datetime

from pydantic import BaseModel

from ..financial_operand_contract import OperationTransientFinancialOperandDeclarationV1
from ..financial_operand_custody import OperationFinancialOperandCustodyCheckpointV1
from ..models import OperationIdentity
from ..typed_financial_operand_context import BoundTypedFinancialOperandAccess
from ..typed_financial_operand_submission import OperationTypedFinancialOperandBroker


class _Custody:
    def __init__(self) -> None:
        self.checkpoint: OperationFinancialOperandCustodyCheckpointV1 | None = None

    async def read(self, handoff_id: str) -> OperationFinancialOperandCustodyCheckpointV1 | None:
        checkpoint = self.checkpoint
        return checkpoint if checkpoint is not None and checkpoint.requirement.handoff_id == handoff_id else None

    async def open(self, checkpoint: OperationFinancialOperandCustodyCheckpointV1) -> None:
        assert self.checkpoint is None
        self.checkpoint = checkpoint

    async def advance(
        self,
        predecessor: OperationFinancialOperandCustodyCheckpointV1,
        successor: OperationFinancialOperandCustodyCheckpointV1,
    ) -> None:
        assert self.checkpoint == predecessor
        assert predecessor.successor(successor.state, now=successor.recorded_at) == successor
        self.checkpoint = successor


@asynccontextmanager
async def deliver_financial_operand(
    *,
    identity: OperationIdentity,
    declaration: OperationTransientFinancialOperandDeclarationV1,
    operand: BaseModel,
) -> AsyncIterator[BoundTypedFinancialOperandAccess]:
    """Bind an exact batch through real grant, baseline and one-shot custody checks."""
    lock = asyncio.Lock()

    async def current(requirement) -> None:
        assert lock.locked() and requirement.identity == identity

    async def expired(requirement) -> None:
        raise AssertionError("direct executor fixture exceeded its registered operand lifetime")

    broker = OperationTypedFinancialOperandBroker(
        custody=_Custody(),
        clock=lambda: datetime.now(UTC),
        lock_for=lambda _: lock,
        require_current=current,
        settle_expiry=expired,
    )
    submission = await broker.open(
        declaration=declaration,
        identity=identity,
        revision=0,
        domain_baseline_ref=declaration.baseline_reference(declaration.baseline_accessor(operand)),
    )
    requirement = submission.requirement
    submission.operand = operand
    await broker.submit(submission)
    del operand, submission
    try:
        yield BoundTypedFinancialOperandAccess(broker=broker, declaration=declaration, requirement=requirement)
    finally:
        await broker.close()
