"""Observed Modelo 100 (IRPF / Renta) PDF parsing.

Modelo 100 has three artefact types a taxpayer encounters, all parsed
through this module:

- **Borrador** — AEAT's pre-filing draft, downloaded from Portal Renta.
  Has pre-populated casillas but no CSV.
- **Predeclaración / simulación** — non-binding simulation from Renta
  Web Open. Same shape; watermarked "VISTA PREVIA".
- **Declaración** — post-filing copy with a CSV stamp.

The parser extracts printed casilla/value rows as observed filing data.
Completeness is enforced only when the caller supplies a registry
extraction profile.

The public API surfaces :class:`BorradorObservation`,
:class:`BorradorParseMode`, :class:`BorradorParseError`,
:class:`ArtefactKind` and :func:`parse_borrador`.

Examples:
    >>> from aeat.adapters.inbound.borrador import parse_borrador
    >>> filing = parse_borrador(pdf_path)  # doctest: +SKIP
"""

from __future__ import annotations

from ._errors import BorradorParseError
from ._parser import parse_borrador
from ._schema import ArtefactKind, BorradorExtractionProfile, BorradorObservation, BorradorParseMode

__all__ = [
    "ArtefactKind",
    "BorradorExtractionProfile",
    "BorradorObservation",
    "BorradorParseError",
    "BorradorParseMode",
    "parse_borrador",
]
