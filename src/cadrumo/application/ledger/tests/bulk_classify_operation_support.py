"""Synthetic revision and authority ports for the canonical CSV batch service."""

from __future__ import annotations

from collections.abc import AsyncGenerator
from contextlib import asynccontextmanager
from dataclasses import replace
from types import SimpleNamespace
from typing import cast, override
from uuid import UUID

from pydantic import BaseModel

from ....core.operations import OperationEffect, profile_operation_subject
from ....core.secure_object_write import SecureObjectWrite
from ....domain.calculations.registry.authority import PinnedAuthorityOperation
from ....domain.transactions.models import Transaction, TransactionCatalogue
from ...operations.owner import OperationExecutorContext
from ...user_profile.access_contracts import AccessDenialCode
from ...user_profile.access_errors import ProfileAccessRefusedError
from ..action_ports import LedgerActionPorts
from ..bulk_classify_operation import LEDGER_BULK_CLASSIFY_OPERATION_DEFINITION_ID
from ..persistence_ports import LedgerPersistenceConflictError
from .test_classification_rule_plan import _BUCKET, _ClassificationScenario, _InMemoryTransactionRepository

PROFILE_ID = UUID(_BUCKET)


class CommitFence:
    """Record the actual authority section entered by the shared writer bridge."""

    def __init__(self) -> None:
        self.active = False
        self.entries = 0
        self.deny = False

    @asynccontextmanager
    async def irreversible_section(self) -> AsyncGenerator[None]:
        if self.deny:
            raise ProfileAccessRefusedError(AccessDenialCode.PROFILE_MISMATCH)
        self.active = True
        self.entries += 1
        try:
            yield
        finally:
            self.active = False


class RevisionedCatalogueRepository(_InMemoryTransactionRepository):
    """In-memory CAS with explicit confirmed and uncertain writer outcomes."""

    def __init__(self, catalogue: TransactionCatalogue, fence: CommitFence) -> None:
        super().__init__(catalogue)
        self.fence = fence
        self.revision = "a" * 64
        self.loads = 0
        self.write_attempts = 0
        self.committed_writes = 0
        self.stale = False
        self.fail_after_write = False

    @property
    def current(self) -> TransactionCatalogue:
        """Inspect stored rows without simulating another service catalogue load."""
        return self._catalogue

    def load_revisioned(self) -> tuple[TransactionCatalogue, str]:
        """Return exactly one guarded catalogue snapshot per batch."""
        assert not self.fence.active, "parsing and catalogue reads must not retain COMMIT authority"
        self.loads += 1
        return self._catalogue, self.revision

    @override
    def save_with_secure_object_writes(
        self, catalogue: TransactionCatalogue, extra_writes: tuple[SecureObjectWrite, ...]
    ) -> None:
        """Detect an accidental bypass of the canonical whole-catalogue CAS."""
        raise AssertionError("CSV batch must carry the loaded catalogue revision")

    def save_if_revision_with_secure_object_writes(
        self,
        catalogue: TransactionCatalogue,
        *,
        expected_revision_id: str,
        extra_writes: tuple[SecureObjectWrite, ...],
    ) -> None:
        """Persist only while the concrete operation fence and loaded revision agree."""
        assert self.fence.active, "the canonical writer must run inside COMMIT authority"
        assert extra_writes, "batch classification must co-commit its bucket history"
        self.write_attempts += 1
        if self.stale or expected_revision_id != self.revision:
            raise LedgerPersistenceConflictError("synthetic stale catalogue")
        self._catalogue = catalogue
        self.revision = "b" * 64
        self.committed_writes += 1
        if self.fail_after_write:
            raise ValueError("synthetic writer failed after committing")


class EffectEvents:
    """Capture only the credential-free phase and effect journal facts."""

    def __init__(self) -> None:
        self.effects: list[OperationEffect] = []
        self.phases: list[str] = []

    async def phase(self, phase: str) -> None:
        """Record a fixed operation phase token."""
        self.phases.append(phase)

    async def effect(self, effect: OperationEffect) -> None:
        """Record the authoritative writer outcome."""
        self.effects.append(effect)


class PrivateOperands:
    """Capture synthetic private result models separately from the journal."""

    def __init__(self) -> None:
        self.values: list[BaseModel] = []

    async def put(self, value: BaseModel, *, written_at: object) -> str:
        """Retain one synthetic encrypted-operand stand-in by safe reference."""
        self.values.append(value)
        return "d" * 64


class BulkClassifySubject:
    """One exact profile with canonical classification action ports."""

    def __init__(self, *, operation: PinnedAuthorityOperation, transactions: tuple[Transaction, ...]) -> None:
        self.operation = operation
        self.fence = CommitFence()
        self.events = EffectEvents()
        self.operands = PrivateOperands()
        catalogue = TransactionCatalogue.from_transactions(transactions)
        scenario = _ClassificationScenario(catalogue, operation=operation)
        self.repository = RevisionedCatalogueRepository(catalogue, self.fence)
        self.ports = replace(scenario.ports, transaction_repository=self.repository)
        self.context = cast(
            OperationExecutorContext,
            SimpleNamespace(
                identity=SimpleNamespace(
                    definition_id=LEDGER_BULK_CLASSIFY_OPERATION_DEFINITION_ID,
                    subject_ref=profile_operation_subject(str(PROFILE_ID)),
                ),
                authority_operation=operation,
                cancellation=self.fence,
                events=self.events,
                operands=self.operands,
            ),
        )

    def compose(self, *, bucket_id: str, operation: PinnedAuthorityOperation) -> LedgerActionPorts:
        """Require the executor to request the reviewed profile and pinned authority."""
        assert bucket_id == str(PROFILE_ID)
        assert operation is self.operation
        return self.ports
