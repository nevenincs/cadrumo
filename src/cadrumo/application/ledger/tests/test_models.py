"""Tests for manual ledger application contracts."""

from __future__ import annotations

import re
from collections.abc import Callable
from datetime import date
from decimal import Decimal

import pytest
from pydantic import ValidationError

from ....domain.transactions.enums import BusinessClassification, TransactionDirection
from ..models import ManualLedgerTransactionCommand, ManualLedgerTransactionPatch, _ManualLedgerTransactionInput

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


def test_manual_ledger_command_and_patch_share_the_canonical_input_normalisation() -> None:
    """Create and patch boundaries normalize the same shared ledger facts identically."""

    command = _command(
        currency=" eur ",
        counterparty=" Proveedor SL ",
        category_id=" office-supplies ",
        source_jurisdiction=" DE ",
        counterparty_country=" ES ",
        attachment_ids=(" attachment-1 ",),
    )
    patch = ManualLedgerTransactionPatch(
        currency=" eur ",
        counterparty=" Proveedor SL ",
        category_id=" office-supplies ",
        source_jurisdiction=" DE ",
        counterparty_country=" ES ",
        attachment_ids=(" attachment-1 ",),
    )

    for input_model in (command, patch):
        assert input_model.currency == "EUR"
        assert input_model.counterparty == "Proveedor SL"
        assert input_model.category_id == "office-supplies"
        assert input_model.source_jurisdiction == "DE"
        assert input_model.counterparty_country == "ES"
        assert input_model.attachment_ids == ("attachment-1",)


def test_manual_ledger_command_and_patch_have_one_input_normalisation_owner() -> None:
    """The shared input invariant is declared only on the private ledger base."""

    assert ManualLedgerTransactionCommand.__bases__ == (_ManualLedgerTransactionInput,)
    assert ManualLedgerTransactionPatch.__bases__ == (_ManualLedgerTransactionInput,)
    for model in (ManualLedgerTransactionCommand, ManualLedgerTransactionPatch):
        assert "_normalise_country_codes" not in model.__dict__
        assert "_normalise_currency" not in model.__dict__
        assert "_normalise_identifier_tuple" not in model.__dict__


def test_manual_ledger_transaction_command_rejects_invalid_payloads() -> None:
    """Invalid operator payloads are refused at the real command boundary."""
    rejection_cases: tuple[tuple[str, str, Callable[[], object]], ...] = (
        *(
            (
                f"source-jurisdiction-{bad!r}",
                "ISO 3166-1 alpha-2 uppercase",
                lambda bad=bad: _command(source_jurisdiction=bad),
            )
            for bad in ("es", "ESP", "E1", "e", "")
        ),
        (
            "mixed-without-business-pct",
            "business_pct is required",
            lambda: _command(description="mixed expense", business_classification=BusinessClassification.MIXED),
        ),
        (
            "multi-purchase-evidence",
            "purchase_invoice_evidence_id",
            lambda: _command(
                description="duplicate evidence",
                purchase_invoice_evidence_id=("evidence-1", "evidence-2"),
            ),
        ),
        (
            "duplicate-attachment-ids",
            "identifier tuple must not contain duplicates",
            lambda: _command(description="duplicate evidence", attachment_ids=("evidence-1", " evidence-1 ")),
        ),
        (
            "zero-amount",
            "amount must be non-zero",
            lambda: _command(
                amount=Decimal("0"),
                direction=TransactionDirection.INCOMING,
                description="zero value evidence belongs on an existing row",
            ),
        ),
        (
            "negative-outgoing",
            "non-negative magnitude",
            lambda: _command(amount=Decimal("-121.00"), description="negative outgoing is invalid"),
        ),
        (
            "negative-incoming",
            "non-negative magnitude",
            lambda: _command(
                amount=Decimal("-121.00"),
                direction=TransactionDirection.INCOMING,
                description="negative incoming is invalid",
            ),
        ),
        (
            "internal-transfer-tax-payload",
            r"INTERNAL_TRANSFER.*tax or evidence fields",
            lambda: _command(
                direction=TransactionDirection.INTERNAL_TRANSFER,
                description="move between own accounts",
                taxable_base=Decimal("100.00"),
            ),
        ),
    )
    for case_id, match, build in rejection_cases:
        try:
            build()
        except ValidationError as exc:
            assert re.search(match, str(exc)), case_id
            continue
        pytest.fail(f"{case_id} unexpectedly validated")


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
