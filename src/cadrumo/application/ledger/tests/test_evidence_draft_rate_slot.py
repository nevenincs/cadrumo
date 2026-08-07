"""A percentage outside the closed IVA taxonomy refuses; it never rounds.

Structured-document ingestion reads the rate off the document itself rather
than taking it from an operator, which is what makes this reachable: the
taxpayer does not choose the percentage on a supplier's invoice, so any
percentage that has ever existed can arrive at the confirm boundary.

Five percent is the specific case, and it is real rather than hypothetical.
Spain applied a transient reduced rate to electricity and gas supplies through
2022-2024; :class:`~domain.invoices.IvaRate` deliberately does NOT carry a
``RATE_5`` slot, and its own docstring names ingesting pre-2025 data as the
event that would require adding one. Until then a 2024 electricity invoice is a
document this application can read and cannot represent.

**Refusing is the correct outcome and rounding is the dangerous one.** Silently
resolving five percent to the four percent slot understates the cuota; resolving
it to ten percent overstates it. Both produce a structurally valid invoice
record carrying a figure that appears on no document, and neither leaves a
signal -- which is precisely the silent-misfiling class the confirm boundary
exists to prevent. The nearest slot is never the right answer for a rate the
taxonomy does not know.
"""

from __future__ import annotations

from decimal import Decimal
from io import BytesIO
from pathlib import Path

import pytest

from ....adapters.persistence.profile.invoices import InvoiceCatalogueRepository
from ....adapters.persistence.storage.sql import SecureObjectRepository
from ....core.config import Settings
from ....domain.invoices import IvaRate, numeric_iva_rate_slots
from ....domain.invoices import InvoiceValidationError
from ....domain.iva import InvoiceKind
from .._evidence_draft import confirm_invoice_draft_from_evidence
from ._evidence_test_support import _BUCKET_ID, _make_svc
from ._evidence_test_support import isolated_settings as isolated_settings
from ._evidence_test_support import runtime_profile as runtime_profile
from ._evidence_test_support import secure_objects as secure_objects

pytestmark = [pytest.mark.unit, pytest.mark.hex_application]
__all__ = ["isolated_settings", "runtime_profile", "secure_objects"]

_SUPPLIER_CIF = "B12345674"

# A 2024 electricity invoice at the transient 5% rate: base 100,00, cuota 5,00.
# Every figure is internally coherent -- the document is not malformed, it is
# simply expressed in a rate slot this taxonomy does not carry.
_TRANSIENT_RATE_INVOICE_LINES = (
    "Factura de Energia Peninsular SL",
    f"NIF: {_SUPPLIER_CIF}",
    "Numero de factura: 2024-0451",
    "Fecha: 14/06/2024",
    "Base imponible: 100,00",
    "IVA 5%",
    "Cuota IVA: 5,00",
    "Total factura: 105,00",
)

# The same document at a slot the taxonomy DOES carry. This is the positive
# control: it differs from the fixture above only in the percentage, so a
# refusal above that is really caused by a broken fixture would show up here
# as well.
_KNOWN_RATE_INVOICE_LINES = (
    "Factura de Energia Peninsular SL",
    f"NIF: {_SUPPLIER_CIF}",
    "Numero de factura: 2024-0452",
    "Fecha: 14/06/2024",
    "Base imponible: 100,00",
    "IVA 21%",
    "Cuota IVA: 21,00",
    "Total factura: 121,00",
)


def _text_pdf_bytes(lines: tuple[str, ...]) -> bytes:
    from reportlab.lib.pagesizes import A4
    from reportlab.pdfgen import canvas

    buf = BytesIO()
    page = canvas.Canvas(buf, pagesize=A4)
    y = 760
    for line in lines:
        page.drawString(72, y, line)
        y -= 20
    page.save()
    return buf.getvalue()


def _confirm(
    lines: tuple[str, ...],
    *,
    isolated_settings: Settings,
    secure_objects: SecureObjectRepository,
    tmp_path: Path,
    filename: str,
):
    pdf_path = tmp_path / filename
    pdf_path.write_bytes(_text_pdf_bytes(lines))
    svc = _make_svc(isolated_settings, secure_objects)
    record = svc.add(bucket_id=_BUCKET_ID, source_path=pdf_path).record
    return confirm_invoice_draft_from_evidence(
        counterparty_country="ES",
        bucket_id=_BUCKET_ID,
        kind=InvoiceKind.RECEIVED,
        evidence_id=record.evidence_id,
        counterparty_name="Energia Peninsular SL",
        settings=isolated_settings,
        invoice_repository=InvoiceCatalogueRepository(objects=secure_objects),
    )


def test_the_transient_five_percent_rate_is_genuinely_outside_the_taxonomy() -> None:
    """Non-vacuity: the refusal below is only meaningful while 5 is unknown.

    Asserted rather than assumed, because the day a ``RATE_5`` slot is legitimately
    added -- the exact event :class:`IvaRate` names -- the refusal test becomes
    wrong rather than merely stale, and it must fail HERE, pointing at the
    taxonomy change, instead of failing there as a mystery.
    """
    slots = numeric_iva_rate_slots()

    assert Decimal("5") not in slots, (
        "a RATE_5 slot now exists, so a 5% document is representable and must no longer refuse; "
        "update this module rather than the mapper"
    )
    assert {Decimal("4"), Decimal("10"), Decimal("21")} <= set(slots), (
        "the neighbouring slots this rate must NOT round into have to exist for the test to mean anything"
    )


def test_a_five_percent_document_refuses_and_names_the_accepted_rates(
    isolated_settings: Settings,
    secure_objects: SecureObjectRepository,
    tmp_path: Path,
) -> None:
    """The confirm boundary refuses, and the refusal is actionable.

    A bare "value invalid" would leave the operator with a document they can
    read and no idea why the application will not take it, so the rejected rate
    and the accepted set both travel on the error's context where the localised
    message renders them.

    Asserted on the context rather than on ``str(exc)`` deliberately: the
    operator-facing wording lives in the locale catalogues, and pinning English
    prose here would both duplicate that authority and break on translation.
    """
    with pytest.raises(InvoiceValidationError) as excinfo:
        _confirm(
            _TRANSIENT_RATE_INVOICE_LINES,
            isolated_settings=isolated_settings,
            secure_objects=secure_objects,
            tmp_path=tmp_path,
            filename="factura_luz_2024.pdf",
        )

    error = excinfo.value
    assert error.translated_message == "application.invoices.creation.errors.unsupported_iva_rate"
    assert error.context["iva_rate"] == "5", f"the refusal must name the rate rejected: {error.context}"
    accepted = error.context["accepted"]
    for slot in ("4", "10", "21"):
        assert slot in accepted, f"the refusal must name the accepted set, missing {slot}: {accepted}"
    assert "5" not in accepted.split(", "), "5 must not appear in the set the refusal advertises as accepted"


def test_the_refusal_is_the_same_one_whether_or_not_a_cuota_was_printed(
    isolated_settings: Settings,
    secure_objects: SecureObjectRepository,
    tmp_path: Path,
) -> None:
    """One unrepresentable rate, one refusal -- on both confirm branches.

    The confirm path forks on whether the document printed a cuota: a printed
    figure is evidence and builds an explicit invoice line, an absent one lets
    the writer derive it. Both forks resolve the same percentage, and they once
    resolved it through two different functions raising two different error
    types -- so the operator's experience of the identical mistake depended on
    a property of their document that has nothing to do with the rate.
    """
    printed_cuota = _TRANSIENT_RATE_INVOICE_LINES
    no_printed_cuota = tuple(line for line in _TRANSIENT_RATE_INVOICE_LINES if not line.startswith("Cuota IVA"))
    assert len(no_printed_cuota) == len(printed_cuota) - 1, "the second fixture must differ by the cuota line alone"

    raised = []
    for index, lines in enumerate((printed_cuota, no_printed_cuota)):
        with pytest.raises(InvoiceValidationError) as excinfo:
            _confirm(
                lines,
                isolated_settings=isolated_settings,
                secure_objects=secure_objects,
                tmp_path=tmp_path,
                filename=f"factura_luz_fork_{index}.pdf",
            )
        raised.append(excinfo.value)

    assert raised[0].translated_message == raised[1].translated_message
    assert raised[0].context["accepted"] == raised[1].context["accepted"]


def test_the_same_document_at_a_known_rate_confirms(
    isolated_settings: Settings,
    secure_objects: SecureObjectRepository,
    tmp_path: Path,
) -> None:
    """Positive control: the fixture shape itself is confirmable.

    Without this, the refusal above is equally consistent with a fixture the
    reader cannot parse at all -- a test that passes because nothing works is
    indistinguishable from one that passes because the guard fired.
    """
    result = _confirm(
        _KNOWN_RATE_INVOICE_LINES,
        isolated_settings=isolated_settings,
        secure_objects=secure_objects,
        tmp_path=tmp_path,
        filename="factura_luz_21.pdf",
    )

    assert [line.iva_rate for line in result.invoice.lines] == [IvaRate.RATE_21]
    assert result.invoice.grand_total == Decimal("121.00")
