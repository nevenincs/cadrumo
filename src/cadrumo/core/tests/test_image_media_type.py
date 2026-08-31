"""The image-format sniffer that stamps a multimodal input's declared media type.

The bytes reaching this function are whatever the operator attached, and the
answer travels to a provider as a declaration the provider validates against the
same bytes. So the two properties that matter are: it must answer correctly for
every format the product can actually forward, and it must REFUSE anything else
rather than guess -- a guess produces a mislabelled image, and a mislabelled
image is either a hard provider refusal or a silent misread.

Every fixture here is a real encoded image produced by Pillow, not a
hand-written magic-byte prefix: a prefix constant would only prove the function
matches the constant the test itself supplied.
"""

from __future__ import annotations

from io import BytesIO

import pytest
from PIL import Image

from ..image_media_type import ImageMediaType, detect_image_media_type
from ..errors.hierarchy import CoreValidationError

pytestmark = [pytest.mark.unit, pytest.mark.hex_core]


def _encoded(pillow_format: str) -> bytes:
    """Encode a small real image in ``pillow_format`` and return its bytes."""
    image = Image.new("RGB", (8, 8), "white")
    buffer = BytesIO()
    image.save(buffer, format=pillow_format)
    return buffer.getvalue()


@pytest.mark.parametrize(
    ("pillow_format", "expected"),
    [
        ("PNG", ImageMediaType.PNG),
        ("JPEG", ImageMediaType.JPEG),
        ("WEBP", ImageMediaType.WEBP),
        ("GIF", ImageMediaType.GIF),
    ],
)
def test_detects_every_supported_format_from_real_encoded_bytes(
    pillow_format: str,
    expected: ImageMediaType,
) -> None:
    """Each supported member is recovered from a genuinely encoded image."""
    assert detect_image_media_type(_encoded(pillow_format)) is expected


@pytest.mark.parametrize("pillow_format", ["BMP", "TIFF"])
def test_refuses_a_real_image_in_an_unsupported_format(pillow_format: str) -> None:
    """A valid image the providers do not accept refuses rather than resolving to a guess.

    BMP and TIFF are exactly the dangerous cases: they are real images an
    operator can plausibly attach, so a lenient sniffer would have to invent a
    member for them -- and whichever it invented would be a lie the provider
    validates against the bytes.
    """
    with pytest.raises(CoreValidationError) as caught:
        detect_image_media_type(_encoded(pillow_format))
    assert "Unsupported image format" in str(caught.value)


def test_the_refusal_enumerates_the_accepted_set() -> None:
    """The refusal tells the operator what IS accepted, never a bare 'invalid'."""
    with pytest.raises(CoreValidationError) as caught:
        detect_image_media_type(b"%PDF-1.7\n")
    message = str(caught.value)
    for member in ImageMediaType:
        assert member.value in message


def test_refuses_truncated_and_empty_input() -> None:
    """Too-few bytes to identify anything is a refusal, never an index error."""
    with pytest.raises(CoreValidationError):
        detect_image_media_type(b"")
    with pytest.raises(CoreValidationError):
        detect_image_media_type(b"RIFF")


def test_every_member_value_is_its_exact_iana_media_type() -> None:
    """Members are usable directly as wire values, with no translation table.

    The provider compares the declared string byte-for-byte, so a member whose
    value drifted from the IANA name would refuse every image of that format.
    """
    assert {member.value for member in ImageMediaType} == {
        "image/png",
        "image/jpeg",
        "image/webp",
        "image/gif",
    }
