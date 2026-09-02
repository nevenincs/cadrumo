"""Observed Modelo 100 (IRPF / Renta) PDF parsing boundary.

Modelo 100 has three artefact types a taxpayer encounters, all parsed
through this package:

- **Borrador** — AEAT's pre-filing draft, downloaded from Portal Renta.
  Has pre-populated casillas but no CSV.
- **Predeclaración / simulación** — non-binding simulation from Renta
  Web Open. Same shape; watermarked "VISTA PREVIA".
- **Declaración** — post-filing copy with a CSV stamp.

The parser extracts printed casilla/value rows as observed filing data. This
adapter does not resolve :class:`~domain.calculations.registry.RegistrySnapshot`
objects or decide filing-grade completeness by itself. Completeness is enforced
only when the caller supplies a
:class:`~adapters.inbound.borrador.schema.BorradorExtractionProfile`
projection and selects registry-profile parsing, which filters to the profile's
target casillas and raises below its declared minimum coverage. Returned
observations carry a privacy-preserving source reference derived from the PDF
digest, never the operator's local source path.

Public API::

    from cadrumo.adapters.inbound.borrador.parser import parse_borrador
    from cadrumo.adapters.inbound.borrador.schema import (
        ArtefactKind,
        BorradorExtractionProfile,
        BorradorParseMode,
        InboundBorradorObservation,
    )
    from cadrumo.adapters.inbound.borrador.errors import (
        ArtefactNotRecognisedError,
        BorradorParseError,
    )

See Also:
    :func:`~adapters.inbound.borrador.parser.parse_borrador`
        Single defining entry point that composes artefact detection with the
        year-keyed extractor registry.
    :mod:`~adapters.inbound.declaracion`
        Sibling filed-declaration parser that owns the declaration-PDF surface.
    :mod:`~adapters.inbound.pdf`
        Shared PDF extraction helpers used by the Renta parser backend.
    :class:`~domain.calculations.registry.schema_extraction.ExtractionProfileDefinition`
        Registry-side profile shape callers project into the lightweight
        protocol consumed here.
"""

from __future__ import annotations

__all__: tuple[str, ...] = ()
