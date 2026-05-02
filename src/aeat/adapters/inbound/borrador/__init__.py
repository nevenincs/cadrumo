"""Casilla-complete Modelo 100 (IRPF / Renta) PDF parsing.

Modelo 100 has three artefact types a taxpayer encounters, all parsed
through this module:

- **Borrador** — AEAT's pre-filing draft, downloaded from Portal Renta.
  Has pre-populated casillas but no CSV.
- **Predeclaración / simulación** — non-binding simulation from Renta
  Web Open. Same shape; watermarked "VISTA PREVIA".
- **Declaración** — post-filing copy with a CSV stamp.

The current extractor targets the *summary block* (~30 casillas at the
top of every Renta artefact covering ingresos, deducciones, base
imponible, cuota líquida, cuota diferencial). Full anexo coverage
(A, B, C, D, H, Ñ, etc.) is out of scope.

The public API surfaces :class:`BorradorFiling`,
:class:`BorradorParseError`, :class:`ArtefactKind` and
:func:`parse_borrador`.

Examples:
    >>> from aeat.adapters.inbound.borrador import parse_borrador
    >>> filing = parse_borrador(pdf_path)  # doctest: +SKIP
"""

from __future__ import annotations

from ._errors import BorradorParseError
from ._parser import parse_borrador
from ._schema import ArtefactKind, BorradorFiling

__all__ = [
    "ArtefactKind",
    "BorradorFiling",
    "BorradorParseError",
    "parse_borrador",
]
