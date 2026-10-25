"""In-memory rasterisation of a PDF into page images for a vision reader.

A scan-only or image-only PDF has no text layer to read, so each page is
rendered to a PNG in process memory and handed to the vision role as an image
attachment. Rendering happens here, on this computer, whatever lane later reads
the pages. Nothing is written to disk.
"""

from __future__ import annotations

import base64
from io import BytesIO
from typing import Protocol, cast

from ....core.optional_extras import LLM_EXTRA, require_optional_extra
from .errors import LLMPdfRasterisationError

__all__ = ["rasterise_pdf_pages_to_base64_png"]


class _PillowImageLike(Protocol):
    def save(self, fp: BytesIO, format: str | None = None) -> None: ...


class _PdfiumBitmapLike(Protocol):
    def to_pil(self) -> _PillowImageLike: ...

    def close(self) -> None: ...


class _PdfiumPageLike(Protocol):
    def render(self, *, scale: float) -> _PdfiumBitmapLike: ...

    def close(self) -> None: ...


def rasterise_pdf_pages_to_base64_png(pdf_bytes: bytes, *, scale: float = 2.0) -> tuple[str, ...]:
    """Rasterise each page of an in-memory PDF to a base64-encoded PNG, on-host.

    Renders every page in process memory via pypdfium2 and Pillow so a vision
    model can read a scan-only or image-only PDF that has no extractable
    text layer. Nothing is written to disk and nothing leaves the host
    (``sensitive-financial-data-secure-storage-only``).

    Args:
        pdf_bytes: In-memory PDF bytes (read transiently from secure storage).
        scale: pypdfium2 render scale; a larger value yields a larger raster.

    Returns:
        One base64-encoded PNG string per page, in page order.

    Raises:
        MissingOptionalExtraError: If the ``llm`` extra is not installed.
        LLMPdfRasterisationError: If the PDF cannot be rendered.
    """
    # The feature-boundary guard sits ahead of the lazy import, per the
    # established convention. What it refuses is an operator who reached the
    # rasteriser without opting into the inference closure at all; the refusal
    # names the install command instead of letting the render proceed into a
    # boundary the rest of the extra is absent from. It does NOT stand in for a
    # missing Pillow -- Pillow is an unconditional base dependency, so its
    # absence is a broken installation rather than a declined extra, and the
    # bare ``except Exception`` below correctly owns the render failures that
    # remain.
    require_optional_extra(LLM_EXTRA)
    import pypdfium2 as pdfium  # lazy: keep the adapter import light

    try:
        document = pdfium.PdfDocument(pdf_bytes)
    except Exception as exc:
        raise LLMPdfRasterisationError(
            context={"rasterisation_stage": "document_open", "rasterisation_error_type": type(exc).__name__},
        ) from exc
    try:
        pages: list[str] = []
        for page in document:
            # CAST-RATIONALE-PDFIUM-PAGE: pypdfium2 yields untyped page objects; the adapter only needs render/close.
            pdf_page = cast("_PdfiumPageLike", page)
            try:
                bitmap = pdf_page.render(scale=scale)
                try:
                    image = bitmap.to_pil()
                    buffer = BytesIO()
                    image.save(buffer, format="PNG")
                    pages.append(base64.b64encode(buffer.getvalue()).decode("ascii"))
                finally:
                    bitmap.close()
            finally:
                pdf_page.close()
        return tuple(pages)
    except Exception as exc:
        raise LLMPdfRasterisationError(
            context={"rasterisation_stage": "page_render", "rasterisation_error_type": type(exc).__name__},
        ) from exc
    finally:
        document.close()
