"""Casilla-complete declaración PDF parsing (EPIC #305 cluster D).

The module turns a *copia de la declaración* PDF into a strict
:class:`DeclaracionFiling` record carrying every casilla ID + printed
value the extractor recovered. Downstream consumers:

- :mod:`aeat.filing.build_draft` materialises a :class:`FilingDraft`
  from the extracted casillas via ``inputs={c.casilla_id: c.printed_value ...}``.
- :mod:`aeat.verification.verify_declaracion` compares the re-derived
  casillas against the printed ones via :class:`aeat.formulas.Engine.audit_against`.

Public API:

    from aeat.declaracion import (
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
