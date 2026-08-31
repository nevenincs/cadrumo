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
from typing import Any

import pytest

from ....domain.deadlines.models import FiscalResidency, IVARegime, TaxpayerProfile
from ....domain.invoices.enums import InvoiceClass, IvaRate, PaymentStatus
from ....domain.invoices.models import Invoice, InvoiceLine
from ....domain.iva.classification import InvoiceKind
from ..issuer_establishment import issuer_established_in_tai, simplificada_requires_tax_id_for_domestic_issuer

pytestmark = [pytest.mark.unit, pytest.mark.hex_application]

_BASE = Decimal("40.00")
_CUOTA = Decimal("8.40")


def _profile(**overrides: Any) -> TaxpayerProfile:
    payload: dict[str, Any] = {"tax_id": "12345678Z", "iva_regime": IVARegime.GENERAL}
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


def _invoice(**overrides: Any) -> Invoice:
    payload: dict[str, Any] = {
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


def test_a_received_invoice_with_a_tax_id_does_not_trigger_case_3() -> None:
    """The reachable RECEIVED case: a present tax id already answers everything case 3.º could ask."""
    invoice = _invoice(kind=InvoiceKind.RECEIVED, counterparty_tax_id="B12345674")
    profile = _profile(fiscal_residency=FiscalResidency.RESIDENT_IRPF)

    assert simplificada_requires_tax_id_for_domestic_issuer(invoice, profile) is False


def test_the_kind_guard_holds_even_for_a_shape_invoice_itself_already_refuses() -> None:
    """Proves the ``kind`` check on its own terms, not merely as an artefact of another guard.

    A tax-id-less RECEIVED SIMPLIFICADA cannot be built through ``Invoice``'s
    normal construction path -- its own class-consistency validator already
    refuses that combination (see ``test_invoice_simplificada.py``), which
    means ``counterparty_tax_id is None`` alone already implies ``kind is
    ISSUED`` for every real ``Invoice``. That makes this predicate's ``kind``
    check currently unreachable through valid data: a test built only from
    real invoices could see it deleted and stay green, exactly the class of
    silent, never-fired guard that real-behaviour cases keep exposing.

    ``model_copy(update=...)`` bypasses pydantic validation (unlike
    reconstructing via ``Invoice(...)``), so it can force the
    otherwise-unreachable combination onto an already-valid model without
    touching any other field. This is testing the FUNCTION's own contract in
    isolation, independent of whether ``Invoice`` will always guarantee the
    combination cannot occur.
    """
    invoice = _invoice(kind=InvoiceKind.RECEIVED, counterparty_tax_id="B12345674").model_copy(
        update={"counterparty_tax_id": None},
    )
    profile = _profile(fiscal_residency=FiscalResidency.RESIDENT_IRPF)

    assert simplificada_requires_tax_id_for_domestic_issuer(invoice, profile) is False


def test_a_canarias_or_ceuta_melilla_resident_is_a_pinned_known_limitation() -> None:
    """PINNED KNOWN-WRONG BEHAVIOUR, over-strict and therefore the safer of the two mistakes.

    ``TaxpayerProfile`` has no field distinguishing a Canarias- or
    Ceuta/Melilla-resident taxpayer (IGIC/IPSI territory, outside the LIVA
    TAI) from a mainland one, so ``fiscal_residency == RESIDENT_IRPF`` reads
    ``True`` for both even though only the mainland taxpayer is genuinely
    established in the TAI. This predicate therefore WRONGLY reports
    "established" for a Canarias/Ceuta/Melilla issuer and so wrongly demands
    a counterparty NIF the law does not actually require there -- never the
    reverse.

    This test pins that CURRENT behaviour deliberately, using the only
    profile shape this codebase can construct for such a taxpayer today
    (there is no way to declare "resident, but in Canarias" on
    ``TaxpayerProfile``). It must fail, on purpose, the day a territorial-
    scope fact is added to the profile and this predicate is updated to read
    it for a genuinely Canarias/Ceuta/Melilla-flagged profile: that failure
    is the reminder pointing at exactly what to fix.
    """
    profile = _profile(fiscal_residency=FiscalResidency.RESIDENT_IRPF)

    assert issuer_established_in_tai(profile) is True  # wrong for a Canarias/Ceuta/Melilla resident; see docstring
