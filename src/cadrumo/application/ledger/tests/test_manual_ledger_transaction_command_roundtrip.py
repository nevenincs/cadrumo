"""Strict JSON roundtrip test for :class:`ManualLedgerTransactionCommand`.

The discipline rule (``aeat-quality-gates``) requires a dedicated
``model_dump_json`` / ``model_validate_json`` test for every persistence-
shaped pydantic model that flows over the wire. The manual-ledger
command is the application-layer record produced by ``_command_from_patch``
and consumed by the ledger pipeline; it carries every tax-relevant
field (taxable_base, iva_rate, irpf_category, prorrata_reference,
attachment_ids, etc.) plus the operator/audit metadata triple
(actor, source_command, idempotency_key).

Coverage:

- A fully-populated command with every defaultable field set to a
  non-default value, including the tax classification fields
  (taxable_base, iva_rate, iva_amount, irpf_category, usage_ratio_id,
  prorrata_reference, purchase_invoice_evidence_id, attachment_ids)
  per the discipline rule's "populate every defaultable field with a
  non-default value" mandate.
- Strict pydantic equality across the JSON boundary.
- Decimal precision preservation for amount / taxable_base / iva_rate.
- Anti-tautology proof: dropping a required field on the on-disk
  payload raises ValidationError, ensuring the roundtrip cannot
  silently pass on a broken payload.
- Anti-tautology proof: extra unknown keys raise ValidationError per
  extra="forbid".
- INTERNAL_TRANSFER variant roundtrip — exercises the alternate
  validator branch where tax fields MUST be absent.
"""

from __future__ import annotations

import json
from datetime import date
from decimal import Decimal

import pytest
from pydantic import ValidationError

from ....core.prorrata_exclusions import Art104TresExclusion
from ....domain.iva.prorrata import InputClassification
from ....domain.transactions.enums import BusinessClassification, TransactionDirection
from ..models import ManualLedgerTransactionCommand

pytestmark = [pytest.mark.unit, pytest.mark.hex_application]


def _populated_command() -> ManualLedgerTransactionCommand:
    """A MIXED-classification command with every defaultable field populated."""

    return ManualLedgerTransactionCommand(
        bucket_id="bucket-fixture-001",
        booked_date=date(2025, 4, 15),
        value_date=date(2025, 4, 16),
        amount=Decimal("1234.56"),  # non-negative magnitude; flow is OUTGOING via direction
        currency="EUR",
        direction=TransactionDirection.OUTGOING,
        counterparty="Acme Office Supplies SL",
        description="Material de oficina Q2",
        business_classification=BusinessClassification.MIXED,
        business_pct=Decimal("0.75"),
        category_id="cat.actividad.suministros",
        taxable_base=Decimal("1020.30"),
        iva_rate=Decimal("0.21"),
        iva_amount=Decimal("214.26"),
        irpf_category="rendimientos.actividades",
        usage_ratio_id="usage.home-office.2025",
        prorrata_reference="prorrata.iva.2025",
        art_104_tres_exclusion=Art104TresExclusion.NON_HABITUAL_REAL_ESTATE_OR_FINANCIAL,
        input_classification=InputClassification.COMMON,
        purchase_invoice_evidence_id="evidence.invoice.AC-2025-042",
        attachment_ids=("attach.invoice.pdf", "attach.delivery-note.pdf"),
        notes="Q2 office expense, mixed personal/business",
        actor="operator-jdoe",
        source_command="aeat app ledger add --interactive",
        idempotency_key="cmd-2025-04-15-0001",
    )


def _populated_internal_transfer_command() -> ManualLedgerTransactionCommand:
    """An INTERNAL_TRANSFER command — alternate branch with no tax fields."""

    return ManualLedgerTransactionCommand(
        bucket_id="bucket-fixture-001",
        booked_date=date(2025, 4, 20),
        amount=Decimal("5000.00"),
        direction=TransactionDirection.INTERNAL_TRANSFER,
        counterparty="Personal savings account",
        description="Transfer from current account to savings",
        business_classification=BusinessClassification.PERSONAL,
        # INTERNAL_TRANSFER forbids every tax / evidence field — must
        # be absent on the wire and on reload.
        actor="operator-jdoe",
        source_command="aeat app ledger add --interactive",
    )


def test_command_json_roundtrip_preserves_strict_equality() -> None:
    """Build a fully-populated command, push through JSON, assert equality.

    The model_dump_json / model_validate_json pair is the wire
    contract for the ledger pipeline (the command flows through
    repository writes, bucket-event payloads, and CLI emit paths).
    This pins that every field, including the Decimal precision and
    the attachment-ids ordering, survives the round-trip.
    """

    original = _populated_command()
    encoded = original.model_dump_json()
    roundtripped = ManualLedgerTransactionCommand.model_validate_json(encoded)
    assert roundtripped == original


def test_command_preserves_art_104_tres_exclusion_through_json() -> None:
    """The operator-declared art-104.Tres exclusion tag survives the command wire contract."""
    original = _populated_command()
    assert original.art_104_tres_exclusion is Art104TresExclusion.NON_HABITUAL_REAL_ESTATE_OR_FINANCIAL
    roundtripped = ManualLedgerTransactionCommand.model_validate_json(original.model_dump_json())
    assert roundtripped.art_104_tres_exclusion is Art104TresExclusion.NON_HABITUAL_REAL_ESTATE_OR_FINANCIAL


def test_command_preserves_input_classification_through_json() -> None:
    """The operator-declared LIVA art. 106 input_classification survives the command wire contract."""
    original = _populated_command()
    assert original.input_classification is InputClassification.COMMON
    roundtripped = ManualLedgerTransactionCommand.model_validate_json(original.model_dump_json())
    assert roundtripped.input_classification is InputClassification.COMMON


def test_command_json_roundtrip_preserves_decimal_precision() -> None:
    """Tax-field Decimals must not lose precision through JSON."""

    original = _populated_command()
    encoded = original.model_dump_json()
    roundtripped = ManualLedgerTransactionCommand.model_validate_json(encoded)
    assert isinstance(roundtripped.amount, Decimal)
    assert roundtripped.amount == Decimal("1234.56")
    assert roundtripped.taxable_base == Decimal("1020.30")
    assert roundtripped.iva_rate == Decimal("0.21")
    assert roundtripped.iva_amount == Decimal("214.26")
    assert roundtripped.business_pct == Decimal("0.75")


def test_internal_transfer_command_json_roundtrip() -> None:
    """INTERNAL_TRANSFER command roundtrips with no tax fields injected.

    The alternate validator branch rejects any tax / evidence field
    on INTERNAL_TRANSFER; verify the JSON path doesn't smuggle a
    default tax field through on reload.
    """

    original = _populated_internal_transfer_command()
    encoded = original.model_dump_json()
    roundtripped = ManualLedgerTransactionCommand.model_validate_json(encoded)
    assert roundtripped == original
    assert roundtripped.taxable_base is None
    assert roundtripped.iva_rate is None
    assert roundtripped.attachment_ids == ()
    assert roundtripped.business_pct is None  # PERSONAL classification


def test_command_round_trip_dropped_required_field_raises() -> None:
    """Anti-tautology proof: dropping bucket_id raises ValidationError on reload."""

    original = _populated_command()
    encoded = json.loads(original.model_dump_json())
    del encoded["bucket_id"]
    mutated = json.dumps(encoded)
    with pytest.raises(ValidationError):
        ManualLedgerTransactionCommand.model_validate_json(mutated)


def test_command_round_trip_extra_field_raises() -> None:
    """Anti-tautology proof: extra unknown keys rejected by extra='forbid'."""

    original = _populated_command()
    encoded = json.loads(original.model_dump_json())
    encoded["unexpected_field"] = "smuggled-in"
    mutated = json.dumps(encoded)
    with pytest.raises(ValidationError):
        ManualLedgerTransactionCommand.model_validate_json(mutated)


def test_command_round_trip_invariant_business_pct_with_mixed_classification() -> None:
    """A roundtrip must preserve the business-pct invariant for MIXED rows."""

    original = _populated_command()  # MIXED classification
    encoded = original.model_dump_json()
    roundtripped = ManualLedgerTransactionCommand.model_validate_json(encoded)
    assert roundtripped.business_classification is BusinessClassification.MIXED
    assert roundtripped.business_pct == Decimal("0.75")


def test_command_round_trip_attachment_ids_preserve_order_and_count() -> None:
    """attachment_ids is a tuple — order and duplicates rejection survive the wire."""

    original = _populated_command()
    encoded = original.model_dump_json()
    roundtripped = ManualLedgerTransactionCommand.model_validate_json(encoded)
    assert roundtripped.attachment_ids == ("attach.invoice.pdf", "attach.delivery-note.pdf")
