"""Unit tests for invoice and invoice-line models."""

from __future__ import annotations

from datetime import date
from decimal import Decimal

import pytest
from pydantic import ValidationError

from ._enums import InvoiceKind, IvaRate, PaymentStatus
from ._models import Invoice, InvoiceCatalogue, InvoiceLine, derive_invoice_id

pytestmark = [pytest.mark.unit, pytest.mark.domain_model]


def _valid_line(
    *,
    description: str = "Consultoría mensual",
    quantity: str = "1",
    unit_price: str = "100.00",
    iva_rate: IvaRate = IvaRate.RATE_21,
) -> InvoiceLine:
    quantity_dec = Decimal(quantity)
    unit_price_dec = Decimal(unit_price)
    subtotal = quantity_dec * unit_price_dec
    rate = {
        IvaRate.RATE_0: Decimal("0"),
        IvaRate.RATE_4: Decimal("0.04"),
        IvaRate.RATE_10: Decimal("0.10"),
        IvaRate.RATE_21: Decimal("0.21"),
    }.get(iva_rate)
    iva_amount = Decimal("0") if rate is None else (subtotal * rate)
    return InvoiceLine(
        description=description,
        quantity=quantity_dec,
        unit_price=unit_price_dec,
        subtotal=subtotal,
        iva_rate=iva_rate,
        iva_amount=iva_amount,
    )


def _valid_invoice(
    *,
    kind: InvoiceKind = InvoiceKind.ISSUED,
    invoice_number: str = "INV-001",
    issued_at: date = date(2026, 4, 1),
    counterparty_name: str = "Cliente SL",
    counterparty_tax_id: str = "B12345674",
    counterparty_country: str = "ES",
    currency: str = "EUR",
    lines: tuple[InvoiceLine, ...] | None = None,
    payment_status: PaymentStatus = PaymentStatus.PAID,
    linked_transaction_ids: tuple[str, ...] = (),
) -> Invoice:
    chosen_lines = lines if lines is not None else (_valid_line(),)
    base = sum((line.subtotal for line in chosen_lines), start=Decimal("0"))
    iva = sum((line.iva_amount for line in chosen_lines), start=Decimal("0"))
    grand = base + iva
    return Invoice.model_validate(
        {
            "kind": kind,
            "invoice_number": invoice_number,
            "issued_at": issued_at,
            "counterparty_name": counterparty_name,
            "counterparty_tax_id": counterparty_tax_id,
            "counterparty_country": counterparty_country,
            "base_total": base,
            "iva_total": iva,
            "grand_total": grand,
            "currency": currency,
            "lines": chosen_lines,
            "payment_status": payment_status,
            "linked_transaction_ids": linked_transaction_ids,
        }
    )


def test_invoice_id_is_64_char_lowercase_hex_and_stable() -> None:
    """Invoice ID must be derived and stable across equivalent re-construction."""
    first = _valid_invoice()
    second = _valid_invoice()
    assert first.invoice_id == second.invoice_id
    assert len(first.invoice_id) == 64
    assert all(ch in "0123456789abcdef" for ch in first.invoice_id)


def test_invoice_is_frozen_and_rejects_mutation() -> None:
    """Invoice models must be frozen."""
    invoice = _valid_invoice()
    with pytest.raises(ValidationError):
        invoice.notes = "mutated"  # type: ignore[misc]


def test_invoice_line_accepts_one_cent_rounding() -> None:
    """Line-level rounding within 1 cent must pass the subtotal/iva checks."""
    line = InvoiceLine.model_validate(
        {
            "description": "Rounded line",
            "quantity": Decimal("3"),
            "unit_price": Decimal("0.333"),
            "subtotal": Decimal("1.00"),
            "iva_rate": IvaRate.RATE_21,
            "iva_amount": Decimal("0.21"),
        }
    )
    assert line.subtotal == Decimal("1.00")


def test_invoice_line_rejects_larger_rounding_drift() -> None:
    """Drift beyond 1 cent on a line must fail validation."""
    with pytest.raises(ValidationError):
        InvoiceLine.model_validate(
            {
                "description": "Bad line",
                "quantity": Decimal("1"),
                "unit_price": Decimal("100.00"),
                "subtotal": Decimal("50.00"),
                "iva_rate": IvaRate.RATE_21,
                "iva_amount": Decimal("10.50"),
            }
        )


def test_iva_rate_percentage_is_resolved_against_centralized_vat_substrate() -> None:
    """iva_rate_percentage must derive its values from registry/aeat/vat/rates.toml.

    Confirms the V-1 audit finding teardown: the helper no longer carries
    a hardcoded ``RATE_21 -> 0.21`` literal. Every numeric slot is
    resolved against :func:`aeat.domain.vat.lookup_rate` for Spain at
    a given date.
    """
    from aeat.domain.invoices._enums import iva_rate_percentage
    from aeat.domain.vat import EUMemberState, VATRateKind, lookup_rate

    sample_date = date(2025, 6, 15)

    assert iva_rate_percentage(IvaRate.RATE_0, on_date=sample_date) == Decimal("0")
    assert iva_rate_percentage(IvaRate.EXEMPT, on_date=sample_date) is None
    assert iva_rate_percentage(IvaRate.NOT_SUBJECT, on_date=sample_date) is None

    for slot, kind in [
        (IvaRate.RATE_4, VATRateKind.SUPER_REDUCED),
        (IvaRate.RATE_10, VATRateKind.REDUCED),
        (IvaRate.RATE_21, VATRateKind.GENERAL),
    ]:
        substrate_rate = lookup_rate(EUMemberState.ES, kind, sample_date)
        expected = substrate_rate.pct / Decimal("100")
        assert iva_rate_percentage(slot, on_date=sample_date) == expected


def test_invoice_exempt_lines_require_zero_iva() -> None:
    """EXEMPT and NOT_SUBJECT lines must carry iva_amount == 0 exactly."""
    with pytest.raises(ValidationError):
        InvoiceLine.model_validate(
            {
                "description": "Exempt with iva",
                "quantity": Decimal("1"),
                "unit_price": Decimal("10"),
                "subtotal": Decimal("10"),
                "iva_rate": IvaRate.EXEMPT,
                "iva_amount": Decimal("0.01"),
            }
        )


def test_invoice_requires_exact_invoice_level_totals() -> None:
    """Invoice-level totals must equal the line sums exactly (no tolerance)."""
    line = _valid_line(quantity="1", unit_price="100.00")
    with pytest.raises(ValidationError):
        Invoice.model_validate(
            {
                "kind": InvoiceKind.ISSUED,
                "invoice_number": "INV-001",
                "issued_at": date(2026, 4, 1),
                "counterparty_name": "Cliente SL",
                "counterparty_tax_id": "B12345674",
                "counterparty_country": "ES",
                "base_total": Decimal("100.01"),
                "iva_total": Decimal("21.00"),
                "grand_total": Decimal("121.01"),
                "currency": "EUR",
                "lines": (line,),
                "payment_status": PaymentStatus.PAID,
            }
        )


def test_invoice_rejects_accumulated_line_drift() -> None:
    """Per-line 1-cent drift that accumulates at the invoice level is rejected."""
    line_a = InvoiceLine.model_validate(
        {
            "description": "Line a",
            "quantity": Decimal("1"),
            "unit_price": Decimal("100.00"),
            "subtotal": Decimal("100.01"),
            "iva_rate": IvaRate.RATE_21,
            "iva_amount": Decimal("21.00"),
        }
    )
    line_b = InvoiceLine.model_validate(
        {
            "description": "Line b",
            "quantity": Decimal("1"),
            "unit_price": Decimal("100.00"),
            "subtotal": Decimal("100.01"),
            "iva_rate": IvaRate.RATE_21,
            "iva_amount": Decimal("21.00"),
        }
    )
    # line subtotal sum is 200.02 but we declare base_total as 200.00 → >1-cent drift.
    with pytest.raises(ValidationError):
        Invoice.model_validate(
            {
                "kind": InvoiceKind.ISSUED,
                "invoice_number": "INV-001",
                "issued_at": date(2026, 4, 1),
                "counterparty_name": "Cliente SL",
                "counterparty_tax_id": "B12345674",
                "counterparty_country": "ES",
                "base_total": Decimal("200.00"),
                "iva_total": Decimal("42.00"),
                "grand_total": Decimal("242.00"),
                "currency": "EUR",
                "lines": (line_a, line_b),
                "payment_status": PaymentStatus.PAID,
            }
        )


def test_invoice_exempt_invoice_enforces_zero_iva_total() -> None:
    """An invoice with only EXEMPT / NOT_SUBJECT lines must have iva_total == 0."""
    exempt_line = InvoiceLine.model_validate(
        {
            "description": "Exempt service",
            "quantity": Decimal("1"),
            "unit_price": Decimal("50"),
            "subtotal": Decimal("50"),
            "iva_rate": IvaRate.EXEMPT,
            "iva_amount": Decimal("0"),
        }
    )
    invoice = _valid_invoice(lines=(exempt_line,))
    assert invoice.iva_total == Decimal("0")
    assert invoice.grand_total == invoice.base_total


def test_invoice_validates_spanish_tax_id_for_es_country() -> None:
    """ES counterparties must pass NIF/NIE/CIF validation."""
    with pytest.raises(ValidationError):
        _valid_invoice(counterparty_country="ES", counterparty_tax_id="INVALID")


def test_invoice_validates_vat_prefix_for_non_es_country() -> None:
    """Non-ES counterparties must carry a VAT number with the country prefix."""
    invoice = _valid_invoice(counterparty_country="DE", counterparty_tax_id="DE123456789")
    assert invoice.counterparty_tax_id == "DE123456789"
    with pytest.raises(ValidationError):
        _valid_invoice(counterparty_country="DE", counterparty_tax_id="123456789")


def test_invoice_linked_transaction_ids_are_deduplicated_and_hex_validated() -> None:
    """Linked transaction IDs must be 64-char lowercase hex and deduplicated."""
    hex_a = "a" * 64
    hex_b = "b" * 64
    invoice = _valid_invoice(linked_transaction_ids=(hex_a, hex_b, hex_a))
    assert invoice.linked_transaction_ids == (hex_a, hex_b)
    with pytest.raises(ValidationError):
        _valid_invoice(linked_transaction_ids=("not-hex",))


def test_invoice_rejects_caller_supplied_invoice_id_mismatch() -> None:
    """A caller-supplied ``invoice_id`` must match the derived digest."""
    invoice = _valid_invoice()
    with pytest.raises(ValidationError):
        Invoice.model_validate(
            {
                "invoice_id": "0" * 64,
                **{key: value for key, value in invoice.model_dump(mode="python").items() if key != "invoice_id"},
            }
        )


def test_derive_invoice_id_is_stable_over_equivalent_decimals() -> None:
    """Derivation must be invariant under equivalent Decimal forms."""
    first = derive_invoice_id(
        kind=InvoiceKind.ISSUED,
        invoice_number="INV-001",
        issued_at=date(2026, 4, 1),
        counterparty_tax_id="B12345674",
        currency="EUR",
        grand_total=Decimal("121.00"),
    )
    second = derive_invoice_id(
        kind=InvoiceKind.ISSUED,
        invoice_number="INV-001",
        issued_at=date(2026, 4, 1),
        counterparty_tax_id="B12345674",
        currency="EUR",
        grand_total=Decimal("121"),
    )
    assert first == second


def test_invoice_number_is_uppercased_for_identity() -> None:
    """Invoice number casing must not yield distinct identities."""
    lower = _valid_invoice(invoice_number="inv-001")
    upper = _valid_invoice(invoice_number="INV-001")
    assert lower.invoice_id == upper.invoice_id
    assert lower.invoice_number == "INV-001"


def test_catalogue_rejects_duplicate_invoice_ids_on_construction() -> None:
    """Duplicate logical IDs must be rejected when building a catalogue."""
    invoice = _valid_invoice()
    with pytest.raises(ValidationError):
        InvoiceCatalogue.from_invoices([invoice, invoice])


def test_catalogue_iteration_yields_invoices() -> None:
    """Iteration yields invoices, not model fields."""
    first = _valid_invoice(invoice_number="INV-001")
    second = _valid_invoice(invoice_number="INV-002")
    catalogue = InvoiceCatalogue.from_invoices([first, second])
    assert [invoice.invoice_id for invoice in catalogue] == [first.invoice_id, second.invoice_id]
    assert first.invoice_id in catalogue
    assert len(catalogue) == 2
