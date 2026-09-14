"""Application-owned capability for reading PDF text-layer pages.

The evidence use cases decide when a deterministic text read is appropriate;
the composition root supplies the reader.  Keeping this contract here leaves
the PDF library and its exception shape at the outer adapter boundary while
the application works with in-memory bytes, page text, and its own refusal
type.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Protocol


class EvidencePageTextExtractor(Protocol):
    """Read PDF bytes into ordered, application-owned page text values."""

    def __call__(self, data: bytes) -> tuple[str, ...]:
        """Return one stripped text value per source page."""
        ...


@dataclass(frozen=True, slots=True)
class EvidenceTextLayerPorts:
    """Required page-text capability supplied by outer composition."""

    extract_pages_text: EvidencePageTextExtractor


__all__ = ["EvidencePageTextExtractor", "EvidenceTextLayerPorts"]
