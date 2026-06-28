"""Shared primitives for the project's PDF-import families.

The :mod:`aeat.adapters.inbound.pdf` package owns types and errors that every
per-PDF-class module under :mod:`aeat.domain.justificante`, :mod:`aeat.adapters.inbound.declaracion`,
:mod:`aeat.adapters.inbound.borrador` consumes. It is
*deliberately underscore-prefixed* because the concrete parsing modules
are the public surface; callers from outside the project should not
need to import from here.

Public symbols:

- :class:`ExtractedCasilla` — one casilla ID + printed value tuple produced
  by any PDF-class extractor.
- :class:`PdfModeloImportError` — base exception for every PDF-import
  parsing error.
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
