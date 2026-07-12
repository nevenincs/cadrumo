"""Unit tests for :mod:`aeat.adapters.inbound.sanitizer._metadata`.

The tests synthesise PDFs in-process (no fixture dep) covering:

* Every legacy DocInfo key the sanitiser must wipe.
* A canonical XMP packet declaring PDF/A-1B conformance — the same
  shape AEAT's modern justificantes ship with, so the
  ``pdfa_claim_invalidated`` warning is wired up.
* A no-op path when the source PDF carries no DocInfo / XMP at all.
"""

from __future__ import annotations

import io

import pikepdf
import pytest

from .._metadata import scrub_docinfo, scrub_xmp

pytestmark = [pytest.mark.unit, pytest.mark.hex_inbound_adapter]


def _new_pdf_with_docinfo() -> pikepdf.Pdf:
    """Constructs a one-page PDF with a populated DocInfo dictionary."""
    pdf = pikepdf.Pdf.new()
    pdf.add_blank_page(page_size=(612, 792))
    pdf.docinfo["/Title"] = pikepdf.String("real title")
    pdf.docinfo["/Subject"] = pikepdf.String("real subject")
    pdf.docinfo["/Author"] = pikepdf.String("real author")
    pdf.docinfo["/Keywords"] = pikepdf.String("real keywords")
    pdf.docinfo["/Creator"] = pikepdf.String("real creator")
    pdf.docinfo["/Producer"] = pikepdf.String("real producer")
    pdf.docinfo["/CreationDate"] = pikepdf.String("D:20260424123456+02'00'")
    pdf.docinfo["/ModDate"] = pikepdf.String("D:20260425010101+02'00'")
    return pdf


def _new_pdf_with_pdfa_xmp() -> pikepdf.Pdf:
    """Constructs a one-page PDF with an XMP packet claiming PDF/A-1B."""
    pdf = pikepdf.Pdf.new()
    pdf.add_blank_page(page_size=(612, 792))
    with pdf.open_metadata(set_pikepdf_as_editor=False) as metadata:
        metadata["dc:title"] = "real title"
        metadata["dc:description"] = "real description"
        metadata["dc:creator"] = ["real creator"]
        metadata["pdf:Keywords"] = "real keywords"
        metadata["pdfaid:part"] = "1"
        metadata["pdfaid:conformance"] = "B"
    return pdf


def _round_trip(pdf: pikepdf.Pdf) -> pikepdf.Pdf:
    """Save ``pdf`` to a buffer and re-open. Forces structural settling."""
    buffer = io.BytesIO()
    pdf.save(buffer)
    buffer.seek(0)
    return pikepdf.Pdf.open(buffer)


class TestScrubDocinfo:
    """The DocInfo dictionary is wiped wholesale."""

    def test_drops_every_known_key(self) -> None:
        pdf = _new_pdf_with_docinfo()
        result = scrub_docinfo(pdf)
        assert result.surface == "docinfo_other"
        assert result.count >= 8  # the eight populated keys, possibly more

        re_opened = _round_trip(pdf)
        assert re_opened.trailer.get("/Info") is None

    def test_no_op_when_docinfo_absent(self) -> None:
        pdf = pikepdf.Pdf.new()
        pdf.add_blank_page(page_size=(612, 792))
        # New PDFs may carry a /Producer key by default; clear it explicitly.
        if pdf.trailer.get("/Info") is not None:
            del pdf.trailer["/Info"]
        result = scrub_docinfo(pdf)
        assert result.count == 0


class TestScrubXmp:
    """XMP wipe + rewrite both clear PII surfaces and flag PDF/A claims."""

    def test_delete_strategy_drops_packet(self) -> None:
        pdf = _new_pdf_with_pdfa_xmp()
        scrubbed, warnings = scrub_xmp(pdf, strategy="delete")
        assert scrubbed.surface == "xmp_packet"
        assert scrubbed.count == 1
        codes = {w.code for w in warnings}
        assert "pdfa_claim_invalidated" in codes

        re_opened = _round_trip(pdf)
        assert "/Metadata" not in re_opened.Root

    def test_rewrite_strategy_keeps_packet_clears_pii(self) -> None:
        pdf = _new_pdf_with_pdfa_xmp()
        scrubbed, warnings = scrub_xmp(pdf, strategy="rewrite")
        assert scrubbed.surface == "xmp_packet"
        assert scrubbed.count >= 5  # title, description, creator, keywords, pdfaid:* keys
        codes = {w.code for w in warnings}
        assert "pdfa_claim_invalidated" in codes

        re_opened = _round_trip(pdf)
        # Packet still exists, but PII keys are gone.
        assert "/Metadata" in re_opened.Root
        with re_opened.open_metadata(set_pikepdf_as_editor=False) as metadata:
            keys = list(metadata)
            assert not any(k.endswith("}title") for k in keys)
            assert not any(k.endswith("}Keywords") for k in keys)
            assert not any("pdfa/ns/id" in k for k in keys)

    def test_no_op_when_xmp_absent(self) -> None:
        pdf = pikepdf.Pdf.new()
        pdf.add_blank_page(page_size=(612, 792))
        # Drop any auto-created XMP first so the test starts clean.
        if "/Metadata" in pdf.Root:
            del pdf.Root.Metadata
        scrubbed, warnings = scrub_xmp(pdf, strategy="delete")
        assert scrubbed.count == 0
        assert warnings == ()

    def test_no_pdfa_warning_when_claim_absent(self) -> None:
        pdf = pikepdf.Pdf.new()
        pdf.add_blank_page(page_size=(612, 792))
        with pdf.open_metadata(set_pikepdf_as_editor=False) as metadata:
            metadata["dc:title"] = "real title"
        _, warnings = scrub_xmp(pdf, strategy="delete")
        codes = {w.code for w in warnings}
        assert "pdfa_claim_invalidated" not in codes
