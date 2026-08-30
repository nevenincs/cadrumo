"""Closed taxonomy of image media types a multimodal read may carry.

A vision request crosses a provider boundary that demands the format be
*declared*, not sniffed: the Anthropic Messages API validates an image block's
``media_type`` against the actual bytes and refuses the pair when they disagree.
The local Ollama transport sniffs instead, which is why the declaration was
absent for as long as that was the only transport.

Members carry the exact IANA media-type string as their value, so a member is
usable directly as a wire value without a lookup table. The set is the
intersection of what the Messages API accepts for an image block and what this
product can actually produce: a rasterised PDF page (always PNG) and a raw
operator-supplied image attachment (whatever the operator had).

:func:`detect_image_media_type` is the single sniffer for that second case. It
refuses an unsupported format rather than guessing one, because a mislabelled
image is the failure this whole declaration exists to prevent.
"""

from __future__ import annotations

from enum import StrEnum

from .errors.hierarchy import CoreValidationError

__all__ = ["ImageMediaType", "detect_image_media_type"]


class ImageMediaType(StrEnum):
    """IANA media type of an image forwarded to a multimodal model."""

    PNG = "image/png"
    """Portable Network Graphics -- what the PDF page rasteriser emits."""

    JPEG = "image/jpeg"
    """JPEG -- the most common format for an operator-supplied photo or scan."""

    WEBP = "image/webp"
    """WebP, in its RIFF container."""

    GIF = "image/gif"
    """GIF, either the 87a or 89a version."""


_MAGIC_PREFIXES: tuple[tuple[bytes, ImageMediaType], ...] = (
    (b"\x89PNG\r\n\x1a\n", ImageMediaType.PNG),
    (b"\xff\xd8\xff", ImageMediaType.JPEG),
    (b"GIF87a", ImageMediaType.GIF),
    (b"GIF89a", ImageMediaType.GIF),
)


def detect_image_media_type(data: bytes) -> ImageMediaType:
    """Return the :class:`ImageMediaType` the raw bytes actually are.

    Args:
        data: Raw image bytes, exactly as the operator supplied them.

    Returns:
        The member matching the file's magic bytes.

    Raises:
        CoreValidationError: When the bytes are not one of the supported
            formats. Never guesses a member: an image sent to a cloud
            provider under the wrong ``media_type`` is refused by the
            provider at best and silently misread at worst.
    """
    for prefix, media_type in _MAGIC_PREFIXES:
        if data.startswith(prefix):
            return media_type
    # WebP is the one format whose magic is split: a "RIFF" container header,
    # a four-byte little-endian length, then the "WEBP" form type at offset 8.
    if data[:4] == b"RIFF" and data[8:12] == b"WEBP":
        return ImageMediaType.WEBP
    supported = ", ".join(member.value for member in ImageMediaType)
    msg = f"Unsupported image format for a multimodal read; supported formats are: {supported}."
    raise CoreValidationError(msg)
