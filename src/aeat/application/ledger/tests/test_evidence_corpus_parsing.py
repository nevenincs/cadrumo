"""Adversarial parsing tests against the real evidence corpus.

Drives the actual on-host evidence parsers -- pdfplumber text extraction and the
pypdfium2 rasteriser -- over a corpus of real, licence-clean invoice files
(Wikimedia Commons public-domain images, an Apache-2.0 EN16931 reference invoice
PDF) plus generated adversarial variants (prompt-injection text, foreign
language, malformed and empty PDFs). The parsers must extract real content,
fall back from a text-layer-free document to rasterisation, and fail *loudly*
(raise, never crash) on hostile input -- nothing is written outside memory.
"""

from __future__ import annotations

import base64
import json
from io import BytesIO
from pathlib import Path

import pytest
from PIL import Image

from ....adapters.inbound.pdf._pdfplumber import extract_pages_text_from_bytes
from ....adapters.outbound.llm import rasterise_pdf_pages_to_base64_png

pytestmark = [pytest.mark.unit, pytest.mark.hex_application]

_CORPUS = Path(__file__).parent / "_evidence_corpus"
_PNG_MAGIC = b"\x89PNG\r\n\x1a\n"


def _read(name: str) -> bytes:
    return (_CORPUS / name).read_bytes()


def test_real_text_layer_invoice_extracts_content() -> None:
    """The real EN16931 reference invoice yields its text layer for the classifier."""
    pages = extract_pages_text_from_bytes(
        _read("zugferd_en16931_invoice.pdf"), error_class=ValueError, pdf_label="the invoice",
    )
    joined = "\n".join(pages)
    assert joined.strip()
    assert any(token in joined for token in ("Rechnung", "Invoice", "RECHNUNG", "EUR"))


def test_real_scanned_pdf_has_no_text_layer_then_rasterises() -> None:
    """A real image-only invoice PDF has no text layer, so it falls back to rasterisation."""
    data = _read("scanned_invoice_from_commons_1.pdf")
    with pytest.raises(ValueError):  # no usable text layer -> caller routes to the vision reader
        extract_pages_text_from_bytes(data, error_class=ValueError, pdf_label="the invoice")
    pages = rasterise_pdf_pages_to_base64_png(data)
    assert pages
    assert base64.b64decode(pages[0])[:8] == _PNG_MAGIC


def test_real_image_invoice_is_a_valid_image() -> None:
    """The real public-domain invoice images load (the image-evidence base64 path)."""
    for name in ("commons_invoice_1.jpg", "commons_invoice_2.jpg"):
        image = Image.open(BytesIO(_read(name)))
        assert image.format in {"JPEG", "PNG"}
        assert image.size[0] > 0 and image.size[1] > 0


def test_foreign_language_invoice_still_extracts_text() -> None:
    """A non-Spanish (Hungarian) invoice still yields a usable text layer."""
    pages = extract_pages_text_from_bytes(
        _read("adversarial_foreign_language_invoice.pdf"), error_class=ValueError, pdf_label="the invoice",
    )
    assert any("SZAMLA" in p or "AFA" in p or "EUR" in p for p in pages)


def test_prompt_injection_invoice_extracts_text_without_executing_it() -> None:
    """Prompt-injection text in the invoice is extracted as inert text, not obeyed.

    Extraction returns the hostile text verbatim; the safety boundary is the
    downstream allow-list parser (covered by ``test_llm_parse_adversarial``), not
    the extractor, which must simply not crash on adversarial content.
    """
    pages = extract_pages_text_from_bytes(
        _read("adversarial_prompt_injection_invoice.pdf"), error_class=ValueError, pdf_label="the invoice",
    )
    joined = "\n".join(pages)
    assert "SYSTEM OVERRIDE" in joined  # extracted verbatim as text, carries no authority


def test_malformed_pdf_raises_not_crashes() -> None:
    """A PDF header followed by garbage fails loudly on both parsers, never silently."""
    data = _read("adversarial_malformed.pdf")
    with pytest.raises(Exception):  # noqa: B017 — any parser error is acceptable; the contract is "raise, not crash"
        extract_pages_text_from_bytes(data, error_class=ValueError, pdf_label="the invoice")
    with pytest.raises(Exception):  # noqa: B017
        rasterise_pdf_pages_to_base64_png(data)


def test_empty_pdf_raises_not_crashes() -> None:
    """A zero-byte .pdf fails loudly rather than producing a bogus result."""
    data = _read("adversarial_empty.pdf")
    assert data == b""
    with pytest.raises(Exception):  # noqa: B017
        rasterise_pdf_pages_to_base64_png(data)


def test_every_corpus_fixture_declares_provenance() -> None:
    """Every corpus fixture carries a provenance sidecar (fixture-provenance rule)."""
    fixtures = [p for p in _CORPUS.iterdir() if not p.name.endswith(".provenance.json")]
    assert fixtures, "corpus must not be empty"
    for fixture in fixtures:
        sidecar = fixture.with_suffix(fixture.suffix + ".provenance.json")
        assert sidecar.exists(), f"missing provenance sidecar for {fixture.name}"
        meta = json.loads(sidecar.read_text(encoding="utf-8"))
        assert meta["provenance"] in {"real_corpus", "synthetic_generated"}
        # Real-corpus fixtures must name a licence and a source; adversarial ones
        # are honestly declared synthetic.
        if meta["provenance"] == "real_corpus":
            assert meta.get("licence")
            assert meta.get("source")
