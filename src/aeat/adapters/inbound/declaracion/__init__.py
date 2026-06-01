"""Declaración PDF parsing boundary.

The module exposes strict declaration parser records and the public
``parse_declaracion`` entry point. The parser returns observed PDF
values. Validated registry snapshots decide extraction coverage and
filing usability.

Public API::

    from aeat.adapters.inbound.declaracion import (
        DeclaracionObservation,
        DeclaracionParseError,
        TemplateRevision,
        parse_declaracion,
        parse_declaracion_bytes,
    )
"""

from __future__ import annotations

from ._errors import DeclaracionParseError, TemplateNotDetectedError
from ._parser import parse_declaracion, parse_declaracion_bytes
from ._schema import (
    DeclaracionObservation,
    ExtractionWarning,
    TemplateRevision,
)

__all__ = [
    "DeclaracionObservation",
    "DeclaracionParseError",
    "ExtractionWarning",
    "TemplateNotDetectedError",
    "TemplateRevision",
    "parse_declaracion",
    "parse_declaracion_bytes",
]
