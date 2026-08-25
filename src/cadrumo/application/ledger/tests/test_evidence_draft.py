"""Real-behaviour tests for on-host invoice-document reading into a draft.

Builds real text-bearing PDFs in memory (reportlab), stores them through the
real encrypted-bucket write path, and asserts
:func:`extract_invoice_draft_from_evidence` recovers the grounded fields with no
file written and no field fabricated. No mocks.

See Also:
    :class:`~application.ledger.InvoiceDraft`
        Public reviewed-draft record returned before any invoice is persisted.
    :func:`~application.ledger.transcribe_text_layer`
        Acquisition-stage primitive that refuses a document with no text layer.
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
from collections.abc import Iterator
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
from ....core import STR_KEYED_MAPPING_ADAPTER, scan_directory
from ....core.config import Settings
from ....domain.attachments import load_attachment
from ....domain.invoices import InvoiceValidationError
from ....domain.iva import InvoiceKind
from ....domain.user_profile import ProfileSetupState, UserProfileFact, UserProfileRecord
from ....tests.llm_vision_evidence_support import _json_array, _run_against_loopback_ollama
from ....tests.pdf_fixtures import text_pdf_bytes
from ....tests.profile_capsule import seed_test_profile_record
from .._evidence import MediaKind, PurchaseInvoiceEvidenceInputError, PurchaseInvoiceEvidenceNotFoundError
from .._evidence_draft import (
    InvoiceDraft,
    confirm_invoice_draft_from_evidence,
    extract_invoice_draft_from_evidence,
)
from .._evidence_input import EvidenceInput
from .._evidence_textlayer import transcribe_text_layer
from .._preconditions import LedgerPreconditionCondition
from ._evidence_test_support import _BUCKET_ID, _make_svc
from ._evidence_test_support import runtime_profile as runtime_profile
from ._evidence_test_support import seeded_filer_profile as seeded_filer_profile
from ._ledger_value_fixtures import isolated_settings, secure_objects
from ._loopback_reader import serving_a_loopback_reader

pytestmark = [pytest.mark.unit, pytest.mark.hex_application]
__all__ = ["isolated_settings", "runtime_profile", "secure_objects", "seeded_filer_profile"]

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


# ---------------------------------------------------------------------------
# A real loopback reader for the paths that now go through the semantic reader
# ---------------------------------------------------------------------------
#
# These cases are about MINTING, IDEMPOTENCY, OVERRIDES and LINKING -- not about
# what happens when no reader is installed. Wiring the semantic reader made them
# stop at a connection error, which says nothing about any of those contracts,
# so they are served a real endpoint rather than inverted into refusal
# assertions. The refusal itself is gated separately, in
# `test_grounded_reading_wiring.py`, where it is the subject rather than an
# accident of the environment.
#
# Replies are keyed on each document's own printed figures, so the full and
# partial invoices cannot be confused for one another.

_FULL_INVOICE_FIELDS = {
    "supplier_tax_id": _SUPPLIER_CIF,
    "supplier_tax_id_anchor": _SUPPLIER_CIF,
    "invoice_number": "2026-0142",
    "invoice_number_anchor": "2026-0142",
    "invoice_date": "2026-03-10",
    "invoice_date_anchor": "10/03/2026",
    "taxable_base": "100,00",
    "taxable_base_anchor": "100,00",
    "iva_rate": "21",
    "iva_rate_anchor": "21%",
    "iva_amount": "21,00",
    "iva_amount_anchor": "21,00",
    "grand_total": "121,00",
    "grand_total_anchor": "121,00",
    "currency": "EUR",
}

_PARTIAL_INVOICE_FIELDS = {
    "taxable_base": "250,00",
    "taxable_base_anchor": "250,00",
    "grand_total": "250,00",
    "grand_total_anchor": "250,00",
}


@pytest.fixture(autouse=True)
def _loopback_reader() -> Iterator[None]:
    """Serve a real reading endpoint for every case in this module."""
    with serving_a_loopback_reader(
        (
            ("2026-0142", _FULL_INVOICE_FIELDS),
            ("250,00", _PARTIAL_INVOICE_FIELDS),
        ),
    ):
        yield


def _evidence_input(data: bytes, mime_type: str) -> EvidenceInput:
    return EvidenceInput(
        mime_type=mime_type,
        data=data,
        content_sha256=hashlib.sha256(data).hexdigest(),
        attachment_id="a" * 64,
    )


def test_image_evidence_has_no_text_layer_and_refuses() -> None:
    """An image carries nothing to transcribe, so the acquisition stage refuses.

    The refusal is what the router keys the vision escalation on: a document
    that cannot be transcribed is a statement about the DOCUMENT, so it is the
    one case where escalating to a reader that works on pixels is right.
    """
    ev = _evidence_input(b"\x89PNG\r\n\x1a\nfake-png-bytes", "image/png")

    with pytest.raises(PurchaseInvoiceEvidenceInputError):
        transcribe_text_layer(ev)


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
        pdf_path.write_bytes(text_pdf_bytes(_FULL_INVOICE_LINES))
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
        pdf_path.write_bytes(text_pdf_bytes(_PARTIAL_INVOICE_LINES))
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
        pdf_path.write_bytes(text_pdf_bytes(_FULL_INVOICE_LINES))
        svc = _make_svc(isolated_settings, secure_objects)
        record = svc.add(bucket_id=_BUCKET_ID, source_path=pdf_path).record

        empty_dir = tmp_path_factory.mktemp("no-write-expected-from-store")
        extract_invoice_draft_from_evidence(
            bucket_id=_BUCKET_ID,
            evidence_id=record.evidence_id,
            settings=isolated_settings,
        )

        assert scan_directory(empty_dir) == ()


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

    ``transcribe_text_layer`` (the acquisition-stage primitive) still refuses on a
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
        body = STR_KEYED_MAPPING_ADAPTER.validate_python(observed["body"])
        messages = _json_array(body["messages"])
        user_message = STR_KEYED_MAPPING_ADAPTER.validate_python(messages[-1])
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
        assert scan_directory(empty_dir) == ()

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
        seed_test_profile_record(
            UserProfileRecord(
                setup_state=ProfileSetupState.COMPLETE,
                profile_id=_BUCKET_ID,
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
        # The refusal is instructive through its TYPED payload, not prose: the
        # verdict builder deliberately keeps no message string, so the failed
        # condition and the capability fact are what tell the caller why.
        assert dict(raised.value.context)["llm_vision_enabled"] is False
        assert raised.value.terminal_precondition_verdict is not None
        assert raised.value.terminal_precondition_verdict.failed_condition_id == (
            LedgerPreconditionCondition.EVIDENCE_VISION_CAPABILITY_ENABLED.value
        )


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
        pdf_path.write_bytes(text_pdf_bytes(_FULL_INVOICE_LINES))
        svc = _make_svc(isolated_settings, secure_objects)
        record = svc.add(bucket_id=_BUCKET_ID, source_path=pdf_path).record
        repo = self._repo(secure_objects)

        confirmation = confirm_invoice_draft_from_evidence(
            counterparty_country="ES",
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

    def test_extracting_from_a_catalogue_invoice_id_refuses_on_bytes_not_existence(
        self,
        isolated_settings: Settings,
        secure_objects: SecureObjectRepository,
        tmp_path: Path,
    ) -> None:
        """A confirmed invoice id is a valid evidence reference with no document.

        ``purchase_invoice_evidence_id`` accepts an id from either space, so pasting
        the confirmed invoice id where the evidence id goes is a realistic operator
        slip. The refusal must say the reference carries no document bytes -- telling
        the operator no such record exists would send them hunting a record that is
        genuinely there.
        """
        pdf_path = tmp_path / "factura.pdf"
        pdf_path.write_bytes(text_pdf_bytes(_FULL_INVOICE_LINES))
        svc = _make_svc(isolated_settings, secure_objects)
        record = svc.add(bucket_id=_BUCKET_ID, source_path=pdf_path).record
        confirmation = confirm_invoice_draft_from_evidence(
            counterparty_country="ES",
            bucket_id=_BUCKET_ID,
            kind=InvoiceKind.RECEIVED,
            evidence_id=record.evidence_id,
            counterparty_name="Acme Suministros SL",
            settings=isolated_settings,
            invoice_repository=self._repo(secure_objects),
        )

        with pytest.raises(PurchaseInvoiceEvidenceInputError) as excinfo:
            extract_invoice_draft_from_evidence(
                bucket_id=_BUCKET_ID,
                evidence_id=confirmation.invoice.invoice_id,
                settings=isolated_settings,
            )

        # PurchaseInvoiceEvidenceNotFoundError is a sibling class, not a subclass, so
        # `pytest.raises` above already excludes the "no such record" refusal.
        assert excinfo.value.context == {"evidence_id": confirmation.invoice.invoice_id}

    def test_confirm_is_idempotent_guarded_on_identical_resolved_fields(
        self,
        isolated_settings: Settings,
        secure_objects: SecureObjectRepository,
        tmp_path: Path,
    ) -> None:
        pdf_path = tmp_path / "factura.pdf"
        pdf_path.write_bytes(text_pdf_bytes(_FULL_INVOICE_LINES))
        svc = _make_svc(isolated_settings, secure_objects)
        record = svc.add(bucket_id=_BUCKET_ID, source_path=pdf_path).record
        repo = self._repo(secure_objects)

        first = confirm_invoice_draft_from_evidence(
            counterparty_country="ES",
            bucket_id=_BUCKET_ID,
            kind=InvoiceKind.RECEIVED,
            evidence_id=record.evidence_id,
            counterparty_name="Acme Suministros SL",
            settings=isolated_settings,
            invoice_repository=repo,
        )
        assert first.created is True

        second = confirm_invoice_draft_from_evidence(
            counterparty_country="ES",
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
        pdf_path.write_bytes(text_pdf_bytes(_FULL_INVOICE_LINES))
        svc = _make_svc(isolated_settings, secure_objects)
        record = svc.add(bucket_id=_BUCKET_ID, source_path=pdf_path).record
        repo = self._repo(secure_objects)

        confirmation = confirm_invoice_draft_from_evidence(
            counterparty_country="ES",
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
        pdf_path.write_bytes(text_pdf_bytes(_FULL_INVOICE_LINES))
        svc = _make_svc(isolated_settings, secure_objects)
        record = svc.add(bucket_id=_BUCKET_ID, source_path=pdf_path).record
        repo = self._repo(secure_objects)

        confirmation = confirm_invoice_draft_from_evidence(
            counterparty_country="ES",
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
        pdf_path.write_bytes(text_pdf_bytes(_PARTIAL_INVOICE_LINES))
        svc = _make_svc(isolated_settings, secure_objects)
        record = svc.add(bucket_id=_BUCKET_ID, source_path=pdf_path).record
        repo = self._repo(secure_objects)

        with pytest.raises(PurchaseInvoiceEvidenceInputError):
            confirm_invoice_draft_from_evidence(
                counterparty_country="ES",
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
        pdf_path.write_bytes(text_pdf_bytes(_FULL_INVOICE_LINES))
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
        # Since the confirm path began ASSERTING the supplied tax id against
        # the extracted one, an override that disagrees is refused earlier and
        # more specifically, as a ``PurchaseInvoiceEvidenceInputError`` naming
        # the field. The property under test is unchanged -- an invalid
        # override refuses rather than minting a malformed invoice -- and the
        # checksum refusal below still governs the case where extraction found
        # no tax id to compare against.
        with pytest.raises((InvoiceValidationError, ValidationError, PurchaseInvoiceEvidenceInputError)):
            confirm_invoice_draft_from_evidence(
                counterparty_country="ES",
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
        pdf_path.write_bytes(text_pdf_bytes(_FULL_INVOICE_LINES))
        svc = _make_svc(isolated_settings, secure_objects)
        record = svc.add(bucket_id=_BUCKET_ID, source_path=pdf_path).record
        repo = self._repo(secure_objects)

        empty_dir = tmp_path_factory.mktemp("no-write-expected-confirm")
        confirm_invoice_draft_from_evidence(
            counterparty_country="ES",
            bucket_id=_BUCKET_ID,
            kind=InvoiceKind.RECEIVED,
            evidence_id=record.evidence_id,
            counterparty_name="Acme Suministros SL",
            settings=isolated_settings,
            invoice_repository=repo,
        )

        assert scan_directory(empty_dir) == ()

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
        pdf_path.write_bytes(text_pdf_bytes(_FULL_INVOICE_LINES))
        svc = _make_svc(isolated_settings, secure_objects)
        record = svc.add(bucket_id=_BUCKET_ID, source_path=pdf_path).record
        assert record.attachment_id is not None
        repo = self._repo(secure_objects)

        confirmation = confirm_invoice_draft_from_evidence(
            counterparty_country="ES",
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
        pdf_path.write_bytes(text_pdf_bytes(_PARTIAL_INVOICE_LINES))
        svc = _make_svc(isolated_settings, secure_objects)
        record = svc.add(bucket_id=_BUCKET_ID, source_path=pdf_path).record
        assert record.attachment_id is not None
        repo = self._repo(secure_objects)

        confirmation = confirm_invoice_draft_from_evidence(
            counterparty_country="ES",
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
        pdf_path.write_bytes(text_pdf_bytes(_FULL_INVOICE_LINES))
        svc = _make_svc(isolated_settings, secure_objects)
        record = svc.add(bucket_id=_BUCKET_ID, source_path=pdf_path).record
        assert record.attachment_id is not None
        repo = self._repo(secure_objects)

        first = confirm_invoice_draft_from_evidence(
            counterparty_country="ES",
            bucket_id=_BUCKET_ID,
            kind=InvoiceKind.RECEIVED,
            evidence_id=record.evidence_id,
            counterparty_name="Acme Suministros SL",
            settings=isolated_settings,
            invoice_repository=repo,
        )
        assert first.created is True

        second = confirm_invoice_draft_from_evidence(
            counterparty_country="ES",
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
