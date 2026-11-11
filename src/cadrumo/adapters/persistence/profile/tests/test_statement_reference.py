"""The bank statement's printed reference: read at import, kept by edits, split and merge, never an identity.

Every row here goes through the real CSV provider, the real ledger actions and
the encrypted transaction catalogue, and is read back from the stored bytes.
"""

from __future__ import annotations

import json
from collections.abc import Iterator
from datetime import UTC, datetime, time
from decimal import Decimal
from pathlib import Path

import pytest
from pydantic import TypeAdapter

from cadrumo.adapters.inbound.financial.ledger_import import build_ledger_import_ports

from .....application.ledger.actions_import import import_ledger_transactions
from .....application.ledger.actions_split_merge import merge_transactions, split_transaction
from .....application.ledger.manual_update import update_manual_transaction_fields
from .....application.ledger.models import (
    LedgerSourceImportCommand,
    ManualLedgerTransactionPatch,
    SplitChildCommand,
)
from .....domain.transactions.enums import TransactionDirection
from .....domain.transactions.models import derive_transaction_id
from .....domain.transactions.raw_transaction import RawProvenance, RawTransaction, SourceFormat
from .....domain.transactions.repository import transaction_object_key
from ....inbound.financial.providers.base import ParsedLedgerRow
from ...storage.secure_object_namespaces import TRANSACTION_CATALOGUE_NAMESPACE
from ...storage.sql.secure_object_records import SecureObjectRecord
from .classification_origin_support import BUCKET_ID, NOW_DATE, PERSON, Ledger, composed_ledger
from .ledger_action_persistence_support import import_ledger_source

pytestmark = [pytest.mark.unit, pytest.mark.hex_persistence_adapter, pytest.mark.usefixtures("operation")]

_JSON_OBJECT = TypeAdapter(dict[str, object])
_REFERENCE = "0049-7731-REF-000184"


@pytest.fixture
def ledger(tmp_path: Path) -> Iterator[Ledger]:
    with composed_ledger(tmp_path) as composed:
        yield composed


def _import_statement(ledger: Ledger, tmp_path: Path, *, header: str, row: str) -> str:
    statement = tmp_path / "extracto.csv"
    statement.write_text(f"{header}\n{row}\n", encoding="utf-8")
    result = import_ledger_source(
        LedgerSourceImportCommand(bucket_id=BUCKET_ID, path=statement, provider="csv", actor=PERSON),
        ports=build_ledger_import_ports(),
        transaction_repository=ledger.transactions,
        bucket_event_repository=ledger.events,
    )
    assert result.imported == 1
    (ref,) = result.imported_transaction_refs
    return ref.transaction_id


def _import_with_reference(ledger: Ledger, tmp_path: Path) -> str:
    return _import_statement(
        ledger,
        tmp_path,
        header="Fecha,Concepto,Importe,Divisa,Referencia",
        row=f"{NOW_DATE.isoformat()},RECIBO LUZ,-60.50,EUR,  {_REFERENCE}  ",
    )


def _import_without_reference(ledger: Ledger, tmp_path: Path) -> str:
    return _import_statement(
        ledger,
        tmp_path,
        header="Fecha,Concepto,Importe,Divisa",
        row=f"{NOW_DATE.isoformat()},RECIBO LUZ,-60.50,EUR",
    )


def _stored_record(ledger: Ledger, transaction_id: str) -> SecureObjectRecord:
    record = ledger.objects.load(
        TRANSACTION_CATALOGUE_NAMESPACE.namespace,
        transaction_object_key(BUCKET_ID, transaction_id),
        expected_class=TRANSACTION_CATALOGUE_NAMESPACE.sensitivity,
        max_supported_version=TRANSACTION_CATALOGUE_NAMESPACE.schema_version,
    )
    assert record is not None
    return record


def _stored_raw(ledger: Ledger, transaction_id: str) -> dict[str, object]:
    envelope = _JSON_OBJECT.validate_json(_stored_record(ledger, transaction_id).payload)
    row = _JSON_OBJECT.validate_python(envelope["payload"])
    return _JSON_OBJECT.validate_python(row["raw"])


def _rewrite_as_stored_before_the_reference(ledger: Ledger, transaction_id: str) -> None:
    """Re-encrypt a stored row in the shape a build without the field wrote: no key at all."""
    record = _stored_record(ledger, transaction_id)
    envelope = _JSON_OBJECT.validate_json(record.payload)
    row = _JSON_OBJECT.validate_python(envelope["payload"])
    raw = _JSON_OBJECT.validate_python(row["raw"])
    del raw["statement_reference"]
    envelope["payload"] = {**row, "raw": raw}
    ledger.objects.save(
        namespace=TRANSACTION_CATALOGUE_NAMESPACE.namespace,
        object_key=transaction_object_key(BUCKET_ID, transaction_id),
        classification=record.classification,
        schema_version=record.schema_version,
        written_at=record.written_at,
        payload=json.dumps(envelope).encode("utf-8"),
    )


def test_the_printed_reference_is_stored_trimmed_inside_the_encrypted_row(ledger: Ledger, tmp_path: Path) -> None:
    transaction_id = _import_with_reference(ledger, tmp_path)

    assert ledger.row(transaction_id).raw.statement_reference == _REFERENCE
    assert _stored_raw(ledger, transaction_id)["statement_reference"] == _REFERENCE


def test_a_statement_without_a_reference_stores_none_and_not_the_synthesized_id(ledger: Ledger, tmp_path: Path) -> None:
    transaction_id = _import_without_reference(ledger, tmp_path)
    stored = ledger.row(transaction_id)

    assert stored.raw.statement_reference is None
    # The row still has a provider id, synthesized from the file; it is not a printed reference.
    assert stored.raw.provider_transaction_id
    assert "statement_reference" not in _stored_raw(ledger, transaction_id)


def test_a_row_without_the_field_keeps_its_bytes_and_revision_when_the_catalogue_is_saved(
    ledger: Ledger, tmp_path: Path
) -> None:
    transaction_id = _import_without_reference(ledger, tmp_path)
    before = _stored_record(ledger, transaction_id)

    ledger.transactions.save(ledger.transactions.load())

    after = _stored_record(ledger, transaction_id)
    assert after.payload == before.payload
    assert after.revision_id == before.revision_id


def test_a_row_stored_in_the_old_shape_loads_edits_and_saves_through_the_revision_guard(
    ledger: Ledger, tmp_path: Path
) -> None:
    transaction_id = _import_with_reference(ledger, tmp_path)
    _rewrite_as_stored_before_the_reference(ledger, transaction_id)
    old_shape = ledger.row(transaction_id)
    assert old_shape.raw.statement_reference is None

    updated = update_manual_transaction_fields(
        bucket_id=BUCKET_ID,
        transaction_id=transaction_id,
        patch=ManualLedgerTransactionPatch(notes="Revisado"),
        actor=PERSON,
        source_command="aeat app ledger update",
        expected_current=old_shape,
        ports=ledger.ports,
    )

    assert updated.transaction.notes == "Revisado"
    assert updated.transaction.raw.statement_reference is None
    assert "statement_reference" not in _stored_raw(ledger, updated.ref.transaction_id)


def test_an_edit_that_renames_the_movement_keeps_the_printed_reference(ledger: Ledger, tmp_path: Path) -> None:
    transaction_id = _import_with_reference(ledger, tmp_path)

    updated = update_manual_transaction_fields(
        bucket_id=BUCKET_ID,
        transaction_id=transaction_id,
        patch=ManualLedgerTransactionPatch(description="Luz oficina"),
        actor=PERSON,
        source_command="aeat app ledger update",
        ports=ledger.ports,
    )

    # A new description gives the row a new id; the bank's reference is unchanged.
    assert updated.ref.transaction_id != transaction_id
    assert ledger.row(updated.ref.transaction_id).raw.statement_reference == _REFERENCE


def test_split_parts_and_their_merge_keep_the_printed_reference(ledger: Ledger, tmp_path: Path) -> None:
    transaction_id = _import_with_reference(ledger, tmp_path)

    split = split_transaction(
        bucket_id=BUCKET_ID,
        transaction_id=transaction_id,
        children=(
            SplitChildCommand(amount=Decimal("40.50"), description="Luz oficina"),
            SplitChildCommand(amount=Decimal("20.00"), description="Luz vivienda"),
        ),
        actor=PERSON,
        ports=ledger.ports,
    )
    assert [ledger.row(child).raw.statement_reference for child in split.child_transaction_ids] == [
        _REFERENCE,
        _REFERENCE,
    ]

    merged = merge_transactions(
        bucket_id=BUCKET_ID,
        child_transaction_ids=split.child_transaction_ids,
        actor=PERSON,
        ports=ledger.ports,
    )
    assert ledger.row(merged.merged_transaction_id).raw.statement_reference == _REFERENCE


def test_the_reference_takes_no_part_in_the_transaction_id_or_duplicate_detection(ledger: Ledger) -> None:
    printed = ParsedLedgerRow(
        raw=RawTransaction(
            provider_transaction_id="statement-row-7",
            booked_date=NOW_DATE,
            amount=Decimal("60.50"),
            currency="EUR",
            description="RECIBO LUZ",
            provenance=RawProvenance(
                source_path=Path("extracto.csv"),
                source_sha256="e" * 64,
                source_row_index=7,
                source_format=SourceFormat.CSV,
                ingested_at=datetime.combine(NOW_DATE, time(9), tzinfo=UTC),
                provider_name="CSV provider",
            ),
            raw_fields={"Concepto": "RECIBO LUZ"},
            statement_reference=_REFERENCE,
        ),
        direction=TransactionDirection.OUTGOING,
    )
    unprinted = ParsedLedgerRow(
        raw=printed.raw.model_copy(update={"statement_reference": None}),
        direction=TransactionDirection.OUTGOING,
    )
    assert derive_transaction_id(printed.raw) == derive_transaction_id(unprinted.raw)

    first = import_ledger_transactions(
        bucket_id=BUCKET_ID,
        parsed_rows=(printed,),
        ports=build_ledger_import_ports(),
        transaction_repository=ledger.transactions,
        bucket_event_repository=ledger.events,
    )
    second = import_ledger_transactions(
        bucket_id=BUCKET_ID,
        parsed_rows=(unprinted,),
        ports=build_ledger_import_ports(),
        transaction_repository=ledger.transactions,
        bucket_event_repository=ledger.events,
    )

    assert first.summary.imported == 1
    assert second.summary.imported == 0
    assert second.summary.skipped == 1
    assert len(ledger.transactions.load().transactions) == 1
