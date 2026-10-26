"""Hardened atomic filesystem custody for exact typed financial handoffs."""

from __future__ import annotations

import asyncio
import os
from datetime import datetime
from pathlib import Path
from typing import override

from pydantic import BaseModel

from ....application.journal_repository import JournalRepositoryBase
from ....application.operations.financial_operand_custody import (
    OperationFinancialOperandCustodyCheckpointV1,
    OperationFinancialOperandCustodyState,
)
from ....application.operations.persistence.financial_operand_custody import (
    OperationFinancialOperandCustodyConflictError,
    OperationTypedFinancialOperandCustodyRepository,
)
from ....core.config import Settings
from ....core.locks import exclusive_file_lock
from ....core.models import STRICT_FROZEN_CONFIG
from ....core.storage_taxonomy import StorageCategory
from ....core.storage_taxonomy_locations import storage_path
from ..storage.errors import RepositoryError


class _CustodyRecord(BaseModel):
    model_config = STRICT_FROZEN_CONFIG

    checkpoint: OperationFinancialOperandCustodyCheckpointV1

    @property
    def operation_id(self) -> str:
        return self.checkpoint.requirement.handoff_id

    @property
    def started_at(self) -> datetime:
        return self.checkpoint.recorded_at


class _CustodyRepository(JournalRepositoryBase[_CustodyRecord]):
    def __init__(self, *, root: Path) -> None:
        """Bind the exact external directory to the canonical hardened substrate."""
        super().__init__(
            storage_root=root.parent,
            journal_dirname=root.name,
            parse_operation=_CustodyRecord.model_validate_json,
            error_type=RepositoryError,
            not_found_type=RepositoryError,
            corrupt_type=RepositoryError,
            subject="typed financial operand custody",
            id_subject="handoff",
        )

    def read_checkpoint(self, handoff_id: str) -> OperationFinancialOperandCustodyCheckpointV1 | None:
        path = self.path_for(handoff_id)
        if not self._validate_existing_root():
            return None
        with exclusive_file_lock(self.lock_target):
            if not os.path.lexists(path):
                return None
            return self.load(handoff_id).checkpoint

    def create(self, checkpoint: OperationFinancialOperandCustodyCheckpointV1) -> None:
        if (
            checkpoint.sequence != 1
            or checkpoint.state is not OperationFinancialOperandCustodyState.AWAITING_SUBMISSION
        ):
            raise OperationFinancialOperandCustodyConflictError(
                "typed financial custody must start awaiting submission"
            )
        self._ensure_root()
        path = self.path_for(checkpoint.requirement.handoff_id)
        with exclusive_file_lock(self.lock_target):
            if os.path.lexists(path):
                raise OperationFinancialOperandCustodyConflictError("typed financial handoff already exists")
            self._write(path, _CustodyRecord(checkpoint=checkpoint))

    def advance_checkpoint(
        self,
        predecessor: OperationFinancialOperandCustodyCheckpointV1,
        successor: OperationFinancialOperandCustodyCheckpointV1,
    ) -> None:
        expected = predecessor.successor(successor.state, now=successor.recorded_at)
        if expected != successor:
            raise OperationFinancialOperandCustodyConflictError("typed financial custody successor binding differs")
        if not self._validate_existing_root():
            raise OperationFinancialOperandCustodyConflictError("typed financial custody is absent")
        with exclusive_file_lock(self.lock_target):
            stored = self.load(predecessor.requirement.handoff_id).checkpoint
            if stored != predecessor:
                raise OperationFinancialOperandCustodyConflictError("typed financial custody predecessor changed")
            self._write(self.path_for(successor.requirement.handoff_id), _CustodyRecord(checkpoint=successor))


class OperationTypedFinancialOperandCustodyFilesystemRepository(OperationTypedFinancialOperandCustodyRepository):
    """Run hardened journal reads and CAS writes outside the event loop."""

    def __init__(self, *, root: Path | None = None, settings: Settings | None = None) -> None:
        """Use a distinct current-contract directory, leaving prototype records unavailable."""
        directory = (
            root
            if root is not None
            else storage_path(StorageCategory.OPERATION_JOURNAL, settings=settings) / "typed_financial_operand_custody"
        )
        self._repository = _CustodyRepository(root=directory)

    @override
    async def read(self, handoff_id: str) -> OperationFinancialOperandCustodyCheckpointV1 | None:
        return await asyncio.to_thread(self._repository.read_checkpoint, handoff_id)

    @override
    async def open(self, checkpoint: OperationFinancialOperandCustodyCheckpointV1) -> None:
        await asyncio.to_thread(self._repository.create, checkpoint)

    @override
    async def advance(
        self,
        predecessor: OperationFinancialOperandCustodyCheckpointV1,
        successor: OperationFinancialOperandCustodyCheckpointV1,
    ) -> None:
        await asyncio.to_thread(self._repository.advance_checkpoint, predecessor, successor)
