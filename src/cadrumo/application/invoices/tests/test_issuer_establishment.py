"""Tests for the RD 1619/2012 art. 6.1.d case 3.º issuer-establishment predicate.

Case 3.º makes a factura simplificada's counterparty tax id mandatory for a
domestic operation whose issuer is established in the TAI. The fact is read
from the taxpayer's OWN profile (:class:`~cadrumo.domain.deadlines.TaxpayerProfile`),
never from the invoice, since establishment is a property of who issued the
invoice, not of the document itself.
"""

from __future__ import annotations

from datetime import date
from decimal import Decimal

import pytest

from ....domain.deadlines import FiscalResidency, IVARegime, TaxpayerProfile
from ....domain.invoices import Invoice, InvoiceClass, InvoiceLine, IvaRate, PaymentStatus
from ....domain.iva import InvoiceKind
from .. import issuer_established_in_tai, simplificada_requires_tax_id_for_domestic_issuer

pytestmark = [pytest.mark.unit, pytest.mark.hex_application]

_BASE = Decimal("40.00")
_CUOTA = Decimal("8.40")


def _profile(**overrides: object) -> TaxpayerProfile:
    payload: dict[str, object] = {"tax_id": "12345678Z", "iva_regime": IVARegime.GENERAL}
    payload.update(overrides)
    return TaxpayerProfile(**payload)  # type: ignore[arg-type]


def _line() -> InvoiceLine:
    return InvoiceLine(
        description="Reparación urgente",
        quantity=Decimal("1"),
        unit_price=_BASE,
        subtotal=_BASE,
        iva_rate=IvaRate.RATE_21,
        iva_amount=_CUOTA,
    )


def _invoice(**overrides: object) -> Invoice:
    payload: dict[str, object] = {
        "kind": InvoiceKind.ISSUED,
        "invoice_class": InvoiceClass.SIMPLIFICADA,
        "invoice_number": "T-2026-001",
        "issued_at": date(2026, 5, 3),
        "counterparty_name": "Cliente de mostrador",
        "counterparty_tax_id": None,
        "counterparty_country": "ES",
        "base_total": _BASE,
        "iva_total": _CUOTA,
        "grand_total": _BASE + _CUOTA,
        "currency": "EUR",
        "lines": (_line(),),
        "payment_status": PaymentStatus.PAID,
    }
    payload.update(overrides)
    return Invoice(**payload)  # type: ignore[arg-type]


def test_a_resident_taxpayer_is_established_in_the_tai() -> None:
    """The common case: a Spanish-resident autónomo is established."""
    assert issuer_established_in_tai(_profile(fiscal_residency=FiscalResidency.RESIDENT_IRPF)) is True


def test_undeclared_residency_defaults_to_established() -> None:
    """``None`` is treated as RESIDENT_IRPF, matching the field's own documented default."""
    assert issuer_established_in_tai(_profile(fiscal_residency=None)) is True


def test_a_non_resident_taxpayer_is_not_established_in_the_tai() -> None:
    """The one negative case this predicate models."""
    profile = _profile(
        fiscal_residency=FiscalResidency.NON_RESIDENT_IRNR,
        country_of_fiscal_residence="FR",
    )

    assert issuer_established_in_tai(profile) is False


def test_a_domestic_ticket_from_a_resident_issuer_needs_a_tax_id() -> None:
    """The truthful case 3.º scenario: domestic simplificada, established issuer."""
    invoice = _invoice()
    profile = _profile(fiscal_residency=FiscalResidency.RESIDENT_IRPF)

    assert simplificada_requires_tax_id_for_domestic_issuer(invoice, profile) is True


def test_a_domestic_ticket_from_a_non_resident_issuer_does_not_trigger_case_3() -> None:
    """A non-established issuer's domestic-looking ticket does not fall under case 3.º."""
    invoice = _invoice()
    profile = _profile(fiscal_residency=FiscalResidency.NON_RESIDENT_IRNR, country_of_fiscal_residence="FR")

    assert simplificada_requires_tax_id_for_domestic_issuer(invoice, profile) is False


def test_an_ordinaria_is_not_evaluated_under_case_3() -> None:
    """Ordinaria/rectificativa already require the tax id unconditionally; this predicate is simplificada-only."""
    invoice = _invoice(invoice_class=InvoiceClass.ORDINARIA, counterparty_tax_id="B12345674")
    profile = _profile(fiscal_residency=FiscalResidency.RESIDENT_IRPF)

    assert simplificada_requires_tax_id_for_domestic_issuer(invoice, profile) is False


def test_a_simplificada_that_already_carries_a_tax_id_has_nothing_further_to_ask() -> None:
    """A present tax id already satisfies the law; the predicate has nothing to add."""
    invoice = _invoice(counterparty_tax_id="B12345674")
    profile = _profile(fiscal_residency=FiscalResidency.RESIDENT_IRPF)

    assert simplificada_requires_tax_id_for_domestic_issuer(invoice, profile) is False


def test_a_foreign_simplificada_does_not_trigger_case_3() -> None:
    """Case 3.º is scoped to a domestic operation; a foreign counterparty is a different case."""
    invoice = _invoice(counterparty_country="DE")
    profile = _profile(fiscal_residency=FiscalResidency.RESIDENT_IRPF)

    assert simplificada_requires_tax_id_for_domestic_issuer(invoice, profile) is False
