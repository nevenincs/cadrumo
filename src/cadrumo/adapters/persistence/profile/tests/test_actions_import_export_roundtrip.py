"""Import/export roundtrip coverage for ledger transaction source columns."""

from __future__ import annotations

import csv
import json
from decimal import Decimal
from io import StringIO
from pathlib import Path

import pytest

from cadrumo.adapters.inbound.financial.ledger_import import build_ledger_import_ports
from cadrumo.adapters.persistence.storage.sql.secure_objects import SecureObjectRepository
from cadrumo.application.export.tabular import ExportSerializationFormat
from cadrumo.application.ledger.actions_export import export_ledger_transactions
from cadrumo.application.ledger.actions_import import import_ledger_source
from cadrumo.application.ledger.models import LedgerExportCommand, LedgerSourceImportCommand
from cadrumo.domain.transactions.enums import TransactionDirection

from .ledger_action_persistence_support import (
    _BUCKET_ID,
    _repositories,
)

pytestmark = [pytest.mark.unit, pytest.mark.hex_application]
__all__ = ["secure_objects"]


@pytest.mark.parametrize("export_format", [ExportSerializationFormat.CSV, ExportSerializationFormat.JSONL])
def test_import_ledger_source_honors_explicit_direction_column_on_positive_amount_in_exports(
    secure_objects: SecureObjectRepository,
    tmp_path: Path,
    export_format: ExportSerializationFormat,
) -> None:
    transaction_repository, event_repository = _repositories(secure_objects)
    statement = tmp_path / "explicit-direction.csv"
    statement.write_text(
        "Date,Payee,Payment reference,Amount (EUR),Currency,Transaction ID,direction,source_jurisdiction\n"
        "2026-04-17,French Vendor,FR expense,48.40,EUR,n26-fr-expense,OUTGOING,FR\n",
        encoding="utf-8",
    )

    imported = import_ledger_source(
        LedgerSourceImportCommand(bucket_id=_BUCKET_ID, path=statement, provider="csv", actor="operator-A"),
        ports=build_ledger_import_ports(),
        transaction_repository=transaction_repository,
        bucket_event_repository=event_repository,
    )
    exported = export_ledger_transactions(
        LedgerExportCommand(bucket_id=_BUCKET_ID, export_format=export_format),
        transaction_repository=transaction_repository,
        bucket_event_repository=event_repository,
    )

    assert imported.imported == 1
    (stored,) = transaction_repository.load().values()
    assert stored.raw.amount == Decimal("48.40")
    assert stored.direction is TransactionDirection.OUTGOING
    assert stored.source_jurisdiction == "FR"
    if export_format == ExportSerializationFormat.CSV:
        rows = tuple(csv.DictReader(StringIO(exported.payload.decode("utf-8"))))
    else:
        rows = tuple(json.loads(line) for line in exported.payload.decode("utf-8").splitlines() if line.strip())
    assert len(rows) == 1
    (row,) = rows
    assert row["amount"] == "48.40"
    assert row["direction"] == "OUTGOING"
    assert row["source_jurisdiction"] == "FR"
