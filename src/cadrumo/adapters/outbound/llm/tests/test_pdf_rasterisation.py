"""In-memory PDF rasterisation for the vision reader.

A scan-only PDF is rendered to base64 PNG pages in process memory on this
computer, whatever lane later reads the pages; an unreadable PDF refuses with
the stage that failed.
"""

from __future__ import annotations

import base64
import io

import pytest
from PIL import Image

from ..errors import LLMPdfRasterisationError
from ..pdf_rasterisation import rasterise_pdf_pages_to_base64_png

pytestmark = [pytest.mark.unit, pytest.mark.hex_outbound_adapter]

_PNG_MAGIC = b"\x89PNG\r\n\x1a\n"


def _scan_only_pdf(pages: int) -> bytes:
    """Build a raster (text-layer-free) PDF of ``pages`` pages in memory."""
    images = [Image.new("RGB", (240, 140), colour) for colour in ("white", "black", "red")[:pages]]
    buffer = io.BytesIO()
    images[0].save(buffer, format="PDF", save_all=True, append_images=images[1:])
    return buffer.getvalue()


def test_each_page_rasterises_to_one_in_memory_png_in_page_order() -> None:
    pages = rasterise_pdf_pages_to_base64_png(_scan_only_pdf(2))

    assert len(pages) == 2
    decoded = [Image.open(io.BytesIO(base64.b64decode(page))) for page in pages]
    assert all(base64.b64decode(page)[:8] == _PNG_MAGIC for page in pages)
    # Page order is the document's: the first page is white, the second black.
    assert decoded[0].convert("L").getpixel((0, 0)) == 255
    assert decoded[1].convert("L").getpixel((0, 0)) == 0


def test_bytes_that_are_not_a_pdf_refuse_at_document_open() -> None:
    with pytest.raises(LLMPdfRasterisationError) as refusal:
        rasterise_pdf_pages_to_base64_png(b"not a pdf")

    assert refusal.value.context is not None
    assert refusal.value.context["rasterisation_stage"] == "document_open"
