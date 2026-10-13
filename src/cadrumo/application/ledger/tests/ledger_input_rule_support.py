"""Shared fixtures for tests that drive ledger input rules through the real operation code."""

from __future__ import annotations

from collections.abc import AsyncGenerator
from contextlib import asynccontextmanager
from datetime import UTC, date, datetime
from decimal import Decimal
from pathlib import Path
from types import MappingProxyType, SimpleNamespace
from uuid import UUID

from pydantic import BaseModel

from ....core.operations import OperationEffect, profile_operation_subject
from ....domain.calculations.registry.authority import PinnedAuthorityOperation
from ....domain.transactions.enums import TransactionDirection
from ....domain.transactions.models import Transaction, TransactionCatalogue
from ....domain.transactions.raw_transaction import RawProvenance, RawTransaction, SourceFormat

PROFILE = UUID("5aa00000-0000-4000-8000-0000000000aa")


def current_transaction() -> Transaction:
    """Build a domain-valid active row for an executor to read."""
    raw = RawTransaction(
        provider_transaction_id="input-rule-row",
        booked_date=date(2026, 4, 15),
        value_date=None,
        amount=Decimal("121.00"),
        currency="EUR",
        counterparty="Client SL",
        description="Invoice 1",
        provenance=RawProvenance(
            source_path=Path(__file__),
            source_sha256="c" * 64,
            source_row_index=1,
            source_format=SourceFormat.MANUAL,
            ingested_at=datetime(2026, 4, 15, 9, 30, tzinfo=UTC),
            provider_name="test",
        ),
        raw_fields={"source": "test"},
    )
    return Transaction.model_validate(
        {
            "raw": raw,
            "direction": TransactionDirection.OUTGOING,
            "source_jurisdiction": "ES",
            "group_label": None,
        },
    )


class RecordingEvents:
    """Collect the phase and effect declarations an executor makes."""

    def __init__(self) -> None:
        """Start with nothing declared."""
        self.effects: list[OperationEffect] = []

    async def phase(self, _phase: str) -> None:
        """Accept a phase declaration."""

    async def effect(self, effect: OperationEffect) -> None:
        """Record one effect declaration."""
        self.effects.append(effect)


class RecordingOperands:
    """Keep the last operand an executor stored."""

    def __init__(self) -> None:
        """Start empty."""
        self.value: BaseModel | None = None

    async def put(self, operand: BaseModel, *, written_at: object) -> str:
        """Store the operand and return a fixed reference."""
        self.value = operand
        return "d" * 64


class Cancellation:
    """Grant the irreversible section without a supervisor."""

    @asynccontextmanager
    async def irreversible_section(self) -> AsyncGenerator[None]:
        """Enter and leave the section."""
        yield


def executor_ports(authority: PinnedAuthorityOperation, current: Transaction) -> SimpleNamespace:
    """Describe exact-profile ports that hold one stored row and nothing else."""
    bucket_id = str(PROFILE)
    catalogue = TransactionCatalogue.model_construct(transactions=MappingProxyType({current.transaction_id: current}))

    class TransactionRepository:
        def __init__(self) -> None:
            self.bucket_id = bucket_id

        def load(self) -> TransactionCatalogue:
            return catalogue

    return SimpleNamespace(
        operation=authority,
        transaction_repository=TransactionRepository(),
        bucket_event_repository=SimpleNamespace(bucket_id=bucket_id),
        invoice_repository=SimpleNamespace(bucket_id=bucket_id),
        work_unit_repository=SimpleNamespace(bucket_id=bucket_id),
        calculation_repository=SimpleNamespace(bucket_id=bucket_id),
    )


def executor_context(
    definition_id: str,
    authority: PinnedAuthorityOperation,
    events: RecordingEvents,
    operands: RecordingOperands,
) -> SimpleNamespace:
    """Describe the executor context for one profile-bound operation."""
    return SimpleNamespace(
        identity=SimpleNamespace(definition_id=definition_id, subject_ref=profile_operation_subject(str(PROFILE))),
        authority_operation=authority,
        cancellation=Cancellation(),
        events=events,
        operands=operands,
    )
