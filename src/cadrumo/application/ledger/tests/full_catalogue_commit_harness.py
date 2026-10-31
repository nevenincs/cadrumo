"""Executor harness for operations that commit through a full-catalogue revision guard."""

from __future__ import annotations

from contextlib import asynccontextmanager
from datetime import date
from types import SimpleNamespace
from typing import Any, cast
from uuid import UUID

import pytest
from pydantic import BaseModel

from ....core.operations import OperationEffect, profile_operation_subject
from ....core.secure_object_write import SecureObjectWrite
from ....domain.calculations.registry.authority import PinnedAuthorityOperation
from ....domain.transactions.models import Transaction, TransactionCatalogue
from ...operations.owner import OperationExecutorContext
from ..action_ports import LedgerActionPorts
from ..persistence_ports import LedgerPersistenceConflictError
from ..protocols import RevisionGuardedTransactionCatalogueCoCommitWriterProtocol


class _Events:
    def __init__(self) -> None:
        self.effects: list[OperationEffect] = []

    async def phase(self, _phase: str) -> None:
        return None

    async def effect(self, effect: OperationEffect) -> None:
        self.effects.append(effect)


class _Operands:
    def __init__(self, result_ref: str) -> None:
        self.value: BaseModel | None = None
        self._result_ref = result_ref

    async def put(self, operand: BaseModel, *, written_at: object) -> str:
        self.value = operand
        return self._result_ref


class FullCatalogueCommitHarness:
    """Ports, context and recorders for an executor that must commit under one fresh revision.

    The unguarded repository paths refuse, so a pass proves the executor used the
    revision-guarded writer inside its irreversible section.
    """

    def __init__(self, *, profile_id: UUID, catalogue: TransactionCatalogue, verb: str, result_ref: str) -> None:
        self.in_commit = False
        self.revision_calls: list[TransactionCatalogue] = []
        self.guarded_writes: list[str] = []
        self.catalogue = catalogue
        self.events = _Events()
        self.operands = _Operands(result_ref)
        self._profile_id = profile_id
        self.authority = cast(PinnedAuthorityOperation, object())
        self.repository = self._build_repository(profile_id, verb)
        self.ports = LedgerActionPorts(
            operation=self.authority,
            transaction_repository=cast(Any, self.repository),
            bucket_event_repository=cast(Any, object()),
            invoice_repository=cast(Any, SimpleNamespace(bucket_id=str(profile_id))),
            attachment_store=cast(Any, object()),
            usage_ratio_profile=cast(Any, object()),
            usage_ratio_profile_loader=cast(Any, object()),
            work_unit_repository=cast(Any, SimpleNamespace(bucket_id=str(profile_id))),
            calculation_repository=cast(Any, SimpleNamespace(bucket_id=str(profile_id))),
            purchase_invoice_evidence_records=(),
        )

    def _build_repository(self, profile_id: UUID, verb: str) -> object:
        harness = self
        catalogue = self.catalogue

        class TransactionRepository:
            bucket_id = str(profile_id)

            def exists(self) -> bool:
                return True

            def load(self) -> TransactionCatalogue:
                return catalogue

            def load_for_date_range(self, _start: date, _end: date) -> TransactionCatalogue:
                return catalogue

            def load_by_ids(self, _transaction_ids: object) -> TransactionCatalogue:
                return catalogue

            def partition_by_date_range(self, _start: date, _end: date) -> object:
                raise AssertionError(f"{verb} should use the full revisioned catalogue")

            def save(self, _catalogue: TransactionCatalogue) -> None:
                raise AssertionError(f"{verb} must use its full-catalogue revision guard")

            def save_with_secure_object_writes(
                self,
                _catalogue: TransactionCatalogue,
                _extra_writes: tuple[SecureObjectWrite, ...],
            ) -> None:
                raise AssertionError(f"{verb} must use its full-catalogue revision guard")

            def replace_if_current_with_secure_object_writes(
                self,
                _current: Transaction,
                _replacement: Transaction,
                _extra_writes: tuple[SecureObjectWrite, ...],
            ) -> None:
                raise AssertionError(f"{verb} must use its full-catalogue revision guard")

            def load_revisioned(self) -> tuple[TransactionCatalogue, str]:
                assert harness.in_commit
                harness.revision_calls.append(catalogue)
                return catalogue, "revision-one"

            def save_if_revision_with_secure_object_writes(
                self,
                _new_catalogue: TransactionCatalogue,
                *,
                expected_revision_id: str,
                extra_writes: tuple[SecureObjectWrite, ...],
            ) -> None:
                assert harness.in_commit
                assert extra_writes == ()
                harness.guarded_writes.append(expected_revision_id)

        return TransactionRepository()

    def exercise_pinned_commit(self, ports: LedgerActionPorts) -> None:
        """Assert the action received a pinned guard and commit through it once."""
        assert self.in_commit
        pinned = cast(RevisionGuardedTransactionCatalogueCoCommitWriterProtocol, ports.transaction_repository)
        assert pinned is not self.repository
        pinned_catalogue, pinned_revision = pinned.load_revisioned()
        assert pinned_catalogue is self.catalogue
        assert pinned_revision == "revision-one"
        with pytest.raises(LedgerPersistenceConflictError):
            pinned.save(self.catalogue)
        pinned.save_if_revision_with_secure_object_writes(
            self.catalogue,
            expected_revision_id=pinned_revision,
            extra_writes=(),
        )

    def context(self, definition_id: str) -> OperationExecutorContext:
        """Return an executor context whose irreversible section marks the commit window."""
        harness = self

        class Cancellation:
            @asynccontextmanager
            async def irreversible_section(self):
                harness.in_commit = True
                try:
                    yield
                finally:
                    harness.in_commit = False

        return cast(
            OperationExecutorContext,
            SimpleNamespace(
                identity=SimpleNamespace(
                    definition_id=definition_id,
                    subject_ref=profile_operation_subject(str(self._profile_id)),
                ),
                authority_operation=self.authority,
                cancellation=Cancellation(),
                events=self.events,
                operands=self.operands,
            ),
        )
