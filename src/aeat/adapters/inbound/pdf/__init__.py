"""Shared primitives for the project's PDF-import families.

The :mod:`aeat.adapters.inbound.pdf` package owns types and errors that every
per-PDF-class module under :mod:`aeat.domain.justificante`,
:mod:`aeat.adapters.inbound.declaracion`, and
:mod:`aeat.adapters.inbound.borrador` consumes. The concrete parser packages are
the public import surfaces for callers; this package stays a small shared
primitive layer for casilla extraction and Spanish printed-amount parsing.

Public symbols:

- :class:`ExtractedCasilla` — one casilla ID + printed value tuple produced
  by any PDF-class extractor.
- :class:`PdfModeloImportError` — base exception for every PDF-import
  parsing error.
- :class:`LabelHit`, :func:`apply_label_regex`, and
  :func:`parse_spanish_decimal` — label-anchored extraction helpers used by
  declaration and borrador parsers.

See Also:
    - :mod:`aeat.adapters.inbound.declaracion` for registry-grounded filed
      declaration parsing.
    - :mod:`aeat.adapters.inbound.borrador` for borrador/Renta artefact parsing.
    - :mod:`aeat.adapters.inbound.justificante` for AEAT filing-receipt parsing.
"""

from __future__ import annotations

from ....domain.justificante import PdfModeloImportError
from ._label_regex import (
    SPANISH_AMOUNT_GROUP,
    LabelHit,
    apply_label_regex,
    parse_spanish_decimal,
)
from ._shared import ExtractedCasilla

__all__ = [
    "SPANISH_AMOUNT_GROUP",
    "ExtractedCasilla",
    "LabelHit",
    "PdfModeloImportError",
    "apply_label_regex",
    "parse_spanish_decimal",
]
