"""Draw one page of a stored PDF, JPEG or PNG as a bounded PNG, in memory.

A PDF page is rasterised with pypdfium2 at the scale that makes it at most the
asked width. A JPEG or PNG is decoded with Pillow, turned upright from its
EXIF orientation and scaled down when it is wider than asked; it is always
written out again as a PNG, so no metadata the source carried reaches the
image. Nothing is written to disk.

Every bound is checked before the expensive step it guards: the source's
bytes before decoding, an image's declared pixel size before its pixels are
decoded, a PDF page's size before it is rasterised, and the encoded PNG
before it is returned.
"""

from __future__ import annotations

import math
from io import BytesIO
from typing import Final

import pypdfium2 as pdfium
from PIL import Image, ImageOps

from ....application.ledger.evidence_page_contracts import (
    EVIDENCE_PAGE_MAX_WIDTH,
    EvidencePageMediaType,
    RenderedEvidencePage,
)
from ....application.ledger.evidence_page_errors import (
    LedgerEvidencePageOutOfRangeError,
    LedgerEvidencePageTooLargeError,
    LedgerEvidencePageUnreadableError,
)
from ..einvoice.xml import MAX_XML_PAYLOAD_BYTES

__all__ = ["EVIDENCE_PAGE_MAX_HEIGHT", "EVIDENCE_PAGE_MAX_PIXELS", "PageImageRenderer"]

EVIDENCE_PAGE_MAX_HEIGHT: Final = 16 * EVIDENCE_PAGE_MAX_WIDTH
"""The tallest image drawn: a till receipt is long, but not without end."""

EVIDENCE_PAGE_MAX_PIXELS: Final = 16 * 1024 * 1024
"""The most pixels one drawn page holds, which bounds the raster in memory to 64 MiB."""

_MAX_SOURCE_PIXELS: Final = 64 * 1024 * 1024
"""The most pixels a source image may declare before its pixels are decoded."""

_MAX_PDF_SCALE: Final = 8.0
"""At most 576 dots per inch, so a postage-stamp page is not blown up without bound."""

_PILLOW_FORMAT: Final = {EvidencePageMediaType.JPEG: "JPEG", EvidencePageMediaType.PNG: "PNG"}


def _fitted(width: float, height: float, max_width: int, *, enlarge: bool) -> tuple[int, int]:
    """The largest size of ``width`` by ``height``'s shape within every output bound.

    A PDF page has no pixel size of its own and is drawn as wide as asked; an
    image is never made larger than it is.
    """
    scale = min(
        max_width / width,
        EVIDENCE_PAGE_MAX_HEIGHT / height,
        math.sqrt(EVIDENCE_PAGE_MAX_PIXELS / (width * height)),
    )
    if not enlarge:
        scale = min(scale, 1.0)
    return max(1, min(max_width, math.floor(width * scale))), max(1, math.floor(height * scale))


def _encoded(image: Image.Image, *, max_image_bytes: int) -> bytes:
    if image.mode not in {"1", "L", "LA", "P", "RGB", "RGBA"}:
        image = image.convert("RGBA" if "A" in image.getbands() else "RGB")
    buffer = BytesIO()
    image.save(buffer, format="PNG")
    png = buffer.getvalue()
    if len(png) > max_image_bytes:
        raise LedgerEvidencePageTooLargeError()
    return png


class PageImageRenderer:
    """The page renderer the page read runs in its worker."""

    def __init__(self, *, max_source_bytes: int = MAX_XML_PAYLOAD_BYTES) -> None:
        """Bound the documents this renderer accepts; the default is the e-invoice reader's bound."""
        self._max_source_bytes = max_source_bytes

    @property
    def max_source_bytes(self) -> int:
        """The largest document, in bytes, this renderer accepts."""
        return self._max_source_bytes

    def render(
        self,
        source: bytes,
        *,
        media_type: EvidencePageMediaType,
        page: int,
        max_width: int,
        max_image_bytes: int,
    ) -> RenderedEvidencePage:
        """Return page ``page`` (1-based) of ``source`` at most ``max_width`` pixels wide."""
        if len(source) > self._max_source_bytes:
            raise LedgerEvidencePageTooLargeError()
        if media_type is EvidencePageMediaType.PDF:
            return self._pdf_page(source, page=page, max_width=max_width, max_image_bytes=max_image_bytes)
        return self._image(
            source, media_type=media_type, page=page, max_width=max_width, max_image_bytes=max_image_bytes
        )

    @staticmethod
    def _pdf_page(source: bytes, *, page: int, max_width: int, max_image_bytes: int) -> RenderedEvidencePage:
        try:
            document = pdfium.PdfDocument(source)
        except pdfium.PdfiumError:
            raise LedgerEvidencePageUnreadableError() from None
        try:
            page_count = len(document)
            if page_count < 1:
                raise LedgerEvidencePageUnreadableError()
            if page > page_count:
                raise LedgerEvidencePageOutOfRangeError()
            pdf_page = document[page - 1]
            try:
                points_wide, points_high = pdf_page.get_size()
                if not (points_wide > 0 and points_high > 0):
                    raise LedgerEvidencePageUnreadableError()
                width, _ = _fitted(points_wide, points_high, max_width, enlarge=True)
                bitmap = pdf_page.render(scale=min(width / points_wide, _MAX_PDF_SCALE))
                try:
                    # The raster shares the bitmap's memory, so it is copied out
                    # before the bitmap is released. A rotated page draws turned,
                    # so the raster is held to the bounds again.
                    raster = bitmap.to_pil()
                    fitted = _fitted(raster.width, raster.height, max_width, enlarge=False)
                    image = raster.resize(fitted, Image.Resampling.LANCZOS) if fitted != raster.size else raster.copy()
                finally:
                    bitmap.close()
            finally:
                pdf_page.close()
        except pdfium.PdfiumError:
            raise LedgerEvidencePageUnreadableError() from None
        finally:
            document.close()
        return RenderedEvidencePage(
            page_count=page_count,
            width=image.width,
            height=image.height,
            png=_encoded(image, max_image_bytes=max_image_bytes),
        )

    @staticmethod
    def _image(
        source: bytes,
        *,
        media_type: EvidencePageMediaType,
        page: int,
        max_width: int,
        max_image_bytes: int,
    ) -> RenderedEvidencePage:
        if page != 1:
            raise LedgerEvidencePageOutOfRangeError()
        try:
            with Image.open(BytesIO(source), formats=(_PILLOW_FORMAT[media_type],)) as opened:
                declared_width, declared_height = opened.size
                if declared_width < 1 or declared_height < 1:
                    raise LedgerEvidencePageUnreadableError()
                if declared_width * declared_height > _MAX_SOURCE_PIXELS:
                    raise LedgerEvidencePageTooLargeError()
                if media_type is EvidencePageMediaType.JPEG:
                    # Decode a large photo at a reduced scale straight away; the
                    # exact size is reached by the resample below.
                    opened.draft("RGB", _fitted(declared_width, declared_height, max_width, enlarge=False))
                upright = ImageOps.exif_transpose(opened)
                fitted = _fitted(upright.width, upright.height, max_width, enlarge=False)
                image = upright.resize(fitted, Image.Resampling.LANCZOS) if fitted != upright.size else upright
                image.load()
        except (OSError, ValueError, SyntaxError, Image.DecompressionBombError):
            raise LedgerEvidencePageUnreadableError() from None
        return RenderedEvidencePage(
            page_count=1,
            width=image.width,
            height=image.height,
            png=_encoded(image, max_image_bytes=max_image_bytes),
        )
