"""Tests for manual ledger application contracts."""

from __future__ import annotations

from datetime import date
from decimal import Decimal

import pytest
from pydantic import ValidationError

from ....domain.transactions import (
    BusinessClassification,
    TransactionDirection,
)
from .. import ManualLedgerTransactionCommand

pytestmark = [pytest.mark.unit, pytest.mark.hex_application]

_BUCKET_ID = "21212121-2121-4121-8121-212121212121"


def _command(**overrides: object) -> ManualLedgerTransactionCommand:
    """Build a minimal valid command, overriding the field under test.

    Constructs via ``model_validate`` (matching this module's existing
    dict-construction tests) so the override map does not splat a
    ``dict[str, object]`` into the typed constructor.
    """

    fields: dict[str, object] = {
        "bucket_id": _BUCKET_ID,
        "booked_date": date(2026, 5, 1),
        "amount": Decimal("121.00"),
        "direction": TransactionDirection.OUTGOING,
        "description": "material oficina",
    }
    fields.update(overrides)
    return ManualLedgerTransactionCommand.model_validate(fields)


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
        bucket_id=f" {_BUCKET_ID} ",
        booked_date=date(2026, 5, 1),
        amount=Decimal("121.00"),
        currency=" eur ",
        direction=TransactionDirection.OUTGOING,
        counterparty=" Proveedor SL ",
        description="  material oficina  ",
        purchase_invoice_evidence_id=" evidence-1 ",
        attachment_ids=(" attachment-1 ",),
        actor=" operator ",
        source_command=" aeat app ledger add ",
    )

    assert command.bucket_id == _BUCKET_ID
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
            bucket_id=_BUCKET_ID,
            booked_date=date(2026, 5, 1),
            amount=Decimal("121.00"),
            direction=TransactionDirection.OUTGOING,
            description="mixed expense",
            business_classification=BusinessClassification.MIXED,
        )


def test_manual_ledger_transaction_command_rejects_multi_purchase_evidence_value() -> None:
    with pytest.raises(ValidationError, match="purchase_invoice_evidence_id"):
        ManualLedgerTransactionCommand.model_validate(
            {
                "bucket_id": _BUCKET_ID,
                "booked_date": date(2026, 5, 1),
                "amount": Decimal("121.00"),
                "direction": TransactionDirection.OUTGOING,
                "description": "duplicate evidence",
                "purchase_invoice_evidence_id": ("evidence-1", "evidence-2"),
            },
        )


def test_manual_ledger_transaction_command_rejects_duplicate_attachment_ids() -> None:
    with pytest.raises(ValidationError, match="identifier tuple must not contain duplicates"):
        ManualLedgerTransactionCommand(
            bucket_id=_BUCKET_ID,
            booked_date=date(2026, 5, 1),
            amount=Decimal("121.00"),
            direction=TransactionDirection.OUTGOING,
            description="duplicate evidence",
            attachment_ids=("evidence-1", " evidence-1 "),
        )


def test_manual_ledger_transaction_command_rejects_zero_amount_rows() -> None:
    with pytest.raises(ValidationError, match="amount must be non-zero"):
        ManualLedgerTransactionCommand(
            bucket_id=_BUCKET_ID,
            booked_date=date(2026, 5, 1),
            amount=Decimal("0"),
            direction=TransactionDirection.INCOMING,
            description="zero value evidence belongs on an existing row",
        )


def test_manual_ledger_transaction_command_rejects_negative_magnitude() -> None:
    # Flow is carried by direction; a negative amount is no longer a valid
    # encoding of OUTGOING and is refused at the command boundary regardless
    # of the declared direction.
    with pytest.raises(ValidationError, match="non-negative magnitude"):
        ManualLedgerTransactionCommand(
            bucket_id=_BUCKET_ID,
            booked_date=date(2026, 5, 1),
            amount=Decimal("-121.00"),
            direction=TransactionDirection.OUTGOING,
            description="negative outgoing is invalid",
        )

    with pytest.raises(ValidationError, match="non-negative magnitude"):
        ManualLedgerTransactionCommand(
            bucket_id=_BUCKET_ID,
            booked_date=date(2026, 5, 1),
            amount=Decimal("-121.00"),
            direction=TransactionDirection.INCOMING,
            description="negative incoming is invalid",
        )


def test_manual_ledger_transaction_command_accepts_magnitude_for_either_direction() -> None:
    # The same non-negative magnitude is valid for both INCOMING and OUTGOING;
    # direction alone decides the flow.
    outgoing = ManualLedgerTransactionCommand(
        bucket_id=_BUCKET_ID,
        booked_date=date(2026, 5, 1),
        amount=Decimal("121.00"),
        direction=TransactionDirection.OUTGOING,
        description="office supplies",
    )
    incoming = ManualLedgerTransactionCommand(
        bucket_id=_BUCKET_ID,
        booked_date=date(2026, 5, 1),
        amount=Decimal("121.00"),
        direction=TransactionDirection.INCOMING,
        description="client payment",
    )
    assert outgoing.amount == Decimal("121.00")
    assert incoming.amount == Decimal("121.00")


def test_manual_ledger_transaction_command_rejects_tax_payload_on_internal_transfer() -> None:
    with pytest.raises(ValidationError, match=r"INTERNAL_TRANSFER.*tax or evidence fields"):
        ManualLedgerTransactionCommand(
            bucket_id=_BUCKET_ID,
            booked_date=date(2026, 5, 1),
            amount=Decimal("121.00"),
            direction=TransactionDirection.INTERNAL_TRANSFER,
            description="move between own accounts",
            taxable_base=Decimal("100.00"),
        )


