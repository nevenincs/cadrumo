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
from ..business_premises import (
    BusinessPremisesLease,
    SituacionInmueble,
    business_premises_lease_from_inputs,
    require_situacion_inmueble,
)
from ..enums import IvaRate, PaymentStatus
from ..errors import InvoiceValidationError
from ..models import Invoice, InvoiceLine, derive_invoice_id

pytestmark = [pytest.mark.unit, pytest.mark.hex_domain, pytest.mark.usefixtures("operation")]


def _lease_invoice(
    kind: InvoiceKind = InvoiceKind.ISSUED,
    business_premises_lease: BusinessPremisesLease | None = None,
) -> Invoice:
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
            "business_premises_lease": business_premises_lease,
        },
    )


def test_an_issued_lease_keeps_its_premises_facts_and_canonicalises_the_referencia() -> None:
    invoice = _lease_invoice(
        business_premises_lease=BusinessPremisesLease(
            situacion_inmueble=SituacionInmueble.SPAIN_OTHER_THAN_BASQUE_NAVARRE,
            referencia_catastral=" 9872023vh5797s0001wx ",
        ),
    )

    assert invoice.business_premises_lease is not None
    assert invoice.business_premises_lease.situacion_inmueble == "1"
    assert invoice.business_premises_lease.referencia_catastral == "9872023VH5797S0001WX"
    assert invoice.invoice_id == derive_invoice_id(
        kind=invoice.kind,
        invoice_number=invoice.invoice_number,
        issued_at=invoice.issued_at,
        counterparty_tax_id=invoice.counterparty_tax_id,
        currency=invoice.currency,
        grand_total=invoice.grand_total,
    )


def test_a_lease_may_be_recorded_before_its_premises_are_known() -> None:
    invoice = _lease_invoice(business_premises_lease=BusinessPremisesLease())

    assert invoice.business_premises_lease == BusinessPremisesLease()


def test_a_captured_reference_does_not_invent_a_missing_situation() -> None:
    lease = BusinessPremisesLease(referencia_catastral="9872023VH5797S0001WX")

    assert lease.situacion_inmueble is None
    assert lease.referencia_catastral == "9872023VH5797S0001WX"


def test_an_invoice_without_a_lease_carries_no_premises_facts() -> None:
    assert _lease_invoice().business_premises_lease is None
    with pytest.raises(ValidationError):
        BusinessPremisesLease.model_validate({"arrendamiento_local_negocio": True})

    with pytest.raises(InvoiceValidationError, match="require the business-premises lease choice"):
        business_premises_lease_from_inputs(
            lease_selected=False,
            situacion_inmueble="1",
            referencia_catastral="9872023VH5797S0001WX",
        )


def test_the_lease_is_the_lessors_fact_and_refuses_a_received_invoice() -> None:
    with pytest.raises(ValidationError, match="issued invoice"):
        _lease_invoice(
            InvoiceKind.RECEIVED,
            business_premises_lease=BusinessPremisesLease(
                situacion_inmueble=SituacionInmueble.SPAIN_WITHOUT_CATASTRAL_REFERENCE,
            ),
        )


@pytest.mark.parametrize("situacion", ["3", "4"])
def test_a_situacion_without_a_spanish_referencia_refuses_one(situacion: str) -> None:
    with pytest.raises(ValidationError, match="cannot carry one"):
        BusinessPremisesLease.model_validate(
            {
                "situacion_inmueble": situacion,
                "referencia_catastral": "9872023VH5797S0001WX",
            }
        )


def test_the_referencia_is_bounded_by_the_record_designs_25_positions() -> None:
    with pytest.raises(ValidationError, match="at most 25 characters"):
        BusinessPremisesLease.model_validate(
            {
                "situacion_inmueble": SituacionInmueble.BASQUE_COUNTRY_OR_NAVARRE,
                "referencia_catastral": "X" * 26,
            }
        )


def test_only_the_four_record_design_codes_are_a_situacion() -> None:
    assert [require_situacion_inmueble(code) for code in (" 1", "2", "3", "4 ")] == ["1", "2", "3", "4"]
    for typed in ("0", "5", "uno", ""):
        with pytest.raises(InvoiceValidationError, match="1, 2, 3 or 4"):
            require_situacion_inmueble(typed)


@pytest.mark.parametrize("selected", [False, True])
def test_historical_flat_invoice_facts_hydrate_only_the_nested_family(selected: bool) -> None:
    payload = _lease_invoice().model_dump(mode="python")
    payload.pop("business_premises_lease")
    payload.update(
        arrendamiento_local_negocio=selected,
        situacion_inmueble="1" if selected else None,
        referencia_catastral=" 9872023vh5797s0001wx " if selected else None,
    )

    loaded = Invoice.model_validate(payload)

    expected = (
        BusinessPremisesLease(
            situacion_inmueble=SituacionInmueble.SPAIN_OTHER_THAN_BASQUE_NAVARRE,
            referencia_catastral="9872023VH5797S0001WX",
        )
        if selected
        else None
    )
    assert loaded.business_premises_lease == expected
    assert loaded.invoice_id == payload["invoice_id"]
    assert (
        not {"arrendamiento_local_negocio", "situacion_inmueble", "referencia_catastral"} & loaded.model_dump().keys()
    )


def test_historical_and_nested_invoice_lease_facts_cannot_disagree() -> None:
    payload = _lease_invoice(business_premises_lease=BusinessPremisesLease()).model_dump(mode="python")
    payload["arrendamiento_local_negocio"] = False

    with pytest.raises(ValidationError, match="facts disagree"):
        Invoice.model_validate(payload)


@pytest.mark.parametrize(
    "legacy",
    [
        {"arrendamiento_local_negocio": "false"},
        {"arrendamiento_local_negocio": False, "situacion_inmueble": "1"},
        {"arrendamiento_local_negocio": True, "situacion_inmueble": "5"},
        {"arrendamiento_local_negocio": True, "situacion_inmueble": "3", "referencia_catastral": "REF"},
    ],
)
def test_historical_invoice_lease_hydration_preserves_validation(legacy: dict[str, object]) -> None:
    payload = _lease_invoice().model_dump(mode="python")
    payload.pop("business_premises_lease")
    payload.update(legacy)

    with pytest.raises(ValidationError):
        Invoice.model_validate(payload)
