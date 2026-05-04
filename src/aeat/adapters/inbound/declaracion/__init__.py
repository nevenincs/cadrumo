"""Declaración PDF parsing boundary.

The module retains strict declaration parser records and the public
``parse_declaracion`` entry point. Casilla-complete extraction must be
backed by validated registry snapshots.

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
from ._parser import parse_declaracion
from ._schema import (
    DeclaracionFiling,
    ExtractionStatus,
    ExtractionWarning,
    TemplateRevision,
)

__all__ = [
    "DeclaracionFiling",
    "DeclaracionParseError",
    "ExtractionStatus",
    "ExtractionWarning",
    "TemplateRevision",
    "parse_declaracion",
]
