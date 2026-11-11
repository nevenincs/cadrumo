"""Closed invoice read snapshots retain only the disclosed catalogue facts."""

from __future__ import annotations

from datetime import UTC, date, datetime
from decimal import Decimal

import pytest
from pydantic import ValidationError

from ....domain.attachments.enums import AttachmentKind, AttachmentSource
from ....domain.attachments.models import Attachment
from ....domain.invoices.business_premises import BusinessPremisesLease, SituacionInmueble
from ....domain.invoices.models import Invoice
from ....domain.iva.schema import InvoiceKind
from ...exchange_rate_provider import exchange_rate_provider
from ...operations.registry_schema_validation import strict_model_json_schema
from ..catalogue_creation import build_catalogue_invoice
from ..catalogue_read_projection import (
    CatalogueInvoiceSnapshot,
    InvoiceDocumentIndex,
    InvoiceDocumentSnapshot,
    InvoiceLineSnapshot,
)

pytestmark = [pytest.mark.unit, pytest.mark.hex_application, pytest.mark.usefixtures("operation")]


def _invoice(*, kind: InvoiceKind = InvoiceKind.RECEIVED, lease: BusinessPremisesLease | None = None) -> Invoice:
    return build_catalogue_invoice(
        bucket_id="20202020-2020-4202-8202-202020202020",
        kind=kind,
        counterparty_name="Papeleria Sol SL",
        counterparty_tax_id="B00010157",
        counterparty_country="ES",
        invoice_number="2026-0142",
        issued_at=date(2026, 3, 10),
        taxable_base=Decimal("137.25"),
        iva_rate=Decimal("21"),
        currency="EUR",
        business_premises_lease=lease,
        rate_provider=exchange_rate_provider(),
    )


def _snapshot(
    *, kind: InvoiceKind = InvoiceKind.RECEIVED, lease: BusinessPremisesLease | None = None
) -> CatalogueInvoiceSnapshot:
    return CatalogueInvoiceSnapshot.from_invoice(
        _invoice(kind=kind, lease=lease), documents=InvoiceDocumentIndex.from_manifests(())
    )


def test_snapshot_roundtrip_preserves_amounts_lines_and_absence() -> None:
    snapshot = _snapshot()
    decoded = CatalogueInvoiceSnapshot.model_validate_json(snapshot.model_dump_json())
    assert decoded == snapshot
    assert decoded.base_total.decimal == "137.25"
    assert decoded.grand_total.decimal != decoded.base_total.decimal
    assert decoded.lines[0].description
    assert decoded.lines[0].quantity.decimal == "1"
    assert decoded.fx_rate is None
    assert decoded.retention_amount is None
    assert decoded.source_filename is None
    assert "source_path" not in decoded.model_fields_set
    assert "provenance" not in decoded.model_fields_set
    assert strict_model_json_schema(CatalogueInvoiceSnapshot)


def test_snapshot_discloses_the_lease_referencia_catastral_normalised_by_the_domain() -> None:
    lease = BusinessPremisesLease(
        situacion_inmueble=SituacionInmueble.SPAIN_OTHER_THAN_BASQUE_NAVARRE,
        referencia_catastral=" 9872023vh5797s0001wx ",
    )
    snapshot = _snapshot(kind=InvoiceKind.ISSUED, lease=lease)
    assert snapshot.referencia_catastral == "9872023VH5797S0001WX"
    decoded = CatalogueInvoiceSnapshot.model_validate_json(snapshot.model_dump_json())
    assert decoded.referencia_catastral == "9872023VH5797S0001WX"


def test_snapshot_referencia_catastral_is_absent_without_a_lease_or_a_reference() -> None:
    assert _snapshot().referencia_catastral is None
    unreferenced = BusinessPremisesLease(situacion_inmueble=SituacionInmueble.ABROAD)
    assert _snapshot(kind=InvoiceKind.ISSUED, lease=unreferenced).referencia_catastral is None


@pytest.mark.parametrize(
    ("field", "value"),
    [("quantity", "0"), ("quantity", "-1"), ("unit_price", "-0.01"), ("iva_amount", "NaN")],
)
def test_line_rejects_invalid_decimal_bounds(field: str, value: str) -> None:
    data = _snapshot().lines[0].model_dump(mode="python")
    data[field] = {"decimal": value}
    with pytest.raises(ValidationError):
        InvoiceLineSnapshot.model_validate(data)


@pytest.mark.parametrize(
    ("field", "value"),
    [
        ("base_total", {"decimal": "-1"}),
        ("fx_rate", {"decimal": "0"}),
        ("source_filename", "C:/private/invoice.csv"),
        ("invoice_number", ""),
        ("counterparty_name", ""),
        ("fx_rate_source", ""),
        ("lines", []),
        ("documents", [{"attachment_id": "a" * 64, "name": "private/factura.pdf", "media_type": "application/pdf"}]),
        ("documents", [{"attachment_id": "a" * 64, "name": "..", "media_type": "application/pdf"}]),
        (
            "documents",
            [
                {"attachment_id": "a" * 64, "name": "factura.pdf", "media_type": "application/pdf"},
                {"attachment_id": "a" * 64, "name": "factura.pdf", "media_type": "application/pdf"},
            ],
        ),
    ],
)
def test_snapshot_rejects_invalid_public_shape(field: str, value: object) -> None:
    data = _snapshot().model_dump(mode="python")
    data[field] = value
    with pytest.raises(ValidationError):
        CatalogueInvoiceSnapshot.model_validate(data)


def _manifest(
    digest: str,
    *,
    invoices: tuple[str, ...],
    source: AttachmentSource = AttachmentSource.LOCAL_FILE,
    reference: str = "/home/persona/facturas/factura.pdf",
    mime_type: str = "application/pdf",
) -> Attachment:
    return Attachment(
        attachment_id=digest,
        kind=AttachmentKind.INVOICE_PDF,
        source=source,
        source_reference=reference,
        sha256=digest,
        mime_type=mime_type,
        bytes_size=10,
        captured_at=datetime.fromtimestamp(0, UTC),
        linked_invoice_ids=invoices,
    )


def test_the_index_names_a_local_document_by_its_last_path_component_on_either_kind_of_system() -> None:
    index = InvoiceDocumentIndex.from_manifests(
        (
            _manifest("b" * 64, invoices=("i1",), reference=r"C:\Users\persona\Facturas\recibida.PDF"),
            _manifest("a" * 64, invoices=("i1",), reference="/home/persona/facturas/emitida.xml", mime_type="text/xml"),
        )
    )

    assert index.of("i1") == (
        InvoiceDocumentSnapshot(attachment_id="a" * 64, name="emitida.xml", media_type="text/xml"),
        InvoiceDocumentSnapshot(attachment_id="b" * 64, name="recibida.PDF", media_type="application/pdf"),
    )


def test_a_document_not_read_from_a_local_file_is_served_without_a_name() -> None:
    index = InvoiceDocumentIndex.from_manifests(
        (_manifest("c" * 64, invoices=("i1",), source=AttachmentSource.URL, reference="https://example.test/f.pdf"),)
    )

    assert index.of("i1") == (InvoiceDocumentSnapshot(attachment_id="c" * 64, name=None, media_type="application/pdf"),)


def test_one_document_kept_for_two_invoices_is_served_with_each_and_an_unlinked_one_with_none() -> None:
    index = InvoiceDocumentIndex.from_manifests(
        (_manifest("d" * 64, invoices=("i1", "i2")), _manifest("e" * 64, invoices=()))
    )

    assert [document.attachment_id for document in index.of("i1")] == ["d" * 64]
    assert [document.attachment_id for document in index.of("i2")] == ["d" * 64]
    assert index.of("i3") == ()


def test_the_snapshot_serves_exactly_the_documents_indexed_for_its_invoice() -> None:
    plain = _snapshot()
    index = InvoiceDocumentIndex.from_manifests(
        (_manifest("f" * 64, invoices=(plain.invoice_id,)), _manifest("0" * 64, invoices=("another",)))
    )
    invoice = _invoice()

    documented = CatalogueInvoiceSnapshot.from_invoice(invoice, documents=index)

    assert documented.invoice_id == plain.invoice_id
    assert documented.documents == (
        InvoiceDocumentSnapshot(attachment_id="f" * 64, name="factura.pdf", media_type="application/pdf"),
    )
    assert plain.documents == ()
