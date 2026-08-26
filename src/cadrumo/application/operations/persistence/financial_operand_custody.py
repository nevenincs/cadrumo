"""Durable custody-checkpoint persistence contract for financial operands.

The repository stores the checkpoints defined by the operand custody contract
and nothing else. Its guarantee is narrow and load-bearing: an advance is
accepted only when it follows the predecessor the caller actually observed, so
two supervisor paths racing to settle one wait cannot both win.

That compare-and-swap is what makes release exactly-once at the durable layer
rather than only in memory. The in-process transition table refuses an illegal
move; this refuses a legal move applied twice.

See Also:
    :class:`~cadrumo.application.operations._financial_operand_custody.OperationFinancialOperandCustodyCheckpoint`
        The non-sensitive record this contract persists and replays.
"""

from __future__ import annotations

from typing import TYPE_CHECKING, Protocol, runtime_checkable

if TYPE_CHECKING:
    from .._financial_operand_custody import OperationFinancialOperandCustodyCheckpoint


class OperationFinancialOperandCustodyConflictError(RuntimeError):
    """Raised when a custody advance loses its compare-and-swap."""


@runtime_checkable
class OperationFinancialOperandCustodyRepository(Protocol):
    """Persist and replay one operand wait's custody positions."""

    async def read(self, interaction_id: str) -> OperationFinancialOperandCustodyCheckpoint | None:
        """Return the latest checkpoint for one wait, or ``None`` if never opened."""
        ...

    async def open(self, checkpoint: OperationFinancialOperandCustodyCheckpoint) -> None:
        """Record the opening checkpoint, refusing a wait that already exists."""
        ...

    async def advance(
        self,
        predecessor: OperationFinancialOperandCustodyCheckpoint,
        successor: OperationFinancialOperandCustodyCheckpoint,
    ) -> None:
        """Replace ``predecessor`` with ``successor`` only if it is still current.

        Raises:
            OperationFinancialOperandCustodyConflictError: The stored checkpoint
                is no longer ``predecessor``, so another path already settled or
                advanced this wait.
        """
        ...

    async def unsettled(self) -> tuple[OperationFinancialOperandCustodyCheckpoint, ...]:
        """Return every wait left in a non-terminal state, for restart reconciliation."""
        ...


__all__ = [
    "OperationFinancialOperandCustodyConflictError",
    "OperationFinancialOperandCustodyRepository",
]
