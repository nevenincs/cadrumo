"""Read back what a calculation summary carries, for verification.

Everything here runs on the core PDF libraries -- pikepdf for structure,
attachments and metadata, pypdfium2 for the text a reader sees -- so verifying a
summary never needs the optional ``pdf`` extra that writing one does.

The visible-layer digest is defined here because the writer and every verifier
must compute it the same way. It is the SHA-256 of the canonical JSON list of
each page's media box, the SHA-256 of its decoded content streams, and the
SHA-256 of each font program it uses, keyed by the font's resource name. A page
carrying an annotation, or any resource other than a font, is reported as an
overlay: such a feature can change what a page shows without changing any byte
the digest covers, and the writer never emits one.

Metadata is read through pikepdf's own metadata interface, which parses the
packet with a namespace-aware parser, so a re-serialised packet reads the same.
"""

from __future__ import annotations

import io
from collections.abc import Mapping
from decimal import Decimal
from typing import Final

import pikepdf
import pypdfium2
from pikepdf import Dictionary

from ....application.modelo.calculation_summary_pdf_ports import (
    CALCULATION_SUMMARY_XMP_NAMESPACE,
    CalculationSummaryPdfContents,
    CalculationSummaryPdfUnreadableError,
)
from ....core.hashing import canonical_json_bytes, sha256_hex

_FONT_RESOURCE: Final[str] = "/Font"
_FONT_PROGRAM_KEYS: Final[tuple[str, ...]] = ("/FontFile2", "/FontFile3", "/FontFile")
_ABSENT_FONT_PROGRAM: Final[str] = "not-embedded"


def _decoded_content(page: pikepdf.Page) -> bytes:
    contents = page.obj.get("/Contents")
    if contents is None:
        return b""
    if isinstance(contents, pikepdf.Array):
        return b"".join(part.read_bytes() for part in contents)
    return contents.read_bytes()


def _number(value: object) -> str:
    """Spell one box coordinate canonically, whatever its stored form."""
    return format(Decimal(str(value)).normalize(), "f")


def _font_program_digest(font: pikepdf.Object) -> str:
    descriptor = font.get("/FontDescriptor")
    if descriptor is None:
        descendants = font.get("/DescendantFonts")
        if descendants is not None and len(descendants) > 0:
            descriptor = descendants[0].get("/FontDescriptor")
    if descriptor is None:
        return _ABSENT_FONT_PROGRAM
    for key in _FONT_PROGRAM_KEYS:
        program = descriptor.get(key)
        if program is not None:
            return sha256_hex(program.read_bytes())
    return _ABSENT_FONT_PROGRAM


def visible_layer_digest(pdf: pikepdf.Pdf) -> tuple[str, tuple[str, ...]]:
    """Return the visible-layer digest of ``pdf`` and the overlays it carries."""
    pages: list[dict[str, object]] = []
    overlays: list[str] = []
    for index, page in enumerate(pdf.pages, start=1):
        annotations = page.obj.get("/Annots")
        if annotations is not None and len(annotations) > 0:
            overlays.append(f"page {index}: annotations")
        resources = page.obj.get("/Resources", Dictionary())
        overlays.extend(f"page {index}: resource {kind}" for kind in resources if kind != _FONT_RESOURCE)
        fonts = resources.get(_FONT_RESOURCE, Dictionary())
        pages.append(
            {
                "media_box": [_number(value) for value in page.mediabox],
                "content_sha256": sha256_hex(_decoded_content(page)),
                "fonts": {str(name): _font_program_digest(font) for name, font in fonts.items()},
            },
        )
    return sha256_hex(canonical_json_bytes(pages)), tuple(overlays)


def _product_metadata(pdf: pikepdf.Pdf) -> Mapping[str, str] | None:
    prefix = "{" + CALCULATION_SUMMARY_XMP_NAMESPACE + "}"
    metadata = pdf.open_metadata(set_pikepdf_as_editor=False, update_docinfo=False)
    found = {key.removeprefix(prefix): str(metadata[key]) for key in metadata if key.startswith(prefix)}
    return found or None


def _page_text(payload: bytes) -> str:
    document = pypdfium2.PdfDocument(payload)
    try:
        texts: list[str] = []
        for index in range(len(document)):
            page = document[index]
            text_page = page.get_textpage()
            try:
                texts.append(text_page.get_text_range())
            finally:
                text_page.close()
                page.close()
        return "\n".join(texts)
    finally:
        document.close()


def read_calculation_summary_pdf(payload: bytes, /) -> CalculationSummaryPdfContents:
    """Recover a summary's embedded files, product metadata, page digest and text.

    Raises:
        CalculationSummaryPdfUnreadableError: ``payload`` is not a PDF these
            libraries can open and read.
    """
    try:
        with pikepdf.open(io.BytesIO(payload)) as pdf:
            attachments = {str(name): spec.get_file().read_bytes() for name, spec in pdf.attachments.items()}
            product_metadata = _product_metadata(pdf)
            digest, overlays = visible_layer_digest(pdf)
        page_text = _page_text(payload)
    except (pikepdf.PdfError, pypdfium2.PdfiumError, ValueError, KeyError, TypeError) as exc:
        raise CalculationSummaryPdfUnreadableError(
            translated_message="application.modelo.errors.calculation_summary_pdf_unreadable",
            context={"error_type": type(exc).__name__},
        ) from exc
    return CalculationSummaryPdfContents(
        attachments=attachments,
        product_metadata=product_metadata,
        visible_layer_sha256=digest,
        visible_layer_overlays=overlays,
        page_text=page_text,
    )


__all__ = ["read_calculation_summary_pdf", "visible_layer_digest"]
