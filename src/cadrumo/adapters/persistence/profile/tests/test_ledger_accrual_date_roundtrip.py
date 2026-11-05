"""A stated Renta accrual date survives add, update, read and export through the real stores.

Worked by hand: a fee of 500.00 delivered on 30 March and collected on 2 April
accrues for Renta on 30 March (LIRPF art. 14), while its IVA follows the
operation date and not the accrual date. The operator states the accrual date
and the app keeps it apart from the bank date and from ``operation_date``.
"""

from __future__ import annotations

from collections.abc import Iterator
from datetime import date
from decimal import Decimal
from pathlib import Path

import pytest

from cadrumo.adapters.persistence.profile.tests.ledger_action_create_support import ledger_ports_for_test
from cadrumo.adapters.persistence.profile.transactions import TransactionCatalogueRepository
from cadrumo.adapters.persistence.storage.sql.secure_objects import SecureObjectRepository
from cadrumo.adapters.persistence.storage.tests.secure_sql import isolated_runtime_profile
from cadrumo.application.ledger.actions_export import export_ledger_transactions
from cadrumo.application.ledger.manual_read import get_manual_transaction, ledger_transaction_payload
from cadrumo.application.ledger.manual_update import update_manual_transaction_fields
from cadrumo.application.ledger.models import (
    LedgerExportCommand,
    ManualLedgerTransactionCommand,
    ManualLedgerTransactionPatch,
)
from cadrumo.domain.transactions.enums import TransactionDirection

from .....application.ledger.tests.manual_transaction_support import create_manual_transaction
from .ledger_action_persistence_support import BUCKET_ID

pytestmark = [pytest.mark.unit, pytest.mark.hex_application, pytest.mark.usefixtures("authority_operation")]

_BOOKED = date(2026, 4, 2)
_ACCRUED = date(2026, 3, 30)
_CORRECTED = date(2026, 3, 28)


@pytest.fixture
def secure_objects(tmp_path: Path) -> Iterator[SecureObjectRepository]:
    with isolated_runtime_profile(tmp_path=tmp_path, bucket_id=BUCKET_ID) as profile:
        yield profile.repository


def _fee(*, accrual_date: date | None) -> ManualLedgerTransactionCommand:
    return ManualLedgerTransactionCommand(
        bucket_id=BUCKET_ID,
        booked_date=_BOOKED,
        amount=Decimal("500.00"),
        direction=TransactionDirection.INCOMING,
        description="honorarios entregados a finales de marzo",
        accrual_date=accrual_date,
    )


def test_an_accrual_date_is_added_updated_cleared_and_read_back_apart_from_the_other_dates(
    secure_objects: SecureObjectRepository,
) -> None:
    with ledger_ports_for_test(bucket_id=BUCKET_ID, objects=secure_objects) as ports:
        created = create_manual_transaction(_fee(accrual_date=_ACCRUED), ports=ports)
        transaction_id = created.transaction.transaction_id

        stored = get_manual_transaction(bucket_id=BUCKET_ID, transaction_id=transaction_id, ports=ports).transaction
        assert stored.accrual_date == _ACCRUED
        assert stored.operation_date is None
        assert stored.raw.booked_date == _BOOKED

        update_manual_transaction_fields(
            bucket_id=BUCKET_ID,
            transaction_id=transaction_id,
            patch=ManualLedgerTransactionPatch(accrual_date=_CORRECTED),
            actor="operator",
            source_command="ledger.update",
            ports=ports,
        )
        corrected = get_manual_transaction(bucket_id=BUCKET_ID, transaction_id=transaction_id, ports=ports).transaction
        payload = ledger_transaction_payload(corrected)
        assert payload.accrual_date == _CORRECTED.isoformat()
        assert payload.operation_date is None

        update_manual_transaction_fields(
            bucket_id=BUCKET_ID,
            transaction_id=transaction_id,
            patch=ManualLedgerTransactionPatch(operation_date=_BOOKED),
            actor="operator",
            source_command="ledger.update",
            ports=ports,
        )
        moved = get_manual_transaction(bucket_id=BUCKET_ID, transaction_id=transaction_id, ports=ports).transaction
        assert moved.operation_date == _BOOKED
        assert moved.accrual_date == _CORRECTED

        update_manual_transaction_fields(
            bucket_id=BUCKET_ID,
            transaction_id=transaction_id,
            patch=ManualLedgerTransactionPatch(accrual_date=None),
            actor="operator",
            source_command="ledger.update",
            ports=ports,
        )
    reloaded = TransactionCatalogueRepository(bucket_id=BUCKET_ID, objects=secure_objects).load().get(transaction_id)
    assert reloaded is not None
    assert reloaded.accrual_date is None
    assert reloaded.operation_date == _BOOKED


def test_an_undated_row_keeps_no_accrual_date_and_the_export_carries_the_stated_one(
    secure_objects: SecureObjectRepository, tmp_path: Path
) -> None:
    with ledger_ports_for_test(bucket_id=BUCKET_ID, objects=secure_objects) as ports:
        silent = create_manual_transaction(_fee(accrual_date=None), ports=ports).transaction
        assert silent.accrual_date is None
        assert ledger_transaction_payload(silent).accrual_date is None

        stated = create_manual_transaction(
            _fee(accrual_date=_ACCRUED).model_copy(update={"description": "segundo honorario entregado en marzo"}),
            ports=ports,
        ).transaction
        output = tmp_path / "ledger.csv"
        export_ledger_transactions(
            LedgerExportCommand(bucket_id=BUCKET_ID, output_path=output),
            transaction_repository=ports.transaction_repository,
            bucket_event_repository=ports.bucket_event_repository,
        )

    lines = output.read_text(encoding="utf-8").splitlines()
    header = lines[0].split(",")
    column = header.index("accrual_date")
    rows = {cells[header.index("transaction_id")]: cells for cells in (line.split(",") for line in lines[1:])}
    assert rows[stated.transaction_id][column] == _ACCRUED.isoformat()
    assert rows[silent.transaction_id][column] == ""
