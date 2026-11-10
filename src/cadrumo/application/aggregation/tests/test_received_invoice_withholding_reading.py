"""Each refusal and allocation route of reading a received invoice's stated retención."""

from __future__ import annotations

from datetime import date
from decimal import Decimal

import pytest

from cadrumo.domain.calculations.registry.tests.authored_editions import filing_year_envelope
from cadrumo.domain.invoices.tests.catalogue_support import build_invoice_catalogue

from ....core.aggregation import RetencionScheme
from ....core.period import Period
from ....domain.invoices.models import Invoice
from ....domain.transactions.models import Transaction, TransactionCatalogue
from ..received_invoice_withholding import (
    ReceivedInvoiceWithholding,
    ReceivedInvoiceWithholdingFindingKind,
    received_invoice_withholding,
)
from .received_invoice_withholding_support import (
    NATURAL_PERSON_PROFESSIONAL_NIF,
    PROFESSIONAL_COMPANY_NIF,
    paying_movement,
    received_invoice,
)

pytestmark = [pytest.mark.unit, pytest.mark.hex_application, pytest.mark.usefixtures("operation")]

BUCKET = "bbbbbbbb-bbbb-4bbb-8bbb-bbbbbbbbbbbb"
_YEAR = filing_year_envelope().horizon
_Q1 = Period.from_year_and_code(_YEAR, "1T")
_KIND = ReceivedInvoiceWithholdingFindingKind


def _invoice(
    *,
    tax_id: str = NATURAL_PERSON_PROFESSIONAL_NIF,
    currency: str = "EUR",
    country: str = "ES",
    base: str = "300.00",
    retencion: str = "45.00",
    rate: str = "0.15",
    linked: tuple[str, ...] = (),
) -> Invoice:
    invoice = received_invoice(
        "R-001",
        date(_YEAR, 2, 3),
        supplier="Proveedor Ejemplo",
        tax_id=NATURAL_PERSON_PROFESSIONAL_NIF,
        base=Decimal(base),
        retencion=Decimal(retencion),
        rate=Decimal(rate),
        linked=linked,
        bucket_id=BUCKET,
    )
    return invoice.model_copy(
        update={"counterparty_country": country, "counterparty_tax_id": tax_id, "currency": currency}
    )


def _payment(provider_id: str, day: int, *, cash: str, category: str | None = "actividad_economica") -> Transaction:
    return paying_movement(provider_id, date(_YEAR, 2, day), cash=Decimal(cash), irpf_category=category)


def _read(invoice: Invoice, *payments: Transaction, modelo: str = "111") -> ReceivedInvoiceWithholding:
    linked = invoice.model_copy(update={"linked_transaction_ids": tuple(p.transaction_id for p in payments)})
    return received_invoice_withholding(
        build_invoice_catalogue((linked,)),
        TransactionCatalogue.from_transactions(payments),
        bucket_id=BUCKET,
        modelo=modelo,
        period=_Q1,
    )


def _kinds(read: ReceivedInvoiceWithholding) -> list[_KIND]:
    return [finding.kind for finding in read.findings]


def test_a_non_resident_supplier_is_a_finding_for_the_modelo_its_payment_kind_reaches() -> None:
    read = _read(_invoice(country="FR"), _payment("P1", 10, cash="318.00"))

    assert read.observations == ()
    assert _kinds(read) == [_KIND.NON_RESIDENT]
    assert read.findings[0].modelo == "111"


def test_a_non_resident_supplier_paid_for_another_modelo_raises_nothing_here() -> None:
    read = _read(_invoice(country="FR"), _payment("P1", 10, cash="318.00"), modelo="115")

    assert read == ReceivedInvoiceWithholding(observations=(), findings=())


def test_a_non_resident_supplier_with_no_payment_is_a_finding_of_unknown_modelo() -> None:
    read = _read(_invoice(country="FR"))

    assert _kinds(read) == [_KIND.NON_RESIDENT]
    assert read.findings[0].modelo is None


def test_an_invoice_in_a_foreign_currency_without_a_rate_is_incomplete() -> None:
    read = _read(_invoice(currency="USD"), _payment("P1", 10, cash="318.00"))

    assert _kinds(read) == [_KIND.INVOICE_INCOMPLETE]
    assert read.findings[0].modelo == "111"


def test_an_unpaid_irpf_supplier_invoice_is_simply_not_yet_due() -> None:
    assert _read(_invoice()) == ReceivedInvoiceWithholding(observations=(), findings=())


def test_a_payment_of_mixed_income_kinds_leaves_the_kind_undeclared() -> None:
    read = _read(
        _invoice(),
        _payment("P1", 10, cash="100.00"),
        _payment("P2", 11, cash="218.00", category="arrendamiento_local"),
    )

    assert _kinds(read) == [_KIND.INCOME_KIND_UNDECLARED]
    assert read.findings[0].modelo is None


def test_an_unclassified_payment_is_undeclared_for_whichever_modelo_is_asked() -> None:
    read = _read(_invoice(), _payment("P1", 10, cash="318.00", category=None), modelo="115")

    assert _kinds(read) == [_KIND.INCOME_KIND_UNDECLARED]


def test_a_nif_the_registry_does_not_place_leaves_the_recipient_unknown() -> None:
    read = _read(_invoice(tax_id="G12345678"), _payment("P1", 10, cash="318.00"))

    assert _kinds(read) == [_KIND.RECIPIENT_UNKNOWN]
    assert read.findings[0].modelo == "111"


def test_a_retencion_matching_no_activity_rate_is_unrecognised() -> None:
    read = _read(_invoice(retencion="47.13", rate="0.1571"), _payment("P1", 10, cash="318.00"))

    assert _kinds(read) == [_KIND.RATE_UNRECOGNISED]
    assert read.findings[0].modelo == "111"


def test_a_resident_professional_paid_whole_gives_one_observation_for_modelo_111() -> None:
    read = _read(_invoice(), _payment("P1", 10, cash="318.00"))

    assert read.findings == ()
    assert [
        (o.scheme, o.taxable_base, o.retencion_amount, o.accrued_on, o.perceptor_nif) for o in read.observations
    ] == [
        (
            RetencionScheme("actividades_profesionales"),
            Decimal("300.00"),
            Decimal("45.00"),
            date(_YEAR, 2, 10).isoformat(),
            NATURAL_PERSON_PROFESSIONAL_NIF,
        )
    ]


def test_the_same_invoice_is_nothing_to_modelo_115() -> None:
    read = _read(_invoice(), _payment("P1", 10, cash="318.00"), modelo="115")

    assert read == ReceivedInvoiceWithholding(observations=(), findings=())


def test_part_payments_split_the_base_and_retencion_so_the_cents_add_up() -> None:
    read = _read(_invoice(), _payment("P1", 10, cash="100.00"), _payment("P2", 20, cash="218.00"))

    assert read.findings == ()
    assert [(o.accrued_on, o.taxable_base, o.retencion_amount) for o in read.observations] == [
        (date(_YEAR, 2, 10).isoformat(), Decimal("94.34"), Decimal("14.15")),
        (date(_YEAR, 2, 20).isoformat(), Decimal("205.66"), Decimal("30.85")),
    ]


def test_an_is_suppliers_rent_is_recognised_whole_when_first_paid() -> None:
    invoice = _invoice(tax_id=PROFESSIONAL_COMPANY_NIF, base="1500.00", retencion="285.00", rate="0.19")

    read = _read(invoice, _payment("P1", 10, cash="1530.00", category="arrendamiento_local"), modelo="115")

    assert read.findings == ()
    assert [(o.scheme, o.taxable_base, o.retencion_amount) for o in read.observations] == [
        (RetencionScheme("arrendamiento_urbano"), Decimal("1500.00"), Decimal("285.00"))
    ]
