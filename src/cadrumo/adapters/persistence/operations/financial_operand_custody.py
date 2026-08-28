"""Durable filesystem custody checkpoints for transient financial operands.

The store holds one versioned checkpoint per wait and nothing more. Checkpoints
are non-sensitive by construction - the operand contract keeps every amount out
of the record - so this is an ordinary durable file rather than encrypted
secure storage, which is the same posture the owner lease takes.

Every advance is a compare-and-swap under an exclusive lock. Two supervisor
paths that both believe they should release one wait will both present the same
predecessor; the first swap wins and the second is refused, so the buffer is
cleared once.
"""

from __future__ import annotations

from typing import TYPE_CHECKING, override

from ....application.operations.financial_operand_custody import (
    OperationFinancialOperandCustodyCheckpoint,
)
from ....application.operations.persistence.financial_operand_custody import (
    OperationFinancialOperandCustodyConflictError,
    OperationFinancialOperandCustodyRepository,
)
from ....core import StorageCategory, exclusive_file_lock, storage_path
from ....core.config import Settings
from ..storage import RepositoryError

if TYPE_CHECKING:
    from pathlib import Path

_CUSTODY_DIRECTORY = "financial_operand_custody"


def _checkpoint_path(root: Path, interaction_id: str) -> Path:
    """Return the one file backing a wait, refusing a traversing identifier."""
    if not interaction_id or "/" in interaction_id or "\\" in interaction_id or interaction_id.startswith("."):
        raise RepositoryError(f"invalid custody interaction identifier: {interaction_id!r}")
    return root / f"{interaction_id}.json"


class OperationFinancialOperandCustodyFilesystemRepository(OperationFinancialOperandCustodyRepository):
    """One durable checkpoint per wait, advanced only by compare-and-swap."""

    def __init__(self, *, root: Path | None = None, settings: Settings | None = None) -> None:
        """Bind the directory this repository keeps its checkpoints in.

        ``settings`` resolves the default location, so a caller that already
        resolved a storage root gets custody beside that root's journal rather
        than beside whatever the ambient settings point at.
        """
        self._root = (
            root
            if root is not None
            else storage_path(StorageCategory.OPERATION_JOURNAL, settings=settings) / _CUSTODY_DIRECTORY
        )
        self._root.mkdir(parents=True, exist_ok=True)

    @override
    async def read(self, interaction_id: str) -> OperationFinancialOperandCustodyCheckpoint | None:
        """Return the latest checkpoint for one wait, or ``None`` if never opened."""
        path = _checkpoint_path(self._root, interaction_id)
        if not path.is_file():
            return None
        return OperationFinancialOperandCustodyCheckpoint.model_validate_json(path.read_text(encoding="utf-8"))

    @override
    async def open(self, checkpoint: OperationFinancialOperandCustodyCheckpoint) -> None:
        """Record the opening checkpoint, refusing a wait that already exists."""
        path = _checkpoint_path(self._root, checkpoint.interaction_id)
        with exclusive_file_lock(path.with_suffix(".lock")):
            if path.exists():
                raise OperationFinancialOperandCustodyConflictError(
                    f"custody for interaction {checkpoint.interaction_id!r} is already open"
                )
            path.write_text(checkpoint.model_dump_json(), encoding="utf-8")

    @override
    async def advance(
        self,
        predecessor: OperationFinancialOperandCustodyCheckpoint,
        successor: OperationFinancialOperandCustodyCheckpoint,
    ) -> None:
        """Replace ``predecessor`` with ``successor`` only if it is still current."""
        if successor.interaction_id != predecessor.interaction_id:
            raise RepositoryError("a custody advance cannot move a checkpoint to another interaction")
        path = _checkpoint_path(self._root, predecessor.interaction_id)
        with exclusive_file_lock(path.with_suffix(".lock")):
            if not path.is_file():
                raise OperationFinancialOperandCustodyConflictError(
                    f"custody for interaction {predecessor.interaction_id!r} is not open"
                )
            stored = OperationFinancialOperandCustodyCheckpoint.model_validate_json(path.read_text(encoding="utf-8"))
            if stored != predecessor:
                raise OperationFinancialOperandCustodyConflictError(
                    f"custody for interaction {predecessor.interaction_id!r} advanced under this caller"
                )
            path.write_text(successor.model_dump_json(), encoding="utf-8")

    @override
    async def unsettled(self) -> tuple[OperationFinancialOperandCustodyCheckpoint, ...]:
        """Return every wait left in a non-terminal state, for restart reconciliation."""
        checkpoints = [
            OperationFinancialOperandCustodyCheckpoint.model_validate_json(path.read_text(encoding="utf-8"))
            for path in sorted(self._root.glob("*.json"))
        ]
        return tuple(checkpoint for checkpoint in checkpoints if not checkpoint.is_terminal)


__all__ = ["OperationFinancialOperandCustodyFilesystemRepository"]
