"""Fail-closed declaración PDF parsing boundary.

The module retains strict declaration parser records and the public
``parse_declaracion`` entry point, but legacy Python extractor dispatch is
disabled until validated registry snapshots back extraction.

Downstream consumers must treat this surface as unavailable for
casilla-complete extraction until that registry-backed implementation exists.

Public API:

    from aeat.adapters.inbound.declaracion import (
        DeclaracionFiling,
        DeclaracionParseError,
        TemplateRevision,
        parse_declaracion,
    )
"""

from __future__ import annotations

from ._errors import DeclaracionParseError
from ._extractor import DeclaracionExtractor
from ._parser import parse_declaracion
from ._schema import (
    DeclaracionFiling,
    ExtractionStatus,
    ExtractionWarning,
    TemplateRevision,
)


def registered_extractors() -> tuple[type[DeclaracionExtractor], ...]:
    """Reject legacy inspection of Python-registered extractor classes."""

    raise DeclaracionParseError(
        "declaracion extractor registry inspection requires validated registry snapshots; "
        "legacy Python extractor registry is disabled"
    )


__all__ = [
    "DeclaracionExtractor",
    "DeclaracionFiling",
    "DeclaracionParseError",
    "ExtractionStatus",
    "ExtractionWarning",
    "TemplateRevision",
    "parse_declaracion",
    "registered_extractors",
]
