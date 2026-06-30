"""Declaración PDF parsing boundary.

The module exposes strict declaration parser records and the public
``parse_declaracion`` / ``parse_declaracion_bytes`` entry points. The parser
returns observed PDF values interpreted through a validated
:class:`~aeat.domain.calculations.registry.RegistrySnapshot`; the snapshot's
``declaracion_pdf`` extraction profile decides target casillas, extraction
coverage, and filing usability.

This is the registry-profile-driven declaration-copy parser. It deliberately
has no per-modelo extractor class registry: template detection resolves the
modelo/year/revision coordinate, and registry metadata supplies the extraction
shape. The sibling :mod:`aeat.adapters.inbound.borrador` parser is a different
observed-value surface for Renta drafts and simulations.

Public API::

    from aeat.adapters.inbound.declaracion import (
        DeclaracionObservation,
        DeclaracionParseError,
        TemplateRevision,
        parse_declaracion,
        parse_declaracion_bytes,
    )

See Also:
    :func:`parse_declaracion`
        Filesystem entry point for declaration-copy PDFs.
    :func:`parse_declaracion_bytes`
        In-memory entry point used by live-read flows that already hold
        decrypted PDF bytes.
    :class:`~aeat.domain.calculations.registry.ExtractionProfileDefinition`
        Registry-owned extraction contract consumed by this parser.
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
