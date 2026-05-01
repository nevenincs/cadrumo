"""Casilla-complete declaración PDF parsing (EPIC #305).

The module turns a *copia de la declaración* PDF into a strict
:class:`DeclaracionFiling` record carrying every casilla ID + printed
value the extractor recovered. Downstream consumers:

- :mod:`aeat.application.filing.build_draft` materialises a :class:`FilingDraft`
  from the extracted casillas via ``inputs={c.casilla_id: c.printed_value ...}``.
- :mod:`aeat.application.verification.verify_declaracion` compares the re-derived
  casillas against the printed ones via :class:`aeat.domain.formulas.Engine.audit_against`.

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
from ._generic_extractor import GenericDeclaracionExtractor
from ._parser import parse_declaracion
from ._schema import (
    DeclaracionFiling,
    ExtractionStatus,
    ExtractionWarning,
    TemplateRevision,
)


def registered_extractors() -> tuple[type[DeclaracionExtractor], ...]:
    """Return all concrete declaración extractor classes registered for dispatch."""
    from ._extractors import _REGISTERED_CLASSES

    return _REGISTERED_CLASSES


__all__ = [
    "DeclaracionFiling",
    "DeclaracionExtractor",
    "DeclaracionParseError",
    "ExtractionStatus",
    "ExtractionWarning",
    "GenericDeclaracionExtractor",
    "TemplateRevision",
    "parse_declaracion",
    "registered_extractors",
]
