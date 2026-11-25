"""The page renderer draws real PDF, JPEG and PNG bytes within its bounds, and refuses by type."""

from __future__ import annotations

from io import BytesIO

import pytest
from PIL import Image

from .....application.ledger.evidence_page_contracts import EvidencePageMediaType
from .....application.ledger.evidence_page_errors import (
    LedgerEvidencePageOutOfRangeError,
    LedgerEvidencePageTooLargeError,
    LedgerEvidencePageUnreadableError,
)
from .....tests.pdf_fixtures import multi_page_text_pdf_bytes
from ..page_image import PageImageRenderer

pytestmark = [pytest.mark.unit, pytest.mark.hex_inbound_adapter]

_IMAGE_BOUND = 8 * 1024 * 1024
_PNG_SIGNATURE = b"\x89PNG\r\n\x1a\n"


def _photo(size: tuple[int, int], *, image_format: str, orientation: int | None = None) -> bytes:
    """A real image whose left half is dark and right half light, so a turn can be seen."""
    image = Image.new("RGB", size, (250, 250, 250))
    image.paste((10, 10, 10), (0, 0, size[0] // 2, size[1]))
    buffer = BytesIO()
    if orientation is None:
        image.save(buffer, format=image_format)
    else:
        exif = Image.Exif()
        exif[0x0112] = orientation
        image.save(buffer, format=image_format, exif=exif)
    return buffer.getvalue()


def _decoded(png: bytes) -> Image.Image:
    assert png.startswith(_PNG_SIGNATURE)
    image = Image.open(BytesIO(png), formats=("PNG",))
    image.load()
    return image


def test_a_pdf_page_is_drawn_at_the_asked_width_with_its_page_count() -> None:
    pdf = multi_page_text_pdf_bytes(("First page",), ("Second page",), ("Third page",))

    page = PageImageRenderer().render(
        pdf, media_type=EvidencePageMediaType.PDF, page=2, max_width=900, max_image_bytes=_IMAGE_BOUND
    )

    assert page.page_count == 3
    assert page.width == 900
    # A4 is 595 by 842 points, so the drawn page keeps that shape.
    assert page.height == pytest.approx(900 * 842 / 595, abs=2)
    assert _decoded(page.png).size == (page.width, page.height)


def test_a_page_beyond_the_pdf_is_refused() -> None:
    pdf = multi_page_text_pdf_bytes(("Only page",))

    with pytest.raises(LedgerEvidencePageOutOfRangeError):
        PageImageRenderer().render(
            pdf, media_type=EvidencePageMediaType.PDF, page=2, max_width=900, max_image_bytes=_IMAGE_BOUND
        )


def test_a_wide_jpeg_is_scaled_down_and_written_as_png() -> None:
    page = PageImageRenderer().render(
        _photo((3000, 1500), image_format="JPEG"),
        media_type=EvidencePageMediaType.JPEG,
        page=1,
        max_width=1200,
        max_image_bytes=_IMAGE_BOUND,
    )

    assert (page.page_count, page.width, page.height) == (1, 1200, 600)
    assert _decoded(page.png).size == (1200, 600)


def test_a_photo_is_turned_upright_from_its_exif_orientation() -> None:
    # Orientation 6 asks a viewer to turn the stored pixels a quarter clockwise.
    page = PageImageRenderer().render(
        _photo((400, 200), image_format="JPEG", orientation=6),
        media_type=EvidencePageMediaType.JPEG,
        page=1,
        max_width=1200,
        max_image_bytes=_IMAGE_BOUND,
    )

    assert (page.width, page.height) == (200, 400)
    upright = _decoded(page.png).convert("L")
    # The dark left half of the stored photo is now the top half.
    top, bottom = upright.getpixel((100, 50)), upright.getpixel((100, 350))
    assert isinstance(top, int)
    assert isinstance(bottom, int)
    assert top < 100
    assert bottom > 150


def test_a_narrow_png_keeps_its_size() -> None:
    page = PageImageRenderer().render(
        _photo((300, 120), image_format="PNG"),
        media_type=EvidencePageMediaType.PNG,
        page=1,
        max_width=1200,
        max_image_bytes=_IMAGE_BOUND,
    )

    assert (page.width, page.height) == (300, 120)


def test_an_image_has_only_its_first_page() -> None:
    with pytest.raises(LedgerEvidencePageOutOfRangeError):
        PageImageRenderer().render(
            _photo((300, 120), image_format="PNG"),
            media_type=EvidencePageMediaType.PNG,
            page=2,
            max_width=1200,
            max_image_bytes=_IMAGE_BOUND,
        )


@pytest.mark.parametrize(
    ("source", "media_type"),
    [
        (b"%PDF-1.4\nnot really a document", EvidencePageMediaType.PDF),
        (_photo((40, 40), image_format="PNG"), EvidencePageMediaType.JPEG),
        (_photo((40, 40), image_format="JPEG"), EvidencePageMediaType.PNG),
        (b"\xff\xd8\xff\xe0 truncated", EvidencePageMediaType.JPEG),
    ],
    ids=["broken-pdf", "png-declared-jpeg", "jpeg-declared-png", "truncated-jpeg"],
)
def test_bytes_that_are_not_their_declared_type_are_unreadable(
    source: bytes, media_type: EvidencePageMediaType
) -> None:
    with pytest.raises(LedgerEvidencePageUnreadableError):
        PageImageRenderer().render(source, media_type=media_type, page=1, max_width=800, max_image_bytes=_IMAGE_BOUND)


def test_a_source_above_the_byte_bound_is_refused_before_it_is_decoded() -> None:
    source = _photo((600, 400), image_format="PNG")

    with pytest.raises(LedgerEvidencePageTooLargeError):
        PageImageRenderer(max_source_bytes=len(source) - 1).render(
            source, media_type=EvidencePageMediaType.PNG, page=1, max_width=800, max_image_bytes=_IMAGE_BOUND
        )


def test_a_drawn_page_above_the_image_bound_is_refused() -> None:
    pdf = multi_page_text_pdf_bytes(("A page",))

    with pytest.raises(LedgerEvidencePageTooLargeError):
        PageImageRenderer().render(
            pdf, media_type=EvidencePageMediaType.PDF, page=1, max_width=900, max_image_bytes=1_000
        )


def test_an_image_declaring_more_pixels_than_the_bound_is_refused_before_decoding() -> None:
    # A PNG header claiming 10 000 by 10 000 pixels compresses to almost nothing.
    source = BytesIO()
    Image.new("1", (10_000, 10_000)).save(source, format="PNG")

    with pytest.raises(LedgerEvidencePageTooLargeError):
        PageImageRenderer().render(
            source.getvalue(),
            media_type=EvidencePageMediaType.PNG,
            page=1,
            max_width=800,
            max_image_bytes=_IMAGE_BOUND,
        )
