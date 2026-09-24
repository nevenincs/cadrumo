"""The capture guard trusts ledger store revisions instead of decoding the ledger twice.

The ledger stores are the real encrypted ones for an isolated profile. Store
reads are counted by observing the real repository methods, never by
replacing them.
"""

from __future__ import annotations

import sys
from collections.abc import Callable
from dataclasses import dataclass, replace
from datetime import UTC, date, datetime, timedelta
from decimal import Decimal
from pathlib import Path
from types import CodeType, FrameType
from typing import Any, cast

import pytest

from ...adapters.persistence.profile.invoices import InvoiceCatalogueRepository
from ...adapters.persistence.profile.transactions import TransactionCatalogueRepository
from ...adapters.persistence.storage.tests.secure_sql import isolated_runtime_profile
from ...core.errors.hierarchy import InternalInvariantError
from ...domain.calculations.registry.authority import PinnedAuthorityOperation
from ...domain.modelos.calculation_revision import CalculationRevisionCatalogue
from ...domain.modelos.filing_record import ModeloRecordCatalogue
from ...domain.modelos.work_unit import WorkUnitCatalogue
from ...domain.transactions.enums import TransactionDirection
from ...domain.transactions.models import Transaction, TransactionCatalogue
from ...domain.transactions.raw_transaction import RawProvenance, RawTransaction, SourceFormat
from ...domain.user_profile.values import ProfileSetupState, create_user_profile_record
from ..ledger_action_composition import compose_ledger_action_ports
from ...application.overview.home import HomeAccountSession, HomeSessionPosture
from ...application.workbench_generation import SecureProfileWorkbenchGenerationReadDoorV1, WorkbenchGenerationInputsV1

pytestmark = [pytest.mark.integration, pytest.mark.hex_entrypoint]

_BUCKET_ID = "44444444-4444-4444-8444-444444444444"
_NOW = datetime(2026, 9, 3, 10, 30, tzinfo=UTC)


@dataclass
class _Store[ValueT]:
    value: ValueT

    def load(self, *_args: object) -> ValueT:
        return self.value

    def load_revisioned(self) -> tuple[ValueT, str]:
        return self.value, "revision-1"


def _row(provider_id: str) -> Transaction:
    raw = RawTransaction(
        provider_transaction_id=provider_id,
        booked_date=date(2026, 3, 1),
        value_date=date(2026, 3, 1),
        amount=Decimal("50.00"),
        currency="EUR",
        counterparty="Synthetic SL",
        description="synthetic row",
        provenance=RawProvenance(
            source_path=Path(__file__),
            source_sha256="e" * 64,
            source_row_index=1,
            source_format=SourceFormat.MANUAL,
            ingested_at=_NOW,
            provider_name="manual",
        ),
        raw_fields={"Concepto": "synthetic row"},
    )
    return Transaction.model_validate(
        {"raw": raw, "direction": TransactionDirection.OUTGOING, "source_jurisdiction": "ES", "group_label": None}
    )


class _WithoutRevision:
    """The same store with its revision capability withheld."""

    def __init__(self, store: object) -> None:
        self._store = store

    def __getattr__(self, name: str) -> object:
        if name == "load_revision":
            raise AttributeError(name)
        return getattr(self._store, name)


def _calls(codes: tuple[CodeType, ...], action: Callable[[], object]) -> dict[CodeType, int]:
    counts = dict.fromkeys(codes, 0)
    previous = sys.getprofile()

    def observe(frame: FrameType, event: str, arg: object) -> None:
        del arg
        if event == "call" and frame.f_code in counts:
            counts[frame.f_code] += 1

    sys.setprofile(observe)
    try:
        action()
    finally:
        sys.setprofile(previous)
    return counts


_TRANSACTION_LOAD = TransactionCatalogueRepository.load.__code__
_INVOICE_LOAD = InvoiceCatalogueRepository.load.__code__


def _door(
    operation: PinnedAuthorityOperation,
    *,
    account_session_reader: Callable[[], HomeAccountSession] | None = None,
    withhold_revisions: bool = False,
) -> SecureProfileWorkbenchGenerationReadDoorV1:
    ports = compose_ledger_action_ports(bucket_id=_BUCKET_ID, operation=operation)
    if withhold_revisions:
        ports = replace(
            ports,
            transaction_repository=cast(Any, _WithoutRevision(ports.transaction_repository)),
            invoice_repository=cast(Any, _WithoutRevision(ports.invoice_repository)),
        )
    record = create_user_profile_record(
        context=operation.profile_create_context(),
        profile_id=_BUCKET_ID,
        setup_state=ProfileSetupState.INCOMPLETE,
        facts=(),
    )
    return SecureProfileWorkbenchGenerationReadDoorV1(
        profile_id=_BUCKET_ID,
        operation=operation,
        profile_repository=cast(Any, _Store(record)),
        work_unit_repository=cast(Any, _Store(WorkUnitCatalogue())),
        calculation_repository=cast(Any, _Store(CalculationRevisionCatalogue())),
        filing_repository=cast(Any, _Store(ModeloRecordCatalogue())),
        clock=lambda: _NOW,
        account_session_reader=account_session_reader
        or (
            lambda: HomeAccountSession(
                posture=HomeSessionPosture.ACTIVE,
                profile_label="Perfil local",
                expires_at=_NOW + timedelta(hours=1),
            )
        ),
        ledger_action_ports=ports,
    )


def test_a_quiet_capture_decodes_each_ledger_catalogue_once(
    tmp_path: Path, operation: PinnedAuthorityOperation
) -> None:
    with isolated_runtime_profile(tmp_path=tmp_path, bucket_id=_BUCKET_ID):
        TransactionCatalogueRepository(bucket_id=_BUCKET_ID).save(TransactionCatalogue.from_transactions((_row("a"),)))
        door = _door(operation)
        captured: list[WorkbenchGenerationInputsV1] = []
        counts = _calls(
            (_TRANSACTION_LOAD, _INVOICE_LOAD), lambda: captured.append(door.read_workbench_generation_inputs())
        )

    assert counts == {_TRANSACTION_LOAD: 1, _INVOICE_LOAD: 1}
    (inputs,) = captured
    assert inputs.ledger.value is not None


def test_the_counter_detects_the_second_decode_without_revisions(
    tmp_path: Path, operation: PinnedAuthorityOperation
) -> None:
    with isolated_runtime_profile(tmp_path=tmp_path, bucket_id=_BUCKET_ID):
        TransactionCatalogueRepository(bucket_id=_BUCKET_ID).save(TransactionCatalogue.from_transactions((_row("a"),)))
        door = _door(operation, withhold_revisions=True)
        counts = _calls((_TRANSACTION_LOAD, _INVOICE_LOAD), door.read_workbench_generation_inputs)

    assert counts == {_TRANSACTION_LOAD: 2, _INVOICE_LOAD: 2}


def test_a_ledger_write_during_capture_refuses_the_generation(
    tmp_path: Path, operation: PinnedAuthorityOperation
) -> None:
    with isolated_runtime_profile(tmp_path=tmp_path, bucket_id=_BUCKET_ID):
        repository = TransactionCatalogueRepository(bucket_id=_BUCKET_ID)
        repository.save(TransactionCatalogue.from_transactions((_row("a"),)))
        reads = 0

        def session_then_write() -> HomeAccountSession:
            # The door asks for the session once before its reads and once after
            # them; a write between those instants is a write during the capture.
            nonlocal reads
            reads += 1
            if reads == 2:
                TransactionCatalogueRepository(bucket_id=_BUCKET_ID).save(
                    TransactionCatalogue.from_transactions((_row("a"), _row("b")))
                )
            return HomeAccountSession(
                posture=HomeSessionPosture.ACTIVE,
                profile_label="Perfil local",
                expires_at=_NOW + timedelta(hours=1),
            )

        door = _door(operation, account_session_reader=session_then_write)
        with pytest.raises(InternalInvariantError, match="changed during capture"):
            door.read_workbench_generation_inputs()
