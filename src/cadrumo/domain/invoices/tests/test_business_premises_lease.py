"""The business-premises lease facts an issued invoice carries for Modelo 347.

RD 1065/2007 art. 34.1.d has the lessor of a local de negocio relate the lease
apart, with "las referencias catastrales y los datos necesarios para la
localización de los inmuebles arrendados". The facts belong to the lessor's
issued invoice, the situación codes are the record design's four, and codes 3
("sin referencia catastral") and 4 (abroad) carry no Spanish referencia.
"""

from __future__ import annotations

from datetime import date
from decimal import Decimal

import pytest
from pydantic import ValidationError

from ...iva.classification import InvoiceKind
from ..enums import IvaRate, PaymentStatus
from ..errors import InvoiceValidationError
from ..models import Invoice, InvoiceLine, derive_invoice_id, require_situacion_inmueble

pytestmark = [pytest.mark.unit, pytest.mark.hex_domain, pytest.mark.usefixtures("operation")]


def _lease_invoice(kind: InvoiceKind = InvoiceKind.ISSUED, **facts: object) -> Invoice:
    base = Decimal("1000.00")
    iva = Decimal("210.00")
    issued_at = date(2025, 3, 1)
    return Invoice.model_validate(
        {
            "invoice_id": derive_invoice_id(
                kind=kind,
                invoice_number="ALQ-2025-03",
                issued_at=issued_at,
                counterparty_tax_id="B87654323",
                currency="EUR",
                grand_total=base + iva,
            ),
            "kind": kind,
            "invoice_number": "ALQ-2025-03",
            "issued_at": issued_at,
            "counterparty_name": "INQUILINO LOCAL SL",
            "counterparty_tax_id": "B87654323",
            "counterparty_country": "ES",
            "base_total": base,
            "iva_total": iva,
            "grand_total": base + iva,
            "currency": "EUR",
            "lines": (
                InvoiceLine(
                    description="Alquiler local",
                    quantity=Decimal("1"),
                    unit_price=base,
                    subtotal=base,
                    iva_rate=IvaRate.from_registry("RATE_21"),
                    iva_amount=iva,
                ),
            ),
            "payment_status": PaymentStatus.PAID,
            **facts,
        },
    )


def test_an_issued_lease_keeps_its_premises_facts_and_canonicalises_the_referencia() -> None:
    invoice = _lease_invoice(
        arrendamiento_local_negocio=True,
        situacion_inmueble="1",
        referencia_catastral=" 9872023vh5797s0001wx ",
    )

    assert invoice.arrendamiento_local_negocio is True
    assert invoice.situacion_inmueble == "1"
    assert invoice.referencia_catastral == "9872023VH5797S0001WX"


def test_a_lease_may_be_recorded_before_its_premises_are_known() -> None:
    invoice = _lease_invoice(arrendamiento_local_negocio=True)

    assert invoice.situacion_inmueble is None
    assert invoice.referencia_catastral is None


def test_an_invoice_without_a_lease_carries_no_premises_facts() -> None:
    assert _lease_invoice().arrendamiento_local_negocio is False

    with pytest.raises(ValidationError, match="arrendamiento_local_negocio"):
        _lease_invoice(situacion_inmueble="1", referencia_catastral="9872023VH5797S0001WX")


def test_the_lease_is_the_lessors_fact_and_refuses_a_received_invoice() -> None:
    with pytest.raises(ValidationError, match="issued invoice"):
        _lease_invoice(InvoiceKind.RECEIVED, arrendamiento_local_negocio=True, situacion_inmueble="3")


@pytest.mark.parametrize("situacion", ["3", "4"])
def test_a_situacion_without_a_spanish_referencia_refuses_one(situacion: str) -> None:
    with pytest.raises(ValidationError, match="cannot carry one"):
        _lease_invoice(
            arrendamiento_local_negocio=True,
            situacion_inmueble=situacion,
            referencia_catastral="9872023VH5797S0001WX",
        )


def test_the_referencia_is_bounded_by_the_record_designs_25_positions() -> None:
    with pytest.raises(ValidationError, match="at most 25 characters"):
        _lease_invoice(arrendamiento_local_negocio=True, situacion_inmueble="2", referencia_catastral="X" * 26)


def test_only_the_four_record_design_codes_are_a_situacion() -> None:
    assert [require_situacion_inmueble(code) for code in (" 1", "2", "3", "4 ")] == ["1", "2", "3", "4"]
    for typed in ("0", "5", "uno", ""):
        with pytest.raises(InvoiceValidationError, match="1, 2, 3 or 4"):
            require_situacion_inmueble(typed)
