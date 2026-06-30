"""Observed Modelo 100 (IRPF / Renta) PDF parsing boundary.

Modelo 100 has three artefact types a taxpayer encounters, all parsed
through this module:

- **Borrador** — AEAT's pre-filing draft, downloaded from Portal Renta.
  Has pre-populated casillas but no CSV.
- **Predeclaración / simulación** — non-binding simulation from Renta
  Web Open. Same shape; watermarked "VISTA PREVIA".
- **Declaración** — post-filing copy with a CSV stamp.

The parser extracts printed casilla/value rows as observed filing data. This
adapter does not resolve :class:`~aeat.domain.calculations.registry.RegistrySnapshot`
objects or decide filing-grade completeness by itself. Completeness is enforced
only when the caller supplies a
:class:`~aeat.adapters.inbound.borrador._schema.BorradorExtractionProfile`
projection and selects registry-profile parsing.

The public API surfaces :class:`BorradorObservation`,
:class:`BorradorParseMode`, :class:`BorradorParseError`,
:class:`BorradorExtractionProfile`, :class:`ArtefactKind`, and
:func:`parse_borrador`.

See Also:
    :func:`parse_borrador`
        Single public entry point that composes artefact detection with the
        year-keyed extractor registry.
    :mod:`aeat.adapters.inbound.declaracion`
        Sibling filed-declaration parser that owns the declaration-PDF surface.
    :mod:`aeat.adapters.inbound.pdf`
        Shared PDF extraction helpers used by the Renta parser backend.
    :class:`~aeat.domain.calculations.registry.ExtractionProfileDefinition`
        Registry-side profile shape callers may project into the lightweight
        protocol consumed here.

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
