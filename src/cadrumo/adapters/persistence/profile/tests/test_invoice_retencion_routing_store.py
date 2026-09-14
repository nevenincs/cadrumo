"""Assembled encrypted-store checks for invoice retención routing."""

from __future__ import annotations

from datetime import date
from decimal import Decimal
from pathlib import Path

import pytest

from cadrumo.adapters.persistence.profile.retencion_observations import RetencionObservationRepositoryAdapter
from cadrumo.adapters.persistence.storage.tests.secure_sql import isolated_runtime_profile
from cadrumo.application.aggregation.invoice_retencion import (
    InvoiceRetencionProjectionDefect,
    route_invoice_retenciones,
)
from cadrumo.application.aggregation.retencion_observations_repository import (
    RetencionObservationPorts,
    persist_retencion_observations,
)
from cadrumo.core.aggregation import BindingSourceKind, RetencionScheme
from cadrumo.core.period import Period
from cadrumo.domain.invoices.enums import IvaRate, PaymentStatus, iva_rate_percentage
from cadrumo.domain.invoices.models import Invoice, InvoiceLine
from cadrumo.domain.iva.classification import InvoiceKind
from cadrumo.domain.iva.schema import IvaCategory

pytestmark = [pytest.mark.unit, pytest.mark.hex_persistence_adapter]

_PROFESIONAL = RetencionScheme("actividades_profesionales")


def _invoice(
    *,
    kind: InvoiceKind = InvoiceKind.RECEIVED,
    number: str = "F-PROV-001",
    base: str = "1000.00",
    retention_amount: str | None = "150.00",
    retention_rate: str | None = "0.15",
) -> Invoice:
    subtotal = Decimal(base)
    rate = iva_rate_percentage(IvaRate.RATE_21, date(2026, 1, 1))
    assert rate is not None
    line = InvoiceLine(
        description="Servicios profesionales",
        quantity=Decimal("1"),
        unit_price=subtotal,
        subtotal=subtotal,
        iva_rate=IvaRate.RATE_21,
        iva_amount=subtotal * rate,
    )
    return Invoice.model_validate(
        {
            "kind": kind,
            "invoice_number": number,
            "issued_at": date(2026, 3, 15),
            "counterparty_name": "Asesoría Profesional SL",
            "counterparty_tax_id": "B12345674",
            "counterparty_country": "ES",
            "base_total": subtotal,
            "iva_total": line.iva_amount,
            "grand_total": subtotal + line.iva_amount,
            "currency": "EUR",
            "lines": (line,),
            "payment_status": PaymentStatus.PAID,
            "iva_category": IvaCategory.DOMESTIC_GENERAL,
            "retention_rate": None if retention_rate is None else Decimal(retention_rate),
            "retention_amount": None if retention_amount is None else Decimal(retention_amount),
        },
    )


def test_routed_retencion_lands_in_the_existing_encrypted_store(tmp_path: Path) -> None:
    """A received invoice reaches the one per-perceptor store and reads back."""
    period = Period.from_year_and_code(2026, "1T")
    routing = route_invoice_retenciones(((_invoice(), _PROFESIONAL),))

    with isolated_runtime_profile(tmp_path=tmp_path) as profile:
        repository = RetencionObservationRepositoryAdapter(objects=profile.repository)
        persist_retencion_observations(
            ports=RetencionObservationPorts(repository=repository),
            modelo="111",
            filing_year=period.filing_year,
            period=period,
            observations=routing.observations,
        )
        stored = repository.load_observations("111", period)

    assert len(stored) == 1
    assert stored[0].retencion_amount == Decimal("150.00")
    assert stored[0].taxable_base == Decimal("1000.00")
    assert stored[0].source_kind is BindingSourceKind.PAYABLE_INVOICE
    assert stored[0].scheme is _PROFESIONAL


def test_an_excluded_invoice_leaves_the_store_empty(tmp_path: Path) -> None:
    """An issued invoice contributes no stored retención liability."""
    period = Period.from_year_and_code(2026, "1T")
    routing = route_invoice_retenciones(((_invoice(kind=InvoiceKind.ISSUED), _PROFESIONAL),))

    with isolated_runtime_profile(tmp_path=tmp_path) as profile:
        repository = RetencionObservationRepositoryAdapter(objects=profile.repository)
        persist_retencion_observations(
            ports=RetencionObservationPorts(repository=repository),
            modelo="111",
            filing_year=period.filing_year,
            period=period,
            observations=routing.observations,
        )
        stored = repository.load_observations("111", period)

    assert routing.observations == ()
    assert stored == ()
    assert routing.excluded[0].defects == (InvoiceRetencionProjectionDefect.NOT_A_RETENEDOR_LIABILITY,)

