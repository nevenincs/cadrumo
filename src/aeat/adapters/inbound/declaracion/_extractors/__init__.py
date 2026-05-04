"""Fail-closed declaración extractor dispatch boundary.

Concrete extractor selection is modelo/template legal structure and must
come from validated registry snapshots. The previous package initializer
imported per-model Python extractor modules and assembled a hardcoded
``(modelo, año, revision)`` registry at import time; that registry is
disabled during the calculation-truth hard cut.
"""

from __future__ import annotations

from .._errors import NoExtractorRegisteredError
from .._extractor import DeclaracionExtractor
from .._schema import TemplateRevision


def get_extractor(tr: TemplateRevision) -> DeclaracionExtractor:
    """Reject extractor dispatch until registry-backed definitions exist."""

    raise NoExtractorRegisteredError(
        "declaracion extractor dispatch requires validated registry snapshots; "
        "legacy Python extractor registry is disabled"
    )


__all__ = ["get_extractor"]
