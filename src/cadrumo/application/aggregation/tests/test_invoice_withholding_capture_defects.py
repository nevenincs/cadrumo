"""Invoice withholding capture refuses through the one projection, naming every defect.

The capture builder and the store projection answer the same question -- does
this invoice carry a retención the taxpayer owes as retenedor? -- so the
capture asks the projection rather than a first-defect copy of it. An operator
fixing a record must see everything wrong with it in one refusal, as a stable
token list for machines and as a localized explanation per defect for people.
"""

from __future__ import annotations

from datetime import date
from decimal import Decimal

import pytest

from ....core.config import override_settings
from ....core.errors.error_codes import build_error_envelope
from ....domain.invoices.enums import IvaRate, PaymentStatus, iva_rate_percentage
from ....domain.invoices.models import Invoice, InvoiceLine
from ....domain.iva.classification import InvoiceKind
from ....domain.iva.schema import IvaCategory
from ..invoice_retencion import (
    InvoiceRetencionProjectionDefect,
    InvoiceWithholdingDefectsError,
    InvoiceWithholdingEvidenceError,
    InvoiceWithholdingEvidenceRequest,
    build_invoice_withholding_capture,
    project_received_invoice_retencion,
)
from ..withholding_recognition import (
    WithholdingIncomeKind,
    WithholdingRecipientTaxRegime,
    WithholdingRecipientTaxStatus,
)
from .withholding_filer_profile_support import quarterly_filer_cadence

pytestmark = [pytest.mark.unit, pytest.mark.hex_application, pytest.mark.usefixtures("operation")]

_LANGUAGES = ("en", "es", "ca", "hu")


def _invoice(
    *,
    kind: InvoiceKind = InvoiceKind.RECEIVED,
    country: str = "ES",
    tax_id: str = "B12345674",
    retention_amount: str | None = "190.00",
    retention_rate: str | None = "0.19",
) -> Invoice:
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
            "bucket_id": "00000000-0000-4000-8000-000000000455",
            "kind": kind,
            "invoice_number": "CAPTURE-DEFECTS-001",
            "issued_at": date(2025, 3, 31),
            "counterparty_name": "Resident professional SL",
            "counterparty_tax_id": tax_id,
            "counterparty_country": country,
            "base_total": base,
            "iva_total": line.iva_amount,
            "grand_total": base + line.iva_amount,
            "currency": "EUR",
            "lines": (line,),
            "payment_status": PaymentStatus.PAID,
            "iva_category": IvaCategory("domestic_general"),
            "retention_rate": None if retention_rate is None else Decimal(retention_rate),
            "retention_amount": None if retention_amount is None else Decimal(retention_amount),
        }
    )


def _request(invoice: Invoice) -> InvoiceWithholdingEvidenceRequest:
    """Build movable-capital evidence: it needs no annual detail, so only the invoice is under test."""
    return InvoiceWithholdingEvidenceRequest.model_validate(
        {
            "invoice_id": invoice.invoice_id,
            "income_kind": WithholdingIncomeKind.ORDINARY_MOVABLE_CAPITAL,
            "scheme": "intereses",
            "recipient_tax_status": WithholdingRecipientTaxStatus.RESIDENT,
            "recipient_tax_regime": WithholdingRecipientTaxRegime.IRPF,
            "exigibility_event_id": "exigibility-q4",
            "exigibility_occurred_on": date(2025, 12, 15),
            "allocation_id": "allocation-q4",
            "allocated_base": Decimal("500.00"),
            "allocated_withholding": Decimal("95.00"),
            "allocated_settlement": Decimal("0.00"),
            "idempotency_key": "capture-defects-q4",
        }
    )


def _capture_refusal(invoice: Invoice) -> InvoiceWithholdingDefectsError:
    with pytest.raises(InvoiceWithholdingDefectsError) as exc_info:
        build_invoice_withholding_capture(
            invoice,
            catalogue_revision_id="a" * 64,
            request=_request(invoice),
            applicable_year=2025,
            cadence=quarterly_filer_cadence(2025),
        )
    return exc_info.value


def test_an_invoice_with_two_defects_is_refused_with_both() -> None:
    """A non-resident supplier's invoice with no withheld amount names both defects, in sweep order."""
    invoice = _invoice(country="PT", tax_id="PT123456789", retention_amount=None, retention_rate=None)

    with override_settings(cadrumo_output_language="en"):
        refusal = _capture_refusal(invoice)
        envelope = build_error_envelope(refusal)

    expected = (
        InvoiceRetencionProjectionDefect.NO_RETENCION_DECLARED,
        InvoiceRetencionProjectionDefect.NON_RESIDENT_SUPPLIER,
    )
    assert refusal.defects == expected
    assert refusal.defects == project_received_invoice_retencion(invoice, scheme=_request(invoice).scheme).defects
    assert refusal.refusal_code == "no_retencion_declared,non_resident_supplier"
    assert envelope.code == "REFUSED_INVOICE_WITHHOLDING_DEFECTS"
    assert envelope.category == "REFUSED"
    assert envelope.context is not None
    assert envelope.context["refusal_code"] == "no_retencion_declared,non_resident_supplier"
    reasons = envelope.context["defect_reasons"]
    assert "The invoice declares no withheld amount." in reasons
    assert "The supplier is not resident in Spain" in reasons
    assert reasons.index("no withheld amount") < reasons.index("not resident in Spain")


def test_a_single_defect_refuses_with_the_code_it_always_carried() -> None:
    """An issued invoice's retención is a credit; the refusal keeps its one-token code."""
    refusal = _capture_refusal(_invoice(kind=InvoiceKind.ISSUED))

    assert refusal.defects == (InvoiceRetencionProjectionDefect.NOT_A_RETENEDOR_LIABILITY,)
    assert refusal.refusal_code == "not_a_retenedor_liability"
    assert isinstance(refusal, InvoiceWithholdingEvidenceError)


def test_a_clean_invoice_still_captures_the_projected_liability() -> None:
    """A routable invoice yields the capture command, bounded by the projection's euro figures."""
    invoice = _invoice()
    projection = project_received_invoice_retencion(invoice, scheme=_request(invoice).scheme)
    assert projection.observation is not None

    capture = build_invoice_withholding_capture(
        invoice,
        catalogue_revision_id="a" * 64,
        request=_request(invoice),
        applicable_year=2025,
        cadence=quarterly_filer_cadence(2025),
    )

    snapshot = capture.command.liability_snapshot
    assert snapshot.liability_base == projection.observation.taxable_base == Decimal("1000.00")
    assert snapshot.liability_withholding == projection.observation.retencion_amount == Decimal("190.00")
    assert snapshot.liability_settlement == Decimal("1020.00")
    assert capture.command.perceptor_nif == projection.observation.perceptor_nif
    assert capture.scope.modelo == "123"


@pytest.mark.parametrize("language", _LANGUAGES)
def test_every_defect_and_the_refusal_render_real_text_in_every_locale(language: str) -> None:
    """Each defect has its own translated explanation, and the refusal message is translated too.

    The refusal is built from every defect member at once, so a member added
    without a catalogue key fails here rather than at an operator's refusal.
    """
    every_defect = tuple(InvoiceRetencionProjectionDefect)
    with override_settings(cadrumo_output_language=language):
        refusal = InvoiceWithholdingDefectsError(every_defect)
        envelope = build_error_envelope(refusal)
        english_fallback = {
            defect: defect.value.replace("_", " ").capitalize() for defect in InvoiceRetencionProjectionDefect
        }

    assert envelope.context is not None
    reasons = envelope.context["defect_reasons"]
    for defect in every_defect:
        assert defect.value not in reasons, f"{defect.value} rendered as its key in {language}"
        assert english_fallback[defect] not in reasons, f"{defect.value} fell back to a humanised key in {language}"
    assert envelope.message.strip()
    assert "canonical_invoice_withholding_defects" not in envelope.message
    assert envelope.context["refusal_code"] == ",".join(defect.value for defect in every_defect)


@pytest.mark.parametrize("defect", tuple(InvoiceRetencionProjectionDefect))
def test_each_defect_explanation_is_translated_rather_than_copied(defect: InvoiceRetencionProjectionDefect) -> None:
    """No locale reuses another's explanation of the same defect."""
    rendered: dict[str, str] = {}
    for language in _LANGUAGES:
        with override_settings(cadrumo_output_language=language):
            context = InvoiceWithholdingDefectsError((defect,)).context
        assert context is not None
        rendered[language] = str(context["defect_reasons"])
    assert len(set(rendered.values())) == len(_LANGUAGES), rendered
