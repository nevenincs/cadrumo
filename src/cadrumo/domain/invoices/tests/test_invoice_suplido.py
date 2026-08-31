"""The suplido contract on the invoice record.

LIVA art. 78.Tres.3.º excludes from the base imponible "las sumas pagadas en
nombre y por cuenta del cliente en virtud de mandato expreso del mismo" -- a
disbursement the issuer paid on the client's behalf under an explicit
mandate. Before this contract that sum had no representable position on the
invoice at all: it is not part of ``base_total`` (the law excludes it), not
part of ``iva_total`` (no cuota accrues on someone else's expense), yet the
client genuinely owes it, so it belongs in ``grand_total``. It is
:mod:`recargo`'s sibling on the identity, not a variant of it -- both join
``total``, but a suplido carries no statutory rate and is not restricted to a
taxable supply the way recargo is.
"""

from __future__ import annotations

from datetime import date
from decimal import Decimal
from typing import Any

import pytest
from pydantic import ValidationError

from ....adapters.outbound.fx.ecb_provider import ECB_RATE_SOURCE_ID
from ....domain.iva.classification import InvoiceKind
from ....domain.iva.schema import IvaCategory
from ..decomposition import decompose_invoice
from ..enums import IvaRate, PaymentStatus
from ..models import Invoice, InvoiceLine

pytestmark = [pytest.mark.unit, pytest.mark.hex_domain]

_BASE = Decimal("1000.00")
_CUOTA = Decimal("210.00")
_SUPLIDO = Decimal("60.00")
"""A notary/registro disbursement passed through unchanged (LIVA art. 78.Tres.3.º)."""


def _rated_line() -> InvoiceLine:
    return InvoiceLine(
        description="Gestión de constitución de sociedad",
        quantity=Decimal("1"),
        unit_price=_BASE,
        subtotal=_BASE,
        iva_rate=IvaRate.RATE_21,
        iva_amount=_CUOTA,
    )


def _exempt_line() -> InvoiceLine:
    return InvoiceLine(
        description="Servicio exento",
        quantity=Decimal("1"),
        unit_price=_BASE,
        subtotal=_BASE,
        iva_rate=IvaRate.EXEMPT,
        iva_amount=Decimal("0"),
    )


def _invoice(**overrides: Any) -> Invoice:
    payload: dict[str, Any] = {
        "kind": InvoiceKind.ISSUED,
        "invoice_number": "2026/SU-1",
        "issued_at": date(2026, 3, 15),
        "counterparty_name": "Cliente SL",
        "counterparty_tax_id": "B12345674",
        "counterparty_country": "ES",
        "base_total": _BASE,
        "iva_total": _CUOTA,
        "grand_total": _BASE + _CUOTA + _SUPLIDO,
        "currency": "EUR",
        "lines": (_rated_line(),),
        "payment_status": PaymentStatus.PAID,
        "suplido_amount": _SUPLIDO,
    }
    payload.update(overrides)
    return Invoice(**payload)  # type: ignore[arg-type]


def test_a_gestor_can_record_a_disbursement_paid_on_the_clients_behalf() -> None:
    """The truthful suplido invoice is representable, and its total carries the disbursement."""
    invoice = _invoice()

    assert invoice.suplido_amount == _SUPLIDO
    assert invoice.grand_total == Decimal("1270.00")
    assert invoice.grand_total == invoice.base_total + invoice.iva_total + _SUPLIDO


def test_dropping_the_suplido_from_the_total_is_refused() -> None:
    """The falsified document -- disbursed but not totalled -- must not pass.

    Mirrors the recargo defect this identity was extended for: an invoice
    stating a suplido whose total does not include it understates what the
    client owes by exactly the passed-through amount.
    """
    with pytest.raises(
        ValidationError,
        match=r"grand_total must equal base_total \+ iva_total \+ recargo_amount \+ suplido_amount",
    ):
        _invoice(grand_total=_BASE + _CUOTA)


def test_an_ordinary_invoice_declares_no_suplido_and_an_explicit_zero_is_a_different_statement() -> None:
    """Unrecorded and none-arose stay distinguishable, for the same reason recargo keeps them apart."""
    silent = _invoice(suplido_amount=None, grand_total=_BASE + _CUOTA)
    declared_zero = _invoice(suplido_amount=Decimal("0"), grand_total=_BASE + _CUOTA)

    assert silent.suplido_amount is None
    assert declared_zero.suplido_amount == Decimal("0")
    assert silent.suplido_amount != declared_zero.suplido_amount
    assert silent.grand_total == declared_zero.grand_total


def test_a_negative_suplido_is_refused() -> None:
    """A disbursement that reduces the total is not a disbursement."""
    with pytest.raises(ValidationError, match="suplido_amount must be non-negative"):
        _invoice(suplido_amount=Decimal("-60.00"), grand_total=_BASE + _CUOTA - _SUPLIDO)


def test_a_suplido_may_exceed_the_cuota_unlike_recargo() -> None:
    """No statutory rate bounds a suplido: it is an arbitrary third-party disbursement."""
    large = Decimal("5000.00")
    invoice = _invoice(suplido_amount=large, grand_total=_BASE + _CUOTA + large)

    assert invoice.suplido_amount == large


def test_a_suplido_may_accompany_an_exempt_supply() -> None:
    """Unlike recargo, a suplido is not restricted to a taxable supply."""
    invoice = _invoice(
        lines=(_exempt_line(),),
        iva_total=Decimal("0"),
        grand_total=_BASE + _SUPLIDO,
    )

    assert invoice.suplido_amount == _SUPLIDO
    assert invoice.grand_total == _BASE + _SUPLIDO


def test_the_decomposition_carries_the_suplido_into_the_contraprestacion() -> None:
    """A grounded suplido invoice decomposes with the disbursement inside ``total``."""
    verdict = decompose_invoice(_invoice(iva_category=IvaCategory.DOMESTIC_GENERAL))

    assert verdict.is_grounded
    components = verdict.components
    assert components is not None
    assert components.suplido == _SUPLIDO
    assert components.total == Decimal("1270.00")
    assert components.cash == Decimal("1270.00")


def test_suplido_and_retencion_sit_on_opposite_sides_like_recargo_does() -> None:
    """The suplido joins ``total`` and, through it, ``cash``; retención comes off ``cash`` only."""
    retencion = Decimal("150.00")
    verdict = decompose_invoice(
        _invoice(iva_category=IvaCategory.DOMESTIC_GENERAL, retention_amount=retencion),
    )

    components = verdict.components
    assert components is not None
    assert components.total == _BASE + _CUOTA + _SUPLIDO
    assert components.cash == components.total - retencion
    assert components.cash == Decimal("1120.00")


def test_recargo_and_suplido_both_join_the_total_independently() -> None:
    """Both third-position terms accumulate rather than colliding on one slot."""
    recargo = Decimal("52.00")
    verdict = decompose_invoice(
        _invoice(
            iva_category=IvaCategory.DOMESTIC_GENERAL,
            recargo_amount=recargo,
            grand_total=_BASE + _CUOTA + recargo + _SUPLIDO,
        ),
    )

    components = verdict.components
    assert components is not None
    assert components.recargo == recargo
    assert components.suplido == _SUPLIDO
    assert components.total == _BASE + _CUOTA + recargo + _SUPLIDO


def test_the_suplido_converts_to_euro_with_the_rest_of_the_invoice() -> None:
    """A foreign-currency suplido is converted, not passed through as face value."""
    invoice = _invoice(
        currency="USD",
        fx_rate=Decimal("0.90"),
        fx_rate_date=date(2026, 3, 15),
        fx_rate_source=ECB_RATE_SOURCE_ID,
    )

    assert invoice.suplido_amount_eur == Decimal("54.00")


def test_an_unconverted_foreign_suplido_reports_no_euro_figure() -> None:
    """Without a resolved rate the euro value is unknown rather than the face value."""
    invoice = _invoice(currency="USD")

    assert invoice.suplido_amount is not None
    assert invoice.suplido_amount_eur is None
