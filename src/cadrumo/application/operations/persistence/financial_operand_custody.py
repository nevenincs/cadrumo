"""Durable custody-checkpoint persistence contract for financial operands.

The repository stores the checkpoints defined by the operand custody contract
and nothing else. Its guarantee is narrow and load-bearing: an advance is
accepted only when it follows the predecessor the caller actually observed, so
two supervisor paths racing to settle one wait cannot both win.

That compare-and-swap is what makes release exactly-once at the durable layer
rather than only in memory. The in-process transition table refuses an illegal
move; this refuses a legal move applied twice.

See Also:
    :class:`~cadrumo.application.operations.financial_operand_custody.OperationFinancialOperandCustodyCheckpointV1`
        The non-sensitive record this contract persists and replays.
"""

from __future__ import annotations

from typing import TYPE_CHECKING, Protocol

from ....core.errors.hierarchy import CadrumoError

if TYPE_CHECKING:
    from ..financial_operand_custody import (
        OperationFinancialOperandCustodyCheckpointV1,
    )


class OperationFinancialOperandCustodyConflictError(CadrumoError):
    """Raised when an exact custody advance loses its compare-and-swap."""


class OperationTypedFinancialOperandCustodyRepository(Protocol):
    """Hardened durable CAS for an exact versioned typed handoff."""

    async def read(self, handoff_id: str) -> OperationFinancialOperandCustodyCheckpointV1 | None:
        """Read the exact last position without reconstructing any operand."""
        ...

    async def open(self, checkpoint: OperationFinancialOperandCustodyCheckpointV1) -> None:
        """Create one requirement once, refusing an existing handoff."""
        ...

    async def advance(
        self,
        predecessor: OperationFinancialOperandCustodyCheckpointV1,
        successor: OperationFinancialOperandCustodyCheckpointV1,
    ) -> None:
        """Commit only the exact current requirement's legal next position."""
        ...
