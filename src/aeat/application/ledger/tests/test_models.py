"""Tests for manual ledger application contracts."""

from __future__ import annotations

from datetime import UTC, date, datetime
from decimal import Decimal
from pathlib import Path

import pytest
from pydantic import ValidationError

from ....core.external_constants import CLASSIFIED_BY_MANUAL as _CLASSIFIED_BY_MANUAL_FROM_CORE
from ....domain.transactions import (
    BucketTransactionRef,
    BusinessClassification,
    RawProvenance,
    RawTransaction,
    SourceFormat,
    Transaction,
    TransactionDirection,
)
from .. import CLASSIFIED_BY_MANUAL, ManualLedgerTransactionCommand, ManualLedgerTransactionResult

pytestmark = [pytest.mark.unit, pytest.mark.hex_application]


def _command(**overrides: object) -> ManualLedgerTransactionCommand:
    """Build a minimal valid command, overriding the field under test."""

    fields: dict[str, object] = {
        "bucket_id": "bucket-a",
        "booked_date": date(2026, 5, 1),
        "amount": Decimal("-121.00"),
        "direction": TransactionDirection.OUTGOING,
        "description": "material oficina",
    }
    fields.update(overrides)
    return ManualLedgerTransactionCommand(**fields)


def test_source_jurisdiction_accepts_iso_3166_alpha2_and_strips_whitespace() -> None:
    """A two-letter uppercase ISO 3166-1 code is accepted; surrounding space is stripped."""

    assert _command(source_jurisdiction="ES").source_jurisdiction == "ES"
    assert _command(source_jurisdiction=" DE ").source_jurisdiction == "DE"
    assert _command(source_jurisdiction=None).source_jurisdiction is None


@pytest.mark.parametrize("bad", ["es", "ESP", "E1", "e", ""])
def test_source_jurisdiction_rejects_non_iso_3166_alpha2(bad: str) -> None:
    """Lowercase, wrong-length, and non-alphabetic codes are refused at the boundary."""

    with pytest.raises(ValidationError, match="ISO 3166-1 alpha-2 uppercase"):
        _command(source_jurisdiction=bad)


def test_manual_ledger_transaction_command_normalises_operator_text() -> None:
    command = ManualLedgerTransactionCommand(
        bucket_id=" bucket-a ",
        booked_date=date(2026, 5, 1),
        amount=Decimal("-121.00"),
        currency=" eur ",
        direction=TransactionDirection.OUTGOING,
        counterparty=" Proveedor SL ",
        description="  material oficina  ",
        purchase_invoice_evidence_id=" evidence-1 ",
        attachment_ids=(" attachment-1 ",),
        actor=" operator ",
        source_command=" aeat app ledger add ",
    )

    assert command.bucket_id == "bucket-a"
    assert command.currency == "EUR"
    assert command.counterparty == "Proveedor SL"
    assert command.description == "material oficina"
    assert command.purchase_invoice_evidence_id == "evidence-1"
    assert command.attachment_ids == ("attachment-1",)
    assert command.actor == "operator"
    assert command.source_command == "aeat app ledger add"


def test_manual_ledger_transaction_command_enforces_mixed_business_percentage() -> None:
    with pytest.raises(ValidationError, match="business_pct is required"):
        ManualLedgerTransactionCommand(
            bucket_id="bucket-a",
            booked_date=date(2026, 5, 1),
            amount=Decimal("-121.00"),
            direction=TransactionDirection.OUTGOING,
            description="mixed expense",
            business_classification=BusinessClassification.MIXED,
        )


def test_manual_ledger_transaction_command_rejects_multi_purchase_evidence_value() -> None:
    with pytest.raises(ValidationError, match="purchase_invoice_evidence_id"):
        ManualLedgerTransactionCommand.model_validate(
            {
                "bucket_id": "bucket-a",
                "booked_date": date(2026, 5, 1),
                "amount": Decimal("-121.00"),
                "direction": TransactionDirection.OUTGOING,
                "description": "duplicate evidence",
                "purchase_invoice_evidence_id": ("evidence-1", "evidence-2"),
            }
        )


def test_manual_ledger_transaction_command_rejects_duplicate_attachment_ids() -> None:
    with pytest.raises(ValidationError, match="identifier tuple must not contain duplicates"):
        ManualLedgerTransactionCommand(
            bucket_id="bucket-a",
            booked_date=date(2026, 5, 1),
            amount=Decimal("-121.00"),
            direction=TransactionDirection.OUTGOING,
            description="duplicate evidence",
            attachment_ids=("evidence-1", " evidence-1 "),
        )


def test_manual_ledger_transaction_command_rejects_zero_amount_rows() -> None:
    with pytest.raises(ValidationError, match="amount must be non-zero"):
        ManualLedgerTransactionCommand(
            bucket_id="bucket-a",
            booked_date=date(2026, 5, 1),
            amount=Decimal("0"),
            direction=TransactionDirection.INCOMING,
            description="zero value evidence belongs on an existing row",
        )


def test_manual_ledger_transaction_command_enforces_direction_sign_policy() -> None:
    with pytest.raises(ValidationError, match=r"OUTGOING.*negative"):
        ManualLedgerTransactionCommand(
            bucket_id="bucket-a",
            booked_date=date(2026, 5, 1),
            amount=Decimal("121.00"),
            direction=TransactionDirection.OUTGOING,
            description="positive outgoing is invalid",
        )

    with pytest.raises(ValidationError, match=r"INCOMING.*positive"):
        ManualLedgerTransactionCommand(
            bucket_id="bucket-a",
            booked_date=date(2026, 5, 1),
            amount=Decimal("-121.00"),
            direction=TransactionDirection.INCOMING,
            description="negative incoming is invalid",
        )


def test_manual_ledger_transaction_command_rejects_tax_payload_on_internal_transfer() -> None:
    with pytest.raises(ValidationError, match=r"INTERNAL_TRANSFER.*tax or evidence fields"):
        ManualLedgerTransactionCommand(
            bucket_id="bucket-a",
            booked_date=date(2026, 5, 1),
            amount=Decimal("121.00"),
            direction=TransactionDirection.INTERNAL_TRANSFER,
            description="move between own accounts",
            taxable_base=Decimal("100.00"),
        )


def test_manual_ledger_transaction_result_requires_matching_strict_shapes() -> None:
    raw = RawTransaction(
        transaction_id="manual-row-1",
        booked_date=date(2026, 5, 1),
        value_date=date(2026, 5, 1),
        amount=Decimal("-121.00"),
        currency="EUR",
        counterparty="Proveedor SL",
        description="manual ledger row",
        provenance=RawProvenance(
            source_path=Path(__file__),
            source_sha256="e" * 64,
            source_row_index=1,
            source_format=SourceFormat.MANUAL,
            ingested_at=datetime(2026, 5, 1, 12, 0, tzinfo=UTC),
            provider_name="manual",
        ),
        raw_fields={"source": "manual"},
    )
    transaction = Transaction.model_validate({"raw": raw, "direction": TransactionDirection.OUTGOING})
    result = ManualLedgerTransactionResult(
        ref=BucketTransactionRef(bucket_id="bucket-a", transaction_id=transaction.transaction_id),
        transaction=transaction,
        bucket_event_ids=("event-1",),
    )

    assert result.ref.bucket_id == "bucket-a"
    assert result.ref.transaction_id == transaction.transaction_id
    assert result.transaction.raw.provenance.source_format is SourceFormat.MANUAL
    assert result.bucket_event_ids == ("event-1",)


def test_classified_by_manual_constant_value() -> None:
    # The sentinel must equal the literal used in every call-site so that
    # comparisons against persisted ``classified_by`` payloads remain correct.
    assert CLASSIFIED_BY_MANUAL == "manual"


def test_classified_by_manual_is_same_object_from_application_and_core() -> None:
    # The application-layer public surface and the canonical core source must be
    # the same object; any caller importing from either surface reads the same constant.
    assert CLASSIFIED_BY_MANUAL is _CLASSIFIED_BY_MANUAL_FROM_CORE
