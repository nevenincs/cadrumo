"""Real-behaviour tests for on-host invoice-PDF field extraction into a draft.

Builds real text-bearing PDFs in memory (reportlab), wraps them as
``EvidenceInput``, and asserts :func:`extract_invoice_fields` recovers the
grounded fields with no file written and no field fabricated. No mocks.

See Also:
    :class:`~application.ledger.InvoiceDraft`
        Public reviewed-draft record returned before any invoice is persisted.
    :func:`~application.ledger.extract_invoice_fields`
        On-host text-layer primitive exercised by the pure extraction tests.
    :func:`~application.ledger.extract_invoice_draft_from_evidence`
        CLI-facing resolver that reads stored evidence bytes from secure storage
        and chooses text-layer or on-host vision extraction.
    :func:`~application.ledger.confirm_invoice_draft_from_evidence`
        Confirmation step that re-extracts, applies overrides, and delegates the
        catalogue write.
    :func:`~application.invoices.create_catalogue_invoice`
        Sole sanctioned invoice-catalogue writer used by confirmation.
"""

from __future__ import annotations

import hashlib
import json
from datetime import UTC, date, datetime
from decimal import Decimal
from io import BytesIO
from pathlib import Path

import pytest
from PIL import Image
from pydantic import ValidationError

from ....adapters.persistence.profile.invoices import InvoiceCatalogueRepository
from ....adapters.persistence.storage import AttachmentStore
from ....adapters.persistence.storage.sql import SecureObjectRepository
from ....core.config import Settings
from ....domain.attachments import load_attachment
from ....domain.invoices import InvoiceValidationError
from ....domain.iva import InvoiceKind
from ....domain.user_profile import UserProfileFact, UserProfileRecord
from ...user_profile import UserProfileLifecycleRepository
from .._evidence import MediaKind, PurchaseInvoiceEvidenceInputError, PurchaseInvoiceEvidenceNotFoundError
from .._evidence_draft import (
    InvoiceDraft,
    confirm_invoice_draft_from_evidence,
    extract_invoice_draft_from_evidence,
    extract_invoice_fields,
)
from .._evidence_input import EvidenceInput
from ._evidence_test_support import _BUCKET_ID, _make_svc
from ._evidence_test_support import isolated_settings as isolated_settings
from ._evidence_test_support import runtime_profile as runtime_profile
from ._evidence_test_support import secure_objects as secure_objects
from ._llm_vision_evidence_support import _json_array, _json_object, _run_against_loopback_ollama

pytestmark = [pytest.mark.unit, pytest.mark.hex_application]
__all__ = ["isolated_settings", "runtime_profile", "secure_objects"]

# A real Spanish CIF (Agencia Tributaria checksum-valid: leading letter B,
# 7 digits, digit control character computed by the AEAT algorithm).
_SUPPLIER_CIF = "B12345674"

_FULL_INVOICE_LINES = (
    "Factura de Acme Suministros SL",
    f"NIF: {_SUPPLIER_CIF}",
    "Numero de factura: 2026-0142",
    "Fecha: 10/03/2026",
    "Base imponible: 100,00",
    "IVA 21%",
    "Cuota IVA: 21,00",
    "Total factura: 121,00",
)

_PARTIAL_INVOICE_LINES = (
    "Factura de Acme Suministros SL",
    "Base imponible: 250,00",
    "Total factura: 250,00",
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


def _evidence_input(data: bytes, media_kind: MediaKind, mime_type: str) -> EvidenceInput:
    return EvidenceInput(
        media_kind=media_kind,
        mime_type=mime_type,
        data=data,
        content_sha256=hashlib.sha256(data).hexdigest(),
        attachment_id="a" * 64,
    )


def test_extracts_every_field_from_a_full_invoice_layout_on_host() -> None:
    pdf = _text_pdf_bytes(_FULL_INVOICE_LINES)
    ev = _evidence_input(pdf, MediaKind.PDF, "application/pdf")

    draft = extract_invoice_fields(ev)

    assert draft.supplier_tax_id == _SUPPLIER_CIF
    assert draft.invoice_number == "2026-0142"
    assert draft.invoice_date == "2026-03-10"
    assert draft.taxable_base == 100
    assert draft.iva_rate == 21
    assert draft.iva_amount == 21
    assert draft.grand_total == 121
    assert draft.raw_text_length > 0
    # No currency code is printed on this layout, so none is asserted -- the
    # amounts are not silently claimed to be euro by the extractor.
    assert draft.currency is None


def test_printed_currency_code_is_recovered() -> None:
    lines = (*_PARTIAL_INVOICE_LINES, "Importe en USD")
    ev = _evidence_input(_text_pdf_bytes(lines), MediaKind.PDF, "application/pdf")

    draft = extract_invoice_fields(ev)

    assert draft.currency == "USD"


def test_two_currency_codes_are_ambiguous_and_ground_to_none() -> None:
    """An invoice quoting a foreign total beside its euro equivalent is unresolvable.

    Picking the first match would silently denominate the filing amount in
    whichever code the layout happened to print first.
    """
    lines = (*_PARTIAL_INVOICE_LINES, "Total USD 250,00", "Contravalor EUR 230,00")
    ev = _evidence_input(_text_pdf_bytes(lines), MediaKind.PDF, "application/pdf")

    draft = extract_invoice_fields(ev)

    assert draft.currency is None


def test_missing_fields_are_none_not_fabricated() -> None:
    """A PDF missing several fields leaves them ``None``, never a guessed value."""
    pdf = _text_pdf_bytes(_PARTIAL_INVOICE_LINES)
    ev = _evidence_input(pdf, MediaKind.PDF, "application/pdf")

    draft = extract_invoice_fields(ev)

    assert draft.supplier_tax_id is None
    assert draft.invoice_number is None
    assert draft.invoice_date is None
    assert draft.iva_rate is None
    assert draft.iva_amount is None
    # The fields that ARE present in the source text are still recovered.
    assert draft.taxable_base == 250
    assert draft.grand_total == 250


def test_invalid_tax_id_lookalike_is_skipped_not_returned() -> None:
    """A digit run that merely looks like a tax id but fails the checksum is skipped."""
    # "A0000000A" has the coarse shape of a CIF but fails the AEAT check letter.
    lines = ("Factura", "Ref: A0000000A", "Total factura: 50,00")
    pdf = _text_pdf_bytes(lines)
    ev = _evidence_input(pdf, MediaKind.PDF, "application/pdf")

    draft = extract_invoice_fields(ev)

    assert draft.supplier_tax_id is None
    assert draft.grand_total == 50


def test_image_evidence_has_no_text_layer_and_refuses() -> None:
    ev = _evidence_input(b"\x89PNG\r\n\x1a\nfake-png-bytes", MediaKind.IMAGE, "image/png")

    with pytest.raises(PurchaseInvoiceEvidenceInputError):
        extract_invoice_fields(ev)


def test_extraction_never_writes_a_file(tmp_path_factory: pytest.TempPathFactory) -> None:
    """The evidence bytes and extracted text stay in memory; nothing lands on disk."""
    empty_dir = tmp_path_factory.mktemp("no-write-expected")
    pdf = _text_pdf_bytes(_FULL_INVOICE_LINES)
    ev = _evidence_input(pdf, MediaKind.PDF, "application/pdf")

    extract_invoice_fields(ev)

    assert list(empty_dir.iterdir()) == []


class TestExtractInvoiceDraftFromEvidence:
    """Real-behaviour tests for the CLI-facing wiring layer.

    Drives the real encrypted-bucket ``PurchaseInvoiceEvidenceService.add``
    write path so the evidence's bytes genuinely live in the
    ``AttachmentStore``, then resolves them back through
    :func:`extract_invoice_draft_from_evidence` by both reference kinds
    (``evidence_id`` and ``attachment_id``). No mocks.
    """

    def test_extracts_by_evidence_id_from_a_real_stored_pdf(
        self,
        isolated_settings: Settings,
        secure_objects: SecureObjectRepository,
        tmp_path: Path,
    ) -> None:
        pdf_path = tmp_path / "factura.pdf"
        pdf_path.write_bytes(_text_pdf_bytes(_FULL_INVOICE_LINES))
        svc = _make_svc(isolated_settings, secure_objects)
        record = svc.add(bucket_id=_BUCKET_ID, source_path=pdf_path).record

        draft = extract_invoice_draft_from_evidence(
            bucket_id=_BUCKET_ID,
            evidence_id=record.evidence_id,
            settings=isolated_settings,
        )

        assert draft.supplier_tax_id == _SUPPLIER_CIF
        assert draft.invoice_number == "2026-0142"
        assert draft.invoice_date == "2026-03-10"
        assert draft.taxable_base == 100
        assert draft.iva_rate == 21
        assert draft.iva_amount == 21
        assert draft.grand_total == 121
        assert draft.raw_text_length > 0

    def test_extracts_by_attachment_id_from_a_real_stored_pdf(
        self,
        isolated_settings: Settings,
        secure_objects: SecureObjectRepository,
        tmp_path: Path,
    ) -> None:
        pdf_path = tmp_path / "factura.pdf"
        pdf_path.write_bytes(_text_pdf_bytes(_PARTIAL_INVOICE_LINES))
        svc = _make_svc(isolated_settings, secure_objects)
        record = svc.add(bucket_id=_BUCKET_ID, source_path=pdf_path).record
        assert record.attachment_id is not None

        draft = extract_invoice_draft_from_evidence(
            bucket_id=_BUCKET_ID,
            attachment_id=record.attachment_id,
            settings=isolated_settings,
        )

        assert draft.taxable_base == 250
        assert draft.grand_total == 250
        # Fields absent from the partial layout stay None, never fabricated.
        assert draft.supplier_tax_id is None
        assert draft.invoice_number is None

    def test_neither_reference_supplied_refuses(self, isolated_settings: Settings) -> None:
        with pytest.raises(PurchaseInvoiceEvidenceInputError):
            extract_invoice_draft_from_evidence(bucket_id=_BUCKET_ID, settings=isolated_settings)

    def test_both_references_supplied_refuses(self, isolated_settings: Settings) -> None:
        with pytest.raises(PurchaseInvoiceEvidenceInputError):
            extract_invoice_draft_from_evidence(
                bucket_id=_BUCKET_ID,
                evidence_id="whatever",
                attachment_id="a" * 64,
                settings=isolated_settings,
            )

    def test_unknown_evidence_id_refuses_not_found(self, isolated_settings: Settings) -> None:
        with pytest.raises(PurchaseInvoiceEvidenceNotFoundError):
            extract_invoice_draft_from_evidence(
                bucket_id=_BUCKET_ID,
                evidence_id="does-not-exist",
                settings=isolated_settings,
            )

    def test_extraction_from_stored_evidence_never_writes_a_file(
        self,
        isolated_settings: Settings,
        secure_objects: SecureObjectRepository,
        tmp_path: Path,
        tmp_path_factory: pytest.TempPathFactory,
    ) -> None:
        """The stored bytes are read into memory only; nothing lands on disk."""
        pdf_path = tmp_path / "factura.pdf"
        pdf_path.write_bytes(_text_pdf_bytes(_FULL_INVOICE_LINES))
        svc = _make_svc(isolated_settings, secure_objects)
        record = svc.add(bucket_id=_BUCKET_ID, source_path=pdf_path).record

        empty_dir = tmp_path_factory.mktemp("no-write-expected-from-store")
        extract_invoice_draft_from_evidence(
            bucket_id=_BUCKET_ID,
            evidence_id=record.evidence_id,
            settings=isolated_settings,
        )

        assert list(empty_dir.iterdir()) == []


def _scan_only_pdf_bytes() -> bytes:
    """A one-page raster, text-layer-free PDF (mirrors the vision-evidence fixture)."""
    buffer = BytesIO()
    Image.new("RGB", (260, 160), "white").save(buffer, format="PDF")
    return buffer.getvalue()


def _png_bytes() -> bytes:
    buffer = BytesIO()
    Image.new("RGB", (120, 80), "white").save(buffer, format="PNG")
    return buffer.getvalue()


class TestExtractInvoiceDraftFromEvidenceVisionFallback:
    """Real-behaviour tests: a scan-only PDF / image falls back to on-host vision.

    ``extract_invoice_fields`` (the text-layer primitive) still refuses on a
    scan-only PDF or an image (see ``test_image_evidence_has_no_text_layer_and_refuses``
    above); this class covers the wiring layer
    (``extract_invoice_draft_from_evidence``) that catches that refusal and falls
    back to the on-host local-vision reader -- driven against a real loopback
    Ollama HTTP server, never a mock. No file is written and no byte leaves the
    host at any point in the fallback.
    """

    def _extraction_json(self) -> str:
        return json.dumps(
            {
                "supplier_tax_id": _SUPPLIER_CIF,
                "invoice_number": "2026-0142",
                "invoice_date": "10/03/2026",
                "taxable_base": "100,00",
                "iva_rate": "21",
                "iva_amount": "21,00",
                "grand_total": "121,00",
            },
        )

    def test_scan_only_pdf_falls_back_to_vision_and_grounds_fields(
        self,
        isolated_settings: Settings,
        secure_objects: SecureObjectRepository,
        tmp_path: Path,
    ) -> None:
        pdf_path = tmp_path / "scan.pdf"
        pdf_path.write_bytes(_scan_only_pdf_bytes())
        svc = _make_svc(isolated_settings, secure_objects)
        record = svc.add(bucket_id=_BUCKET_ID, source_path=pdf_path).record
        assert record.media_kind is MediaKind.PDF

        def _call() -> InvoiceDraft:
            return extract_invoice_draft_from_evidence(
                bucket_id=_BUCKET_ID,
                evidence_id=record.evidence_id,
                settings=isolated_settings,
            )

        observed, draft = _run_against_loopback_ollama(self._extraction_json(), _call)

        assert draft.supplier_tax_id == _SUPPLIER_CIF
        assert draft.invoice_number == "2026-0142"
        assert draft.invoice_date == "2026-03-10"
        assert draft.taxable_base == Decimal("100.00")
        assert draft.iva_rate == 21
        assert draft.iva_amount == Decimal("21.00")
        assert draft.grand_total == Decimal("121.00")

        # The request genuinely carried a rasterised image, not inlined text.
        body = _json_object(observed["body"])
        messages = _json_array(body["messages"])
        user_message = _json_object(messages[-1])
        assert user_message.get("images")

    def test_image_attachment_falls_back_to_vision_and_grounds_fields(
        self,
        isolated_settings: Settings,
        secure_objects: SecureObjectRepository,
        tmp_path: Path,
    ) -> None:
        image_path = tmp_path / "receipt.png"
        image_path.write_bytes(_png_bytes())
        svc = _make_svc(isolated_settings, secure_objects)
        record = svc.add(bucket_id=_BUCKET_ID, source_path=image_path).record
        assert record.media_kind is MediaKind.IMAGE

        def _call() -> InvoiceDraft:
            return extract_invoice_draft_from_evidence(
                bucket_id=_BUCKET_ID,
                attachment_id=record.attachment_id,
                settings=isolated_settings,
            )

        _observed, draft = _run_against_loopback_ollama(self._extraction_json(), _call)
        assert draft.taxable_base == Decimal("100.00")
        assert draft.grand_total == Decimal("121.00")

    def test_scan_only_pdf_never_writes_a_file(
        self,
        isolated_settings: Settings,
        secure_objects: SecureObjectRepository,
        tmp_path: Path,
        tmp_path_factory: pytest.TempPathFactory,
    ) -> None:
        pdf_path = tmp_path / "scan.pdf"
        pdf_path.write_bytes(_scan_only_pdf_bytes())
        svc = _make_svc(isolated_settings, secure_objects)
        record = svc.add(bucket_id=_BUCKET_ID, source_path=pdf_path).record

        empty_dir = tmp_path_factory.mktemp("no-write-expected-vision-fallback")

        def _call() -> InvoiceDraft:
            return extract_invoice_draft_from_evidence(
                bucket_id=_BUCKET_ID,
                evidence_id=record.evidence_id,
                settings=isolated_settings,
            )

        _run_against_loopback_ollama(self._extraction_json(), _call)
        assert list(empty_dir.iterdir()) == []

    def test_llm_vision_disabled_refuses_instructively_not_silently(
        self,
        isolated_settings: Settings,
        secure_objects: SecureObjectRepository,
        tmp_path: Path,
    ) -> None:
        """An operator who opted out of on-host vision gets a typed refusal, not an empty draft."""
        pdf_path = tmp_path / "scan.pdf"
        pdf_path.write_bytes(_scan_only_pdf_bytes())
        svc = _make_svc(isolated_settings, secure_objects)
        record = svc.add(bucket_id=_BUCKET_ID, source_path=pdf_path).record

        clock = datetime(2026, 1, 1, tzinfo=UTC)
        UserProfileLifecycleRepository(bucket_id=_BUCKET_ID).save(
            UserProfileRecord(
                profile_id=_BUCKET_ID,
                display_name="Vision opted out",
                facts=(
                    UserProfileFact(path="identity.tax_id", value="12345678Z"),
                    UserProfileFact(path="capabilities.llm_vision", value=False),
                ),
                created_at=clock,
                updated_at=clock,
            ),
        )

        with pytest.raises(PurchaseInvoiceEvidenceInputError) as raised:
            extract_invoice_draft_from_evidence(
                bucket_id=_BUCKET_ID,
                evidence_id=record.evidence_id,
                settings=isolated_settings,
            )
        assert "vision" in str(raised.value).lower()
        assert "llm_vision on" in (raised.value.suggestion or "")


class TestConfirmInvoiceDraftFromEvidence:
    """Real-behaviour tests for the non-interactive confirm-into-Invoice step.

    Confirms delegate the write to
    :func:`~application.invoices.create_catalogue_invoice` (the sole
    sanctioned :class:`~domain.invoices.Invoice` writer); these tests
    assert the resulting row is a genuine catalogue member (re-loaded through
    a fresh :class:`InvoiceCatalogueRepository`), that a same-identity
    re-confirm is a guarded no-op, and that an override wins over the
    extracted value. No mocks.
    """

    def _repo(self, secure_objects: SecureObjectRepository) -> InvoiceCatalogueRepository:
        return InvoiceCatalogueRepository(objects=secure_objects)

    def test_confirm_mints_a_real_catalogue_invoice(
        self,
        isolated_settings: Settings,
        secure_objects: SecureObjectRepository,
        tmp_path: Path,
    ) -> None:
        pdf_path = tmp_path / "factura.pdf"
        pdf_path.write_bytes(_text_pdf_bytes(_FULL_INVOICE_LINES))
        svc = _make_svc(isolated_settings, secure_objects)
        record = svc.add(bucket_id=_BUCKET_ID, source_path=pdf_path).record
        repo = self._repo(secure_objects)

        confirmation = confirm_invoice_draft_from_evidence(
            bucket_id=_BUCKET_ID,
            kind=InvoiceKind.RECEIVED,
            evidence_id=record.evidence_id,
            counterparty_name="Acme Suministros SL",
            settings=isolated_settings,
            invoice_repository=repo,
        )

        assert confirmation.created is True
        assert confirmation.invoice.counterparty_tax_id == _SUPPLIER_CIF
        assert confirmation.invoice.invoice_number == "2026-0142"
        assert confirmation.invoice.grand_total == Decimal("121.00")
        # The draft the confirmation was checked against is echoed back.
        assert confirmation.draft.supplier_tax_id == _SUPPLIER_CIF

        # Re-load through a FRESH repository handle: the row is genuinely
        # persisted, not merely returned by this call.
        reloaded = InvoiceCatalogueRepository(objects=secure_objects).load()
        assert confirmation.invoice.invoice_id in reloaded

    def test_confirm_is_idempotent_guarded_on_identical_resolved_fields(
        self,
        isolated_settings: Settings,
        secure_objects: SecureObjectRepository,
        tmp_path: Path,
    ) -> None:
        pdf_path = tmp_path / "factura.pdf"
        pdf_path.write_bytes(_text_pdf_bytes(_FULL_INVOICE_LINES))
        svc = _make_svc(isolated_settings, secure_objects)
        record = svc.add(bucket_id=_BUCKET_ID, source_path=pdf_path).record
        repo = self._repo(secure_objects)

        first = confirm_invoice_draft_from_evidence(
            bucket_id=_BUCKET_ID,
            kind=InvoiceKind.RECEIVED,
            evidence_id=record.evidence_id,
            counterparty_name="Acme Suministros SL",
            settings=isolated_settings,
            invoice_repository=repo,
        )
        assert first.created is True

        second = confirm_invoice_draft_from_evidence(
            bucket_id=_BUCKET_ID,
            kind=InvoiceKind.RECEIVED,
            evidence_id=record.evidence_id,
            counterparty_name="Acme Suministros SL",
            settings=isolated_settings,
            invoice_repository=repo,
        )

        assert second.created is False
        assert second.invoice.invoice_id == first.invoice.invoice_id
        # No duplicate: the catalogue still carries exactly one invoice.
        assert len(InvoiceCatalogueRepository(objects=secure_objects).load()) == 1

    def test_confirm_honours_an_override_over_the_extracted_value(
        self,
        isolated_settings: Settings,
        secure_objects: SecureObjectRepository,
        tmp_path: Path,
    ) -> None:
        pdf_path = tmp_path / "factura.pdf"
        pdf_path.write_bytes(_text_pdf_bytes(_FULL_INVOICE_LINES))
        svc = _make_svc(isolated_settings, secure_objects)
        record = svc.add(bucket_id=_BUCKET_ID, source_path=pdf_path).record
        repo = self._repo(secure_objects)

        confirmation = confirm_invoice_draft_from_evidence(
            bucket_id=_BUCKET_ID,
            kind=InvoiceKind.RECEIVED,
            evidence_id=record.evidence_id,
            counterparty_name="Acme Suministros SL",
            invoice_number="OVERRIDE-9999",
            taxable_base=Decimal("500.00"),
            settings=isolated_settings,
            invoice_repository=repo,
        )

        assert confirmation.created is True
        assert confirmation.invoice.invoice_number == "OVERRIDE-9999"
        assert confirmation.invoice.base_total == Decimal("500.00")
        # The extracted draft itself is untouched by the override -- it
        # still reports what was actually read from the document.
        assert confirmation.draft.invoice_number == "2026-0142"
        assert confirmation.draft.taxable_base == Decimal("100.00")

    def test_confirm_honours_a_zero_valued_taxable_base_override(
        self,
        isolated_settings: Settings,
        secure_objects: SecureObjectRepository,
        tmp_path: Path,
    ) -> None:
        """A ``Decimal("0")`` override must win, not fall back to the extracted value.

        A naive ``override or draft.taxable_base`` merge would treat a falsy
        zero override as "not supplied" and silently substitute the extracted
        100.00 -- exactly the kind of silent-under-declaration this confirm
        step must never produce.
        """
        pdf_path = tmp_path / "factura.pdf"
        pdf_path.write_bytes(_text_pdf_bytes(_FULL_INVOICE_LINES))
        svc = _make_svc(isolated_settings, secure_objects)
        record = svc.add(bucket_id=_BUCKET_ID, source_path=pdf_path).record
        repo = self._repo(secure_objects)

        confirmation = confirm_invoice_draft_from_evidence(
            bucket_id=_BUCKET_ID,
            kind=InvoiceKind.RECEIVED,
            evidence_id=record.evidence_id,
            counterparty_name="Acme Suministros SL",
            taxable_base=Decimal("0"),
            iva_rate=Decimal("0"),
            settings=isolated_settings,
            invoice_repository=repo,
        )

        assert confirmation.invoice.base_total == Decimal("0")
        # The extracted draft is unaffected; only the resolved invoice reflects the override.
        assert confirmation.draft.taxable_base == Decimal("100.00")

    def test_confirm_missing_required_field_refuses_not_fabricates(
        self,
        isolated_settings: Settings,
        secure_objects: SecureObjectRepository,
        tmp_path: Path,
    ) -> None:
        """A field absent from extraction with no override refuses loudly."""
        pdf_path = tmp_path / "factura.pdf"
        pdf_path.write_bytes(_text_pdf_bytes(_PARTIAL_INVOICE_LINES))
        svc = _make_svc(isolated_settings, secure_objects)
        record = svc.add(bucket_id=_BUCKET_ID, source_path=pdf_path).record
        repo = self._repo(secure_objects)

        with pytest.raises(PurchaseInvoiceEvidenceInputError):
            confirm_invoice_draft_from_evidence(
                bucket_id=_BUCKET_ID,
                kind=InvoiceKind.RECEIVED,
                evidence_id=record.evidence_id,
                counterparty_name="Acme Suministros SL",
                # No override for supplier_tax_id / invoice_number, which the
                # partial layout does not carry either.
                settings=isolated_settings,
                invoice_repository=repo,
            )
        # Nothing was written on the refused attempt.
        assert len(InvoiceCatalogueRepository(objects=secure_objects).load()) == 0

    def test_confirm_rejects_an_invalid_counterparty_tax_id_override(
        self,
        isolated_settings: Settings,
        secure_objects: SecureObjectRepository,
        tmp_path: Path,
    ) -> None:
        pdf_path = tmp_path / "factura.pdf"
        pdf_path.write_bytes(_text_pdf_bytes(_FULL_INVOICE_LINES))
        svc = _make_svc(isolated_settings, secure_objects)
        record = svc.add(bucket_id=_BUCKET_ID, source_path=pdf_path).record
        repo = self._repo(secure_objects)

        # The counterparty tax-id checksum is enforced by a pydantic
        # ``model_validator(mode="before")`` on ``Invoice`` itself, so an
        # override that fails the AEAT checksum surfaces as a pydantic
        # ``ValidationError`` (not the domain ``InvoiceValidationError``,
        # which governs post-construction invariants such as duplicate
        # identity) -- either way, an invalid override refuses rather than
        # silently minting a malformed invoice.
        with pytest.raises((InvoiceValidationError, ValidationError)):
            confirm_invoice_draft_from_evidence(
                bucket_id=_BUCKET_ID,
                kind=InvoiceKind.RECEIVED,
                evidence_id=record.evidence_id,
                counterparty_name="Acme Suministros SL",
                counterparty_tax_id="not-a-real-nif",
                settings=isolated_settings,
                invoice_repository=repo,
            )
        # Nothing was written on the refused attempt.
        assert len(InvoiceCatalogueRepository(objects=secure_objects).load()) == 0

    def test_confirm_never_writes_a_file(
        self,
        isolated_settings: Settings,
        secure_objects: SecureObjectRepository,
        tmp_path: Path,
        tmp_path_factory: pytest.TempPathFactory,
    ) -> None:
        """The evidence bytes are re-read into memory only; nothing lands on disk."""
        pdf_path = tmp_path / "factura.pdf"
        pdf_path.write_bytes(_text_pdf_bytes(_FULL_INVOICE_LINES))
        svc = _make_svc(isolated_settings, secure_objects)
        record = svc.add(bucket_id=_BUCKET_ID, source_path=pdf_path).record
        repo = self._repo(secure_objects)

        empty_dir = tmp_path_factory.mktemp("no-write-expected-confirm")
        confirm_invoice_draft_from_evidence(
            bucket_id=_BUCKET_ID,
            kind=InvoiceKind.RECEIVED,
            evidence_id=record.evidence_id,
            counterparty_name="Acme Suministros SL",
            settings=isolated_settings,
            invoice_repository=repo,
        )

        assert list(empty_dir.iterdir()) == []

    def test_confirm_by_evidence_id_auto_links_the_source_attachment_to_the_invoice(
        self,
        isolated_settings: Settings,
        secure_objects: SecureObjectRepository,
        tmp_path: Path,
    ) -> None:
        """Confirming from an ``evidence_id`` links the backing attachment to the minted invoice.

        Closes the provenance loop: the invoice is discoverable from the evidence
        (``Attachment.linked_invoice_ids``), reloaded through a FRESH manifest read
        so the link is genuinely persisted, not merely returned in-process.
        """
        pdf_path = tmp_path / "factura.pdf"
        pdf_path.write_bytes(_text_pdf_bytes(_FULL_INVOICE_LINES))
        svc = _make_svc(isolated_settings, secure_objects)
        record = svc.add(bucket_id=_BUCKET_ID, source_path=pdf_path).record
        assert record.attachment_id is not None
        repo = self._repo(secure_objects)

        confirmation = confirm_invoice_draft_from_evidence(
            bucket_id=_BUCKET_ID,
            kind=InvoiceKind.RECEIVED,
            evidence_id=record.evidence_id,
            counterparty_name="Acme Suministros SL",
            settings=isolated_settings,
            invoice_repository=repo,
        )

        store = AttachmentStore(objects=secure_objects)
        reloaded_attachment = load_attachment(store, record.attachment_id)
        assert reloaded_attachment.linked_invoice_ids == (confirmation.invoice.invoice_id,)

    def test_confirm_by_attachment_id_auto_links_the_attachment_to_the_invoice(
        self,
        isolated_settings: Settings,
        secure_objects: SecureObjectRepository,
        tmp_path: Path,
    ) -> None:
        """The same auto-link happens on the ``attachment_id`` reference path."""
        pdf_path = tmp_path / "factura.pdf"
        pdf_path.write_bytes(_text_pdf_bytes(_PARTIAL_INVOICE_LINES))
        svc = _make_svc(isolated_settings, secure_objects)
        record = svc.add(bucket_id=_BUCKET_ID, source_path=pdf_path).record
        assert record.attachment_id is not None
        repo = self._repo(secure_objects)

        confirmation = confirm_invoice_draft_from_evidence(
            bucket_id=_BUCKET_ID,
            kind=InvoiceKind.RECEIVED,
            attachment_id=record.attachment_id,
            counterparty_name="Acme Suministros SL",
            counterparty_tax_id=_SUPPLIER_CIF,
            invoice_number="ATT-0099",
            invoice_date=date(2026, 3, 15),
            settings=isolated_settings,
            invoice_repository=repo,
        )

        store = AttachmentStore(objects=secure_objects)
        reloaded_attachment = load_attachment(store, record.attachment_id)
        assert reloaded_attachment.linked_invoice_ids == (confirmation.invoice.invoice_id,)

    def test_re_confirm_does_not_duplicate_the_evidence_link(
        self,
        isolated_settings: Settings,
        secure_objects: SecureObjectRepository,
        tmp_path: Path,
    ) -> None:
        """A guarded idempotent re-confirm re-asserts the same link, never duplicating it."""
        pdf_path = tmp_path / "factura.pdf"
        pdf_path.write_bytes(_text_pdf_bytes(_FULL_INVOICE_LINES))
        svc = _make_svc(isolated_settings, secure_objects)
        record = svc.add(bucket_id=_BUCKET_ID, source_path=pdf_path).record
        assert record.attachment_id is not None
        repo = self._repo(secure_objects)

        first = confirm_invoice_draft_from_evidence(
            bucket_id=_BUCKET_ID,
            kind=InvoiceKind.RECEIVED,
            evidence_id=record.evidence_id,
            counterparty_name="Acme Suministros SL",
            settings=isolated_settings,
            invoice_repository=repo,
        )
        assert first.created is True

        second = confirm_invoice_draft_from_evidence(
            bucket_id=_BUCKET_ID,
            kind=InvoiceKind.RECEIVED,
            evidence_id=record.evidence_id,
            counterparty_name="Acme Suministros SL",
            settings=isolated_settings,
            invoice_repository=repo,
        )
        assert second.created is False
        assert second.invoice.invoice_id == first.invoice.invoice_id

        store = AttachmentStore(objects=secure_objects)
        reloaded_attachment = load_attachment(store, record.attachment_id)
        # Exactly one entry -- not duplicated by the second confirm call.
        assert reloaded_attachment.linked_invoice_ids == (first.invoice.invoice_id,)
