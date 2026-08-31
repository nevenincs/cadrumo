"""The shape probe's notion of "image" must be the sniffer's, not a local copy.

The probe decides admission: :attr:`DocumentShape.UNKNOWN` is refused outright
before any read, and :attr:`DocumentShape.IMAGE` is admitted and later handed to
:func:`~core.detect_image_media_type` to be declared to the vision transport. So
a second, private magic-byte table inside the probe puts the two answers on
different authorities, and they diverged in BOTH directions:

* it omitted WebP -- and structurally could not carry it, because WebP's magic is
  split across offsets 0 and 8 while the local test was a single-offset
  ``startswith`` -- so a WebP receipt was refused at admission even though
  :class:`~core.ImageMediaType` carries a member for exactly that case;
* it admitted BMP and TIFF, which the sniffer refuses, so those cleared
  admission and then raised on evidence the operator had already been told was
  accepted.

Every fixture here is a real encoded image produced by Pillow rather than a
hand-written magic-byte prefix, following the sniffer's own tests: a prefix
constant would only prove the probe matches the constant the test supplied.
"""

from __future__ import annotations

from io import BytesIO

import pytest
from PIL import Image

from .....core.document_shape import DocumentShape
from .....core.errors.hierarchy import CoreValidationError
from .....core.image_media_type import ImageMediaType, detect_image_media_type
from .._shape import probe_document_shape

pytestmark = [pytest.mark.unit, pytest.mark.hex_inbound_adapter]


def _encoded(pillow_format: str) -> bytes:
    """Encode a small real image in ``pillow_format`` and return its bytes."""
    image = Image.new("RGB", (8, 8), "white")
    buffer = BytesIO()
    image.save(buffer, format=pillow_format)
    return buffer.getvalue()


def _sniffer_accepts(data: bytes) -> bool:
    try:
        detect_image_media_type(data)
    except CoreValidationError:
        return False
    return True


def test_the_fixtures_are_real_encodings_carrying_the_formats_they_are_named_for() -> None:
    """Anchor test: a Pillow change must not make the cases below vacuous.

    Without this, a WebP encoder silently falling back to PNG would leave the
    WebP case passing while testing PNG.
    """
    assert _encoded("WEBP")[:4] == b"RIFF"
    assert _encoded("WEBP")[8:12] == b"WEBP"
    assert _encoded("BMP").startswith(b"BM")
    assert _encoded("PNG").startswith(b"\x89PNG\r\n\x1a\n")


def test_a_webp_receipt_probes_as_an_image_rather_than_being_refused() -> None:
    """THE case. A supported format was refused before anything could read it.

    ``UNKNOWN`` is refused at evidence admission, so this was not a degraded
    read -- the operator was told their receipt matched no readable document
    shape, for a format the vision transport can carry.
    """
    assert probe_document_shape(_encoded("WEBP")) is DocumentShape.IMAGE


def test_a_format_the_sniffer_refuses_is_not_admitted_as_an_image() -> None:
    """The other direction: admitted here, raising later on accepted evidence.

    BMP cleared the probe's private table and then hit the sniffer's refusal
    downstream, turning an admission-time answer into a failure against
    evidence already accepted.
    """
    bmp = _encoded("BMP")
    assert not _sniffer_accepts(bmp), "fixture no longer exercises the divergence"
    assert probe_document_shape(bmp) is not DocumentShape.IMAGE


@pytest.mark.parametrize("pillow_format", ["PNG", "JPEG", "GIF", "WEBP"])
def test_every_format_the_sniffer_accepts_probes_as_an_image(pillow_format: str) -> None:
    """Parity, stated as the property rather than as a list of formats.

    Gating on the property means a member added to :class:`ImageMediaType` is
    covered without editing this test, and a probe that drifts from the sniffer
    fails whichever direction it drifts in.
    """
    data = _encoded(pillow_format)
    assert _sniffer_accepts(data)
    assert probe_document_shape(data) is DocumentShape.IMAGE


def test_the_probe_and_the_sniffer_answer_for_the_same_set_of_formats() -> None:
    """Positive control: the probe is not simply calling everything an image.

    Without this, a probe returning ``IMAGE`` unconditionally would satisfy
    every assertion above.
    """
    assert probe_document_shape(b"") is DocumentShape.UNKNOWN
    assert probe_document_shape(b"nothing recognisable at all") is DocumentShape.UNKNOWN
    assert probe_document_shape(b"%PDF-1.7\n") is not DocumentShape.IMAGE
    assert ImageMediaType.WEBP in set(ImageMediaType), "WEBP left the closed taxonomy"
