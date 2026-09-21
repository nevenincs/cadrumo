"""Narrow hard-cut contracts for invoice-backed withholding CLI capture."""

from __future__ import annotations

from datetime import date
from decimal import Decimal

import pytest
from pydantic import ValidationError

from ....application.aggregation.invoice_retencion import (
    InvoiceWithholdingEvidenceRequest,
    build_invoice_withholding_capture,
)
from ....application.aggregation.withholding_recognition import (
    WithholdingIncomeKind,
    WithholdingRecipientTaxRegime,
    WithholdingRecipientTaxStatus,
)
from ....core.aggregation import RetencionClave
from ....domain.calculations.registry.withholding_bindings import WithholdingObservation
from ....domain.invoices.enums import IvaRate, PaymentStatus, iva_rate_percentage
from ....domain.invoices.models import Invoice, InvoiceLine
from ....domain.iva.classification import InvoiceKind
from ....domain.iva.schema import IvaCategory

pytestmark = [pytest.mark.unit, pytest.mark.hex_entrypoint, pytest.mark.usefixtures("authority_operation")]


def _invoice() -> Invoice:
    base = Decimal("1000.00")
    rate = iva_rate_percentage(IvaRate.from_registry("RATE_21"), date(2025, 3, 31))
    assert rate is not None
    line = InvoiceLine(
        description="Professional services",
        quantity=Decimal("1"),
        unit_price=base,
        subtotal=base,
        iva_rate=IvaRate.from_registry("RATE_21"),
        iva_amount=base * rate,
    )
    return Invoice.model_validate(
        {
            "bucket_id": "00000000-0000-4000-8000-000000000452",
            "kind": InvoiceKind.RECEIVED,
            "invoice_number": "CLI-WITHHOLDING-001",
            "issued_at": date(2025, 3, 31),
            "counterparty_name": "Resident professional SL",
            "counterparty_tax_id": "B12345674",
            "counterparty_country": "ES",
            "base_total": base,
            "iva_total": line.iva_amount,
            "grand_total": base + line.iva_amount,
            "currency": "EUR",
            "lines": (line,),
            "payment_status": PaymentStatus.PAID,
            "iva_category": IvaCategory("domestic_general"),
            "retention_rate": Decimal("0.19"),
            "retention_amount": Decimal("190.00"),
        }
    )


def _request(invoice: Invoice) -> InvoiceWithholdingEvidenceRequest:
    return InvoiceWithholdingEvidenceRequest.model_validate(
        {
            "invoice_id": invoice.invoice_id,
            "income_kind": WithholdingIncomeKind.PROFESSIONAL,
            "scheme": "actividades_profesionales",
            "recipient_tax_status": WithholdingRecipientTaxStatus.RESIDENT,
            "recipient_tax_regime": WithholdingRecipientTaxRegime.IRPF,
            "payment_event_id": "payment-q2",
            "payment_occurred_on": date(2025, 4, 2),
            "allocation_id": "allocation-q2",
            "allocated_base": Decimal("500.00"),
            "allocated_withholding": Decimal("95.00"),
            "allocated_settlement": Decimal("510.00"),
            "idempotency_key": "cli-payment-q2",
            "modelo_190_detail": _annual_detail(invoice),
        }
    )


def _annual_detail(invoice: Invoice) -> WithholdingObservation:
    return WithholdingObservation(
        source_id=invoice.invoice_id,
        perceptor_tax_id=invoice.counterparty_tax_id or "",
        perceptor_legal_name=invoice.counterparty_name,
        transaction_date=date(2025, 4, 2),
        clave=RetencionClave.from_registry("G"),
        percibido_dinerario=Decimal("500.00"),
        retencion_practicada=Decimal("95.00"),
        incapacity_cash_perception=Decimal("0"),
        incapacity_cash_withholding=Decimal("0"),
        incapacity_kind_value=Decimal("0"),
        incapacity_kind_ingreso_a_cuenta=Decimal("0"),
        incapacity_kind_repercutido=Decimal("0"),
        foral_retention_estatal=Decimal("0"),
        foral_retention_navarra=Decimal("0"),
        foral_retention_araba=Decimal("0"),
        foral_retention_gipuzkoa=Decimal("0"),
        foral_retention_bizkaia=Decimal("0"),
        base_retenciones=Decimal("500.00"),
        porcentaje_retencion=Decimal("19"),
    )


def test_invoice_liability_revision_is_stable_across_unrelated_catalogue_revisions() -> None:
    """A different invoice write cannot consume or strand this invoice's capacity."""
    invoice = _invoice()
    first = build_invoice_withholding_capture(
        invoice,
        catalogue_revision_id="a" * 64,
        request=_request(invoice),
        applicable_year=2025,
    )
    later = build_invoice_withholding_capture(
        invoice,
        catalogue_revision_id="b" * 64,
        request=_request(invoice),
        applicable_year=2025,
    )

    assert first.catalogue_read_revision_id != later.catalogue_read_revision_id
    assert first.command.source_revision_id == later.command.source_revision_id
    assert first.command.liability_snapshot.source_revision_id == first.command.source_revision_id


def test_cli_evidence_shape_refuses_a_caller_authored_recognition_date() -> None:
    """The transport accepts dated events, never a derived filing coordinate."""
    invoice = _invoice()
    payload = _request(invoice).model_dump(mode="json") | {"recognized_on": "2025-04-02"}

    with pytest.raises(ValidationError, match="recognized_on"):
        InvoiceWithholdingEvidenceRequest.model_validate(payload)


def test_modelo_aggregate_module_no_longer_exposes_direct_retencion_persistence() -> None:
    """The 111/115 CLI module has no direct set-replace mutation helper."""
    from .. import _modelo_aggregate_cli

    assert not hasattr(_modelo_aggregate_cli, "_persist_retencion_observations")
    assert not hasattr(_modelo_aggregate_cli, "_persist_cli_owned_observations")


def test_rent_cli_evidence_refuses_missing_property_detail() -> None:
    """Public rent capture cannot create periodic evidence that strands Modelo 180."""
    invoice = _invoice()
    request = _request(invoice).model_copy(
        update={
            "income_kind": WithholdingIncomeKind.URBAN_RENT,
            "scheme": "arrendamiento_urbano",
        }
    )

    with pytest.raises(ValidationError, match="urban rent requires Modelo 180 property detail"):
        build_invoice_withholding_capture(
            invoice,
            catalogue_revision_id="a" * 64,
            request=request,
            applicable_year=2025,
        )


def test_professional_cli_evidence_refuses_missing_modelo_190_detail() -> None:
    """Public 111 evidence cannot leave a totals-only annual Modelo 190 row."""
    invoice = _invoice()
    request = _request(invoice).model_copy(update={"modelo_190_detail": None})

    with pytest.raises(ValidationError, match="Modelo 190 annual detail"):
        build_invoice_withholding_capture(
            invoice,
            catalogue_revision_id="a" * 64,
            request=request,
            applicable_year=2025,
        )
